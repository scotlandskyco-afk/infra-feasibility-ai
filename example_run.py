"""
Phase 9 — Example standalone run (no Docker required).
Demonstrates the full pipeline for a 200MW Solar project in Iraq.
"""
import json
from app.models.pypsa_model import SolarEnergyModel
from app.models.finance_advanced import FinancialModel, MonteCarloSimulator
from app.models.country_risk import CountryRiskEngine
from app.scenarios.simulator import ScenarioSimulator
from app.reporting.report_builder import ReportBuilder

print("=" * 60)
print(" INFRA FEASIBILITY AI — EXAMPLE RUN")
print(" Global Group of Companies — www.ggcuk.com")
print("=" * 60)

# Project definition
project_meta = {
    "name": "Iraq Solar Farm 200MW",
    "type": "solar",
    "country": "Iraq",
    "capacity_mw": 200,
    "capex_usd": 200_000_000,
    "latitude": 33.3,
    "longitude": 44.4,
}

# Step 1: Energy modelling (using estimated GHI for Iraq ~ 2000 kWh/m2/year)
print("\nStep 1: Energy Modelling...")
energy_model = SolarEnergyModel(
    capacity_mw=200,
    annual_ghi=2000,
    latitude=33.3,
    battery_mwh=100,
    project_name="Iraq Solar Farm",
)
energy_results = energy_model.run_simulation()
print(f"  Annual Production: {energy_results['annual_production_mwh']:,.0f} MWh")
print(f"  Capacity Factor:   {energy_results['capacity_factor_pct']:.1f}%")

# Step 2: Country risk
print("\nStep 2: Country Risk Assessment...")
risk_engine = CountryRiskEngine("IQ")
try:
    risk_results = risk_engine.calculate()
except Exception as e:
    print(f"  [Note] Live API unavailable, using defaults. Error: {e}")
    risk_results = {
        "country_code": "IRQ",
        "composite_risk_score": 28.0,
        "risk_label": "High",
        "risk_adjusted_discount_rate_pct": 15.5,
        "component_scores": {"gdp_growth": 40, "inflation": 25, "political_stability": 22, "currency_stability": 30},
        "raw_indicators": {},
    }
print(f"  Risk Score: {risk_results['composite_risk_score']}/100 ({risk_results['risk_label']})")
print(f"  Risk-Adjusted Discount Rate: {risk_results['risk_adjusted_discount_rate_pct']}%")

# Step 3: Financial model
print("\nStep 3: Financial Modelling...")
discount_rate = risk_results["risk_adjusted_discount_rate_pct"] / 100
fin_model = FinancialModel(
    capex_usd=200_000_000,
    annual_production_mwh=energy_results["annual_production_mwh"],
    electricity_price_usd=70.0,
    project_life_years=25,
    discount_rate=discount_rate,
)
financial_results = fin_model.full_analysis()
print(f"  NPV:           USD {financial_results['npv_usd']:,.0f}")
print(f"  IRR:           {financial_results['irr_pct']:.1f}%")
print(f"  LCOE:          USD {financial_results['lcoe_usd_mwh']:.2f}/MWh")
print(f"  Payback:       {financial_results['payback_years']:.1f} years")

# Step 4: Monte Carlo
print("\nStep 4: Monte Carlo Simulation (2,000 runs)...")
mc = MonteCarloSimulator(fin_model, n_simulations=2000)
mc_results = mc.run()
print(f"  NPV P50: USD {mc_results['npv']['p50']:,.0f}")
print(f"  Probability of Positive NPV: {mc_results['npv']['prob_positive']:.1f}%")

# Step 5: Scenarios
print("\nStep 5: Scenario Analysis...")
sim = ScenarioSimulator(
    base_capex=200_000_000,
    base_production_mwh=energy_results["annual_production_mwh"],
    base_price_usd_mwh=70.0,
    opex_annual=fin_model.opex,
    project_life=25,
    discount_rate=discount_rate,
)
scenario_results = sim.run_scenarios()
for name, s in scenario_results.items():
    print(f"  {name.capitalize():6} — NPV: USD {s['npv_usd']:>15,.0f} | IRR: {s['irr_pct']:.1f}%")

# Step 6: Report
print("\nStep 6: Building Investor Report...")
builder = ReportBuilder(
    project_meta, energy_results, financial_results,
    risk_results, scenario_results, mc_results
)
print(builder.executive_summary_text())

# Export
builder.export_json("sample_report.json")
print("\nFull JSON report saved to: sample_report.json")
print("Claude prompt available via: builder.build_claude_prompt()")
