"""Fast, vectorised per-account feature builder (behavioural + structural + complaint-taint).

Three feature families so the benchmark can run an honest ablation:
  behavioural  - volume, velocity, burstiness, round amounts, pass-through latency, structuring just under a cap
  structural   - fan-in / fan-out, counterparty freshness, shared-device (IP) concentration, flow-through ratio
  complaint    - tainted amount / complaints reaching the account (from trail.py), NEVER the label

Never reads account names. O(n log n) in transactions, so it scales to hundreds of thousands of rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trail import trace_taint

STRUCT_CAP = 50000          # reporting-threshold style cap; "structuring" = repeatedly landing just under it


def build_features(df: pd.DataFrame, complaints: pd.DataFrame | None = None) -> pd.DataFrame:
    t = df[["sender_id", "receiver_id", "amount", "timestamp"]].copy()
    if "sender_ip" in df:
        t["ip"] = df["sender_ip"].astype(str)
    else:
        t["ip"] = "UNKNOWN"
    t["amount"] = pd.to_numeric(t["amount"], errors="coerce").fillna(0.0)
    t["ts"] = pd.to_datetime(t["timestamp"], errors="coerce")
    t = t[(t["sender_id"] != t["receiver_id"]) & t["ts"].notna()].sort_values("ts").reset_index(drop=True)

    out = t.groupby("sender_id").agg(n_out=("amount", "size"), amt_out=("amount", "sum"),
                                     recv_out=("receiver_id", "nunique"), max_out=("amount", "max"),
                                     mean_out=("amount", "mean"), std_out=("amount", "std"))
    inn = t.groupby("receiver_id").agg(n_in=("amount", "size"), amt_in=("amount", "sum"),
                                       send_in=("sender_id", "nunique"), max_in=("amount", "max"),
                                       mean_in=("amount", "mean"), ips_in=("ip", "nunique"))
    f = out.join(inn, how="outer").fillna(0.0)
    f.index.name = "account_id"

    # flow-through: how much of what arrives leaves
    f["flow_through"] = f["amt_out"] / (f["amt_in"] + 1.0)
    f["fan_ratio"] = (f["send_in"] + 1) / (f["recv_out"] + 1)
    f["cv_out"] = (f["std_out"].fillna(0) / (f["mean_out"] + 1.0))

    # round-amount share and just-under-cap structuring (outgoing)
    t["round"] = (t["amount"] % 1000 == 0).astype(float)
    t["near_cap"] = ((t["amount"] >= 0.8 * STRUCT_CAP) & (t["amount"] < STRUCT_CAP)).astype(float)
    g = t.groupby("sender_id")
    f["round_share"] = g["round"].mean().reindex(f.index).fillna(0.0)
    f["near_cap_share"] = g["near_cap"].mean().reindex(f.index).fillna(0.0)

    # burstiness: max transactions inside any 1h window, per account (both directions)
    both = pd.concat([t[["sender_id", "ts"]].rename(columns={"sender_id": "acc"}),
                      t[["receiver_id", "ts"]].rename(columns={"receiver_id": "acc"})]).sort_values("ts")
    both["h"] = both["ts"].dt.floor("h")
    f["burst_1h"] = both.groupby(["acc", "h"]).size().groupby("acc").max().reindex(f.index).fillna(0.0)
    f["active_days"] = both.groupby("acc")["ts"].agg(lambda s: (s.max() - s.min()).total_seconds() / 86400 + 1) \
        .reindex(f.index).fillna(1.0)
    f["tx_per_day"] = (f["n_in"] + f["n_out"]) / f["active_days"]

    # pass-through latency: for each outgoing tx, minutes since that account last received money
    ins = t[["receiver_id", "ts"]].rename(columns={"receiver_id": "acc", "ts": "ts_in"}).sort_values("ts_in")
    outs = t[["sender_id", "ts", "amount"]].rename(columns={"sender_id": "acc"}).sort_values("ts")
    m = pd.merge_asof(outs, ins, left_on="ts", right_on="ts_in", by="acc", direction="backward")
    m["lat_min"] = (m["ts"] - m["ts_in"]).dt.total_seconds() / 60.0
    m["fast"] = (m["lat_min"] <= 120).astype(float)
    lat = m.groupby("acc").agg(lat_med=("lat_min", "median"), fast_share=("fast", "mean"))
    f = f.join(lat).fillna({"lat_med": 1e5, "fast_share": 0.0})

    # structural: shared-device concentration on inbound money
    f["ip_concentration"] = np.where(f["n_in"] >= 2, 1.0 / np.maximum(f["ips_in"], 1), 0.0)

    # counterparty freshness: share of inbound senders whose first-ever appearance is < 3 days before this tx
    first_seen = pd.concat([t[["sender_id", "ts"]].rename(columns={"sender_id": "acc"}),
                            t[["receiver_id", "ts"]].rename(columns={"receiver_id": "acc"})]).groupby("acc")["ts"].min()
    t["sender_first"] = t["sender_id"].map(first_seen)
    t["fresh"] = ((t["ts"] - t["sender_first"]) < pd.Timedelta(days=3)).astype(float)
    f["fresh_sender_share"] = t.groupby("receiver_id")["fresh"].mean().reindex(f.index).fillna(0.0)

    # complaint family (label-free): taint reaching the account
    f["taint_amount"] = 0.0
    f["taint_complaints"] = 0.0
    f["taint_feeders"] = 0.0
    if complaints is not None and len(complaints):
        c = complaints.copy()
        c["ts"] = pd.to_datetime(c["timestamp"], errors="coerce")
        res = trace_taint(t.rename(columns={}), c)
        for acc, v in res["accounts"].items():
            if acc in f.index:
                f.loc[acc, "taint_amount"] = v["tainted_amount"]
                f.loc[acc, "taint_complaints"] = v["complaints_reaching"]
                f.loc[acc, "taint_feeders"] = v["feeder_accounts"]
        for acc, grp in c.groupby("reported_account"):           # the complained account itself
            if acc in f.index:
                f.loc[acc, "taint_complaints"] = max(f.loc[acc, "taint_complaints"], len(grp))
                f.loc[acc, "taint_amount"] = max(f.loc[acc, "taint_amount"], float(grp["amount_lost"].sum()))

    return f.reset_index().rename(columns={"index": "account_id"})


BEHAVIOURAL = ["n_out", "n_in", "amt_out", "amt_in", "mean_out", "max_out", "cv_out", "round_share",
               "near_cap_share", "burst_1h", "tx_per_day", "lat_med", "fast_share", "flow_through"]
STRUCTURAL = ["recv_out", "send_in", "fan_ratio", "ip_concentration", "fresh_sender_share"]
COMPLAINT = ["taint_amount", "taint_complaints", "taint_feeders"]
