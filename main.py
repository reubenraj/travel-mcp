import json
import os
import sqlite3
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

from rules_engine import (
    enforce_partner_rules,
    Recommendation,
    PartnerRules,
    EnforcementResult
)

load_dotenv()

MEMBER_SERVICE_URL  = os.getenv("MEMBER_SERVICE_URL",  "http://localhost:8001")
PARTNER_SERVICE_URL = os.getenv("PARTNER_SERVICE_URL", "http://localhost:8002")


app = FastAPI(
    title="Agentic Travel Recommendations API",
    description="MCP-connected service powering the AI Concierge feature",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RecommendRequest(BaseModel):
    member_id: str
    message: Optional[str] = "Give me travel recommendations"

class RecommendResponse(BaseModel):
    member_id: str
    partner_id: str
    partner_name: str
    ai_response: str
    recommendations: List[Recommendation]
    enforcement_log: List[str]
    tools_called: List[str]
    

# ── Helper: fetch from upstream services ──────────────────────────────────────
async def fetch_member(member_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{MEMBER_SERVICE_URL}/members/{member_id}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Member {member_id} not found")
        resp.raise_for_status()
        return resp.json()

async def fetch_partner(partner_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{PARTNER_SERVICE_URL}/partners/{partner_id}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Partner {partner_id} not found")
        resp.raise_for_status()
        return resp.json()

# ── Helper: fetch recommendations from SQLite ─────────────────────────────────

def fetch_all_recommendations() -> List[Recommendation]:
    db_path = os.path.join(os.path.dirname(__file__), "db", "travel.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM recommendations").fetchall()
    conn.close()
    return [
        Recommendation(
            rec_id=row["rec_id"],
            destination=row["destination"],
            category=row["category"],
            description=row["description"],
            base_price=row["base_price"]
        )
        for row in rows
    ]

# ── Core recommendation pipeline ──────────────────────────────────────────────

async def run_recommendation_pipeline(
    member_id: str,
    message: str
) -> RecommendResponse:
    """
    Full pipeline:
    1. Fetch member profile from member service
    2. Fetch partner rules from partner service
    3. Load recommendation catalog from SQLite
    4. Enforce partner rules
    5. Call Claude agent with context + MCP tools
    6. Return structured response
    """
    tools_called = []

    # Step 1 — member profile
    member = await fetch_member(member_id)
    tools_called.append("get_member_profile")

    # Step 2 — partner rules
    partner = await fetch_partner(member["partner_id"])
    tools_called.append("get_partner_rules")

    # Step 3 — full catalog
    all_recs = fetch_all_recommendations()

    # Step 4 — enforce rules
    rules = PartnerRules(
        partner_id=partner["partner_id"],
        name=partner["name"],
        rec_cap=partner["rec_cap"],
        excluded_categories=partner["excluded_categories"]
    )
    result: EnforcementResult = enforce_partner_rules(all_recs, rules)
    tools_called.append("get_recommendations")

    # Step 5 — build Claude context
    # (agent.py will handle the actual Claude call — imported below)
    from agent import run_agent
    ai_response = await run_agent(
        member=member,
        partner=partner,
        recommendations=result.recommendations,
        message=message
    )

    return RecommendResponse(
        member_id=member["member_id"],
        partner_id=partner["partner_id"],
        partner_name=partner["name"],
        ai_response=ai_response,
        recommendations=result.recommendations,
        enforcement_log=result.enforcement_log,
        tools_called=tools_called
    )

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "recommendation-api"}

@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    """
    Main endpoint. Accepts a member_id and optional message.
    Returns AI-generated recommendations with partner rules enforced.
    """
    return await run_recommendation_pipeline(req.member_id, req.message)

@app.get("/members/{member_id}/profile")
async def member_profile(member_id: str):
    """Convenience endpoint — returns raw member profile."""
    return await fetch_member(member_id)

@app.get("/partners/{partner_id}/rules")
async def partner_rules(partner_id: str):
    """Convenience endpoint — returns raw partner rules."""
    return await fetch_partner(partner_id)