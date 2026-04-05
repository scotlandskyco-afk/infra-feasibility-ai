"""
Phase 3 — Advanced Financial Modelling
NPV, IRR, LCOE, DCF, Monte Carlo simulation
"""
import numpy as np
import numpy_financial as npf
from typing import List, Optional
import pandas as pd


class FinancialModel:
    """
    Full financial analysis for infrastructure and energy projects.

    Parameters:
        capex_usd           — Total capital expenditure (USD)
        annual_production_mwh — Annual energy generation (MWh)
        electricity_price_usd — Electricity sale price (USD/MWh)
        opex_annual_usd     — Annual operating cost (USD)
        project_life_years  — Project lifetime (years)
        discount_rate       — Weighted average cost of capital (decimal, e.g. 0.10)
        degradation_rate    — Annual panel/turbine output degradation (decimal)
        debt_fraction       — Share of CAPEX financed by debt (0–1)
        debt_interest_rate  — Annual debt interest rate (decimal)
    """

    def __init__(
        self,
        capex_usd: float,
        annual_production_mwh: float,
        electricity_price_usd: float = 65.0,
        opex_annual_usd: Optional[float] = None,
        project_life_years: int = 25,
        discount_rate: float = 0.10,
        degradation_rate: float = 0.005,
        debt_fraction: float = 0.70,
        debt_interest_rate: float = 0.055,
    ):
        self.capex = capex_usd
        self.annual_production = annual_production_mwh
        self.electricity_price = electricity_price_usd
        self.opex = opex_annual_usd if opex_annual_usd is not None else capex_usd * 0.015
        self.life = project_life_years
        self.discount_rate = discount_rate
        self.degradation = degradation_rate
        self.debt_fraction = debt_fraction
        self.debt_rate = debt_interest_rate

    def cash_flows(self) -> List[float]:
        """Generate annual net cash flows over project life."""
        flows = [-self.capex]
        for year in range(1, self.life + 1):
            production = self.annual_production * ((1 - self.degradation) ** (year - 1))
            revenue = production * self.electricity_price
            debt_service = (
                (self.capex * self.debt_fraction * self.debt_rate)
                / (1 - (1 + self.debt_rate) ** -20)
                if year <= 20 else 0
            )
            net_cf = revenue - self.opex - debt_service
            flows.append(net_cf)
        return flows

    def npv(self) -> float:
        """Net Present Value (USD)"""
        return round(float(npf.npv(self.discount_rate, self.cash_flows())), 2)

    def irr(self) -> float:
        """Internal Rate of Return (%)"""
        flows = self.cash_flows()
        try:
            irr_val = npf.irr(flows)
            return round(float(irr_val) * 100, 2) if not np.isnan(irr_val) else None
        except Exception:
            return None

    def payback_period(self) -> float:
        """Simple payback period (years)"""
        flows = self.cash_flows()
        cumulative = 0.0
        for i, cf in enumerate(flows):
            cumulative += cf
            if cumulative >= 0:
                return round(float(i), 1)
        return float(self.life)

    def lcoe(self) -> float:
        """
        Levelized Cost of Energy (USD/MWh)
        LCOE = PV(total costs) / PV(total energy)
        """
        total_cost_pv = self.capex
        total_energy_pv = 0.0
        for year in range(1, self.life + 1):
            disc = (1 + self.discount_rate) ** year
            energy = self.annual_production * ((1 - self.degradation) ** (year - 1))
            total_cost_pv += self.opex / disc
            total_energy_pv += energy / disc
        return round(total_cost_pv / total_energy_pv, 2) if total_energy_pv > 0 else None

    def dcf_table(self) -> pd.DataFrame:
        """Generate full discounted cash flow table."""
        rows = []
        for year in range(self.life + 1):
            if year == 0:
                rows.append({"year": 0, "revenue": 0, "opex": 0, "net_cf": -self.capex, "discounted_cf": -self.capex})
            else:
                production = self.annual_production * ((1 - self.degradation) ** (year - 1))
                revenue = production * self.electricity_price
                debt_service = (
                    (self.capex * self.debt_fraction * self.debt_rate)
                    / (1 - (1 + self.debt_rate) ** -20)
                    if year <= 20 else 0
                )
                net_cf = revenue - self.opex - debt_service
                disc_cf = net_cf / ((1 + self.discount_rate) ** year)
                rows.append({
                    "year": year,
                    "revenue": round(revenue, 0),
                    "opex": round(self.opex, 0),
                    "debt_service": round(debt_service, 0),
                    "net_cf": round(net_cf, 0),
                    "discounted_cf": round(disc_cf, 0),
                })
        return pd.DataFrame(rows)

    def full_analysis(self) -> dict:
        """Return complete financial summary."""
        return {
            "capex_usd": self.capex,
            "opex_annual_usd": self.opex,
            "electricity_price_usd_mwh": self.electricity_price,
            "project_life_years": self.life,
            "discount_rate_pct": self.discount_rate * 100,
            "npv_usd": self.npv(),
            "irr_pct": self.irr(),
            "payback_years": self.payback_period(),
            "lcoe_usd_mwh": self.lcoe(),
            "debt_fraction_pct": self.debt_fraction * 100,
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulation for financial risk analysis.
    Varies: electricity price, energy output, CAPEX overrun.
    """

    def __init__(self, base_model: FinancialModel, n_simulations: int = 5000):
        self.base = base_model
        self.n = n_simulations

    def run(self) -> dict:
        """Run Monte Carlo and return statistics."""
        npvs = []
        irrs = []
        lcoes = []

        price_std = self.base.electricity_price * 0.15
        output_std = self.base.annual_production * 0.10
        capex_std = self.base.capex * 0.10

        for _ in range(self.n):
            price = max(10, np.random.normal(self.base.electricity_price, price_std))
            output = max(1, np.random.normal(self.base.annual_production, output_std))
            capex = max(self.base.capex * 0.8, np.random.normal(self.base.capex, capex_std))

            model = FinancialModel(
                capex_usd=capex,
                annual_production_mwh=output,
                electricity_price_usd=price,
                opex_annual_usd=self.base.opex,
                project_life_years=self.base.life,
                discount_rate=self.base.discount_rate,
            )
            npvs.append(model.npv())
            irr = model.irr()
            if irr is not None:
                irrs.append(irr)
            lcoe = model.lcoe()
            if lcoe is not None:
                lcoes.append(lcoe)

        return {
            "simulations": self.n,
            "npv": {
                "mean": round(float(np.mean(npvs)), 0),
                "std": round(float(np.std(npvs)), 0),
                "p10": round(float(np.percentile(npvs, 10)), 0),
                "p50": round(float(np.percentile(npvs, 50)), 0),
                "p90": round(float(np.percentile(npvs, 90)), 0),
                "prob_positive": round(float(np.mean([n > 0 for n in npvs])) * 100, 1),
            },
            "irr": {
                "mean": round(float(np.mean(irrs)), 2) if irrs else None,
                "p10": round(float(np.percentile(irrs, 10)), 2) if irrs else None,
                "p90": round(float(np.percentile(irrs, 90)), 2) if irrs else None,
            },
            "lcoe": {
                "mean": round(float(np.mean(lcoes)), 2) if lcoes else None,
                "p10": round(float(np.percentile(lcoes, 10)), 2) if lcoes else None,
                "p90": round(float(np.percentile(lcoes, 90)), 2) if lcoes else None,
            },
        }
