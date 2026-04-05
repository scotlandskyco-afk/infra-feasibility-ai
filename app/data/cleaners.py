"""
Data cleaning and normalisation utilities for World Bank and NASA POWER responses.
"""

from typing import Dict, List, Optional


def clean_worldbank_series(raw: list) -> Dict[int, Optional[float]]:
    """
    Extract a clean {year: value} dict from a World Bank API v2 response.
    The response is a list of two elements; the second is the data array.
    """
    result: Dict[int, Optional[float]] = {}
    if not raw or len(raw) < 2:
        return result
    for entry in raw[1] or []:
        try:
            year = int(entry["date"])
            value = float(entry["value"]) if entry["value"] is not None else None
            result[year] = value
        except (KeyError, TypeError, ValueError):
            continue
    return dict(sorted(result.items()))


def clean_nasa_solar(raw: dict) -> Dict[str, Dict[int, float]]:
    """
    Extract monthly GHI and temperature averages from NASA POWER API response.
    Returns {"GHI": {month_num: value}, "TEMP": {month_num: value}}.
    """
    result: Dict[str, Dict[int, float]] = {"GHI": {}, "TEMP": {}}
    try:
        params = raw["properties"]["parameter"]
        ghi_data = params.get("ALLSKY_SFC_SW_DWN", {})
        temp_data = params.get("T2M", {})

        monthly_ghi: Dict[int, List[float]] = {m: [] for m in range(1, 13)}
        monthly_temp: Dict[int, List[float]] = {m: [] for m in range(1, 13)}

        for key, val in ghi_data.items():
            if val is not None and val != -999:
                try:
                    month = int(key[-2:])
                    if 1 <= month <= 12:
                        monthly_ghi[month].append(float(val))
                except (ValueError, IndexError):
                    pass

        for key, val in temp_data.items():
            if val is not None and val != -999:
                try:
                    month = int(key[-2:])
                    if 1 <= month <= 12:
                        monthly_temp[month].append(float(val))
                except (ValueError, IndexError):
                    pass

        result["GHI"] = {m: sum(v) / len(v) for m, v in monthly_ghi.items() if v}
        result["TEMP"] = {m: sum(v) / len(v) for m, v in monthly_temp.items() if v}
    except (KeyError, TypeError):
        pass
    return result


def normalise_to_annual(monthly_dict: Dict[int, float]) -> float:
    """
    Average a {month: value} dict to a single annual mean.
    """
    values = [v for v in monthly_dict.values() if v is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)
