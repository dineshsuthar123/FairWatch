from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import alerts, chat, monitor, reports, upload, public_api

app = FastAPI(
    title="FairWatch API",
    description="Real-Time AI Bias Monitoring System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "FairWatch"}


app.include_router(upload.router)
app.include_router(monitor.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(chat.router)
app.include_router(public_api.router)
