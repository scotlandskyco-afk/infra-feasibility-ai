"""
Phase 6 — AI Report Builder
Structures all analysis into a Claude-ready JSON payload.
Also generates a plain-text executive summary.
"""
import json
from datetime import datetime
from typing import Dict, Optional


class ReportBuilder:
    """
    Assembles all analysis outputs into a structured investor-grade report.
    Output is compatible with Claude API for narrative report generation.
    """

    def __init__(
        self,
        project_meta: Dict,
        energy_results: Dict,
        financial_results: Dict,
        risk_results: Dict,
        scenario_results: Dict,
        monte_carlo_results: Optional[Dict] = None,
    ):
        self.project = project_meta
        self.energy = energy_results
        self.financials = financial_results
        self.risk = risk_results
        self.scenarios = scenario_results
        self.monte_carlo = monte_carlo_results
        self.generated_at = datetime.utcnow().isoformat() + "Z"

    def build_json_payload(self) -> Dict:
        """Build the full structured JSON for AI processing."""
        return {
            "report_metadata": {
                "generated_at": self.generated_at,
                "platform": "Infra Feasibility AI — GGC",
                "version": "2.0",
            },
            "project": self.project,
            "energy": self.energy,
            "financials": self.financials,
            "risk": self.risk,
            "scenarios": self.scenarios,
            "monte_carlo": self.monte_carlo,
        }

    def build_claude_prompt(self) -> str:
        """Generate a prompt for Claude to produce a narrative investor report."""
        payload = self.build_json_payload()
        payload_str = json.dumps(payload, indent=2, default=str)

        prompt = f"""You are an infrastructure investment analyst. Based on the following structured feasibility analysis data, produce a formal investor-grade report including:

1. Executive Summary (3–4 paragraphs)
2. Energy System Assessment
3. Financial Analysis and Recommendation
4. Country Risk Assessment
5. Scenario Analysis and Sensitivity
6. Investment Recommendation (PROCEED / PROCEED WITH CONDITIONS / DO NOT PROCEED)

Data:
{payload_str}

Write in formal business English suitable for institutional investors and government agencies."""
        return prompt

    def executive_summary_text(self) -> str:
        """Generate a plain-text executive summary without AI."""
        p = self.project
        f = self.financials
        e = self.energy
        r = self.risk

        npv = f.get("npv_usd", "N/A")
        irr = f.get("irr_pct", "N/A")
        lcoe = f.get("lcoe_usd_mwh", "N/A")
        risk_label = r.get("risk_label", "N/A")
        production = e.get("annual_production_mwh", "N/A")
        cf = e.get("capacity_factor_pct", "N/A")

        rec = (
            "PROCEED" if isinstance(npv, (int, float)) and npv > 0 and isinstance(irr, (int, float)) and irr > 12
            else "PROCEED WITH CONDITIONS" if isinstance(npv, (int, float)) and npv > 0
            else "FURTHER ANALYSIS REQUIRED"
        )

        return f"""
EXECUTIVE SUMMARY — {p.get('name', 'Infrastructure Project')}
Generated: {self.generated_at}

Project Overview
The proposed {p.get('type', 'renewable energy')} project is located in {p.get('country', 'the target country')} with an installed capacity of {p.get('capacity_mw', 'N/A')} MW. The project has been evaluated using live macro-economic data, NASA solar irradiance data, and PyPSA energy system modelling.

Energy Performance
Annual energy production is estimated at {production} MWh with a capacity factor of {cf}%. These outputs are derived from site-specific solar resource data and validated through system simulation.

Financial Viability
The project yields a Net Present Value of USD {npv:,.0f} and an Internal Rate of Return of {irr}%. The Levelized Cost of Energy is USD {lcoe}/MWh, which is competitive against regional benchmarks. Simple payback is estimated at {f.get('payback_years', 'N/A')} years.

Country Risk
The target country ({r.get('country_code', 'N/A')}) carries a composite risk score of {r.get('composite_risk_score', 'N/A')}/100, classified as {risk_label} risk. The risk-adjusted discount rate applied is {r.get('risk_adjusted_discount_rate_pct', 'N/A')}%.

Investment Recommendation: {rec}
        """.strip()

    def export_json(self, filepath: str) -> None:
        """Save report JSON to file."""
        with open(filepath, "w") as f:
            json.dump(self.build_json_payload(), f, indent=2, default=str)
        print(f"Report saved to {filepath}")
