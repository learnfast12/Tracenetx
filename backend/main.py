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
    risk = calculate_risk(account_id)
    return {"account": details, "risk": risk}

@app.get("/filter")
def filter_graph(ip: str = None, phone: str = None, city: str = None, case_id: str = None):
    df = pd.read_csv("transactions.csv")
    if case_id:
        df = df[df["case_id"] == case_id]
    if ip:
        df = df[df["sender_ip"] == ip]
    if phone:
        df = df[df["sender_phone"].astype(str) == phone]
    if city:
        df = df[df["sender_city"].str.lower() == city.lower()]
    nodes = set()
    edges = []
    for _, row in df.iterrows():
        nodes.add(row["sender_id"])
        nodes.add(row["receiver_id"])
        edges.append({"source": row["sender_id"], "target": row["receiver_id"], "amount": row["amount"]})
    risk_map = {n: calculate_risk(n) for n in nodes}
    return {
        "nodes": [{"id": n, "risk": risk_map[n]} for n in nodes],
        "edges": edges
    }

@app.get("/export")
def export_flagged():
    df = pd.read_csv("transactions.csv")
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    rows = []
    for acc in accounts:
        risk = calculate_risk(acc)
        if risk["level"] in ["HIGH", "MEDIUM"]:
            rows.append({
                "account_id": acc,
                "risk_level": risk["level"],
                "risk_score": risk["score"],
                "flags": " | ".join(risk["flags"])
            })
    rows.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"flagged_accounts": rows}

@app.get("/alerts")
def get_alerts():
    df = pd.read_csv("transactions.csv")
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    alerts = []
    for acc in accounts:
        risk = calculate_risk(acc)
        if risk["level"] == "HIGH":
            alerts.append({
                "account_id": acc,
                "score": risk["score"],
                "flags": risk["flags"],
                "level": "HIGH"
            })
    return {"alerts": alerts}

@app.get("/path")
def find_path(source: str, target: str):
    df = pd.read_csv("transactions.csv")
    graph = {}
    for _, row in df.iterrows():
        s, r = row["sender_id"], row["receiver_id"]
        if s not in graph:
            graph[s] = []
        graph[s].append({"to": r, "amount": row["amount"]})
    from collections import deque
    queue = deque([[source]])
    visited = set()
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target:
            path_details = []
            for i in range(len(path)-1):
                s, r = path[i], path[i+1]
                edge = next((e for e in graph.get(s,[]) if e["to"]==r), None)
                path_details.append({"from": s, "to": r, "amount": edge["amount"] if edge else 0})
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
        risk = calculate_risk(acc)
        risk_data.append({"account": acc, "score": risk["score"], "level": risk["level"]})
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
    graph_report = graph_intel.full_intelligence_report(account_id)
    package = response_engine.generate_evidence_package(account_id, account_result, graph_report)
    return package

@app.get("/response/{risk_score}")
def get_response(risk_score: float):
    """Get graduated response recommendation for a risk score"""
    return response_engine.get_graduated_response(risk_score)
