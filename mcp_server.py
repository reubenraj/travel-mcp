"""
mcp_server.py

Defines the three MCP tools that Claude can discover and invoke:
- get_member_profile    → fetches member data from the member service
- get_partner_rules     → fetches partner config from the partner service
- get_recommendations   → runs the full pipeline with rules enforcement

Run standalone:
python mcp_server.py
"""

import os
import json
import sqlite3
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from rules_engine import (
    enforce_partner_rules,
    Recommendation,
    PartnerRules,
)

load_dotenv()

MEMBER_SERVICE_URL  = os.getenv("MEMBER_SERVICE_URL",  "http://localhost:8001")
PARTNER_SERVICE_URL = os.getenv("PARTNER_SERVICE_URL", "http://localhost:8002")

mcp = FastMCP("arrivia-travel-recommendations")


# ── Tool 1: get_member_profile ─────────────────────────────────────────────────

@mcp.tool()
def get_member_profile(member_id: str) -> dict:
    """
    Fetches a member's profile and recent travel history.

    Use this tool first — always retrieve the member profile before
    making any recommendations. The profile contains the partner_id
    you will need to call get_partner_rules.

    Args:
        member_id: The member's unique identifier (e.g. MBR001)

    Returns:
        Member profile including name, loyalty_tier, partner_id,
        and last 5 travel bookings.
    """
    try:
        response = httpx.get(
            f"{MEMBER_SERVICE_URL}/members/{member_id}",
            timeout=10.0
        )
        if response.status_code == 404:
            return {"error": f"Member {member_id} not found"}
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        return {"error": "Member service unavailable — is it running on port 8001?"}
    except Exception as e:
        return {"error": f"Unexpected error fetching member: {str(e)}"}


# ── Tool 2: get_partner_rules ──────────────────────────────────────────────────

@mcp.tool()
def get_partner_rules(partner_id: str) -> dict:
    """
    Fetches the configuration rules for a specific partner.

    Call this after get_member_profile to understand what constraints
    apply to this session. Rules are read-only — you must respect them.

    Key rules to observe:
    - rec_cap: maximum number of recommendations allowed (null = unlimited)
    - excluded_categories: categories you must never recommend
        (e.g. ["cruise"] means never suggest cruise products)

    Args:
        partner_id: The partner's unique identifier (e.g. PARTNER_A)

    Returns:
        Partner config including name, rec_cap, and excluded_categories.
    """
    try:
        response = httpx.get(
            f"{PARTNER_SERVICE_URL}/partners/{partner_id}",
            timeout=10.0
        )
        if response.status_code == 404:
            return {"error": f"Partner {partner_id} not found"}
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        return {"error": "Partner service unavailable — is it running on port 8002?"}
    except Exception as e:
        return {"error": f"Unexpected error fetching partner rules: {str(e)}"}


# ── Tool 3: get_recommendations ────────────────────────────────────────────────

@mcp.tool()
def get_recommendations(member_id: str, partner_id: str) -> dict:
    """
    Fetches travel recommendations with partner rules fully enforced.

    This tool handles the complete pipeline:
    1. Loads the full recommendation catalog
    2. Applies category exclusions for this partner
    3. Applies the recommendation cap for this partner
    4. Returns only rule-compliant recommendations

    Always call get_member_profile and get_partner_rules first so you
    understand the member context before presenting recommendations.

    Args:
        member_id:  The member's unique identifier
        partner_id: The partner's unique identifier

    Returns:
        Filtered recommendations list plus an enforcement_log showing
        exactly which rules were applied and how many items were removed.
    """
    try:
        # Fetch partner rules from the partner service
        partner_resp = httpx.get(
            f"{PARTNER_SERVICE_URL}/partners/{partner_id}",
            timeout=10.0
        )
        if partner_resp.status_code == 404:
            return {"error": f"Partner {partner_id} not found"}
        partner_resp.raise_for_status()
        partner = partner_resp.json()

        # Load full recommendation catalog from SQLite
        db_path = os.path.join(os.path.dirname(__file__), "db", "travel.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM recommendations").fetchall()
        conn.close()

        all_recs = [
            Recommendation(
                rec_id=row["rec_id"],
                destination=row["destination"],
                category=row["category"],
                description=row["description"],
                base_price=row["base_price"]
            )
            for row in rows
        ]

        # Enforce partner rules
        rules = PartnerRules(
            partner_id=partner["partner_id"],
            name=partner["name"],
            rec_cap=partner["rec_cap"],
            excluded_categories=partner["excluded_categories"]
        )
        result = enforce_partner_rules(all_recs, rules)

        return {
            "partner_id": partner_id,
            "total_before_rules": result.total_before_rules,
            "excluded_by_category": result.excluded_by_category,
            "capped_at": result.capped_at,
            "enforcement_log": result.enforcement_log,
            "recommendations": [
                {
                    "rec_id": r.rec_id,
                    "destination": r.destination,
                    "category": r.category,
                    "description": r.description,
                    "base_price": r.base_price
                }
                for r in result.recommendations
            ]
        }

    except httpx.ConnectError:
        return {"error": "Partner service unavailable — is it running on port 8002?"}
    except Exception as e:
        return {"error": f"Unexpected error getting recommendations: {str(e)}"}


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting arrivia MCP server...")
    print(f"  Member service:  {MEMBER_SERVICE_URL}")
    print(f"  Partner service: {PARTNER_SERVICE_URL}")
    print("  Tools available:")
    print("    - get_member_profile")
    print("    - get_partner_rules")
    print("    - get_recommendations")
    mcp.run()