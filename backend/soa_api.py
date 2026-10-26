"""PS-01 on the real C-DAC statements: ranked mule-risk candidates + investigation workspace.

GET /soa/overview          KPIs, data-quality strip, linked holder pairs
GET /soa/ranked            ranked holders with per-signal point contributions and plain-English reasons
GET /soa/holder/{id}       monthly in/out, top counterparties, network graph, pass-through events, signal breakdown
GET /soa/report/{id}       printable HTML case report (Print -> Save as PDF)

Data dir: $SOA_DIR (default ~/soa_out) - produced by soa_loader.py then soa_score.py.
The raw statements are never read here and never leave the user's machine / repo.
"""
import html
import json
import os

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from soa_score import WEIGHTS, unify

router = APIRouter(tags=["soa"])
_CACHE = {}

LABELS = {"passthrough": "Pass-through", "fast_dwell": "Fast turnaround", "fan": "Counterparty spread",
          "burst": "Bursts", "round": "Round amounts", "shared": "Shared counterparties"}
FLAG_THRESHOLD = 60.0
PASS_WINDOW_HOURS = 6


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
        summary = {}
        sp = os.path.join(d, "soa_summary.json")
        if os.path.exists(sp):
            with open(sp) as fh:
                summary = json.load(fh)
        _CACHE.clear()
        _CACHE.update(key=key, ranked=ranked, u=u, summary=summary)
    return _CACHE


def _need():
    c = _load()
    if c is None:
        raise HTTPException(404, "SOA data not generated yet")
    return c


def _clean(v):
    """NaN/NaT -> None so the response is valid JSON."""
    return None if pd.isna(v) else v


def _linked_pairs(u):
    cp = u.dropna(subset=["cp"])[["holder", "cp"]].drop_duplicates()
    if cp.empty:
        return []
    n = cp.groupby("cp").holder.transform("nunique")
    sh = cp[n > 1]
    if sh.empty:
        return []
    p = sh.merge(sh, on="cp")
    p = p[p.holder_x < p.holder_y]
    cnt = p.groupby(["holder_x", "holder_y"]).cp.nunique().sort_values(ascending=False).head(5)
    return [{"a": a, "b": b, "shared": int(v)} for (a, b), v in cnt.items()]


def _contrib(row) -> list:
    out = []
    for k in WEIGHTS:
        if ("c_" + k) in row.index:
            v = row["c_" + k]
            out.append({"key": k, "label": LABELS[k], "points": None if pd.isna(v) else float(v), "weight": WEIGHTS[k][0],
                        "neutral_points": round(WEIGHTS[k][0] * 50, 1) if pd.isna(v) else 0.0})
    return out


@router.get("/soa/overview")
def soa_overview():
    c = _load()
    if c is None:
        return {"available": False, "hint": "Run soa_loader.py then soa_score.py, and set SOA_DIR if not ~/soa_out."}
    if "overview" not in c:
        u, r = c["u"], c["ranked"]
        layouts = {v.get("layout") for k, v in c["summary"].items() if isinstance(v, dict) and v.get("layout")}
        c["overview"] = {
            "available": True,
            "holders": int(len(r)),
            "flagged": int((r.risk_score >= FLAG_THRESHOLD).sum()),
            "flag_threshold": FLAG_THRESHOLD,
            "transactions": int(len(u)),
            "volume": round(float(u.amount.sum())),
            "counterparties": int(u.cp.nunique()),
            "timestamps_usable_pct": round(100 * float(u.ts.notna().mean()), 1),
            "behaviour_only_holders": int((r.graph_coverage != "yes").sum()),
            "layouts": len(layouts) or None,
            "source_files": len([k for k in c["summary"] if not str(k).startswith("_")]) or None,
            "linked_pairs": _linked_pairs(u),
        }
    return c["overview"]


@router.get("/soa/ranked")
def soa_ranked():
    c = _load()
    if c is None:
        return {"available": False, "hint": "Run soa_loader.py then soa_score.py, and set SOA_DIR if not ~/soa_out.",
                "holders": []}
    r = c["ranked"]
    out = []
    for _, row in r.iterrows():
        rec = {k: _clean(v) for k, v in row.items() if not str(k).startswith("c_")}
        rec["contributions"] = _contrib(row)
        out.append(rec)
    return {"available": True, "method": "unsupervised behavioural percentile ranking (no labels in dataset)",
            "holders": out}


def _holder_detail(c, holder_id: str) -> dict:
    u = c["u"]
    g = u[u.holder == holder_id]
    if g.empty:
        raise HTTPException(404, "Unknown holder")
    r = c["ranked"]
    rrow = r[r.holder == holder_id]
    rrow = rrow.iloc[0] if len(rrow) else None
    rank = int(r.index[r.holder == holder_id][0]) + 1 if rrow is not None else None

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
    shared, other_cps = {}, set()
    if len(cp):
        mine = set(cp.cp)
        others = u[(u.holder != holder_id) & u.cp.isin(mine)]
        other_cps = set(others.cp)
        o = others.groupby("holder").cp.nunique()
        shared = {k: int(v) for k, v in o.sort_values(ascending=False).head(5).items()}

    # money trail: credits followed within a few hours by a debit of about the same size
    pass_events, pass_share = [], None
    if len(dated) > 20:
        d = dated.sort_values("ts")
        cr = d[d.dir == "IN"][["ts", "amount"]].rename(columns={"ts": "in_ts", "amount": "in_amt"})
        dr = d[d.dir == "OUT"][["ts", "amount"]].rename(columns={"ts": "out_ts", "amount": "out_amt"})
        if len(cr) and len(dr):
            mm = pd.merge_asof(cr.sort_values("in_ts"), dr.sort_values("out_ts"), left_on="in_ts", right_on="out_ts",
                               direction="forward", tolerance=pd.Timedelta(hours=PASS_WINDOW_HOURS))
            mm = mm.dropna(subset=["out_ts"])
            mm = mm[(mm.out_amt >= 0.9 * mm.in_amt) & (mm.out_amt <= 1.1 * mm.in_amt)]
            pass_share = round(float(len(mm)) / len(cr), 3)
            mm = mm.assign(hours=(mm.out_ts - mm.in_ts).dt.total_seconds() / 3600)
            for _, e in mm.sort_values("in_amt", ascending=False).head(8).iterrows():
                pass_events.append({"in_ts": e.in_ts.strftime("%Y-%m-%d %H:%M"), "in_amt": round(float(e.in_amt)),
                                    "out_ts": e.out_ts.strftime("%Y-%m-%d %H:%M"), "out_amt": round(float(e.out_amt)),
                                    "hours": round(float(e.hours), 2)})

    # small network for the graph view: holder, its biggest counterparties, and linked holders
    tot = round(float(g.amount.sum()))
    nodes = [{"id": holder_id, "kind": "holder", "volume": tot}]
    edges = []
    for t_ in top[:10]:
        nodes.append({"id": t_["counterparty"], "kind": "counterparty", "volume": t_["volume"],
                      "shared": t_["counterparty"] in other_cps})
        edges.append({"source": holder_id if t_["direction"] == "mostly out" else t_["counterparty"],
                      "target": t_["counterparty"] if t_["direction"] == "mostly out" else holder_id,
                      "volume": t_["volume"]})
    for hid, n_ in list(shared.items())[:3]:
        nodes.append({"id": hid, "kind": "linked", "volume": None})
        edges.append({"source": holder_id, "target": hid, "shared": n_})

    tin = float(g[g.dir == "IN"].amount.sum())
    tout = float(g[g.dir == "OUT"].amount.sum())
    return {"holder": holder_id, "rank": rank, "risk_score": None if rrow is None else _clean(rrow.risk_score),
            "reasons": None if rrow is None else rrow.reasons,
            "contributions": [] if rrow is None else _contrib(rrow),
            "graph_coverage": None if rrow is None else rrow.graph_coverage,
            "txns": int(len(g)), "total_in": round(tin), "total_out": round(tout),
            "monthly": monthly, "top_counterparties": top,
            "channels": {k: int(v) for k, v in g.transfer_type.value_counts().items()},
            "shares_counterparties_with": shared,
            "pass_through": {"window_hours": PASS_WINDOW_HOURS, "share_of_credits": pass_share, "events": pass_events},
            "network": {"nodes": nodes, "edges": edges},
            "timestamps_usable": bool(len(dated) > 10)}


@router.get("/soa/holder/{holder_id}")
def soa_holder(holder_id: str):
    return _holder_detail(_need(), holder_id)


def _cr(n) -> str:
    return f"₹{n / 1e7:,.2f} Cr" if n >= 1e7 else f"₹{n:,.0f}"


@router.get("/soa/report/{holder_id}", response_class=HTMLResponse)
def soa_report(holder_id: str):
    d = _holder_detail(_need(), holder_id)
    e = html.escape
    rows = lambda items, cols: "".join("<tr>" + "".join(f"<td>{e(str(x))}</td>" for x in r) + "</tr>" for r in items)
    contrib = rows([(c["label"], f"n/a (neutral +{c['neutral_points']})" if c["points"] is None else f"{c['points']:.1f}", f"{int(c['weight'] * 100)}%")
                    for c in d["contributions"]], 3)
    cps = rows([(t["counterparty"], _cr(t["volume"]), t["txns"], t["direction"]) for t in d["top_counterparties"]], 4)
    pas = rows([(p["in_ts"], _cr(p["in_amt"]), p["out_ts"], _cr(p["out_amt"]), f"{p['hours']} h")
                for p in d["pass_through"]["events"]], 5)
    linked = "".join(f"<li>{e(k)}: {v:,} shared counterparties</li>" for k, v in d["shares_counterparties_with"].items())
    share = d["pass_through"]["share_of_credits"]
    caveats = []
    if not d["timestamps_usable"]:
        caveats.append("Timestamps in this statement are not usable, so time-based signals were skipped.")
    if d["graph_coverage"] and d["graph_coverage"] != "yes":
        caveats.append("This statement has no counterparty column; only behaviour signals were scored.")
    caveats += ["Score is a relative percentile rank among the statement holders provided, not a probability.",
                "The dataset contains no labels or complaints; this report is an investigative lead, not a finding."]
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Case report {e(holder_id)}</title>
<style>
body{{font-family:'IBM Plex Sans',Arial,sans-serif;color:#1b2236;max-width:860px;margin:32px auto;padding:0 24px;line-height:1.5}}
h1{{font-size:26px;margin:0}} h2{{font-size:16px;text-transform:uppercase;letter-spacing:1px;color:#7a5f17;border-bottom:1px solid #ddd;padding-bottom:4px;margin-top:28px}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #eee}} th{{color:#555}}
.score{{font-size:44px;font-weight:700}} .meta{{color:#666;font-size:13px}} .box{{background:#f6f4ee;border-radius:8px;padding:12px 16px}}
@media print{{body{{margin:0}} .noprint{{display:none}}}}
</style></head><body>
<p class="noprint meta">Use your browser's Print &rarr; Save as PDF.</p>
<h1>Case report: {e(holder_id)}</h1>
<p class="meta">TraceNetX &middot; PS-01 &middot; Rank #{d['rank']} of {len(_need()['ranked'])} statement holders &middot; holder identity is hashed</p>
<div class="box"><span class="score">{d['risk_score']}</span> / 100 relative risk<br>{e(str(d['reasons']))}</div>
<h2>Activity</h2>
<table><tr><th>Transactions</th><th>Money in</th><th>Money out</th><th>Credits passed on within {d['pass_through']['window_hours']} h</th></tr>
<tr><td>{d['txns']:,}</td><td>{_cr(d['total_in'])}</td><td>{_cr(d['total_out'])}</td><td>{'n/a' if share is None else f'{share:.0%}'}</td></tr></table>
<h2>Why this score</h2><table><tr><th>Signal</th><th>Points</th><th>Weight</th></tr>{contrib}</table>
<h2>Top counterparties</h2><table><tr><th>Account</th><th>Volume</th><th>Txns</th><th>Direction</th></tr>{cps or '<tr><td colspan=4>No counterparty column in this statement.</td></tr>'}</table>
<h2>Fastest pass-through events</h2><table><tr><th>Credit time</th><th>Credit</th><th>Debit time</th><th>Debit</th><th>Gap</th></tr>{pas or '<tr><td colspan=5>None found, or timestamps unusable.</td></tr>'}</table>
{'<h2>Linked holders</h2><ul>' + linked + '</ul>' if linked else ''}
<h2>Read this first</h2><ul>{''.join(f'<li>{e(c)}</li>' for c in caveats)}</ul>
</body></html>"""
    return HTMLResponse(page)
