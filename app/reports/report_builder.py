"""
Structures analysis outputs as an investor-grade JSON report
and generates a structured Claude AI prompt for narrative writing.
"""

import json
from datetime import date
from typing import Dict


class ReportBuilder:
    """Assembles all model outputs into a standardised JSON report."""

    def __init__(
        self,
        project_meta: Dict,
        energy_results: Dict,
        financial_results: Dict,
        risk_results: Dict,
        scenario_results: Dict,
    ):
        self.project = project_meta
        self.energy = energy_results
        self.financials = financial_results
        self.risk = risk_results
        self.scenarios = scenario_results

    def build_json(self) -> Dict:
        """Return a fully structured JSON-serialisable report dict."""
        return {
            "report_version": "1.0",
            "generated_at": str(date.today()),
            "project": {
                "name": self.project.get("name", "Unnamed Project"),
                "country": self.project.get("country", "N/A"),
                "location": {
                    "lat": self.project.get("lat"),
                    "lon": self.project.get("lon"),
                },
                "technology": self.project.get("technology", "solar"),
                "capacity_mw": self.project.get("capacity_mw"),
                "analysis_date": str(date.today()),
            },
            "energy": {
                "annual_production_mwh": self.energy.get("annual_production_mwh"),
                "capacity_factor": self.energy.get("capacity_factor"),
                "curtailment_pct": self.energy.get("curtailment_pct"),
                "system_cost_usd": self.energy.get("system_cost_usd"),
                "solver": self.energy.get("solver"),
            },
            "financials": {
                "npv_usd": self.financials.get("npv"),
                "irr_pct": round((self.financials.get("irr") or 0) * 100, 2),
                "lcoe_usd_per_mwh": self.financials.get("lcoe"),
                "payback_years": self.financials.get("payback"),
                "capex_usd": self.financials.get("capex"),
                "opex_annual_usd": self.financials.get("opex"),
                "cash_flows": self.financials.get("cash_flows", []),
                "monte_carlo": self.financials.get("monte_carlo", {}),
            },
            "risk": self.risk,
            "scenarios": self.scenarios,
        }

    def build_claude_prompt(self) -> str:
        """Return a structured prompt string for Claude to generate the investor report."""
        report = self.build_json()
        json_str = json.dumps(report, indent=2)

        npv = report["financials"]["npv_usd"] or 0
        irr = report["financials"]["irr_pct"] or 0
        lcoe = report["financials"]["lcoe_usd_per_mwh"] or 0
        risk_score = report["risk"].get("composite_score", 50)

        if npv > 0 and irr > 10:
            recommendation = "GO"
        elif npv > 0 or irr > 6:
            recommendation = "CONDITIONAL GO"
        else:
            recommendation = "NO-GO"

        return f"""You are a senior infrastructure investment analyst at a global development finance institution.
Using the structured project data below, write a formal investor-grade report with the following sections:

1. EXECUTIVE SUMMARY (2 paragraphs — project overview and headline financials)
2. INVESTMENT RECOMMENDATION: {recommendation} (with detailed rationale based on the data)
3. ENERGY ANALYSIS (production performance, capacity factor assessment)
4. FINANCIAL HIGHLIGHTS (present as a table: NPV, IRR, LCOE, Payback, CAPEX, OPEX)
5. RISK ANALYSIS (key risks identified, mitigants, country risk commentary)
6. SCENARIO ANALYSIS (best/base/worst outcomes with key drivers)

Tone: formal, neutral, data-driven. Suitable for a board investment committee or development bank.
Do not invent data. Use only the values provided in the JSON below.

PROJECT DATA:
{json_str}
"""
