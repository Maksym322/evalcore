"""FastAPI application factory (TechDesign §1.2)."""

from fastapi import FastAPI

from app.api.routes_meta import router as meta_router
from app.api.routes_tickets import router as tickets_router


def create_app() -> FastAPI:
    app = FastAPI(title="TicketPilot", version="0.1.0")
    app.include_router(meta_router)
    app.include_router(tickets_router)
    return app


app = create_app()
