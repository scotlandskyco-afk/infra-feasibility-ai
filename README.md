# Infra Feasibility AI

Production-grade SaaS platform for infrastructure and green energy investment analysis.

Built by Global Group of Companies (GGC) — www.ggcuk.com

## Capabilities

- Real-world data via World Bank, NASA POWER, ElectricityMap APIs
- Energy system modelling with PyPSA
- Financial analysis: NPV, IRR, LCOE, Monte Carlo
- Country risk scoring
- Scenario and sensitivity analysis
- AI-structured JSON output (Claude-ready)
- SaaS backend with FastAPI + PostgreSQL + JWT auth
- Docker-ready deployment

## Quick Start

```bash
docker-compose up --build
```

Backend: http://localhost:8000  
Frontend: http://localhost:8501  
API Docs: http://localhost:8000/docs

## Project Structure

```
infra-feasibility-ai/
├── app/
│   ├── data/
│   │   ├── api_clients.py
│   │   └── cleaners.py
│   ├── models/
│   │   ├── pypsa_model.py
│   │   ├── finance_advanced.py
│   │   └── country_risk.py
│   ├── scenarios/
│   │   └── simulator.py
│   ├── reporting/
│   │   └── report_builder.py
│   ├── api/
│   │   ├── main.py
│   │   ├── auth.py
│   │   └── routes.py
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   └── cache/
│       └── cache_manager.py
├── frontend/
│   └── app.py
├── tests/
│   └── test_pipeline.py
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── requirements.txt
└── .env.example
```
