"""Meta routes: liveness only for now (no DB touch, so it stays offline-testable)."""

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
