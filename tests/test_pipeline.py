"""
Phase 9 — Integration tests for the full analysis pipeline.
"""
import pytest
from app.models.finance_advanced import FinancialModel, MonteCarloSimulator
from app.models.pypsa_model import SolarEnergyModel, WindEnergyModel
from app.scenarios.simulator import ScenarioSimulator
from app.reporting.report_builder import ReportBuilder
from app.data.cleaners import normalize_country_code


# ─── Financial Model Tests ────────────────────────────────────────────

def test_financial_model_basic():
    model = FinancialModel(
        capex_usd=200_000_000,
        annual_production_mwh=400_000,
        electricity_price_usd=65.0,
        project_life_years=25,
        discount_rate=0.10,
    )
    assert model.npv() is not None
    assert model.irr() is not None
    assert model.lcoe() > 0
    assert model.payback_period() > 0


def test_npv_sign_logic():
    profitable = FinancialModel(
        capex_usd=100_000_000,
        annual_production_mwh=500_000,
        electricity_price_usd=80.0,
        project_life_years=25,
        discount_rate=0.08,
    )
    assert profitable.npv() > 0


def test_lcoe_formula():
    model = FinancialModel(
        capex_usd=150_000_000,
        annual_production_mwh=350_000,
        electricity_price_usd=65.0,
    )
    lcoe = model.lcoe()
    assert 10 < lcoe < 300  # Sanity range USD/MWh


def test_monte_carlo_runs():
    model = FinancialModel(
        capex_usd=200_000_000,
        annual_production_mwh=400_000,
        electricity_price_usd=65.0,
    )
    mc = MonteCarloSimulator(model, n_simulations=500)
    results = mc.run()
    assert results["simulations"] == 500
    assert "npv" in results
    assert "prob_positive" in results["npv"]


# ─── Energy Model Tests ───────────────────────────────────────────────

def test_solar_model_estimation():
    model = SolarEnergyModel(
        capacity_mw=100,
        annual_ghi=1800,
        latitude=33.3,
    )
    production = model._estimate_production()
    assert production > 0


def test_wind_model_capacity_factor():
    model = WindEnergyModel(capacity_mw=50, mean_wind_speed_ms=7.5)
    results = model.run_simulation()
    assert 10 < results["capacity_factor_pct"] < 55
    assert results["annual_production_mwh"] > 0


# ─── Scenario Tests ───────────────────────────────────────────────────

def test_scenario_simulator():
    sim = ScenarioSimulator(
        base_capex=200_000_000,
        base_production_mwh=400_000,
        base_price_usd_mwh=65.0,
        opex_annual=3_000_000,
    )
    results = sim.run_scenarios()
    assert "best" in results
    assert "base" in results
    assert "worst" in results
    assert results["best"]["npv_usd"] > results["worst"]["npv_usd"]


def test_sensitivity_sorted():
    sim = ScenarioSimulator(
        base_capex=200_000_000,
        base_production_mwh=400_000,
        base_price_usd_mwh=65.0,
        opex_annual=3_000_000,
    )
    tornado = sim.sensitivity_analysis()
    swings = [t["swing"] for t in tornado]
    assert swings == sorted(swings, reverse=True)


# ─── Utility Tests ───────────────────────────────────────────────────

def test_country_code_normalization():
    assert normalize_country_code("GB") == "GBR"
    assert normalize_country_code("IQ") == "IRQ"
    assert normalize_country_code("KZ") == "KAZ"
    assert normalize_country_code("GBR") == "GBR"  # passthrough
