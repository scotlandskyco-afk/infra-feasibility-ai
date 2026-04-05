"""
Phase 5 — Scenario and Sensitivity Analysis
Best / Base / Worst case + sensitivity tornado chart data
"""
from typing import Dict, List
from app.models.finance_advanced import FinancialModel


SCENARIO_ADJUSTMENTS = {
    "best": {
        "electricity_price_factor": 1.25,
        "capex_factor": 0.90,
        "capacity_factor_factor": 1.10,
    },
    "base": {
        "electricity_price_factor": 1.00,
        "capex_factor": 1.00,
        "capacity_factor_factor": 1.00,
    },
    "worst": {
        "electricity_price_factor": 0.75,
        "capex_factor": 1.20,
        "capacity_factor_factor": 0.85,
    },
}


class ScenarioSimulator:
    """
    Runs best/base/worst financial scenarios and sensitivity analysis.
    """

    def __init__(
        self,
        base_capex: float,
        base_production_mwh: float,
        base_price_usd_mwh: float,
        opex_annual: float,
        project_life: int = 25,
        discount_rate: float = 0.10,
    ):
        self.base_capex = base_capex
        self.base_production = base_production_mwh
        self.base_price = base_price_usd_mwh
        self.opex = opex_annual
        self.life = project_life
        self.discount_rate = discount_rate

    def run_scenarios(self) -> Dict:
        results = {}
        for scenario, adj in SCENARIO_ADJUSTMENTS.items():
            model = FinancialModel(
                capex_usd=self.base_capex * adj["capex_factor"],
                annual_production_mwh=self.base_production * adj["capacity_factor_factor"],
                electricity_price_usd=self.base_price * adj["electricity_price_factor"],
                opex_annual_usd=self.opex,
                project_life_years=self.life,
                discount_rate=self.discount_rate,
            )
            results[scenario] = {
                "npv_usd": model.npv(),
                "irr_pct": model.irr(),
                "lcoe_usd_mwh": model.lcoe(),
                "payback_years": model.payback_period(),
                "assumptions": adj,
            }
        return results

    def sensitivity_analysis(self) -> List[Dict]:
        """
        Tornado chart data: vary each input ±20%, hold others constant.
        Returns list sorted by NPV impact magnitude.
        """
        base_model = FinancialModel(
            capex_usd=self.base_capex,
            annual_production_mwh=self.base_production,
            electricity_price_usd=self.base_price,
            opex_annual_usd=self.opex,
            project_life_years=self.life,
            discount_rate=self.discount_rate,
        )
        base_npv = base_model.npv()

        variables = {
            "electricity_price": ("electricity_price_usd", self.base_price),
            "capex": ("capex_usd", self.base_capex),
            "annual_production": ("annual_production_mwh", self.base_production),
            "opex": ("opex_annual_usd", self.opex),
            "discount_rate": ("discount_rate", self.discount_rate),
        }

        tornado = []
        for var_name, (param_name, base_value) in variables.items():
            low_kwargs = {
                "capex_usd": self.base_capex,
                "annual_production_mwh": self.base_production,
                "electricity_price_usd": self.base_price,
                "opex_annual_usd": self.opex,
                "project_life_years": self.life,
                "discount_rate": self.discount_rate,
            }
            high_kwargs = low_kwargs.copy()
            low_kwargs[param_name] = base_value * 0.80
            high_kwargs[param_name] = base_value * 1.20

            low_npv = FinancialModel(**low_kwargs).npv()
            high_npv = FinancialModel(**high_kwargs).npv()

            tornado.append({
                "variable": var_name,
                "base_npv": base_npv,
                "low_npv": low_npv,
                "high_npv": high_npv,
                "swing": abs(high_npv - low_npv),
            })

        return sorted(tornado, key=lambda x: x["swing"], reverse=True)
