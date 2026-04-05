"""
Phase 1 — Data Cleaners
Normalize and validate API responses for downstream modelling.
"""
from typing import Optional
import pandas as pd


def clean_world_bank_series(raw: dict) -> pd.DataFrame:
    """
    Convert World Bank indicator fetch result to a clean DataFrame.
    Returns: DataFrame with columns [year, value]
    """
    entries = raw.get("data", [])
    if not entries:
        return pd.DataFrame(columns=["year", "value"])
    df = pd.DataFrame(entries)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values("year", ascending=False).reset_index(drop=True)
    return df


def clean_nasa_solar(raw: dict) -> dict:
    """
    Clean and validate NASA POWER solar data.
    Returns dict with annual_ghi, mean_temp, daily_series.
    """
    ghi = raw.get("ghi_daily_kwh_m2", {})
    temp = raw.get("temperature_2m_celsius", {})

    valid_ghi = {k: v for k, v in ghi.items() if v and v > 0}
    valid_temp = {k: v for k, v in temp.items() if v is not None}

    annual_ghi = sum(valid_ghi.values())
    mean_temp = sum(valid_temp.values()) / len(valid_temp) if valid_temp else None

    return {
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "annual_ghi_kwh_m2": round(annual_ghi, 2),
        "mean_temp_celsius": round(mean_temp, 2) if mean_temp else None,
        "daily_ghi": valid_ghi,
        "daily_temp": valid_temp,
        "data_points": len(valid_ghi),
    }


def extract_latest_wb_value(indicator_data: dict) -> Optional[float]:
    """Extract the most recent value from a World Bank indicator result."""
    df = clean_world_bank_series(indicator_data)
    if df.empty:
        return None
    return float(df.iloc[0]["value"])


def normalize_country_code(country_input: str) -> str:
    """
    Normalize country input to ISO 3166-1 alpha-3 for World Bank.
    Accepts 2-letter or 3-letter codes; passes through unknown.
    """
    mapping = {
        "GB": "GBR", "US": "USA", "DE": "DEU", "FR": "FRA",
        "IQ": "IRQ", "KZ": "KAZ", "SL": "SLE", "MG": "MDG",
        "PK": "PAK", "SA": "SAU", "AE": "ARE", "NG": "NGA",
        "KE": "KEN", "ET": "ETH", "EG": "EGY", "ZA": "ZAF",
    }
    code = country_input.upper().strip()
    return mapping.get(code, code)
