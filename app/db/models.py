"""
Database ORM models: users, projects, results.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    projects = relationship("Project", back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String, default="solar")  # solar, wind, hydro, thermal
    country_code = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    capacity_mw = Column(Float, nullable=False)
    capex_usd = Column(Float, nullable=False)
    electricity_price_usd_mwh = Column(Float, default=65.0)
    project_life_years = Column(Integer, default=25)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="projects")
    results = relationship("AnalysisResult", back_populates="project")


class AnalysisResult(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    run_at = Column(DateTime, default=datetime.utcnow)
    energy_results = Column(JSON, nullable=True)
    financial_results = Column(JSON, nullable=True)
    risk_results = Column(JSON, nullable=True)
    scenario_results = Column(JSON, nullable=True)
    monte_carlo_results = Column(JSON, nullable=True)
    full_report_json = Column(JSON, nullable=True)
    project = relationship("Project", back_populates="results")
