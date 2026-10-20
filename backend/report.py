"""Printable incident report (PS-01: "evidence-based reports").

GET /report/incident/{cluster_id}   print-ready HTML (use the browser's Print -> Save as PDF)
GET /report/incidents               list of available incident ids

Pure pandas, so it works with or without Neo4j. Everything user-controlled is HTML-escaped.
The report states what the indicators are and are not: leads for investigation, not proof of guilt.
"""
from datetime import datetime
from html import escape

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from complaints import complaint_engine
from dataset_manager import dataset_manager
from ml_pipeline import ml_pipeline
from investigation import priority as _priority
from trail import heaviest_chain

router = APIRouter(tags=["report"])

ACTIONS = {
    "CRITICAL": "Request immediate account freeze / debit hold from the holding bank, file STR with FIU-IND, "
                "preserve logs, and refer the network to the investigating agency.",
    "HIGH": "Request enhanced monitoring and a transaction-statement pull; interview account holder; "
            "consider a temporary hold pending verification.",
    "MEDIUM": "Place on watch list; request KYC refresh and device/IP records.",
    "LOW": "Periodic review only.",
}
CSS = """
body{font:14px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#111;max-width:900px;margin:24px auto;padding:0 20px}
h1{font-size:22px;margin:0 0 2px} h2{font-size:15px;margin:26px 0 8px;border-bottom:2px solid #111;padding-bottom:3px;text-transform:uppercase;letter-spacing:.5px}
.sub{color:#555;font-size:12px} table{border-collapse:collapse;width:100%;font-size:12.5px} th,td{border:1px solid #bbb;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f0f0f0} .kpi{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.kpi div{border:1px solid #bbb;padding:8px 14px;border-radius:4px}
.kpi b{display:block;font-size:18px} .crit{color:#b00020;font-weight:700}.high{color:#c75000;font-weight:700}
.note{background:#fff8e1;border:1px solid #e6c200;padding:10px 12px;font-size:12px;margin-top:22px}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace} @media print{body{margin:0}.noprint{display:none}}
"""


def _inr(n) -> str:
    return f"₹{float(n or 0):,.0f}"


def _find_cluster(cid: str):
    res = complaint_engine.correlate()
    cl = next((c for c in res["clusters"] if c["cluster_id"] == cid), None)
    if not cl:
        raise HTTPException(status_code=404, detail=f"Unknown incident {cid}")
    return res, cl


@router.get("/report/incidents")
def incidents():
    res = complaint_engine.correlate()
    return {"incidents": [{"cluster_id": c["cluster_id"], "accounts": len(c["accounts"]), "complaints": c["complaints"],
                           "total_loss": c["total_loss"]} for c in res["clusters"]]}


@router.get("/report/incident/{cluster_id}", response_class=HTMLResponse)
def incident_report(cluster_id: str):
    res, cl = _find_cluster(cluster_id)
    df = pd.read_csv(dataset_manager.get_active_path())
    ml = {r["account_id"]: r for r in ml_pipeline.predict(df)}
    lead = {l["account_id"]: l for l in _priority(top=100000)["leads"]}      # ML + complaints + baseline blend
    comp = complaint_engine.load()
    cdf = comp[comp["reported_account"].isin(cl["accounts"])].sort_values("ts")
    trail = getattr(complaint_engine, "_last_trail", None) or {"accounts": {}, "pred": {}}

    collector = (cl.get("likely_collector") or {}).get("account")
    rows = []
    for a in cl["accounts"]:
        d = (res["accounts"].get(a) or {}).get("direct") or {}
        m = ml.get(a, {})
        ld = lead.get(a, {})
        lvl = ld.get("priority_tier", "n/a")
        rows.append(f"<tr><td class='mono'>{escape(a)}</td><td>{d.get('complaints', 0)}</td><td>{d.get('distinct_victims', 0)}</td>"
                    f"<td>{_inr(d.get('total_loss'))}</td><td>{escape(str(m.get('role') or '—'))}</td>"
                    f"<td class='{'crit' if lvl == 'CRITICAL' else 'high' if lvl == 'HIGH' else ''}'>{escape(str(lvl))} "
                    f"({ld.get('priority_score', '—')})</td><td>{m.get('risk_score', '—')}</td></tr>")

    chain_html = "<p>No time-ordered chain could be reconstructed.</p>"
    if collector:
        ch = heaviest_chain(trail, collector)
        info = trail["accounts"].get(collector, {})
        if ch:
            steps = "".join(f"<tr><td>{escape(h['timestamp'][:16])}</td><td class='mono'>{escape(h['from'])}</td>"
                            f"<td class='mono'>{escape(h['to'])}</td><td>{_inr(h['amount'])}</td>"
                            f"<td>{_inr(h['tainted_amount'])}</td></tr>" for h in ch)
            chain_html = (f"<p>Collector <b class='mono'>{escape(collector)}</b> received an estimated "
                          f"<b>{_inr(info.get('tainted_amount'))}</b> traceable to {info.get('complaints_reaching', '?')} complaints "
                          f"(proportional tracing, transfers respected in time order). Heaviest single chain:</p>"
                          f"<table><tr><th>Time</th><th>From</th><th>To</th><th>Transfer</th><th>Traceable victim money</th></tr>{steps}</table>")

    events = "".join(f"<tr><td>{escape(str(r.timestamp)[:16])}</td><td class='mono'>{escape(str(r.complaint_id))}</td>"
                     f"<td class='mono'>{escape(str(r.reported_account))}</td><td>{_inr(r.amount_lost)}</td>"
                     f"<td>{escape(str(r.fraud_type))}</td><td>{escape(str(r.city))}</td></tr>" for r in cdf.itertuples())

    tiers = [lead.get(a, {}).get("priority_tier") for a in cl["accounts"]] + ([lead.get(collector, {}).get("priority_tier")] if collector else [])
    top = next((t for t in ("CRITICAL", "HIGH", "MEDIUM", "LOW") if t in tiers), "LOW")
    phones = ", ".join(escape(p) for p in cl.get("shared_phones", [])) or "none"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Incident {escape(cluster_id)} · TraceNetX</title>
<style>{CSS}</style></head><body>
<button class="noprint" onclick="window.print()" style="float:right;padding:6px 14px">Print / Save as PDF</button>
<h1>Incident Report {escape(cluster_id)}</h1>
<div class="sub">TraceNetX · Team OMEGA 404 · generated {now} · dataset: {escape(dataset_manager.get_active_id())} · complaints: {escape(complaint_engine.name)}</div>
<div class="kpi"><div>Complaints<b>{cl['complaints']}</b></div><div>Distinct victims<b>{cl['distinct_victims']}</b></div>
<div>Reported loss<b>{_inr(cl['total_loss'])}</b></div><div>Accounts involved<b>{len(cl['accounts'])}</b></div>
<div>Highest tier<b class="{'crit' if top == 'CRITICAL' else 'high' if top == 'HIGH' else ''}">{escape(top)}</b></div></div>
<p>Fraud types: {escape(', '.join(cl['fraud_types']))}. Shared scammer phones: {phones}.
Complaint window: {escape(str(cl['first_complaint'])[:16])} to {escape(str(cl['last_complaint'])[:16])}.</p>
<h2>Accounts named in complaints</h2><p class="sub">Priority = 45% ML risk + 30% complaint correlation + 25% baseline deviation.</p>
<table><tr><th>Account</th><th>Complaints</th><th>Victims</th><th>Loss</th><th>Structural role</th><th>Priority tier (score)</th><th>ML score</th></tr>{''.join(rows)}</table>
<h2>Money trail to the likely collector</h2>{chain_html}
<h2>Complaint timeline</h2>
<table><tr><th>Time</th><th>Complaint</th><th>Account reported</th><th>Amount</th><th>Type</th><th>City</th></tr>{events}</table>
<h2>Recommended actions ({escape(top)})</h2><p>{escape(ACTIONS.get(top, ACTIONS['LOW']))}</p>
<div class="note"><b>Read this before acting.</b> Scores and trails are investigative indicators computed from transaction and complaint data,
not proof of wrongdoing. Proportional tracing estimates how much victim money <i>could</i> have reached an account; it does not identify
intent. Any action should follow bank procedure and legal process. If this report was generated on the demo dataset, all data is synthetic.</div>
</body></html>"""
    return HTMLResponse(html)
