"""Per-account transaction timeline (PS-01: "transaction timelines").

GET /timeline/{account_id}
  events        chronological in/out transfers with counterparty, amount, running net position
  pass_through  FIFO-matched inflow -> outflow pairs with dwell time (how long money sat in the account)
  bursts        windows with >= 3 transfers inside 60 minutes
  complaints    complaints filed against this account (overlay markers)
  summary       one-line plain-English reading for the investigator

Never reads account names.
"""
from collections import deque

import pandas as pd
from fastapi import APIRouter, HTTPException

from complaints import complaint_engine
from dataset_manager import dataset_manager

router = APIRouter(tags=["timeline"])

PASS_THROUGH_MAX_MIN = 120
BURST_MIN_TX, BURST_WINDOW_MIN = 3, 60


def _fifo_pairs(events):
    """Match each outflow to the oldest unspent inflow (FIFO). Returns pairs with dwell minutes."""
    queue, pairs = deque(), []
    for e in events:
        if e["direction"] == "in":
            queue.append([e["timestamp"], e["counterparty"], e["amount"]])
        else:
            need = e["amount"]
            while need > 0 and queue:
                t_in, src, avail = queue[0]
                used = min(avail, need)
                dwell = (pd.Timestamp(e["timestamp"]) - pd.Timestamp(t_in)).total_seconds() / 60
                pairs.append({"from": src, "in_time": t_in, "to": e["counterparty"], "out_time": e["timestamp"],
                              "amount": round(used, 2), "dwell_min": round(dwell, 1)})
                need -= used
                if used >= avail - 1e-9:
                    queue.popleft()
                else:
                    queue[0][2] = avail - used
    return pairs


def build_timeline(account_id: str) -> dict:
    t = pd.read_csv(dataset_manager.get_active_path())
    t["amount"] = pd.to_numeric(t["amount"], errors="coerce").fillna(0.0)
    t["ts"] = pd.to_datetime(t["timestamp"], errors="coerce")
    t = t[(t["sender_id"] != t["receiver_id"]) & t["ts"].notna()]
    mine = t[(t["sender_id"] == account_id) | (t["receiver_id"] == account_id)].sort_values("ts", kind="stable")
    if mine.empty:
        raise HTTPException(status_code=404, detail=f"No transactions for account {account_id}")

    events, net = [], 0.0
    for r in mine.itertuples():
        incoming = r.receiver_id == account_id
        net += r.amount if incoming else -r.amount
        events.append({"timestamp": str(r.ts), "direction": "in" if incoming else "out",
                       "counterparty": r.sender_id if incoming else r.receiver_id,
                       "amount": float(r.amount), "net_position": round(net, 2)})

    pairs = _fifo_pairs(events)
    fast = [p for p in pairs if p["dwell_min"] <= PASS_THROUGH_MAX_MIN]
    fast_amt = sum(p["amount"] for p in fast)
    total_in = sum(e["amount"] for e in events if e["direction"] == "in")
    total_out = sum(e["amount"] for e in events if e["direction"] == "out")

    # bursts: sliding 60-minute window over all transfers
    times = [pd.Timestamp(e["timestamp"]) for e in events]
    bursts, i = [], 0
    for j in range(len(times)):
        while (times[j] - times[i]).total_seconds() / 60 > BURST_WINDOW_MIN:
            i += 1
        if j - i + 1 >= BURST_MIN_TX:
            w = {"start": str(times[i]), "end": str(times[j]), "transfers": j - i + 1}
            if bursts and pd.Timestamp(bursts[-1]["start"]) <= times[j] and \
                    (times[i] - pd.Timestamp(bursts[-1]["end"])).total_seconds() <= 0:
                bursts[-1] = {**bursts[-1], "end": w["end"], "transfers": max(bursts[-1]["transfers"], w["transfers"])}
            else:
                bursts.append(w)

    comp = complaint_engine.load()
    mine_c = comp[comp["reported_account"] == account_id]
    complaints = [{"timestamp": str(r.timestamp), "complaint_id": r.complaint_id, "amount_lost": float(r.amount_lost),
                   "fraud_type": r.fraud_type} for r in mine_c.itertuples()]

    bits = [f"{len(events)} transfers between {events[0]['timestamp'][:16]} and {events[-1]['timestamp'][:16]}"]
    if total_out and total_in:
        bits.append(f"{100 * min(total_out / total_in, 9.99):.0f}% of inflow was passed on")
    if fast:
        bits.append(f"{len(fast)} onward transfer(s) ({fast_amt:,.0f}) left within {PASS_THROUGH_MAX_MIN} min of arriving")
    if bursts:
        bits.append(f"{len(bursts)} burst window(s) of {BURST_MIN_TX}+ transfers inside an hour")
    if complaints:
        bits.append(f"{len(complaints)} complaint(s) filed against it")
    return {"account_id": account_id, "events": events, "pass_through": pairs, "bursts": bursts,
            "complaints": complaints,
            "totals": {"in": round(total_in, 2), "out": round(total_out, 2),
                       "fast_pass_through_amount": round(fast_amt, 2)},
            "summary": "; ".join(bits) + "."}


@router.get("/timeline/{account_id}")
def timeline(account_id: str):
    return build_timeline(account_id)
