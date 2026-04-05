"""
API clients for World Bank and NASA POWER data sources.
All methods use the local JSON cache to avoid redundant network calls.
Fallback synthetic data is returned when the network is unavailable.
"""

import logging
from typing import Dict, Optional

import requests

from app.data.cache import JSONCache
from app.data.cleaners import clean_worldbank_series, clean_nasa_solar

logger = logging.getLogger(__name__)

WB_BASE = "https://api.worldbank.org/v2"
NASA_BASE = "https://power.larc.nasa.gov/api/temporal/monthly/point"

_cache = JSONCache()


class WorldBankClient:
    """Fetches macroeconomic indicators from the World Bank Open Data API v2."""

    INDICATORS = {
        "gdp": "NY.GDP.MKTP.CD",
        "inflation": "FP.CPI.TOTL.ZG",
        "population": "SP.POP.TOTL",
        "energy_use": "EG.USE.PCAP.KG.OE",
    }

    # Synthetic fallback values per indicator (used when API is unavailable)
    FALLBACK = {
        "gdp": {y: 200_000_000_000.0 for y in range(2015, 2025)},
        "inflation": {y: 4.5 for y in range(2015, 2025)},
        "population": {y: 40_000_000 for y in range(2015, 2025)},
        "energy_use": {y: 1500.0 for y in range(2015, 2025)},
    }

    def _fetch_indicator(
        self, country_code: str, indicator: str, years: int
    ) -> Dict[int, Optional[float]]:
        """Core fetch method shared by all indicator helpers."""
        cache_key = f"wb_{country_code}_{indicator}_{years}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        url = (
            f"{WB_BASE}/country/{country_code}/indicator/{indicator}"
            f"?format=json&per_page={years}&mrv={years}"
        )
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            raw = resp.json()
            data = clean_worldbank_series(raw)
            _cache.set(cache_key, data, ttl_hours=48)
            return data
        except Exception as exc:
            logger.warning("World Bank API error (%s): %s", indicator, exc)
            return {}

    def fetch_gdp(self, country_code: str, years: int = 10) -> Dict[int, Optional[float]]:
        """Fetch GDP (current USD) for country."""
        return self._fetch_indicator(country_code, self.INDICATORS["gdp"], years) or self.FALLBACK["gdp"]

    def fetch_inflation(self, country_code: str, years: int = 10) -> Dict[int, Optional[float]]:
        """Fetch CPI inflation (annual %) for country."""
        return self._fetch_indicator(country_code, self.INDICATORS["inflation"], years) or self.FALLBACK["inflation"]

    def fetch_population(self, country_code: str, years: int = 10) -> Dict[int, Optional[float]]:
        """Fetch total population for country."""
        return self._fetch_indicator(country_code, self.INDICATORS["population"], years) or self.FALLBACK["population"]

    def fetch_energy_use(self, country_code: str, years: int = 10) -> Dict[int, Optional[float]]:
        """Fetch energy use per capita (kg of oil equivalent) for country."""
        return self._fetch_indicator(country_code, self.INDICATORS["energy_use"], years) or self.FALLBACK["energy_use"]


class NASAPowerClient:
    """Fetches solar irradiance and temperature data from NASA POWER API."""

    # Default fallback: monthly GHI for a typical MENA location (kWh/m2/day)
    FALLBACK_GHI = {1: 3.2, 2: 4.1, 3: 5.5, 4: 6.8, 5: 7.8, 6: 8.2,
                    7: 7.9, 8: 7.5, 9: 6.4, 10: 5.0, 11: 3.6, 12: 2.9}
    FALLBACK_TEMP = {m: 22.0 for m in range(1, 13)}

    def fetch_solar(
        self,
        lat: float,
        lon: float,
        start_year: int = 2015,
        end_year: int = 2022,
    ) -> Dict[str, Dict[int, float]]:
        """Fetch monthly average GHI and 2m temperature for a lat/lon point."""
        cache_key = f"nasa_{lat}_{lon}_{start_year}_{end_year}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,T2M",
            "community": "RE",
            "longitude": lon,
            "latitude": lat,
            "start": start_year,
            "end": end_year,
            "format": "JSON",
        }
        try:
            resp = requests.get(NASA_BASE, params=params, timeout=30)
            resp.raise_for_status()
            raw = resp.json()
            data = clean_nasa_solar(raw)
            if data["GHI"]:
                _cache.set(cache_key, data, ttl_hours=168)  # 1 week
                return data
        except Exception as exc:
            logger.warning("NASA POWER API error: %s", exc)

        return {"GHI": self.FALLBACK_GHI, "TEMP": self.FALLBACK_TEMP}
