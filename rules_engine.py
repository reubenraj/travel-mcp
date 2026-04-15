from typing import List, Optional
from pydantic import BaseModel

class Recommendation(BaseModel):
    rec_id: int
    destination: str
    category: str        # flight / hotel / cruise / car
    description: str
    base_price: int

class PartnerRules(BaseModel):
    partner_id: str
    name: str
    rec_cap: Optional[int]           # None = unlimited
    excluded_categories: List[str]  

class EnforcementResult(BaseModel):
    recommendations: List[Recommendation]
    total_before_rules: int
    excluded_by_category: int
    capped_at: Optional[int]
    enforcement_log: List[str]       # human-readable audit trail

def enforce_partner_rules(
    recommendations: List[Recommendation],
    rules: PartnerRules
) -> EnforcementResult:
    """
    Applies partner rules to a recommendation list.
    Returns the filtered list plus a full audit log of what was enforced.

    This function never raises — it always returns a result even if
    all recommendations are filtered out.
    """
    log: List[str] = []
    total_before = len(recommendations)

    log.append(
        f"Starting enforcement for partner {rules.partner_id} "
        f"({rules.name}) — {total_before} candidate recommendations."
    )

    # ── Rule 1: Category exclusion ─────────────────────────────────────────────
    if rules.excluded_categories:
        before_exclusion = len(recommendations)
        recommendations = [
            r for r in recommendations
            if r.category not in rules.excluded_categories
        ]
        removed = before_exclusion - len(recommendations)

        log.append(
            f"Category exclusion: removed {removed} recommendation(s) "
            f"in excluded categories {rules.excluded_categories}. "
            f"{len(recommendations)} remaining."
        )
    else:
        log.append("Category exclusion: no categories excluded for this partner.")

    excluded_by_category = total_before - len(recommendations)

    # ── Rule 2: Recommendation cap ─────────────────────────────────────────────
    capped_at: Optional[int] = None

    if rules.rec_cap is not None and len(recommendations) > rules.rec_cap:
        before_cap = len(recommendations)
        recommendations = recommendations[: rules.rec_cap]
        capped_at = rules.rec_cap
        log.append(
            f"Recommendation cap: truncated from {before_cap} "
            f"to {rules.rec_cap} (partner cap enforced)."
        )
    else:
        if rules.rec_cap is None:
            log.append("Recommendation cap: unlimited — no cap applied.")
        else:
            log.append(
                f"Recommendation cap: {len(recommendations)} result(s) "
                f"within cap of {rules.rec_cap} — no truncation needed."
            )

    log.append(
        f"Enforcement complete. Returning {len(recommendations)} "
        f"recommendation(s) to caller."
    )

    return EnforcementResult(
        recommendations=recommendations,
        total_before_rules=total_before,
        excluded_by_category=excluded_by_category,
        capped_at=capped_at,
        enforcement_log=log
    )