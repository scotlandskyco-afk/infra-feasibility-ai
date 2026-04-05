"""
FastAPI application entrypoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.db.database import engine, Base

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Infra Feasibility AI",
    description="Production-grade infrastructure and green energy investment analysis platform by GGC.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "platform": "Infra Feasibility AI",
        "company": "Global Group of Companies — www.ggcuk.com",
        "version": "2.0",
        "docs": "/docs",
    }
