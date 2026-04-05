"""
Phase 4 — Country Risk Engine
Composite risk scoring from World Bank macroeconomic indicators.
Outputs: risk score (0–100), risk-adjusted discount rate.
"""
from typing import Optional
from app.data.api_clients import WorldBankClient
from app.data.cleaners import extract_latest_wb_value, normalize_country_code


WORST_INFLATION = 50.0
BEST_INFLATION = 1.0
WORST_GDP_GROWTH = -5.0
BEST_GDP_GROWTH = 8.0
BASE_DISCOUNT_RATE = 0.08
RISK_PREMIUM_MAX = 0.12

POLITICAL_STABILITY_PROXY = {
    "GBR": 85, "DEU": 83, "FRA": 74, "USA": 72,
    "ARE": 65, "SAU": 55, "KAZ": 48, "EGY": 42,
    "PAK": 32, "IRQ": 22, "SLE": 30, "MDG": 35,
    "NGA": 28, "KEN": 45, "ETH": 35, "ZAF": 50,
}


class CountryRiskEngine:
    """
    Calculates a composite country risk score and risk-adjusted discount rate.

    Risk score components:
        - GDP growth score (25%)
        - Inflation score (30%)
        - Political stability score (30%)
        - Currency volatility proxy (15%)
    """

    def __init__(self, country_code: str):
        self.country_code = normalize_country_code(country_code)
        self.wb = WorldBankClient()
        self.raw_indicators = {}
        self.scores = {}

    def _score_gdp_growth(self, value: Optional[float]) -> float:
        if value is None:
            return 40.0
        normalized = (value - WORST_GDP_GROWTH) / (BEST_GDP_GROWTH - WORST_GDP_GROWTH)
        return max(0.0, min(100.0, normalized * 100))

    def _score_inflation(self, value: Optional[float]) -> float:
        if value is None:
            return 40.0
        # Lower inflation = higher score
        normalized = (WORST_INFLATION - value) / (WORST_INFLATION - BEST_INFLATION)
        return max(0.0, min(100.0, normalized * 100))

    def _score_political_stability(self) -> float:
        return float(POLITICAL_STABILITY_PROXY.get(self.country_code, 40))

    def _score_currency_volatility(self, inflation: Optional[float]) -> float:
        """Proxy: high inflation correlates with currency volatility."""
        if inflation is None:
            return 50.0
        penalty = min(inflation / WORST_INFLATION, 1.0) * 100
        return max(0.0, 100.0 - penalty)

    def calculate(self) -> dict:
        """Fetch data and compute composite risk score."""
        gdp_raw = self.wb.fetch_indicator(self.country_code, "gdp_growth")
        inf_raw = self.wb.fetch_indicator(self.country_code, "inflation")

        gdp_value = extract_latest_wb_value(gdp_raw)
        inf_value = extract_latest_wb_value(inf_raw)

        self.raw_indicators = {
            "gdp_growth_pct": gdp_value,
            "inflation_pct": inf_value,
        }

        gdp_score = self._score_gdp_growth(gdp_value)
        inf_score = self._score_inflation(inf_value)
        pol_score = self._score_political_stability()
        cur_score = self._score_currency_volatility(inf_value)

        composite = (
            gdp_score * 0.25
            + inf_score * 0.30
            + pol_score * 0.30
            + cur_score * 0.15
        )

        risk_premium = (1 - composite / 100) * RISK_PREMIUM_MAX
        risk_adjusted_rate = BASE_DISCOUNT_RATE + risk_premium

        risk_label = (
            "Low" if composite >= 70
            else "Moderate" if composite >= 45
            else "High" if composite >= 25
            else "Very High"
        )

        self.scores = {
            "country_code": self.country_code,
            "composite_risk_score": round(composite, 2),
            "risk_label": risk_label,
            "risk_adjusted_discount_rate_pct": round(risk_adjusted_rate * 100, 2),
            "component_scores": {
                "gdp_growth": round(gdp_score, 2),
                "inflation": round(inf_score, 2),
                "political_stability": round(pol_score, 2),
                "currency_stability": round(cur_score, 2),
            },
            "raw_indicators": self.raw_indicators,
        }
        return self.scores
