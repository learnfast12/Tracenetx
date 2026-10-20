# TraceNetX — Mule-Account Detection & Money-Trail Investigation

**Team OMEGA 404 · Sri Sairam Engineering College, Chennai**
Built for *Intelligent Mule Account Detection and Financial Fraud Investigation Platform* (PS-01).

TraceNetX turns raw transactions and cybercrime complaints into **ranked, explainable investigative leads** —
from the first-hop mule an NCRP complaint names, to the collector no victim ever paid.

| PS-01 requirement | What TraceNetX does | Where |
|---|---|---|
| Transaction analysis | Velocity, structuring-under-cap, pass-through latency, robust deviation from each account's own baseline | `features.py`, `baseline.py` |
| Mule detection + explainability | XGBoost + LightGBM + RandomForest ensemble, per-account SHAP reasons, 5-level graduated response | `ml_pipeline.py` |
| Money-trail analysis | Time-ordered, amount-proportional victim-money tracing; heaviest chain to any account | `trail.py` |
| Complaint correlation | Complaints ↔ accounts ↔ incident clusters (shared phone / convergence), funds-consistency check | `complaints.py` |
| Graph investigation | Neo4j Spider Map, structural roles (dealer, hawala, shell, recruiter) — never read from account names | `graph*.py`, `roles.py` |
| Investigation dashboard | Prioritised leads (ML + complaints + baseline, every sub-score shown), per-account timeline, printable incident report, evidence package | `investigation.py`, `timeline.py`, `report.py` |

## Run it

```bash
# 1. graph database (optional — the app degrades gracefully without it)
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:latest   # first time
docker start neo4j                                                                                  # afterwards (wait ~20 s)

# 2. backend
cd backend && pip install -r requirements.txt
uvicorn main:app --port 8001          # health: http://localhost:8001/health

# 3. frontend
cd frontend/tracenetx-ui && npm install
REACT_APP_API_URL=http://localhost:8001 npm start      # http://localhost:3002
```

Without Neo4j, ML scoring, complaint correlation, timelines, priority leads and incident reports all work;
only the graph-database views return a clear *503 — start Neo4j* message.

Tests: `cd backend && pip install pytest && python3 -m pytest -q`

## Evidence (read the disclosure)

`python3 backend/benchmark.py` reproduces this. Train and test networks are **different** simulated worlds
(different accounts and rings). The baseline is the three classic threshold rules with thresholds **tuned on the
training networks**. The world includes hard negatives (small traders, crowdfunds, payment aggregators, shared-NAT devices,
affluent customers), stealth mules, structuring under the reporting cap, and 4% of mules never discovered (label noise).

| Setting | Detector | AUROC | Mules found in top-k | Accounts reviewed for 80% recall |
|---|---|---|---|---|
| Evasive criminals | Threshold rules (tuned) | 0.61 | 11% | ~930 |
| Evasive criminals | **TraceNetX** | **0.998** | **95%** | **~88** |
| Stress (all mules stealthy) | Threshold rules (tuned) | 0.59 | 9% | ~890 |
| Stress (all mules stealthy) | **TraceNetX** | **0.999** | **96%** | **~91** |

**Honest caveats**
- The world is synthetic and written by us (`simulator.py`). The numbers show coverage of the typologies we
  encoded, **not** accuracy on real bank data. Real-data validation with a partner bank is the next step.
- Behavioural features do most of the detection work. Complaint-derived signals add little to AUROC; their value is in
  *prioritisation, reaching collectors, and evidence* — not in a better classifier.
- Complaints are not a model input; they are scored separately so nothing is counted twice.
- Tracing estimates how much victim money *could* have reached an account. It is an investigative lead, not proof.

## Layout
```
backend/   FastAPI app (main.py), ML, tracing, complaints, timeline, reports, benchmark, tests/
frontend/  React UI (tracenetx-ui): Spider Map, Investigation, Timeline, Dashboard, Evidence
docs/      research paper and architecture PDF
```
Key endpoints: `/investigation/priority`, `/timeline/{account}`, `/complaints/trail/{account}`,
`/report/incident/{id}`, `/evidence/{account}`, `/ml/model-info`, `/benchmark`, `/health`.
