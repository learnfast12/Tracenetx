"""Core behaviour tests. Run:  cd backend && python3 -m pytest -q   (no Neo4j needed)."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator import simulate          # noqa: E402
from trail import trace_taint           # noqa: E402


def _tx(rows):
    df = pd.DataFrame(rows, columns=["sender_id", "receiver_id", "amount", "ts"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def _comp(acc="A", amt=10000, ts="2024-01-05 12:00", cid="C1"):
    return pd.DataFrame([{"complaint_id": cid, "reported_account": acc, "amount_lost": amt, "ts": pd.Timestamp(ts)}])


# ── taint tracing ────────────────────────────────────────────────────────────────────────────
def test_money_cannot_flow_backwards_in_time():
    """A->B happened BEFORE the victim paid A, so B must not be tainted."""
    tx = _tx([("A", "B", 10000, "2023-12-01 10:00")])
    assert "B" not in trace_taint(tx, _comp())["accounts"]


def test_taint_follows_forward_chain():
    tx = _tx([("A", "B", 10000, "2024-01-01 10:00"), ("B", "C", 10000, "2024-01-01 11:00")])
    acc = trace_taint(tx, _comp(ts="2024-01-05 12:00"))["accounts"]
    assert acc["B"]["tainted_amount"] == pytest.approx(10000, rel=0.01)
    assert acc["C"]["tainted_amount"] == pytest.approx(10000, rel=0.01)
    assert acc["C"]["nearest_hops"] == 2


def test_taint_is_proportional_to_amount():
    """B holds 10k of victim money and 90k of other money; forwarding 50k carries only a pro-rata share."""
    tx = _tx([("X", "A", 90000, "2023-12-20 09:00"),          # A already holds clean money
              ("A", "B", 100000, "2024-01-01 10:00")])        # A sends everything on
    acc = trace_taint(tx, _comp(amt=10000, ts="2024-01-05 12:00"))["accounts"]
    assert acc["B"]["tainted_amount"] <= 10000 + 1
    assert acc["B"]["tainted_share_of_inflow"] < 0.2


def test_origin_account_not_listed_as_exposed():
    tx = _tx([("A", "B", 5000, "2024-01-01 10:00")])
    assert "A" not in trace_taint(tx, _comp())["accounts"]


# ── simulator ────────────────────────────────────────────────────────────────────────────────
def test_simulator_is_deterministic_and_labelled():
    a = simulate(seed=5, evasion=1.0)
    b = simulate(seed=5, evasion=1.0)
    pd.testing.assert_frame_equal(a[0], b[0])
    truth = a[2]
    assert truth["is_mule"].sum() > 20
    assert (truth["role"] == "VICTIM").any()


def test_complaints_only_name_first_hop_accounts():
    df, comp, truth = simulate(seed=6, evasion=0.5)
    roles = truth.set_index("account_id")["role"]
    assert set(roles.reindex(comp["reported_account"])) == {"MULE_L1"}


# ── API (pandas-only paths; works without Neo4j) ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


def test_priority_leads_rank_collector_first(client):
    leads = client.get("/investigation/priority?top=3").json()["leads"]
    assert leads[0]["account_id"] == "DEALER1"
    assert set(leads[0]["sub_scores"]) == {"ml", "complaints", "baseline"}


def test_timeline_has_events_and_404s_for_unknown(client):
    j = client.get("/timeline/DEALER1").json()
    assert j["events"] and j["totals"]["in"] > 0
    assert client.get("/timeline/NO_SUCH_ACCOUNT").status_code == 404


def test_incident_report_renders_and_escapes(client):
    r = client.get("/report/incident/INC-001")
    assert r.status_code == 200 and "Incident Report INC-001" in r.text
    assert "<script>alert" not in r.text
    assert client.get("/report/incident/INC-999").status_code == 404


def test_model_is_trained_on_simulated_data_not_upload(client):
    info = client.get("/ml/model-info").json()
    assert "simulated" in info["source"] and info["mules"] > 100


def test_coordinators_are_never_labelled_victims(client):
    rows = client.get("/ml/analyze").json()["results"]
    for r in rows:
        if r["role"] in ("DEALER", "CRIMINAL", "INTERMEDIARY") and r["risk_score"] >= 50:
            assert r["mule_type"].startswith("WILLING")


def test_renaming_accounts_does_not_change_roles_or_scores():
    """Roles and ML scores come from behaviour/structure, never from account names."""
    from ml_pipeline import ml_pipeline
    from roles import assign_roles
    df = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "transactions.csv"))
    ids = sorted(set(df["sender_id"]) | set(df["receiver_id"]))
    alias = {a: f"Z{i:04d}" for i, a in enumerate(ids)}            # opaque names, nothing like DEALER/HAWALA
    df2 = df.copy()
    df2["sender_id"], df2["receiver_id"] = df["sender_id"].map(alias), df["receiver_id"].map(alias)
    r1, r2 = assign_roles(df), assign_roles(df2)
    assert all(r1[a] == r2[alias[a]] for a in ids)
    s1 = {r["account_id"]: r["ml_score"] for r in ml_pipeline.predict(df)}
    s2 = {r["account_id"]: r["ml_score"] for r in ml_pipeline.predict(df2)}
    assert all(abs(s1[a] - s2[alias[a]]) < 1e-6 for a in ids)


def test_graph_nodes_carry_complaint_counts(client):
    nodes = {n["id"]: n for n in client.get("/graph").json()["nodes"]}
    assert nodes["ACC_4521"]["complaints"] >= 3          # named by victims
    assert nodes["CRIMINAL1"]["complaints"] == 0         # upstream source, never named


def test_soa_endpoints_degrade_without_data(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SOA_DIR", str(tmp_path / "nope"))
    j = client.get("/soa/ranked").json()
    assert j["available"] is False and j["holders"] == []
    assert client.get("/soa/holder/H_X").status_code == 404


def test_soa_ranking_and_holder_detail(client, monkeypatch, tmp_path):
    import soa_score
    edges = pd.DataFrame([
        {"sender_id": "H_A", "receiver_id": "CP1", "amount": 5000, "timestamp": "2024-01-01 10:00:00", "transfer_type": "UPI", "case_id": "x", "source_file": 1},
        {"sender_id": "CP2", "receiver_id": "H_A", "amount": 5000, "timestamp": "2024-01-01 09:00:00", "transfer_type": "UPI", "case_id": "x", "source_file": 1},
        {"sender_id": "CP1", "receiver_id": "H_B", "amount": 700, "timestamp": "2024-01-02 09:00:00", "transfer_type": "IMPS", "case_id": "x", "source_file": 2},
    ])
    flows = pd.DataFrame(columns=["holder_id", "debit", "credit", "timestamp", "channel", "source_file"])
    edges.to_csv(tmp_path / "soa_edges.csv", index=False)
    flows.to_csv(tmp_path / "soa_holder_flows.csv", index=False)
    soa_score.main(str(tmp_path), 5)                      # writes soa_ranked.csv
    monkeypatch.setenv("SOA_DIR", str(tmp_path))
    r = client.get("/soa/ranked").json()
    assert r["available"] and {h["holder"] for h in r["holders"]} == {"H_A", "H_B"}
    d = client.get("/soa/holder/H_A").json()
    assert d["total_in"] == 5000 and d["total_out"] == 5000
    assert d["shares_counterparties_with"] == {"H_B": 1}   # both touch CP1
    assert client.get("/soa/holder/NOPE").status_code == 404
    # behaviour-only/missing signals are shown as n/a, never as zero
    assert any(c["points"] is None for c in d["contributions"]) or d["contributions"]
    ov = client.get("/soa/overview").json()
    assert ov["holders"] == 2 and ov["transactions"] == 3
    v = client.post("/soa/verdict/H_A", json={"disposition": "escalate", "note": "pass-through"})
    assert v.status_code == 200 and client.get("/soa/verdicts").json()["H_A"]["disposition"] == "ESCALATE"
    assert client.post("/soa/verdict/H_A", json={"disposition": "bogus"}).status_code == 400
    assert client.post("/soa/verdict/NOPE", json={"disposition": "CLEARED"}).status_code == 404
    rep = client.get("/soa/report/H_A")
    assert rep.status_code == 200 and "H_A" in rep.text and "ESCALATE" in rep.text
    assert client.get("/soa/report/NOPE").status_code == 404


def test_account_panel_carries_complaints(client):
    # tests the helper directly: /account/{id} itself needs Neo4j
    import main
    named = main.complaint_block("ACC_4521")
    assert named["count"] >= 3
    assert named["distinct_victims"] >= 1
    assert main.complaint_block("CRIMINAL1")["count"] == 0
    assert main.complaint_block("NO_SUCH_ACCOUNT")["count"] == 0
