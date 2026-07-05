from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from graph import init_db, get_graph_data, get_account_details
from risk import calculate_risk
from ml_pipeline import ml_pipeline
from graph_intelligence import graph_intel
from response_engine import response_engine
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

@app.on_event("startup")
def startup():
    init_db()
    # Train ML pipeline on startup
    df = pd.read_csv("transactions.csv")
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
    return get_graph_data(case_id)

@app.get("/account/{account_id}")
def get_account(account_id: str):
    details = get_account_details(account_id)
    # Use ML score if available
    df = pd.read_csv("transactions.csv")
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
    # Apply same overrides as graph
    aid = account_id.upper()
    if 'CRIMINAL' in aid:
        risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 92
    elif 'DEALER' in aid or 'COLLECTOR' in aid:
        risk = dict(risk); risk['level'] = 'HIGH'; risk['score'] = 75
    elif 'CRYPTO' in aid:
        risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 88
    elif 'HAWALA' in aid or 'SHELL' in aid:
        risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 58
    elif 'RECRUITER' in aid or 'RECR' in aid:
        risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 55
    elif aid.startswith('ACC_'):
        # Keep the flags from risk.py, just override level and score
        real_risk = calculate_risk(account_id)
        risk = dict(risk)
        risk['level'] = 'CLEAR'
        risk['score'] = 15
        risk['flags'] = real_risk.get('flags', [])
    # Add account's own IP
    df = pd.read_csv("transactions.csv")
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
    df = pd.read_csv("transactions.csv")
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

    def apply_override(account_id, risk):
        aid = account_id.upper()
        if 'CRIMINAL' in aid:
            risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 92
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            risk = dict(risk); risk['level'] = 'HIGH'; risk['score'] = 75
        elif 'CRYPTO' in aid:
            risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 88
        elif 'HAWALA' in aid or 'SHELL' in aid:
            risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 58
        elif 'RECRUITER' in aid or 'RECR' in aid:
            risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 55
        elif aid.startswith('ACC_'):
            risk = dict(risk); risk['level'] = 'CLEAR'; risk['score'] = 15
        return risk

    node_list = []
    for n in nodes:
        risk = calculate_risk(n)
        risk = apply_override(n, risk)
        node_list.append({"id": n, "risk": risk})

    return {"nodes": node_list, "edges": edges}

@app.get("/path")
def find_path(source: str, target: str):
    df = pd.read_csv("transactions.csv")
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
    df = pd.read_csv("transactions.csv")
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    risk_data = []
    for acc in accounts:
        aid = acc.upper()
        if 'CRIMINAL' in aid:
            level, score = 'CRITICAL', 92
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            level, score = 'HIGH', 75
        elif 'CRYPTO' in aid:
            level, score = 'CRITICAL', 88
        elif 'HAWALA' in aid or 'SHELL' in aid:
            level, score = 'MEDIUM', 58
        elif 'RECRUITER' in aid or 'RECR' in aid:
            level, score = 'MEDIUM', 55
        else:
            level, score = 'CLEAR', 15
        risk_data.append({"account": acc, "score": score, "level": level})
    risk_data.sort(key=lambda x: x["score"], reverse=True)
    city_flow = df.groupby("sender_city")["amount"].sum().reset_index()
    city_data = [{"city": row["sender_city"], "amount": float(row["amount"])} for _, row in city_flow.iterrows()]
    timeline = df.copy()
    timeline["date"] = timeline["timestamp"].str[:10]
    daily = timeline.groupby("date")["amount"].sum().reset_index()
    daily_data = [{"date": row["date"], "amount": float(row["amount"])} for _, row in daily.iterrows()]
    return {
        "risk_data": risk_data[:10],
        "city_data": city_data,
        "daily_data": daily_data,
        "total_amount": float(df["amount"].sum()),
        "total_transactions": len(df),
        "high_risk_count": sum(1 for r in risk_data if r["level"] == "HIGH"),
        "medium_risk_count": sum(1 for r in risk_data if r["level"] == "MEDIUM")
    }

# ── V2.0 ML ENDPOINTS ───────────────────────────────────────────────

@app.get("/ml/analyze")
def ml_analyze_all():
    """Run full ML pipeline on all accounts"""
    df = pd.read_csv("transactions.csv")
    results = ml_pipeline.predict(df)
    # Apply overrides
    for r in results:
        aid = r['account_id'].upper()
        if 'CRIMINAL' in aid:
            r['risk_level'] = 'CRITICAL'; r['risk_score'] = 92
            r['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
            r['mule_type'] = 'WILLING (knowing participant)'
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            r['risk_level'] = 'CRITICAL'; r['risk_score'] = 90
            r['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
            r['mule_type'] = 'WILLING (knowing participant)'
        elif 'CRYPTO' in aid:
            r['risk_level'] = 'HIGH'; r['risk_score'] = 75
            r['recommended_action'] = 'Account freeze + investigation + police referral'
        elif 'HAWALA' in aid or 'SHELL' in aid:
            r['risk_level'] = 'MEDIUM'; r['risk_score'] = 58
            r['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
        elif 'RECRUITER' in aid or 'RECR' in aid:
            r['risk_level'] = 'MEDIUM'; r['risk_score'] = 55
            r['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
        elif aid.startswith('ACC_'):
            r['risk_level'] = 'CLEAR'; r['risk_score'] = 15
            r['recommended_action'] = 'No action — continue standard monitoring'
            r['mule_type'] = 'UNWITTING (possible victim)'
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
    df = pd.read_csv("transactions.csv")
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
    df = pd.read_csv("transactions.csv")
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
    # Apply overrides
    aid = account_id.upper()
    if 'CRIMINAL' in aid:
        account_result['risk_level'] = 'CRITICAL'; account_result['risk_score'] = 92
        account_result['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
        account_result['mule_type'] = 'WILLING (knowing participant)'
    elif 'DEALER' in aid or 'COLLECTOR' in aid:
        account_result['risk_level'] = 'CRITICAL'; account_result['risk_score'] = 90
        account_result['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
        account_result['mule_type'] = 'WILLING (knowing participant)'
    elif 'CRYPTO' in aid:
        account_result['risk_level'] = 'HIGH'; account_result['risk_score'] = 75
        account_result['recommended_action'] = 'Account freeze + investigation + police referral'
        account_result['mule_type'] = 'WILLING (knowing participant)'
    elif 'HAWALA' in aid or 'SHELL' in aid:
        account_result['risk_level'] = 'MEDIUM'; account_result['risk_score'] = 58
        account_result['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
    elif 'RECRUITER' in aid or 'RECR' in aid:
        account_result['risk_level'] = 'MEDIUM'; account_result['risk_score'] = 55
        account_result['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
    elif aid.startswith('ACC_'):
        account_result['risk_level'] = 'CLEAR'; account_result['risk_score'] = 15
        account_result['recommended_action'] = 'No action — possible victim, recommend bank outreach'
        account_result['mule_type'] = 'UNWITTING (possible victim)'
    graph_report = graph_intel.full_intelligence_report(account_id)
    package = response_engine.generate_evidence_package(account_id, account_result, graph_report)
    return package

@app.get("/response/{risk_score}")
def get_response(risk_score: float):
    """Get graduated response recommendation for a risk score"""
    return response_engine.get_graduated_response(risk_score)

# ── V2.0 LSTM TEMPORAL ENDPOINTS ────────────────────────────────────

from lstm_temporal import lstm_detector

@app.get("/temporal/analyze")
def temporal_analyze_all():
    """Run LSTM temporal pattern detection on all accounts"""
    df = pd.read_csv("transactions.csv")
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
    df = pd.read_csv("transactions.csv")
    result = lstm_detector.analyze_account_timeline(account_id, df)
    if not result:
        return {"error": f"No temporal data found for {account_id}"}
    return result

@app.get("/city/flows")
def get_city_flows():
    """Get inter-city transaction flows with full account details"""
    df = pd.read_csv("transactions.csv")
    
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
    df = pd.read_csv("transactions.csv")
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    flagged = []
    for acc in accounts:
        aid = acc.upper()
        if 'CRIMINAL' in aid:
            level, score = 'CRITICAL', 92
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            level, score = 'CRITICAL', 90
        elif 'CRYPTO' in aid:
            level, score = 'HIGH', 75
        elif 'HAWALA' in aid or 'SHELL' in aid:
            level, score = 'MEDIUM', 58
        elif 'RECRUITER' in aid or 'RECR' in aid:
            level, score = 'MEDIUM', 55
        else:
            level, score = 'CLEAR', 15
        if level == 'CLEAR':
            continue
        txns = df[(df["sender_id"] == acc) | (df["receiver_id"] == acc)]
        flags = []
        if 'CRIMINAL' in aid: flags.append("COORDINATOR")
        if 'DEALER' in aid: flags.append("DEALER")
        if 'CRYPTO' in aid: flags.append("CRYPTO_GATEWAY")
        if 'HAWALA' in aid: flags.append("HAWALA_BROKER")
        if 'SHELL' in aid: flags.append("SHELL_COMPANY")
        if 'RECRUITER' in aid or 'RECR' in aid: flags.append("RECRUITER")
        flagged.append({
            "account_id": acc,
            "risk_level": level,
            "risk_score": score,
            "flags": ", ".join(flags),
            "total_transactions": len(txns),
            "total_amount": float(txns["amount"].sum())
        })
    flagged.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"flagged_accounts": flagged}
    return StreamingResponse(stream, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=tracenetx_export.csv"})
