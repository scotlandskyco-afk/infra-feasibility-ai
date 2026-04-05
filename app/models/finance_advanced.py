"""
Advanced financial model with LCOE, NPV, IRR, DCF cash flows,
debt/equity structuring, and Monte Carlo simulation.
"""

import logging
import random
from typing import Dict, List

import numpy as np
import numpy_financial as npf

logger = logging.getLogger(__name__)


class AdvancedFinancialModel:
    """
    Computes full project finance metrics for an infrastructure investment.

    All monetary values in USD. All rates as decimal fractions (0.08 = 8%).
    """

    def __init__(
        self,
        capex_usd: float,
        opex_annual_usd: float,
        annual_energy_mwh: float,
        electricity_price_usd_per_mwh: float,
        discount_rate: float,
        project_life_years: int = 25,
        debt_ratio: float = 0.70,
        debt_interest: float = 0.06,
    ):
        self.capex = capex_usd
        self.opex = opex_annual_usd
        self.energy = annual_energy_mwh
        self.price = electricity_price_usd_per_mwh
        self.discount_rate = discount_rate
        self.life = project_life_years
        self.debt_ratio = debt_ratio
        self.debt_interest = debt_interest

        # Derived financing
        self.debt = capex_usd * debt_ratio
        self.equity = capex_usd * (1 - debt_ratio)
        # Annual debt service (equal annual payment)
        if debt_interest > 0 and project_life_years > 0:
            self.annual_debt_service = (
                self.debt
                * (debt_interest * (1 + debt_interest) ** project_life_years)
                / ((1 + debt_interest) ** project_life_years - 1)
            )
        else:
            self.annual_debt_service = self.debt / max(project_life_years, 1)

    def build_cash_flows(self) -> List[Dict]:
        """
        Generate a year-by-year cash flow table.
        Year 0 is the equity investment (negative).
        Years 1–N: Revenue - OPEX - Debt Service.
        """
        rows = []
        # Year 0: equity outflow
        rows.append({
            "year": 0,
            "revenue": 0.0,
            "opex": 0.0,
            "debt_service": 0.0,
            "net_cash_flow": -self.equity,
        })
        for yr in range(1, self.life + 1):
            revenue = self.energy * self.price
            net = revenue - self.opex - self.annual_debt_service
            rows.append({
                "year": yr,
                "revenue": round(revenue, 2),
                "opex": round(self.opex, 2),
                "debt_service": round(self.annual_debt_service, 2),
                "net_cash_flow": round(net, 2),
            })
        return rows

    def calculate_npv(self) -> float:
        """
        Net Present Value of equity cash flows discounted at discount_rate.
        NPV = sum( CF_t / (1+r)^t ) for t = 0..N
        """
        cfs = [row["net_cash_flow"] for row in self.build_cash_flows()]
        # npf.npv expects rate and an array starting from period 0
        npv = float(npf.npv(self.discount_rate, cfs))
        return round(npv, 2)

    def calculate_irr(self) -> float:
        """
        Internal Rate of Return on equity cash flows.
        IRR is the rate r such that NPV(r) = 0.
        """
        cfs = [row["net_cash_flow"] for row in self.build_cash_flows()]
        try:
            irr = float(npf.irr(cfs))
            return round(irr, 6) if not np.isnan(irr) else 0.0
        except Exception:
            return 0.0

    def calculate_payback(self) -> float:
        """
        Simple payback period in years (undiscounted).
        Counts years until cumulative net cash flow becomes positive.
        """
        cumulative = 0.0
        for row in self.build_cash_flows():
            cumulative += row["net_cash_flow"]
            if cumulative >= 0:
                return float(row["year"])
        return float(self.life)  # never pays back within project life

    def calculate_lcoe(self) -> float:
        """
        Levelized Cost of Energy (USD/MWh).
        LCOE = (CAPEX + NPV of all OPEX) / NPV of total energy produced
        where NPV uses the project discount rate.
        """
        # NPV of OPEX stream
        opex_flows = [0.0] + [self.opex] * self.life
        npv_opex = float(npf.npv(self.discount_rate, opex_flows))

        # NPV of energy production stream (MWh per year)
        energy_flows = [0.0] + [self.energy] * self.life
        npv_energy = float(npf.npv(self.discount_rate, energy_flows))

        if npv_energy <= 0:
            return 0.0
        lcoe = (self.capex + npv_opex) / npv_energy
        return round(lcoe, 4)

    def run_monte_carlo(self, simulations: int = 1000) -> Dict:
        """
        Monte Carlo simulation varying key inputs:
        - electricity_price: +/-20%
        - capex: +/-15%
        - annual_energy: +/-10%
        Returns p10/p50/p90 for NPV and IRR plus raw distributions.
        """
        npv_results = []
        irr_results = []
        lcoe_results = []

        for _ in range(simulations):
            # Sample from uniform distributions around base values
            price_var = self.price * random.uniform(0.80, 1.20)
            capex_var = self.capex * random.uniform(0.85, 1.15)
            energy_var = self.energy * random.uniform(0.90, 1.10)

            trial = AdvancedFinancialModel(
                capex_usd=capex_var,
                opex_annual_usd=self.opex,
                annual_energy_mwh=energy_var,
                electricity_price_usd_per_mwh=price_var,
                discount_rate=self.discount_rate,
                project_life_years=self.life,
                debt_ratio=self.debt_ratio,
                debt_interest=self.debt_interest,
            )
            npv_results.append(trial.calculate_npv())
            irr_results.append(trial.calculate_irr())
            lcoe_results.append(trial.calculate_lcoe())

        def percentiles(data):
            arr = sorted(data)
            n = len(arr)
            return {
                "p10": arr[int(n * 0.10)],
                "p50": arr[int(n * 0.50)],
                "p90": arr[int(n * 0.90)],
                "mean": sum(arr) / n,
            }

        return {
            "npv": percentiles(npv_results),
            "irr": percentiles(irr_results),
            "lcoe": percentiles(lcoe_results),
            "npv_distribution": npv_results,
            "irr_distribution": irr_results,
        }
