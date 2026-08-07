from fastapi import FastAPI

from app.budget.router import router as budget_router
from app.gamification.router import router as gamification_router
from app.notifications.router import router as notifications_router
from app.profile.router import router as profile_router
from app.receipts.router import router as receipts_router
from app.transactions.router import router as transactions_router

app = FastAPI(title="Grana API")

app.include_router(transactions_router)
app.include_router(budget_router)
app.include_router(gamification_router)
app.include_router(notifications_router)
app.include_router(receipts_router)
app.include_router(profile_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
