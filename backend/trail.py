"""Time-respecting money-trail tracing (taint propagation) for TraceNetX.

Why this exists
---------------
A plain graph traversal ("everything reachable downstream of a complained account") ignores two facts
every financial investigator knows:
  1. TIME   - money can only move forward. A transfer that happened BEFORE the victim paid cannot carry
              the victim's money.
  2. AMOUNT - an account that receives 5,000 of victim money and forwards 500,000 of other funds is not
              a 100% pass-through of that victim.

This module replays the ledger chronologically and propagates "taint" (the share of an account's balance
that traces back to a complaint) with the HAIRCUT (proportional) method used in AML tracing:

    on every transfer  s -> r  of amount a:
        fraction_c = taint_s[c] / held_s          (share of s's holdings traceable to complaint c)
        taint_r[c] += a * fraction_c              (r receives the same share)
        taint_s[c] -= a * fraction_c

Result per account: how much victim money provably could have reached it, from how many distinct
complaints, how many hops away, and the single heaviest time-ordered chain that delivered it.

Pure pandas / stdlib. Never reads account names. Works for any uploaded dataset.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import pandas as pd

SEED_WINDOW_DAYS = 14      # victim money is assumed to have landed up to this long before the complaint
MIN_TAINT = 1.0            # ignore dust (currency units)
MIN_SHARE_OF_COMPLAINT = 0.02   # a complaint "reaches" an account only if >= 2% of its loss does


def trace_taint(tx: pd.DataFrame, complaints: pd.DataFrame) -> dict:
    """Replay `tx` chronologically and propagate complaint taint.

    tx:         columns sender_id, receiver_id, amount, ts   (ts = datetime64)
    complaints: columns complaint_id, reported_account, amount_lost, ts
    Returns {"accounts": {acc: {...}}, "paths": {(acc, complaint_id): [hops]}}
    """
    tx = tx.dropna(subset=["ts"]).sort_values("ts", kind="stable").reset_index(drop=True)

    held: Dict[str, float] = defaultdict(float)
    taint: Dict[str, Dict[str, float]] = defaultdict(dict)       # acc -> complaint_id -> tainted amount
    hops: Dict[tuple, int] = {}                                   # (acc, cid) -> min hops from seed
    pred: Dict[tuple, tuple] = {}                                 # (acc, cid) -> (sender, ts, tainted_amt, amount)
    inflow_total: Dict[str, float] = defaultdict(float)
    received: Dict[str, Dict[str, float]] = defaultdict(dict)    # cumulative taint EVER received (pass-through counts)

    # seeds: victim money lands on the reported account SEED_WINDOW_DAYS before the complaint
    seeds = []
    for r in complaints.itertuples():
        if pd.isna(r.ts):
            continue
        seeds.append((r.ts - pd.Timedelta(days=SEED_WINDOW_DAYS), r.reported_account, r.complaint_id,
                      float(r.amount_lost)))
    seeds.sort(key=lambda s: s[0])
    si = 0

    def seed_until(t):
        nonlocal si
        while si < len(seeds) and seeds[si][0] <= t:
            _, acc, cid, amt = seeds[si]
            held[acc] += amt
            taint[acc][cid] = taint[acc].get(cid, 0.0) + amt
            hops[(acc, cid)] = 0
            si += 1

    for row in tx.itertuples(index=False):
        s, r, a, t = row.sender_id, row.receiver_id, float(row.amount), row.ts
        if s == r or a <= 0:
            continue
        seed_until(t)

        inflow_total[r] += a
        sender_taint = taint.get(s)
        if sender_taint and held[s] > 0:
            share = min(1.0, a / held[s])        # fraction of s's holdings leaving in this transfer
            for cid, amt in list(sender_taint.items()):
                moved = amt * share
                if moved < MIN_TAINT:
                    continue
                sender_taint[cid] = amt - moved
                taint[r][cid] = taint[r].get(cid, 0.0) + moved
                received[r][cid] = received[r].get(cid, 0.0) + moved
                key = (r, cid)
                h = hops.get((s, cid), 0) + 1
                if key not in hops or h < hops[key]:
                    hops[key] = h
                # remember the heaviest single delivery for path reconstruction
                if key not in pred or moved > pred[key][2]:
                    pred[key] = (s, t, moved, a)
        held[s] = max(0.0, held[s] - a)
        held[r] += a

    seed_until(pd.Timestamp.max)

    loss_of = {r.complaint_id: float(r.amount_lost) for r in complaints.itertuples()}
    home_of = {r.complaint_id: r.reported_account for r in complaints.itertuples()}

    accounts: Dict[str, dict] = {}
    for acc, cmap in received.items():
        reaching = {c: v for c, v in cmap.items()
                    if home_of.get(c) != acc and v >= max(MIN_TAINT, MIN_SHARE_OF_COMPLAINT * loss_of.get(c, 0))}
        if not reaching:
            continue
        total = sum(reaching.values())
        feeders = {home_of[c] for c in reaching}
        accounts[acc] = {
            "tainted_amount": round(total, 2),
            "complaints_reaching": len(reaching),
            "feeder_accounts": len(feeders),
            "feeders": sorted(feeders),
            "complaint_ids": sorted(reaching, key=lambda c: -reaching[c]),
            "nearest_hops": min(hops.get((acc, c), 99) for c in reaching),
            "tainted_share_of_inflow": round(total / inflow_total[acc], 3) if inflow_total.get(acc) else None,
            "per_complaint": {c: round(v, 2) for c, v in reaching.items()},
        }
    return {"accounts": accounts, "pred": pred, "hops": hops, "home": home_of}


def heaviest_chain(result: dict, account: str, max_len: int = 12) -> List[dict]:
    """Reconstruct the heaviest time-ordered chain delivering victim money to `account`.

    Returns hops oldest-first: [{from, to, timestamp, amount, tainted_amount, complaint_id}, ...]
    """
    info = result["accounts"].get(account)
    if not info:
        return []
    cid = info["complaint_ids"][0]
    chain, cur = [], account
    for _ in range(max_len):
        p = result["pred"].get((cur, cid))
        if not p:
            break
        s, t, moved, amount = p
        chain.append({"from": s, "to": cur, "timestamp": str(t), "amount": round(float(amount), 2),
                      "tainted_amount": round(float(moved), 2), "complaint_id": cid})
        cur = s
    chain.reverse()
    return chain
