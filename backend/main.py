from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router

app = FastAPI(title="Agentic Patient Intake GematikPlatform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# The LangGraph workflow (app.agents.graph.intake_graph) is invoked in app/api/endpoints.py: POST /api/chat
app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
