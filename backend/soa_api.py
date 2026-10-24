"""PS-01 on the real C-DAC statements: ranked mule-risk candidates + per-holder drill-down.

GET /soa/ranked            ranked holders (from soa_score.py output), with plain-English reasons
GET /soa/holder/{id}       monthly in/out, top counterparties, channel mix, holders sharing counterparties

Data dir: $SOA_DIR (default ~/soa_out) - produced by soa_loader.py then soa_score.py.
The raw statements are never read here and never leave the user's machine / repo.
"""
import os

import pandas as pd
from fastapi import APIRouter, HTTPException

from soa_score import unify

router = APIRouter(tags=["soa"])
_CACHE = {}


def _dir() -> str:
    return os.path.expanduser(os.environ.get("SOA_DIR", "~/soa_out"))


def _load():
    d = _dir()
    paths = [os.path.join(d, n) for n in ("soa_ranked.csv", "soa_edges.csv", "soa_holder_flows.csv")]
    if not all(os.path.exists(p) for p in paths):
        return None
    key = (d, tuple(os.path.getmtime(p) for p in paths))
    if _CACHE.get("key") != key:
        ranked = pd.read_csv(paths[0])
        u = unify(pd.read_csv(paths[1]), pd.read_csv(paths[2]))
        _CACHE.update(key=key, ranked=ranked, u=u)
    return _CACHE


@router.get("/soa/ranked")
def soa_ranked():
    c = _load()
    if c is None:
        return {"available": False, "hint": "Run soa_loader.py then soa_score.py, and set SOA_DIR if not ~/soa_out.",
                "holders": []}
    r = c["ranked"].copy()
    r = r.astype(object).where(r.notna(), None)          # NaN -> null (valid JSON)
    return {"available": True, "method": "unsupervised behavioural percentile ranking (no labels in dataset)",
            "holders": r.to_dict("records")}


@router.get("/soa/holder/{holder_id}")
def soa_holder(holder_id: str):
    c = _load()
    if c is None:
        raise HTTPException(404, "SOA data not generated yet")
    u = c["u"]
    g = u[u.holder == holder_id]
    if g.empty:
        raise HTTPException(404, "Unknown holder")

    dated = g.dropna(subset=["ts"])
    monthly = []
    if len(dated) > 10:
        m = dated.assign(month=dated.ts.dt.strftime("%Y-%m")).pivot_table(
            index="month", columns="dir", values="amount", aggfunc="sum", fill_value=0)
        for col in ("IN", "OUT"):
            if col not in m:
                m[col] = 0.0
        monthly = [{"month": k, "in": round(float(v["IN"])), "out": round(float(v["OUT"]))} for k, v in m.iterrows()]

    cp = g.dropna(subset=["cp"])
    top = []
    if len(cp):
        t = (cp.assign(is_in=(cp.dir == "IN").astype(int))
               .groupby("cp").agg(volume=("amount", "sum"), txns=("amount", "size"), in_=("is_in", "sum"))
               .sort_values("volume", ascending=False).head(10))
        top = [{"counterparty": str(k), "volume": round(float(v.volume)), "txns": int(v.txns),
                "direction": "mostly in" if v.in_ * 2 > v.txns else "mostly out"} for k, v in t.iterrows()]

    # other holders that transact with the same counterparties
    shared = {}
    if len(cp):
        mine = set(cp.cp)
        o = u[(u.holder != holder_id) & u.cp.isin(mine)].groupby("holder").cp.nunique()
        shared = {k: int(v) for k, v in o.sort_values(ascending=False).head(5).items()}

    return {"holder": holder_id, "txns": int(len(g)),
            "total_in": round(float(g[g.dir == "IN"].amount.sum())),
            "total_out": round(float(g[g.dir == "OUT"].amount.sum())),
            "monthly": monthly, "top_counterparties": top,
            "channels": {k: int(v) for k, v in g.transfer_type.value_counts().items()},
            "shares_counterparties_with": shared,
            "timestamps_usable": bool(len(dated) > 10)}
