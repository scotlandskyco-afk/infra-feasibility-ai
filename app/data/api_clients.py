"""
Phase 1 — Real Data API Clients
Sources: World Bank, NASA POWER, ElectricityMap
"""
import os
import requests
import httpx
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from app.cache.cache_manager import get_cached, set_cached

load_dotenv()

WORLD_BANK_BASE = os.getenv("WORLD_BANK_BASE_URL", "https://api.worldbank.org/v2")
NASA_POWER_BASE = os.getenv("NASA_POWER_BASE_URL", "https://power.larc.nasa.gov/api/temporal/daily/point")
ELECTRICITYMAP_BASE = os.getenv("ELECTRICITYMAP_BASE_URL", "https://api.electricitymap.org/v3")
ELECTRICITYMAP_KEY = os.getenv("ELECTRICITYMAP_API_KEY", "")


class WorldBankClient:
    """
    Fetches macroeconomic indicators from the World Bank Open Data API.
    No API key required.
    Indicators:
        NY.GDP.MKTP.KD.ZG  — GDP growth (%)
        FP.CPI.TOTL.ZG      — Inflation (CPI %)
        SP.POP.TOTL         — Population
        EG.USE.PCAP.KG.OE   — Energy use per capita (kg oil eq)
    """

    INDICATORS = {
        "gdp_growth": "NY.GDP.MKTP.KD.ZG",
        "inflation": "FP.CPI.TOTL.ZG",
        "population": "SP.POP.TOTL",
        "energy_use_per_capita": "EG.USE.PCAP.KG.OE",
    }

    def fetch_indicator(self, country_code: str, indicator_key: str, years: int = 5) -> dict:
        """Fetch a single indicator for a country over recent years."""
        cache_key = f"wb_{country_code}_{indicator_key}_{years}"
        cached = get_cached(cache_key)
        if cached:
            return cached

        indicator_code = self.INDICATORS.get(indicator_key)
        if not indicator_code:
            raise ValueError(f"Unknown indicator: {indicator_key}")

        end_year = datetime.now().year - 1
        start_year = end_year - years
        url = (
            f"{WORLD_BANK_BASE}/country/{country_code}/indicator/{indicator_code}"
            f"?format=json&date={start_year}:{end_year}&per_page=10"
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        result = {
            "country": country_code,
            "indicator": indicator_key,
            "data": [
                {"year": entry["date"], "value": entry["value"]}
                for entry in data[1]
                if entry["value"] is not None
            ],
        }
        set_cached(cache_key, result)
        return result

    def fetch_all_indicators(self, country_code: str) -> dict:
        """Fetch all macro indicators for a country."""
        result = {}
        for key in self.INDICATORS:
            try:
                result[key] = self.fetch_indicator(country_code, key)
            except Exception as e:
                result[key] = {"error": str(e)}
        return result

    def get_latest_value(self, country_code: str, indicator_key: str) -> Optional[float]:
        """Return the most recent non-null value for an indicator."""
        data = self.fetch_indicator(country_code, indicator_key)
        entries = data.get("data", [])
        if not entries:
            return None
        return entries[0]["value"]


class NASAPowerClient:
    """
    Fetches solar irradiance and temperature data from NASA POWER API.
    No API key required.
    Parameters:
        ALLSKY_SFC_SW_DWN — All-sky surface shortwave downward irradiance (GHI, kWh/m2/day)
        T2M               — Temperature at 2 metres (Celsius)
    """

    def fetch_solar_data(
        self,
        latitude: float,
        longitude: float,
        start_date: str = None,
        end_date: str = None,
    ) -> dict:
        """
        Fetch daily solar irradiance and temperature for a location.
        Dates format: YYYYMMDD
        Defaults to last 365 days.
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if not end_date:
            end_date = (datetime.now() - timedelta(days=2)).strftime("%Y%m%d")

        cache_key = f"nasa_{latitude}_{longitude}_{start_date}_{end_date}"
        cached = get_cached(cache_key)
        if cached:
            return cached

        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,T2M",
            "community": "RE",
            "longitude": longitude,
            "latitude": latitude,
            "start": start_date,
            "end": end_date,
            "format": "JSON",
        }
        response = requests.get(NASA_POWER_BASE, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        properties = data.get("properties", {}).get("parameter", {})
        ghi_data = properties.get("ALLSKY_SFC_SW_DWN", {})
        temp_data = properties.get("T2M", {})

        result = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "ghi_daily_kwh_m2": ghi_data,
            "temperature_2m_celsius": temp_data,
            "annual_ghi_kwh_m2": sum(v for v in ghi_data.values() if v and v > 0),
            "mean_temperature": (
                sum(v for v in temp_data.values() if v is not None)
                / len([v for v in temp_data.values() if v is not None])
                if temp_data
                else None
            ),
        }
        set_cached(cache_key, result)
        return result

    def get_annual_ghi(self, latitude: float, longitude: float) -> float:
        """Return annual GHI in kWh/m2/year for a location."""
        data = self.fetch_solar_data(latitude, longitude)
        return data.get("annual_ghi_kwh_m2", 1600.0)


class ElectricityMapClient:
    """
    Fetches grid carbon intensity and energy mix from ElectricityMap.
    Requires a free API key from electricitymap.org
    """

    def __init__(self):
        self.headers = {"auth-token": ELECTRICITYMAP_KEY}

    def get_carbon_intensity(self, zone: str) -> dict:
        """Fetch current carbon intensity for a grid zone (e.g. 'GB', 'DE', 'US-CAL-CISO')."""
        cache_key = f"emap_ci_{zone}"
        cached = get_cached(cache_key, ttl_hours=1)
        if cached:
            return cached

        url = f"{ELECTRICITYMAP_BASE}/carbon-intensity/latest?zone={zone}"
        response = requests.get(url, headers=self.headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            set_cached(cache_key, result, ttl_hours=1)
            return result
        return {"zone": zone, "carbonIntensity": None, "error": response.text}

    def get_power_breakdown(self, zone: str) -> dict:
        """Fetch current power production breakdown for a zone."""
        cache_key = f"emap_pb_{zone}"
        cached = get_cached(cache_key, ttl_hours=1)
        if cached:
            return cached

        url = f"{ELECTRICITYMAP_BASE}/power-breakdown/latest?zone={zone}"
        response = requests.get(url, headers=self.headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            set_cached(cache_key, result, ttl_hours=1)
            return result
        return {"zone": zone, "error": response.text}
