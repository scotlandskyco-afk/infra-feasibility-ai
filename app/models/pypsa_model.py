"""
PyPSA-based energy network model for infrastructure feasibility analysis.
Builds a simplified AC network, simulates solar generation, and computes
annual production, capacity factor, and system cost.
Falls back to a deterministic calculation if no LP solver is available.
"""

import logging
import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _monthly_ghi_to_hourly(monthly_ghi: Dict[int, float], capacity_mw: float) -> pd.Series:
    """
    Expand monthly average GHI (kWh/m2/day) to an 8760-hour normalised
    capacity factor series using a sinusoidal daily pattern.
    Returns values in range [0, 1] representing p_max_pu for the generator.
    """
    hours_per_month = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
    peak_ghi = max(monthly_ghi.values()) if monthly_ghi else 8.0

    hourly = []
    for month in range(1, 13):
        ghi = monthly_ghi.get(month, peak_ghi * 0.5)
        n_hours = hours_per_month[month - 1]
        for h in range(n_hours):
            hour_of_day = h % 24
            # Sinusoidal daylight pattern: peak at solar noon (hour 12)
            angle = math.pi * (hour_of_day - 6) / 12
            raw = math.sin(angle) if 6 <= hour_of_day <= 18 else 0.0
            # Scale by monthly GHI ratio relative to peak
            pu = max(0.0, raw * (ghi / peak_ghi))
            hourly.append(pu)

    series = pd.Series(hourly[:8760], dtype=float)
    return series


class InfrastructurePyPSAModel:
    """Simplified PyPSA network model for a single-bus solar generation system."""

    def __init__(
        self,
        project_name: str,
        capacity_mw: float,
        lat: float,
        lon: float,
        technology: str = "solar",
        include_battery: bool = False,
    ):
        self.project_name = project_name
        self.capacity_mw = capacity_mw
        self.lat = lat
        self.lon = lon
        self.technology = technology
        self.include_battery = include_battery
        self.network = None
        self._results: Optional[Dict] = None

    def build_network(
        self, solar_profile: Optional[Dict[int, float]] = None
    ) -> None:
        """
        Construct a PyPSA Network with one bus, one generator,
        one load, and optionally a battery storage unit.
        """
        try:
            import pypsa  # noqa: PLC0415
        except ImportError:
            logger.warning("PyPSA not installed; will use analytic fallback.")
            self.network = None
            self._solar_profile = solar_profile or {}
            return

        if solar_profile is None:
            # Default flat 20% capacity factor if no profile supplied
            solar_profile = {m: 5.0 for m in range(1, 13)}

        p_max_pu = _monthly_ghi_to_hourly(solar_profile, self.capacity_mw)
        snapshots = pd.date_range("2023-01-01", periods=8760, freq="h")

        network = pypsa.Network()
        network.set_snapshots(snapshots)

        network.add("Bus", "main_bus", v_nom=33.0)

        network.add(
            "Generator",
            "solar_gen",
            bus="main_bus",
            p_nom=self.capacity_mw,
            p_max_pu=p_max_pu.values,
            carrier="solar",
            marginal_cost=0.0,
            capital_cost=0.0,
        )

        # Load set at 80 % of nameplate capacity
        load_profile = pd.Series(
            self.capacity_mw * 0.8, index=snapshots, dtype=float
        )
        network.add("Load", "demand", bus="main_bus", p_set=load_profile.values)

        if self.include_battery:
            network.add(
                "StorageUnit",
                "battery",
                bus="main_bus",
                p_nom=self.capacity_mw * 0.25,
                max_hours=4,
                efficiency_store=0.95,
                efficiency_dispatch=0.95,
                capital_cost=0.0,
                marginal_cost=0.0,
            )

        self.network = network
        self._solar_profile = solar_profile

    def run_simulation(self) -> None:
        """Run the network optimisation (LOPF). Falls back gracefully."""
        if self.network is None:
            logger.info("No PyPSA network; using analytic fallback.")
            return
        try:
            status, condition = self.network.lopf(
                self.network.snapshots,
                solver_name="highs",
                pyomo=False,
            )
            if status != "ok":
                logger.warning("LOPF status: %s — %s", status, condition)
        except Exception as exc:
            logger.warning("LOPF failed (%s); using analytic fallback.", exc)

    def get_results(self) -> Dict:
        """Return key energy performance metrics."""
        if self.network is not None:
            try:
                gen = self.network.generators_t.p.get("solar_gen")
                if gen is not None and not gen.empty:
                    annual_mwh = float(gen.sum())
                    capacity_factor = annual_mwh / (self.capacity_mw * 8760)
                    load_served = float(self.network.loads_t.p.get("demand", pd.Series(0)).sum())
                    curtailment_pct = max(
                        0.0, (annual_mwh - load_served) / annual_mwh * 100
                    ) if annual_mwh > 0 else 0.0
                    system_cost = self.capacity_mw * 900_000  # $900/kW default CAPEX proxy
                    return {
                        "annual_production_mwh": round(annual_mwh, 1),
                        "capacity_factor": round(capacity_factor, 4),
                        "curtailment_pct": round(curtailment_pct, 2),
                        "system_cost_usd": round(system_cost, 0),
                        "solver": "lopf",
                    }
            except Exception as exc:
                logger.warning("Results extraction failed: %s", exc)

        # ---- Analytic fallback ----
        profile = getattr(self, "_solar_profile", {m: 5.0 for m in range(1, 13)})
        avg_ghi = sum(profile.values()) / max(len(profile), 1) if profile else 5.0
        # Capacity factor approximation: GHI(kWh/m2/day) / 24 as fraction of peak
        peak_ghi = 10.0  # theoretical max kWh/m2/day
        capacity_factor = min(avg_ghi / peak_ghi, 1.0)
        annual_mwh = self.capacity_mw * capacity_factor * 8760
        system_cost = self.capacity_mw * 900_000
        return {
            "annual_production_mwh": round(annual_mwh, 1),
            "capacity_factor": round(capacity_factor, 4),
            "curtailment_pct": 0.0,
            "system_cost_usd": round(system_cost, 0),
            "solver": "analytic_fallback",
        }
