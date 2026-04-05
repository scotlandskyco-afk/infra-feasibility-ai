"""
Scenario and sensitivity analysis engine.
Runs best/base/worst cases and single-variable sensitivity sweeps,
then computes tornado-chart data showing the impact of each variable.
"""

from typing import Dict, List

from app.models.finance_advanced import AdvancedFinancialModel


class ScenarioEngine:
    """
    Wraps AdvancedFinancialModel to produce multi-scenario and
    sensitivity outputs from a base parameter dictionary.
    """

    SCENARIO_ADJUSTMENTS = {
        "best":  {"electricity_price": 1.20, "capex": 0.90, "capacity_factor": 1.10},
        "base":  {"electricity_price": 1.00, "capex": 1.00, "capacity_factor": 1.00},
        "worst": {"electricity_price": 0.80, "capex": 1.15, "capacity_factor": 0.90},
    }

    def __init__(self, base_params: Dict):
        """
        base_params keys:
          capex_usd, opex_annual_usd, annual_energy_mwh,
          electricity_price_usd_per_mwh, discount_rate,
          project_life_years (optional), debt_ratio (optional),
          debt_interest (optional)
        """
        self.base = base_params

    def _build_model(self, overrides: Dict) -> AdvancedFinancialModel:
        p = dict(self.base)
        p.update(overrides)
        return AdvancedFinancialModel(
            capex_usd=p["capex_usd"],
            opex_annual_usd=p.get("opex_annual_usd", 0),
            annual_energy_mwh=p.get("annual_energy_mwh", 0),
            electricity_price_usd_per_mwh=p.get("electricity_price_usd_per_mwh", 80),
            discount_rate=p.get("discount_rate", 0.10),
            project_life_years=p.get("project_life_years", 25),
            debt_ratio=p.get("debt_ratio", 0.70),
            debt_interest=p.get("debt_interest", 0.06),
        )

    def run_scenarios(self) -> Dict:
        """Run best/base/worst scenarios and return NPV, IRR, LCOE for each."""
        results = {}
        for scenario, adj in self.SCENARIO_ADJUSTMENTS.items():
            overrides = {
                "electricity_price_usd_per_mwh": (
                    self.base.get("electricity_price_usd_per_mwh", 80)
                    * adj["electricity_price"]
                ),
                "capex_usd": self.base.get("capex_usd", 50_000_000) * adj["capex"],
                "annual_energy_mwh": (
                    self.base.get("annual_energy_mwh", 100_000)
                    * adj["capacity_factor"]
                ),
            }
            model = self._build_model(overrides)
            results[scenario] = {
                "npv": model.calculate_npv(),
                "irr": model.calculate_irr(),
                "lcoe": model.calculate_lcoe(),
                "payback_years": model.calculate_payback(),
            }
        return results

    def sensitivity_analysis(
        self, variable: str, range_pct: float = 0.30, steps: int = 10
    ) -> List[Dict]:
        """
        Vary a single input variable from -range_pct to +range_pct in equal steps.
        Returns list of {variable_value, delta_pct, npv, irr, lcoe}.
        """
        base_value = self.base.get(variable)
        if base_value is None or base_value == 0:
            return []

        results = []
        for step in range(steps + 1):
            delta = -range_pct + (2 * range_pct * step / steps)
            new_value = base_value * (1 + delta)
            model = self._build_model({variable: new_value})
            results.append({
                "variable": variable,
                "delta_pct": round(delta * 100, 1),
                "variable_value": round(new_value, 4),
                "npv": model.calculate_npv(),
                "irr": model.calculate_irr(),
                "lcoe": model.calculate_lcoe(),
            })
        return results

    def tornado_data(self) -> List[Dict]:
        """
        Run sensitivity on all key variables and return sorted impact ranking
        (highest NPV swing first) for a tornado chart.
        """
        key_vars = [
            "electricity_price_usd_per_mwh",
            "capex_usd",
            "annual_energy_mwh",
            "discount_rate",
            "opex_annual_usd",
        ]
        tornado = []
        for var in key_vars:
            if var not in self.base:
                continue
            data = self.sensitivity_analysis(var, range_pct=0.20, steps=2)
            if len(data) < 2:
                continue
            npv_values = [d["npv"] for d in data]
            swing = max(npv_values) - min(npv_values)
            tornado.append({
                "variable": var,
                "npv_swing": round(swing, 0),
                "npv_low": round(min(npv_values), 0),
                "npv_high": round(max(npv_values), 0),
            })
        return sorted(tornado, key=lambda x: x["npv_swing"], reverse=True)
