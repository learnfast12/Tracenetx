"""Complaint correlation engine for TraceNetX.

Correlates cybercrime complaints (victim -> reported account) with the transaction graph:
  * direct signal   - how many distinct victims / how much loss hit THIS account
  * exposure signal - complaints on feeder accounts whose money flows DOWNSTREAM into this
                      account (this is what surfaces dealers/collectors no victim ever paid)
  * incident clusters - complaints linked by shared phone or by converging on a collector
  * funds-consistency - did the reported account actually receive >= the reported loss shortly
                      before the complaint (a corroboration check, not proof)

Pure pandas, so it works whether or not Neo4j is up and for any uploaded dataset.
Never reads account names.
"""
import io
import math
import os
import uuid
from collections import defaultdict, deque

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from dataset_manager import dataset_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COMPLAINTS = os.path.join(BASE_DIR, "complaints.csv")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_complaints")
os.makedirs(UPLOAD_DIR, exist_ok=True)

REQUIRED = {"complaint_id", "victim_id", "reported_account", "amount_lost", "timestamp"}
OPTIONAL = {"fraud_type": "UNKNOWN", "channel": "UNKNOWN", "reported_phone": "UNKNOWN", "city": "UNKNOWN"}

MAX_HOPS = 5            # how far downstream a complaint's money is followed
CONSISTENCY_DAYS = 14   # inbound-funds window used for the funds-consistency check


class ComplaintEngine:
    def __init__(self):
        self.path = DEFAULT_COMPLAINTS
        self.name = "Demo complaints (complaints.csv)"

    # ── loading ──────────────────────────────────────────────────────
    def load(self) -> pd.DataFrame:
        if not os.path.exists(self.path):
            return pd.DataFrame(columns=list(REQUIRED | set(OPTIONAL)))
        c = pd.read_csv(self.path, dtype={"reported_phone": str})
        missing = REQUIRED - set(c.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        for col, default in OPTIONAL.items():
            if col not in c.columns:
                c[col] = default
        c["amount_lost"] = pd.to_numeric(c["amount_lost"], errors="coerce").fillna(0.0)
        c["ts"] = pd.to_datetime(c["timestamp"], errors="coerce")
        return c

    def upload(self, filename: str, data: bytes) -> dict:
        df = pd.read_csv(io.BytesIO(data), dtype={"reported_phone": str})
        missing = REQUIRED - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}. Required: {sorted(REQUIRED)}")
        save = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{os.path.basename(filename)}")
        with open(save, "wb") as f:
            f.write(data)
        self.path, self.name = save, filename
        return {"name": filename, "rows": len(df)}

    def reset(self):
        self.path, self.name = DEFAULT_COMPLAINTS, "Demo complaints (complaints.csv)"

    # ── graph helpers ────────────────────────────────────────────────
    @staticmethod
    def _tx() -> pd.DataFrame:
        t = pd.read_csv(dataset_manager.get_active_path())
        t["amount"] = pd.to_numeric(t["amount"], errors="coerce").fillna(0.0)
        t["ts"] = pd.to_datetime(t["timestamp"], errors="coerce")
        return t[t["sender_id"] != t["receiver_id"]]

    @staticmethod
    def _downstream(adj, start):
        """BFS forward from `start`; returns {account: hops} (start excluded)."""
        seen, q = {start: 0}, deque([start])
        while q:
            cur = q.popleft()
            if seen[cur] >= MAX_HOPS:
                continue
            for nxt in adj.get(cur, ()):
                if nxt not in seen:
                    seen[nxt] = seen[cur] + 1
                    q.append(nxt)
        seen.pop(start)
        return seen

    # ── core correlation ─────────────────────────────────────────────
    def correlate(self) -> dict:
        c, t = self.load(), self._tx()
        graph_accounts = set(t["sender_id"]) | set(t["receiver_id"])
        adj = defaultdict(set)
        for s, r in zip(t["sender_id"], t["receiver_id"]):
            adj[s].add(r)

        # funds-consistency: did the account receive >= the reported loss shortly before the complaint?
        inbound = {a: g[["ts", "amount"]] for a, g in t.groupby("receiver_id")}
        consistent = []
        for _, row in c.iterrows():
            g = inbound.get(row["reported_account"])
            ok = False
            if g is not None and pd.notna(row["ts"]):
                w = g[(g["ts"] <= row["ts"]) & (g["ts"] >= row["ts"] - pd.Timedelta(days=CONSISTENCY_DAYS))]
                ok = bool(w["amount"].sum() >= row["amount_lost"])
            consistent.append(ok)
        c = c.assign(funds_consistent=consistent)

        # direct signal per reported account
        direct = {}
        for acc, g in c.groupby("reported_account"):
            direct[acc] = {
                "complaints": int(len(g)),
                "distinct_victims": int(g["victim_id"].nunique()),
                "total_loss": float(g["amount_lost"].sum()),
                "fraud_types": sorted(set(g["fraud_type"])),
                "first_complaint": str(g["ts"].min()),
                "last_complaint": str(g["ts"].max()),
                "complaint_ids": list(g["complaint_id"]),
                "funds_consistent_share": round(float(g["funds_consistent"].mean()), 2),
            }

        # exposure signal: push each complained account's victims downstream
        exposure = defaultdict(lambda: {"victims": set(), "feeders": set(), "loss": 0.0, "min_hops": 99})
        feeder_reach = {}
        for acc, d in direct.items():
            if acc not in graph_accounts:
                continue
            reach = self._downstream(adj, acc)
            feeder_reach[acc] = reach
            vic = set(c.loc[c["reported_account"] == acc, "victim_id"])
            for dst, hops in reach.items():
                e = exposure[dst]
                e["victims"] |= vic
                e["feeders"].add(acc)
                e["loss"] += d["total_loss"]
                e["min_hops"] = min(e["min_hops"], hops)

        # score per account
        accounts = {}
        for a in graph_accounts | set(direct):
            d = direct.get(a)
            e = exposure.get(a)
            s_direct = 0.0
            if d:
                s_direct = min(100.0, 25 * min(d["distinct_victims"], 3) + 25 * min(d["total_loss"] / 50000, 1))
            s_exp = 0.0
            if e and len(e["feeders"]) >= 2:   # one feeder alone is just a pass-through, not convergence
                s_exp = min(100.0, 10 * min(len(e["victims"]), 8) + 8 * min(len(e["feeders"]), 8)
                            + 10 * min(e["loss"] / 200000, 1))
            score = round(max(s_direct, 0.85 * s_exp), 1)
            if score == 0:
                continue
            accounts[a] = {
                "complaint_score": score,
                "direct": d,
                "exposure": None if not e else {
                    "victims_reaching": len(e["victims"]),
                    "feeder_accounts": len(e["feeders"]),
                    "loss_reaching": round(e["loss"], 2),
                    "nearest_feeder_hops": e["min_hops"],
                },
                "in_transaction_graph": a in graph_accounts,
            }

        clusters = self._clusters(c, feeder_reach)
        return {
            "accounts": accounts,
            "clusters": clusters,
            "unmatched_accounts": sorted(a for a in direct if a not in graph_accounts),
            "stats": {
                "complaints": int(len(c)),
                "distinct_victims": int(c["victim_id"].nunique()),
                "accounts_complained_about": len(direct),
                "total_reported_loss": round(float(c["amount_lost"].sum()), 2),
                "funds_consistent_share": round(float(c["funds_consistent"].mean()), 2) if len(c) else 0.0,
            },
        }

    def _clusters(self, c: pd.DataFrame, feeder_reach: dict) -> list:
        """Union complained accounts that share a phone or converge on a common downstream account."""
        accs = list(c["reported_account"].unique())
        parent = {a: a for a in accs}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            parent[find(a)] = find(b)

        by_phone = defaultdict(list)
        for a, p in zip(c["reported_account"], c["reported_phone"]):
            if isinstance(p, str) and p not in ("UNKNOWN", "", "nan"):
                by_phone[p].append(a)
        for lst in by_phone.values():
            for x in lst[1:]:
                union(lst[0], x)

        converge = defaultdict(list)
        for f, reach in feeder_reach.items():
            for dst in reach:
                converge[dst].append(f)
        for lst in converge.values():
            if len(lst) >= 2:
                for x in lst[1:]:
                    union(lst[0], x)

        groups = defaultdict(list)
        for a in accs:
            groups[find(a)].append(a)

        out = []
        for members in groups.values():
            g = c[c["reported_account"].isin(members)]
            counter = defaultdict(int)
            for m in members:
                for dst in feeder_reach.get(m, {}):
                    counter[dst] += 1
            collector = None
            if counter:
                best = max(counter.items(), key=lambda kv: (kv[1], kv[0]))
                if best[1] >= 2:
                    collector = {"account": best[0], "fed_by_complained_accounts": best[1]}
            out.append({
                "cluster_id": None,
                "accounts": sorted(members),
                "complaints": int(len(g)),
                "distinct_victims": int(g["victim_id"].nunique()),
                "total_loss": round(float(g["amount_lost"].sum()), 2),
                "fraud_types": sorted(set(g["fraud_type"])),
                "shared_phones": sorted(p for p, lst in by_phone.items() if set(lst) & set(members) and len(set(lst)) >= 2),
                "likely_collector": collector,
                "first_complaint": str(g["ts"].min()),
                "last_complaint": str(g["ts"].max()),
            })
        out.sort(key=lambda x: (-x["total_loss"], -x["complaints"]))
        for i, cl in enumerate(out, 1):
            cl["cluster_id"] = f"INC-{i:03d}"
        return out

    # ── views ────────────────────────────────────────────────────────
    def account_view(self, account_id: str) -> dict:
        res = self.correlate()
        a = res["accounts"].get(account_id)
        if not a:
            return {"account_id": account_id, "complaint_score": 0, "linked": False,
                    "note": "No complaints linked to this account or its upstream feeders."}
        cl = next((x for x in res["clusters"]
                   if account_id in x["accounts"]
                   or (x["likely_collector"] and x["likely_collector"]["account"] == account_id)), None)
        return {"account_id": account_id, "linked": True, **a,
                "incident_cluster": None if not cl else {k: cl[k] for k in
                    ("cluster_id", "complaints", "distinct_victims", "total_loss", "likely_collector")}}

    def complaint_graph(self) -> dict:
        """Nodes + edges (complaint -> reported account) to overlay on the Spider Map."""
        c = self.load()
        nodes = [{"id": r.complaint_id, "type": "COMPLAINT", "amount": float(r.amount_lost),
                  "fraud_type": r.fraud_type, "timestamp": str(r.timestamp)} for r in c.itertuples()]
        edges = [{"source": r.complaint_id, "target": r.reported_account, "type": "REPORTS"} for r in c.itertuples()]
        return {"nodes": nodes, "edges": edges}


complaint_engine = ComplaintEngine()
router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.post("/upload")
async def upload_complaints(file: UploadFile = File(...)):
    try:
        info = complaint_engine.upload(file.filename, await file.read())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "active": info}


@router.post("/reset")
def reset_complaints():
    complaint_engine.reset()
    return {"status": "ok", "active": complaint_engine.name}


@router.get("/summary")
def summary():
    r = complaint_engine.correlate()
    top = sorted(r["accounts"].items(), key=lambda kv: -kv[1]["complaint_score"])[:10]
    return {"dataset": complaint_engine.name, "stats": r["stats"],
            "incident_clusters": len(r["clusters"]),
            "unmatched_accounts": r["unmatched_accounts"],
            "top_accounts": [{"account_id": a, "complaint_score": v["complaint_score"]} for a, v in top]}


@router.get("/correlate")
def correlate_all():
    return complaint_engine.correlate()


@router.get("/clusters")
def clusters():
    return {"clusters": complaint_engine.correlate()["clusters"]}


@router.get("/graph")
def graph():
    return complaint_engine.complaint_graph()


@router.get("/account/{account_id}")
def account(account_id: str):
    return complaint_engine.account_view(account_id)
