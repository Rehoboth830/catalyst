import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.tools.create_ticket import router as create_ticket_router
from app.tools.draft_stakeholder_update import router as draft_update_router
from app.tools.schedule_review import router as schedule_review_router
from app.tools.approval import router as approval_router
from app.tools.clusters import router as clusters_router

app = FastAPI(title="Catalyst Agent Tool Layer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(create_ticket_router)
app.include_router(draft_update_router)
app.include_router(schedule_review_router)
app.include_router(approval_router)
app.include_router(clusters_router)

@app.get("/health")
def health():
    return {"status": "ok"}
