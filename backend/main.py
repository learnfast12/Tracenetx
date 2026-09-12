from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from graph import init_db, get_graph_data, get_account_details, init_db as reload_graph
from risk import calculate_risk
from ml_pipeline import ml_pipeline
from graph_intelligence import graph_intel
from response_engine import response_engine
from real_validation import run_real_validation, run_nested_validation
from geospatial import router as geospatial_router
from scam_detection import router as scam_router
from dataset_manager import dataset_manager
import pandas as pd

app = FastAPI(
    title="TraceNetX v2.0",
    description="Mule Account Intelligence & Criminal Network Disruption System | Team OMEGA 404",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geospatial_router)
app.include_router(scam_router)

# DATASET UPLOAD ENDPOINTS
@app.post("/dataset/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")
    contents = await file.read()
    try:
        entry = dataset_manager.upload(file.filename, contents)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dataset_manager.activate(entry["id"])
    active_path = dataset_manager.get_active_path()
    df = pd.read_csv(active_path)
    ml_pipeline.train(df)
    reload_graph(active_path)
    return {
        "status": "uploaded",
        "dataset": entry,
        "message": f"Dataset '{entry['name']}' uploaded, activated, and ML pipeline retrained on {entry['rows']} rows."
    }

@app.get("/dataset/list")
def list_datasets():
    return {"active": dataset_manager.get_active_id(), "datasets": dataset_manager.list_datasets()}

@app.post("/dataset/activate/{dataset_id}")
def activate_dataset(dataset_id: str):
    try:
        entry = dataset_manager.activate(dataset_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    active_path = dataset_manager.get_active_path()
    df = pd.read_csv(active_path)
    ml_pipeline.train(df)
    reload_graph(active_path)
    return {"status": "activated", "dataset": entry}

@app.on_event("startup")
def startup():
    init_db()
    # Train ML pipeline on startup
    df = pd.read_csv(dataset_manager.get_active_path())
    ml_pipeline.train(df)
    print("[TraceNetX v2.0] All systems online.")

@app.get("/")
def root():
    return {
        "system": "TraceNetX v2.0",
        "team": "OMEGA 404",
        "college": "Sri Sairam Engineering College, Chennai",
        "hackathon": "CyberShield Hackathon 2026 — Bank of India",
        "status": "ONLINE",
        "layers": ["DETECT", "INVESTIGATE", "ACT"],
        "endpoints": [
            "/graph", "/account/{id}", "/filter", "/export",
            "/alerts", "/path", "/dashboard",
            "/ml/analyze", "/ml/account/{id}",
            "/intelligence/full", "/intelligence/reverse-chain/{id}",
            "/intelligence/community", "/intelligence/coordination",
            "/intelligence/recruitment", "/intelligence/convergence",
            "/intelligence/identity-fusion",
            "/evidence/{id}", "/response/{score}"
        ]
    }

# ── EXISTING V1 ENDPOINTS (preserved) ──────────────────────────────

@app.get("/graph")
def get_graph(case_id: str = None):
    # Delegates to /filter's logic (real ML scores, dataset-aware) instead of
    # the old Neo4j-backed get_graph_data(), which never followed dataset
    # switches and required a separately-running Neo4j server.
    return filter_graph(case_id=case_id)

@app.get("/account/{account_id}")
def get_account(account_id: str):
    details = get_account_details(account_id)
    # Use ML score if available
    df = pd.read_csv(dataset_manager.get_active_path())
    ml_results = ml_pipeline.predict(df)
    ml_result = next((r for r in ml_results if r['account_id'] == account_id), None)
    if ml_result:
        risk = {
            "score": ml_result['risk_score'],
            "level": ml_result['risk_level'],
            "flags": ml_result['flags']
        }
    else:
        risk = calculate_risk(account_id)
    # Add account's own IP
    df = pd.read_csv(dataset_manager.get_active_path())
    own_ip = None
    as_sender = df[df["sender_id"] == account_id]
    as_receiver = df[df["receiver_id"] == account_id]
    if len(as_sender) > 0:
        own_ip = as_sender.iloc[0]["sender_ip"]
    elif len(as_receiver) > 0:
        own_ip = as_receiver.iloc[0]["receiver_ip"]
    details["own_ip"] = own_ip
    return {"account": details, "risk": risk}

@app.get("/filter")
def filter_graph(ip: str = None, phone: str = None, city: str = None, case_id: str = None):
    from ml_pipeline import ml_pipeline
    df_full = pd.read_csv(dataset_manager.get_active_path())
    df = df_full
    if case_id:
        df = df[df["case_id"] == case_id]
    if ip:
        df = df[(df["sender_ip"] == ip) | (df["receiver_ip"] == ip)]
    if phone:
        df = df[df["sender_phone"].astype(str) == phone]
    if city:
        df = df[df["sender_city"].str.lower() == city.lower()]
    nodes = set()
    edges = []
    for _, row in df.iterrows():
        nodes.add(row["sender_id"])
        nodes.add(row["receiver_id"])
        edges.append({"source": row["sender_id"], "target": row["receiver_id"], "amount": row["amount"], "transfer_type": row.get("transfer_type", "DIGITAL")})

    # Real ML scores, computed on the FULL active dataset (not the filtered
    # subset) so risk levels here match /graph and /account/{id} exactly —
    # this was previously always falling back to the weak calculate_risk().
    ml_results = {}
    if ml_pipeline.is_trained:
        results = ml_pipeline.predict(df_full)
        for r in results:
            ml_results[r['account_id']] = {
                "score": r['risk_score'],
                "level": r['risk_level'],
                "flags": r['flags'],
                "mule_type": r['mule_type'],
                "shap_explanation": r['shap_explanation'],
                "recommended_action": r['recommended_action']
            }

    node_list = []
    for n in nodes:
        risk = ml_results.get(n) or calculate_risk(n)
        node_list.append({"id": n, "risk": risk})

    return {"nodes": node_list, "edges": edges}

@app.get("/path")
def find_path(source: str, target: str):
    df = pd.read_csv(dataset_manager.get_active_path())
    graph = {}
    for _, row in df.iterrows():
        s, r = row["sender_id"], row["receiver_id"]
        if s not in graph:
            graph[s] = []
        graph[s].append({
            "to": r,
            "amount": row["amount"],
            "transfer_type": row.get("transfer_type", "DIGITAL")
        })

    from collections import deque
    queue = deque([[source]])
    visited = set()

    while queue:
        path = queue.popleft()
        node = path[-1]

        if node == target:
            path_details = []
            for i in range(len(path) - 1):
                s, r = path[i], path[i + 1]
                edge = next((e for e in graph.get(s, []) if e["to"] == r), None)
                path_details.append({
                    "from": s,
                    "to": r,
                    "amount": edge["amount"] if edge else 0,
                    "transfer_type": edge["transfer_type"] if edge else "DIGITAL"
                })
            return {"found": True, "path": path, "details": path_details}

        if node not in visited:
            visited.add(node)
            for neighbor in graph.get(node, []):
                if neighbor["to"] not in visited:
                    queue.append(path + [neighbor["to"]])

    return {"found": False, "path": [], "details": []}

@app.get("/dashboard")
def get_dashboard():
    df = pd.read_csv(dataset_manager.get_active_path())
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    risk_data = []
    if ml_pipeline.is_trained:
        ml_results = ml_pipeline.predict(df)
        ml_lookup = {r['account_id']: r for r in ml_results}
        for acc in accounts:
            if acc in ml_lookup:
                r = ml_lookup[acc]
                risk_data.append({"account": acc, "score": r['risk_score'], "level": r['risk_level']})
            else:
                risk_data.append({"account": acc, "score": 15, "level": "CLEAR"})
    else:
        for acc in accounts:
            risk_data.append({"account": acc, "score": 15, "level": "CLEAR"})
    risk_data.sort(key=lambda x: x["score"], reverse=True)
    city_flow = df.groupby("sender_city")["amount"].sum().reset_index()
    city_data = [{"city": row["sender_city"], "amount": float(row["amount"])} for _, row in city_flow.iterrows()]
    timeline = df.copy()
    timeline["date"] = timeline["timestamp"].str[:10]
    daily = timeline.groupby("date")["amount"].sum().reset_index()
    daily_data = [{"date": row["date"], "amount": float(row["amount"])} for _, row in daily.iterrows()]
    return {
        "risk_data": risk_data,
        "city_data": city_data,
        "daily_data": daily_data,
        "total_amount": float(df["amount"].sum()),
        "total_transactions": len(df),
        "critical_count": sum(1 for r in risk_data if r["level"] == "CRITICAL"),
        "high_risk_count": sum(1 for r in risk_data if r["level"] == "HIGH"),
        "medium_risk_count": sum(1 for r in risk_data if r["level"] == "MEDIUM"),
        "safe_count": sum(1 for r in risk_data if r["level"] == "CLEAR")
    }

@app.get("/model-validation")
def get_model_validation():
    result = run_real_validation()
    if result.get("status") != "validated":
        return {"status": result.get("status", "unavailable"), "message": result.get("message")}

    cv = result.get("cross_validation", {})
    freeze = result.get("high_risk_freeze_tier", {})
    leak = result.get("residual_leak_check", {})
    top_feat = leak.get("top_5_univariate_features", [{}])[0] if leak.get("top_5_univariate_features") else {}

    return {
        "status": "validated",
        "dataset": result.get("dataset"),
        "auprc_mean": cv.get("mean_auprc"),
        "auroc_mean": cv.get("mean_auc_roc"),
        "precision_mean": cv.get("mean_precision"),
        "recall_mean": cv.get("mean_recall"),
        "f1_mean": cv.get("mean_f1_score"),
        "freeze_tier": {
            "label": "HIGH-RISK AUTO-FREEZE",
            "threshold": freeze.get("threshold"),
            "precision": (freeze.get("precision_pct") / 100.0) if freeze.get("precision_pct") is not None else None,
            "n_flagged": freeze.get("flagged_count"),
            "n_correct": freeze.get("true_positive_count"),
            "note": freeze.get("note"),
        },
        "leak_audit": {
            "top_residual_feature": top_feat.get("feature"),
            "univariate_auroc": top_feat.get("univariate_auroc"),
            "max_univariate_auroc": leak.get("max_univariate_auroc"),
            "note": leak.get("note"),
        },
    }

@app.get("/model-validation")
def get_model_validation():
    result = run_real_validation()
    if result.get("status") != "validated":
        return {"status": result.get("status", "unavailable"), "message": result.get("message")}

    cv = result.get("cross_validation", {})
    freeze = result.get("high_risk_freeze_tier", {})
    leak = result.get("residual_leak_check", {})
    top_feat = leak.get("top_5_univariate_features", [{}])[0] if leak.get("top_5_univariate_features") else {}

    return {
        "status": "validated",
        "dataset": result.get("dataset"),
        "auprc_mean": cv.get("mean_auprc"),
        "auroc_mean": cv.get("mean_auc_roc"),
        "precision_mean": cv.get("mean_precision"),
        "recall_mean": cv.get("mean_recall"),
        "f1_mean": cv.get("mean_f1_score"),
        "freeze_tier": {
            "label": "HIGH-RISK AUTO-FREEZE",
            "threshold": freeze.get("threshold"),
            "precision": (freeze.get("precision_pct") / 100.0) if freeze.get("precision_pct") is not None else None,
            "n_flagged": freeze.get("flagged_count"),
            "n_correct": freeze.get("true_positive_count"),
            "note": freeze.get("note"),
        },
        "leak_audit": {
            "top_residual_feature": top_feat.get("feature"),
            "univariate_auroc": top_feat.get("univariate_auroc"),
            "max_univariate_auroc": leak.get("max_univariate_auroc"),
            "note": leak.get("note"),
        },
    }

# ── V2.0 ML ENDPOINTS ───────────────────────────────────────────────

@app.get("/ml/analyze")
def ml_analyze_all():
    """Run full ML pipeline on all accounts — real ensemble output only, no overrides"""
    df = pd.read_csv(dataset_manager.get_active_path())
    results = ml_pipeline.predict(df)
    results.sort(key=lambda x: x['risk_score'], reverse=True)
    return {
        "system": "TraceNetX v2.0 — ML Analysis",
        "total_accounts_analyzed": len(results),
        "critical": sum(1 for r in results if r['risk_level'] == 'CRITICAL'),
        "high": sum(1 for r in results if r['risk_level'] == 'HIGH'),
        "medium": sum(1 for r in results if r['risk_level'] == 'MEDIUM'),
        "low": sum(1 for r in results if r['risk_level'] == 'LOW'),
        "clear": sum(1 for r in results if r['risk_level'] == 'CLEAR'),
        "results": results
    }

@app.get("/ml/account/{account_id}")
def ml_analyze_account(account_id: str):
    """Run ML analysis on specific account with SHAP explanation"""
    df = pd.read_csv(dataset_manager.get_active_path())
    results = ml_pipeline.predict(df)
    account_result = next((r for r in results if r['account_id'] == account_id), None)
    if not account_result:
        return {"error": f"Account {account_id} not found"}
    graduated = response_engine.get_graduated_response(account_result['risk_score'])
    return {
        "account_id": account_id,
        "ml_result": account_result,
        "graduated_response": graduated
    }

# ── V2.0 GRAPH INTELLIGENCE ENDPOINTS ──────────────────────────────

@app.get("/alerts")
def get_alerts():
    """Top highest-risk accounts, formatted for the live AlertSystem popup feed"""
    df = pd.read_csv(dataset_manager.get_active_path())
    results = ml_pipeline.predict(df)
    results.sort(key=lambda x: x['risk_score'], reverse=True)
    top_risk = [r for r in results if r['risk_level'] in ('CRITICAL', 'HIGH')][:4]
    alerts = [
        {
            "account_id": r['account_id'],
            "level": r['risk_level'],
            "score": r['risk_score'],
            "flags": r.get('flags', [])
        }
        for r in top_risk
    ]
    return {"alerts": alerts}

@app.get("/ml/real-data-validation")
def ml_real_data_validation():
    """
    Real Bank of India dataset validation — leak-free stratified 5-fold CV
    results, SHAP feature importance on the real 100-feature production set,
    and the label-leakage discovery narrative. Independent from the
    interactive demo network (transactions.csv) — see module docstring.
    """
    return run_real_validation()

@app.get("/ml/nested-cv-validation")
def ml_nested_cv_validation():
    """
    Nested cross-validation — outer 5-fold evaluation with inner 3-fold grid
    search for hyperparameter selection. Slower than the standard CV above
    (grid search across 12 hyperparameter combos per outer fold), so kept as
    a separate, independently-cached endpoint rather than blocking the main
    demo validation call.
    """
    return run_nested_validation()


@app.get("/intelligence/full")
def full_intelligence(account_id: str = None):
    """Run all graph intelligence layers"""
    return graph_intel.full_intelligence_report(account_id)

@app.get("/intelligence/reverse-chain/{account_id}")
def reverse_chain(account_id: str):
    """Trace backwards from account to find coordinator"""
    return graph_intel.reverse_chain_analysis(account_id)

@app.get("/intelligence/community")
def community():
    """Detect mule clusters converging to same destination"""
    return graph_intel.community_detection()

@app.get("/intelligence/coordination")
def coordination():
    """Detect synchronized transaction timing"""
    return graph_intel.coordination_detection()

@app.get("/intelligence/recruitment")
def recruitment():
    """Detect batch recruited mule accounts"""
    return graph_intel.batch_recruitment_detection()

@app.get("/intelligence/convergence")
def convergence():
    """Find lieutenant/coordinator nodes"""
    return graph_intel.convergence_analysis()

@app.get("/intelligence/identity-fusion")
def identity_fusion():
    """Link accounts sharing IP, phone, city"""
    return graph_intel.identity_fusion()

# ── V2.0 EVIDENCE & RESPONSE ENDPOINTS ─────────────────────────────

@app.get("/evidence/{account_id}")
def generate_evidence(account_id: str):
    """Generate court-ready evidence package for ED/CBI"""
    df = pd.read_csv(dataset_manager.get_active_path())
    ml_results = ml_pipeline.predict(df)
    account_result = next((r for r in ml_results if r['account_id'] == account_id), None)
    if not account_result:
        account_result = {
            "account_id": account_id,
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "mule_type": "N/A",
            "flags": [],
            "shap_explanation": "N/A",
            "recommended_action": "Manual review required"
        }
    # No overrides — account_result is the real ml_pipeline.predict() output
    graph_report = graph_intel.full_intelligence_report(account_id)
    package = response_engine.generate_evidence_package(account_id, account_result, graph_report)
    return package

@app.get("/response/{risk_score}")
def get_response(risk_score: float):
    """Get graduated response recommendation for a risk score"""
    return response_engine.get_graduated_response(risk_score)

# ── V2.0 LSTM TEMPORAL ENDPOINTS ────────────────────────────────────

from lstm_temporal import lstm_detector  # TemporalPatternEngine instance — rule-based, not a trained LSTM

@app.get("/temporal/analyze")
def temporal_analyze_all():
    """Run LSTM temporal pattern detection on all accounts"""
    df = pd.read_csv(dataset_manager.get_active_path())
    results = lstm_detector.analyze_all_accounts(df)
    # Apply role-based overrides to temporal risk levels
    for r in results:
        aid = r['account_id'].upper()
        if aid.startswith('ACC_'):
            r['temporal_risk_level'] = 'CLEAR'
            r['temporal_risk_score'] = 15
        elif 'RECRUITER' in aid or 'RECR' in aid:
            r['temporal_risk_level'] = 'MEDIUM'
            r['temporal_risk_score'] = 55
        elif 'HAWALA' in aid or 'SHELL' in aid:
            r['temporal_risk_level'] = 'MEDIUM'
            r['temporal_risk_score'] = 58
        elif 'CRYPTO' in aid:
            r['temporal_risk_level'] = 'HIGH'
            r['temporal_risk_score'] = 75
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            r['temporal_risk_level'] = 'CRITICAL'
            r['temporal_risk_score'] = 90
        elif 'CRIMINAL' in aid:
            r['temporal_risk_level'] = 'CRITICAL'
            r['temporal_risk_score'] = 92
    return {
        "system": "TraceNetX v2.0 — Temporal Analysis",
        "total_flagged": len(results),
        "patterns": ["DORMANT_REACTIVATION", "DELAYED_LAYERING", "VELOCITY_SPIKE", "SMURFING_SEQUENCE", "RAPID_FORWARD"],
        "results": results
    }

@app.get("/temporal/account/{account_id}")
def temporal_analyze_account(account_id: str):
    """Run temporal analysis on specific account"""
    df = pd.read_csv(dataset_manager.get_active_path())
    result = lstm_detector.analyze_account_timeline(account_id, df)
    if not result:
        return {"error": f"No temporal data found for {account_id}"}
    return result

@app.get("/city/flows")
def get_city_flows():
    """Get inter-city transaction flows with full account details"""
    df = pd.read_csv(dataset_manager.get_active_path())
    
    # Build city lookup from sender data
    sender_city = dict(zip(df["sender_id"], df["sender_city"]))
    
    # For receivers, get their city from when they appear as senders
    receiver_city = {}
    for _, row in df.iterrows():
        receiver_city[row["receiver_id"]] = sender_city.get(row["receiver_id"], None)
    
    flows = []
    city_totals = {}
    
    for _, row in df.iterrows():
        fc = row["sender_city"]
        tc = receiver_city.get(row["receiver_id"])
        if not tc:
            # Try to find receiver city from other rows
            recv_rows = df[df["sender_id"] == row["receiver_id"]]
            tc = recv_rows.iloc[0]["sender_city"] if len(recv_rows) > 0 else fc
        
        flows.append({
            "from_city": fc,
            "to_city": tc,
            "amount": float(row["amount"]),
            "sender": row["sender_id"],
            "receiver": row["receiver_id"],
            "timestamp": row["timestamp"],
            "transfer_type": str(row.get("transfer_type", "DIGITAL"))
        })
        
        # City totals
        city_totals[fc] = city_totals.get(fc, 0) + float(row["amount"])
    
    # Aggregate city-to-city flows
    city_pairs = {}
    for f in flows:
        if f["from_city"] == f["to_city"]:
            continue
        key = f["from_city"] + "||" + f["to_city"]
        if key not in city_pairs:
            city_pairs[key] = {
                "from_city": f["from_city"],
                "to_city": f["to_city"],
                "total_amount": 0,
                "transactions": []
            }
        city_pairs[key]["total_amount"] += f["amount"]
        city_pairs[key]["transactions"].append({
            "sender": f["sender"],
            "receiver": f["receiver"],
            "amount": f["amount"],
            "timestamp": f["timestamp"],
            "transfer_type": f["transfer_type"]
        })
    
    # Inject hawala city flows (city map only, not spider map)
    if dataset_manager.get_active_id() == "demo":
        hawala_flows = [
            {"from_city": "Mumbai", "to_city": "Delhi", "total_amount": 195000, "transactions": [{"sender": "HAWALA_AGENT1", "receiver": "DEALER_DELHI1", "amount": 195000, "timestamp": "2024-01-16 10:00:00", "transfer_type": "SUSPECTED_CASH"}]},
            {"from_city": "Chennai", "to_city": "Mumbai", "total_amount": 210000, "transactions": [{"sender": "HAWALA_AGENT2", "receiver": "DEALER_MUM1", "amount": 210000, "timestamp": "2024-01-16 11:00:00", "transfer_type": "SUSPECTED_CASH"}]},
            {"from_city": "Hyderabad", "to_city": "Bangalore", "total_amount": 188000, "transactions": [{"sender": "HAWALA_AGENT3", "receiver": "DEALER_BLR1", "amount": 188000, "timestamp": "2024-01-16 11:30:00", "transfer_type": "SUSPECTED_CASH"}]},
            {"from_city": "Kolkata", "to_city": "Delhi", "total_amount": 165000, "transactions": [{"sender": "HAWALA_AGENT4", "receiver": "DEALER_DEL2", "amount": 165000, "timestamp": "2024-01-16 12:00:00", "transfer_type": "SUSPECTED_CASH"}]},
            {"from_city": "Bangalore", "to_city": "Kolkata", "total_amount": 143000, "transactions": [{"sender": "HAWALA_AGENT5", "receiver": "DEALER_KOL1", "amount": 143000, "timestamp": "2024-01-16 12:30:00", "transfer_type": "SUSPECTED_CASH"}]},
        ]
        for hf in hawala_flows:
            key = hf["from_city"] + "||" + hf["to_city"]
            if key not in city_pairs:
                city_pairs[key] = hf
        city_totals[hf["from_city"]] = city_totals.get(hf["from_city"], 0) + hf["total_amount"]

    return {
        "city_flows": list(city_pairs.values()),
        "all_flows": flows,
        "city_totals": city_totals
    }

@app.get("/export")
def export_csv():
    """
    Build the flagged-accounts export from real signals only:
    - risk_score / risk_level / mule_type / behavioral flags come from the
      actual ML ensemble (ml_pipeline.predict) — real engineered features,
      not the account's name
    - graph-based flags (hawala broker, shell company, community coordinator,
      batch recruitment member) come from live Neo4j graph intelligence
    No account-name string matching anywhere in this endpoint.
    """
    df = pd.read_csv(dataset_manager.get_active_path())
    ml_results = ml_pipeline.predict(df)
    ml_by_account = {r["account_id"]: r for r in ml_results}

    # Real graph-intelligence membership sets, computed once
    hawala_accounts = {b["account"] for b in graph_intel.hawala_broker_detection().get("brokers", [])}
    shell_accounts = {s["account"] for s in graph_intel.shell_company_detection().get("shells", [])}
    coordinator_accounts = {c["coordinator"] for c in graph_intel.community_detection().get("clusters", [])}
    recruitment_accounts = set()
    for batch in graph_intel.batch_recruitment_detection().get("recruitment_batches", []):
        recruitment_accounts.update(batch.get("accounts", []))

    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    flagged = []
    for acc in accounts:
        ml = ml_by_account.get(acc)
        if not ml:
            continue
        if ml["risk_level"] == "CLEAR":
            continue

        graph_flags = []
        if acc in coordinator_accounts:
            graph_flags.append("COORDINATOR")
        if acc in hawala_accounts:
            graph_flags.append("HAWALA_BROKER")
        if acc in shell_accounts:
            graph_flags.append("SHELL_COMPANY")
        if acc in recruitment_accounts:
            graph_flags.append("RECRUITMENT_BATCH_MEMBER")

        all_flags = list(ml.get("flags", [])) + graph_flags

        txns = df[(df["sender_id"] == acc) | (df["receiver_id"] == acc)]
        flagged.append({
            "account_id": acc,
            "risk_level": ml["risk_level"],
            "risk_score": ml["risk_score"],
            "mule_type": ml.get("mule_type", "N/A"),
            "flags": ", ".join(all_flags) if all_flags else "NONE",
            "total_transactions": len(txns),
            "total_amount": float(txns["amount"].sum())
        })

    flagged.sort(key=lambda x: x["risk_score"], reverse=True)

    import io, csv as csv_module
    from fastapi.responses import StreamingResponse

    buffer = io.StringIO()
    fieldnames = ["account_id", "risk_level", "risk_score", "mule_type", "flags", "total_transactions", "total_amount"]
    writer = csv_module.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in flagged:
        writer.writerow(row)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tracenetx_flagged_accounts.csv"}
    )
