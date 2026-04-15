import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from db.seed import get_connection

app = FastAPI(
    title="Mock Member Data Service",
    description="Simulates Arrivia's internal member data API",
    version="1.0.0"
)

class TravelHistoryItem(BaseModel):
    destination: str
    booking_type: str
    travel_date: str

class MemberProfile(BaseModel):
    member_id: str
    name: str
    loyalty_tier: str
    partner_id: str
    partner_name: str = None
    travel_history: List[TravelHistoryItem]
    
@app.get("/health")
def health():
    return {"status": "ok", "service": "member-data"}

@app.get("/members/{member_id}", response_model=MemberProfile)
def get_member(member_id: str):
    """
    Returns Member's profile along with last 5 bookings.
    Args:
        member_id (str): _description_
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        member = cursor.execute(
            "SELECT m.*, p.name AS partner_name FROM members m JOIN partners p ON m.partner_id = p.partner_id WHERE member_id = ?", (member_id,)
        ).fetchone()

        if not member:
            raise HTTPException(status_code=404, detail=f"Member {member_id} not found")

        history = cursor.execute(
            """SELECT destination, booking_type, travel_date
            FROM travel_history
            WHERE member_id = ?
            ORDER BY travel_date DESC
            LIMIT 5""",
            (member_id,)
        ).fetchall()

        return MemberProfile(
            member_id=member["member_id"],
            name=member["name"],
            loyalty_tier=member["loyalty_tier"],
            partner_id=member["partner_id"],
            partner_name=member["partner_name"],
            travel_history=[
                TravelHistoryItem(
                    destination=row["destination"],
                    booking_type=row["booking_type"],
                    travel_date=row["travel_date"]
                )
                for row in history
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

@app.get("/members", response_model=List[MemberProfile])
def list_members():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        members = cursor.execute(
            "SELECT m.*, p.name AS partner_name FROM members m "
            "JOIN partners p ON m.partner_id = p.partner_id"
        ).fetchall()
        result = []
        for member in members:
            history = cursor.execute(
                """SELECT destination, booking_type, travel_date
                FROM travel_history
                WHERE member_id = ?
                ORDER BY travel_date DESC
                LIMIT 5""",
                (member["member_id"],)
            ).fetchall()
            result.append(MemberProfile(
                member_id=member["member_id"],
                name=member["name"],
                loyalty_tier=member["loyalty_tier"],
                partner_id=member["partner_id"],
                partner_name=member["partner_name"],
                travel_history=[
                    TravelHistoryItem(
                        destination=row["destination"],
                        booking_type=row["booking_type"],
                        travel_date=row["travel_date"]
                    )
                    for row in history
                ]
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()