"""Investigation layer: baseline deviation + prioritised investigative leads.

GET /baseline/deviation            per-account deviation-from-normal scores
GET /investigation/priority        ranked leads = ML risk + complaint correlation + baseline deviation
"""
import pandas as pd
from fastapi import APIRouter

from baseline import baseline_deviation
from complaints import complaint_engine
from dataset_manager import dataset_manager
from ml_pipeline import ml_pipeline
from roles import assign_roles

router = APIRouter(tags=["investigation"])

# Fixed, disclosed weights. Every lead shows its three sub-scores so nothing is a black box.
WEIGHTS = {"ml": 0.45, "complaints": 0.30, "baseline": 0.25}


def _tier(s: float) -> str:
    return "CRITICAL" if s >= 70 else "HIGH" if s >= 50 else "MEDIUM" if s >= 30 else "LOW"


@router.get("/baseline/deviation")
def deviation(min_score: float = 0):
    df = pd.read_csv(dataset_manager.get_active_path())
    res = baseline_deviation(df)
    rows = [{"account_id": a, **v} for a, v in res.items() if v["baseline_score"] >= min_score]
    rows.sort(key=lambda r: -r["baseline_score"])
    return {"accounts": len(rows), "results": rows}


@router.get("/investigation/priority")
def priority(top: int = 15):
    df = pd.read_csv(dataset_manager.get_active_path())
    ml = {r["account_id"]: r for r in ml_pipeline.predict(df)}
    comp = complaint_engine.correlate()
    base = baseline_deviation(df)
    roles = assign_roles(df)

    leads = []
    for acc in set(ml) | set(comp["accounts"]) | set(base):
        s_ml = float(ml.get(acc, {}).get("risk_score", 0))
        c = comp["accounts"].get(acc)
        s_c = float(c["complaint_score"]) if c else 0.0
        b = base.get(acc)
        s_b = float(b["baseline_score"]) if b else 0.0
        score = WEIGHTS["ml"] * s_ml + WEIGHTS["complaints"] * s_c + WEIGHTS["baseline"] * s_b

        reasons = []
        if s_ml >= 50:
            reasons.append(f"ML ensemble risk {s_ml:.0f}/100")
        if c and c.get("direct"):
            d = c["direct"]
            reasons.append(f"{d['distinct_victims']} victim(s), {d['total_loss']:,.0f} reported lost directly to this account")
        if c and c.get("exposure") and c["exposure"]["feeder_accounts"] >= 2:
            e = c["exposure"]
            reasons.append(f"Money from {e['feeder_accounts']} complained-about accounts "
                           f"({e['victims_reaching']} victims) converges here")
        if b:
            reasons += b["flags"][:2]
        if roles.get(acc, "MULE") != "MULE":
            reasons.append(f"Structural role: {roles[acc]}")
        if not reasons:
            continue

        leads.append({
            "account_id": acc,
            "priority_score": round(score, 1),
            "priority_tier": _tier(score),
            "role": roles.get(acc, "MULE"),
            "sub_scores": {"ml": round(s_ml, 1), "complaints": round(s_c, 1), "baseline": round(s_b, 1)},
            "reasons": reasons,
            "complaint_ids": ((c or {}).get("direct") or {}).get("complaint_ids", []),
        })

    leads.sort(key=lambda x: -x["priority_score"])
    return {
        "weights": WEIGHTS,
        "note": "Priority = weighted blend of ML risk, complaint correlation and baseline deviation; sub-scores shown per lead.",
        "leads": leads[:top],
        "complaint_stats": comp["stats"],
        "incident_clusters": comp["clusters"],
        "unmatched_complaint_accounts": comp["unmatched_accounts"],
    }
