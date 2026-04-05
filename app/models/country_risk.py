"""
Country risk scoring engine.
Produces a composite risk score (0–100) and a risk-adjusted discount rate
from four macroeconomic and political input dimensions.
"""

from typing import Dict


class CountryRiskModel:
    """
    Scores country investment risk across four dimensions and produces
    a composite score and a risk-adjusted discount rate.

    Score scale: 0 (very low risk) to 100 (very high risk).
    """

    # Dimension weights must sum to 1.0
    WEIGHTS = {
        "gdp": 0.25,
        "inflation": 0.25,
        "political": 0.30,
        "currency": 0.20,
    }

    def __init__(
        self,
        country_code: str,
        gdp_growth_pct: float,
        inflation_pct: float,
        political_stability_index: float,  # range -2.5 (worst) to +2.5 (best)
        currency_volatility_pct: float,
    ):
        self.country_code = country_code
        self.gdp_growth = gdp_growth_pct
        self.inflation = inflation_pct
        self.political_stability = political_stability_index
        self.currency_volatility = currency_volatility_pct

    def score_gdp_risk(self) -> float:
        """GDP growth risk: higher growth → lower risk."""
        g = self.gdp_growth
        if g > 5:
            return 10.0
        elif g > 3:
            return 30.0
        elif g > 1:
            return 50.0
        elif g >= 0:
            return 70.0
        else:
            return 90.0

    def score_inflation_risk(self) -> float:
        """Inflation risk: lower inflation → lower risk."""
        i = self.inflation
        if i < 3:
            return 10.0
        elif i < 6:
            return 30.0
        elif i < 10:
            return 50.0
        elif i < 20:
            return 70.0
        else:
            return 90.0

    def score_political_risk(self) -> float:
        """
        Political stability risk using World Bank Governance Indicator
        (range -2.5 to +2.5; higher is more stable).
        """
        p = self.political_stability
        if p >= 1.0:
            return 10.0
        elif p >= 0.5:
            return 25.0
        elif p >= 0.0:
            return 50.0
        elif p >= -0.5:
            return 70.0
        elif p >= -1.0:
            return 80.0
        else:
            return 95.0

    def score_currency_risk(self) -> float:
        """Currency volatility risk: higher volatility → higher risk."""
        v = self.currency_volatility
        if v < 3:
            return 10.0
        elif v < 7:
            return 30.0
        elif v < 15:
            return 55.0
        elif v < 30:
            return 75.0
        else:
            return 90.0

    def composite_score(self) -> float:
        """Weighted composite risk score (0–100)."""
        scores = {
            "gdp": self.score_gdp_risk(),
            "inflation": self.score_inflation_risk(),
            "political": self.score_political_risk(),
            "currency": self.score_currency_risk(),
        }
        return round(
            sum(scores[k] * self.WEIGHTS[k] for k in scores), 2
        )

    def risk_adjusted_discount_rate(self, base_rate: float = 0.08) -> float:
        """
        Adds a country-risk premium to the base discount rate.
        Premium scales from 0% (score=0) to 10% (score=100).
        """
        risk_premium = (self.composite_score() / 100) * 0.10
        return round(base_rate + risk_premium, 4)

    def to_dict(self) -> Dict:
        """Return full breakdown as a serialisable dict."""
        score = self.composite_score()
        return {
            "country_code": self.country_code,
            "inputs": {
                "gdp_growth_pct": self.gdp_growth,
                "inflation_pct": self.inflation,
                "political_stability_index": self.political_stability,
                "currency_volatility_pct": self.currency_volatility,
            },
            "dimension_scores": {
                "gdp": self.score_gdp_risk(),
                "inflation": self.score_inflation_risk(),
                "political": self.score_political_risk(),
                "currency": self.score_currency_risk(),
            },
            "composite_score": score,
            "risk_band": (
                "Low" if score < 30 else
                "Moderate" if score < 55 else
                "High" if score < 75 else
                "Very High"
            ),
            "risk_adjusted_discount_rate": self.risk_adjusted_discount_rate(),
        }
