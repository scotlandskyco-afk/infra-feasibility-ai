"""
Phase 2 — PyPSA Energy System Modelling
Builds a realistic solar + battery network and simulates energy production.
"""
import numpy as np
import pandas as pd
from typing import Optional

try:
    import pypsa
    PYPSA_AVAILABLE = True
except ImportError:
    PYPSA_AVAILABLE = False


class SolarEnergyModel:
    """
    Simulates a solar PV project using PyPSA.
    Inputs:
        capacity_mw     — Installed solar capacity in MW
        annual_ghi      — Annual GHI from NASA POWER (kWh/m2/year)
        latitude        — Site latitude
        battery_mwh     — Optional battery storage capacity (MWh)
        project_name    — Label for the project
    """

    def __init__(
        self,
        capacity_mw: float,
        annual_ghi: float,
        latitude: float = 30.0,
        battery_mwh: Optional[float] = None,
        project_name: str = "Solar Project",
    ):
        self.capacity_mw = capacity_mw
        self.annual_ghi = annual_ghi
        self.latitude = latitude
        self.battery_mwh = battery_mwh
        self.project_name = project_name
        self.network = None
        self.results = {}

    def _build_hourly_profile(self) -> np.ndarray:
        """
        Generate a synthetic 8760-hour solar capacity factor profile.
        Uses a simplified solar geometry model scaled to the annual GHI.
        """
        hours = np.arange(8760)
        day_of_year = hours // 24
        hour_of_day = hours % 24

        # Solar declination and zenith approximation
        declination = 23.45 * np.sin(np.radians((360 / 365) * (day_of_year - 81)))
        lat_rad = np.radians(self.latitude)
        dec_rad = np.radians(declination)
        hour_angle = np.radians((hour_of_day - 12) * 15)

        cos_zenith = (
            np.sin(lat_rad) * np.sin(dec_rad)
            + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_angle)
        )
        cf = np.maximum(cos_zenith, 0)

        # Scale to match annual GHI
        peak_ghi_per_hour = self.annual_ghi / 365 / 6  # rough peak hours
        cf_scaled = cf * peak_ghi_per_hour
        cf_normalized = cf_scaled / (self.capacity_mw * 1000) if self.capacity_mw > 0 else cf_scaled
        cf_clipped = np.clip(cf_normalized, 0, 1)
        return cf_clipped

    def build_network(self) -> None:
        """Construct the PyPSA network."""
        if not PYPSA_AVAILABLE:
            raise RuntimeError("PyPSA is not installed. Run: pip install pypsa")

        snapshots = pd.date_range("2024-01-01", periods=8760, freq="h")
        cf_profile = self._build_hourly_profile()
        solar_series = pd.Series(cf_profile, index=snapshots)

        n = pypsa.Network()
        n.set_snapshots(snapshots)

        # Main bus
        n.add("Bus", "main_bus", carrier="AC")

        # Solar generator
        n.add(
            "Generator",
            "solar_pv",
            bus="main_bus",
            carrier="solar",
            p_nom=self.capacity_mw,
            p_max_pu=solar_series,
            marginal_cost=0.0,
            capital_cost=0.0,  # handled in financial model
        )

        # Load (representative average demand)
        avg_load_mw = self.capacity_mw * 0.7
        load_profile = pd.Series(avg_load_mw, index=snapshots)
        n.add("Load", "demand", bus="main_bus", p_set=load_profile)

        # Battery storage (optional)
        if self.battery_mwh:
            n.add(
                "StorageUnit",
                "battery",
                bus="main_bus",
                carrier="battery",
                p_nom=self.battery_mwh / 4,  # C-rate: 4-hour battery
                max_hours=4,
                efficiency_store=0.92,
                efficiency_dispatch=0.92,
                cyclic_state_of_charge=True,
            )

        self.network = n

    def run_simulation(self) -> dict:
        """Run PyPSA simulation and extract key results."""
        if self.network is None:
            self.build_network()

        try:
            self.network.optimize(solver_name="glpk")
            solve_status = "optimal"
        except Exception:
            # Fallback: linear approximation without solver
            solve_status = "approximated"

        # Extract results
        solar_gen = self.network.generators_t.p.get("solar_pv", pd.Series(dtype=float))
        total_production_mwh = float(solar_gen.sum()) if not solar_gen.empty else self._estimate_production()
        capacity_factor = total_production_mwh / (self.capacity_mw * 8760) if self.capacity_mw > 0 else 0

        self.results = {
            "project_name": self.project_name,
            "installed_capacity_mw": self.capacity_mw,
            "annual_production_mwh": round(total_production_mwh, 2),
            "capacity_factor_pct": round(capacity_factor * 100, 2),
            "battery_storage_mwh": self.battery_mwh,
            "annual_ghi_kwh_m2": self.annual_ghi,
            "solve_status": solve_status,
            "peak_output_mw": float(solar_gen.max()) if not solar_gen.empty else self.capacity_mw,
        }
        return self.results

    def _estimate_production(self) -> float:
        """Fallback estimate: capacity * annual_ghi-based capacity factor."""
        # Typical CF from GHI: CF ≈ GHI / (365 * 24 * peak_sun_factor)
        peak_sun_hours = self.annual_ghi / 1000
        return self.capacity_mw * peak_sun_hours


class WindEnergyModel:
    """
    Simplified wind energy model for onshore or offshore wind projects.
    Uses a Rayleigh wind speed distribution.
    """

    def __init__(self, capacity_mw: float, mean_wind_speed_ms: float, project_name: str = "Wind Project"):
        self.capacity_mw = capacity_mw
        self.mean_wind_speed_ms = mean_wind_speed_ms
        self.project_name = project_name

    def estimate_capacity_factor(self) -> float:
        """Estimate CF from mean wind speed using Rayleigh distribution."""
        v = self.mean_wind_speed_ms
        # Empirical CF curve approximation for modern turbines
        if v < 3:
            return 0.05
        elif v < 5:
            return 0.10 + (v - 3) * 0.05
        elif v < 8:
            return 0.20 + (v - 5) * 0.06
        elif v < 12:
            return 0.38 + (v - 8) * 0.02
        else:
            return 0.45

    def run_simulation(self) -> dict:
        cf = self.estimate_capacity_factor()
        annual_production = self.capacity_mw * cf * 8760
        return {
            "project_name": self.project_name,
            "installed_capacity_mw": self.capacity_mw,
            "annual_production_mwh": round(annual_production, 2),
            "capacity_factor_pct": round(cf * 100, 2),
            "mean_wind_speed_ms": self.mean_wind_speed_ms,
        }
