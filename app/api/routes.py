"""
FastAPI routes: auth, projects, analysis, scenarios.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import timedelta

from app.db.database import get_db
from app.db.models import User, Project, AnalysisResult
from app.api.auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.data.api_clients import WorldBankClient, NASAPowerClient
from app.models.pypsa_model import SolarEnergyModel
from app.models.finance_advanced import FinancialModel, MonteCarloSimulator
from app.models.country_risk import CountryRiskEngine
from app.scenarios.simulator import ScenarioSimulator
from app.reporting.report_builder import ReportBuilder

router = APIRouter()


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


@router.post("/auth/signup", status_code=201)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(400, "Email already registered")
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(400, "Username taken")
    user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}


@router.post("/auth/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect credentials")
    token = create_access_token({"sub": user.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}


# ─── Projects ────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_type: str = "solar"
    country_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity_mw: float
    capex_usd: float
    electricity_price_usd_mwh: float = 65.0
    project_life_years: int = 25


@router.post("/projects", status_code=201)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(**project_in.dict(), owner_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "status": "created"}


@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = db.query(Project).filter(Project.owner_id == current_user.id).all()
    return [
        {
            "id": p.id, "name": p.name, "country_code": p.country_code,
            "capacity_mw": p.capacity_mw, "capex_usd": p.capex_usd,
            "created_at": p.created_at,
        }
        for p in projects
    ]


# ─── Analysis ────────────────────────────────────────────────────────────────

@router.post("/analyze/{project_id}")
def run_analysis(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")

    # Energy modelling
    lat = project.latitude or 30.0
    lon = project.longitude or 45.0
    nasa = NASAPowerClient()
    try:
        solar_data = nasa.fetch_solar_data(lat, lon)
        annual_ghi = solar_data.get("annual_ghi_kwh_m2", 1700.0)
    except Exception:
        annual_ghi = 1700.0

    energy_model = SolarEnergyModel(
        capacity_mw=project.capacity_mw,
        annual_ghi=annual_ghi,
        latitude=lat,
        project_name=project.name,
    )
    energy_results = energy_model.run_simulation()

    # Country risk
    risk_engine = CountryRiskEngine(project.country_code)
    try:
        risk_results = risk_engine.calculate()
    except Exception as e:
        risk_results = {"error": str(e), "risk_label": "Unknown", "composite_risk_score": 50}

    discount_rate = risk_results.get("risk_adjusted_discount_rate_pct", 10.0) / 100

    # Financial model
    fin_model = FinancialModel(
        capex_usd=project.capex_usd,
        annual_production_mwh=energy_results["annual_production_mwh"],
        electricity_price_usd=project.electricity_price_usd_mwh,
        project_life_years=project.project_life_years,
        discount_rate=discount_rate,
    )
    financial_results = fin_model.full_analysis()

    # Monte Carlo
    mc = MonteCarloSimulator(fin_model, n_simulations=2000)
    monte_carlo_results = mc.run()

    # Scenarios
    sim = ScenarioSimulator(
        base_capex=project.capex_usd,
        base_production_mwh=energy_results["annual_production_mwh"],
        base_price_usd_mwh=project.electricity_price_usd_mwh,
        opex_annual=fin_model.opex,
        project_life=project.project_life_years,
        discount_rate=discount_rate,
    )
    scenario_results = sim.run_scenarios()
    sensitivity = sim.sensitivity_analysis()

    # Report
    project_meta = {
        "id": project.id,
        "name": project.name,
        "type": project.project_type,
        "country": project.country_code,
        "capacity_mw": project.capacity_mw,
        "capex_usd": project.capex_usd,
        "latitude": lat,
        "longitude": lon,
    }
    builder = ReportBuilder(project_meta, energy_results, financial_results, risk_results, scenario_results, monte_carlo_results)
    report = builder.build_json_payload()
    report["executive_summary"] = builder.executive_summary_text()
    report["claude_prompt"] = builder.build_claude_prompt()
    report["sensitivity"] = sensitivity

    # Save to DB
    result_record = AnalysisResult(
        project_id=project.id,
        energy_results=energy_results,
        financial_results=financial_results,
        risk_results=risk_results,
        scenario_results=scenario_results,
        monte_carlo_results=monte_carlo_results,
        full_report_json=report,
    )
    db.add(result_record)
    db.commit()

    return report


@router.get("/projects/{project_id}/results")
def get_results(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = db.query(AnalysisResult).filter(
        AnalysisResult.project_id == project_id
    ).order_by(AnalysisResult.run_at.desc()).all()
    return [
        {"id": r.id, "run_at": r.run_at, "financial": r.financial_results, "risk": r.risk_results}
        for r in results
    ]


@router.get("/health")
def health_check():
    return {"status": "ok", "platform": "Infra Feasibility AI", "version": "2.0"}
