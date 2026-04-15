import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from db.seed import get_connection

app = FastAPI(
    title="Mock Partner Data Service",
    description="Simulates arrivia's internal partner data API",
    version="1.0.0"
)

class PartnerConfig(BaseModel):
    partner_id: str
    name: str
    rec_cap: Optional[int]          # None = unlimited
    excluded_categories: List[str]  # e.g. ["cruise"]

@app.get("/health")
def health():
    return {"status": "ok", "service": "partner-config"}

@app.get("/partners/{partner_id}", response_model=PartnerConfig)
def get_partner(partner_id: str):
    """
    Returns Partner's configuration details.
    Args:
        partner_id (str): _description_
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        partner = cursor.execute(
            "SELECT * FROM partners WHERE partner_id = ?", (partner_id,)
        ).fetchone()

        if not partner:
            raise HTTPException(status_code=404, detail=f"Partner {partner_id} not found")

        return PartnerConfig(
            partner_id=partner["partner_id"],
            name=partner["name"],
            rec_cap=partner["rec_cap"],
            excluded_categories=json.loads(partner["excluded_cats"])
        )
    finally:
        conn.close()

@app.get("/partners", response_model=List[PartnerConfig])
def list_partners():
    """
    Returns list of all Partners.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        partners = cursor.execute("SELECT * FROM partners").fetchall()

        return [
            PartnerConfig(
                partner_id=p["partner_id"],
                name=p["name"],
                rec_cap=p["rec_cap"],
                excluded_categories=json.loads(p["excluded_cats"])
            )
            for p in partners
        ]
    finally:
        conn.close()
