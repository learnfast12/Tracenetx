"""Ground-truth mule-network simulator for TraceNetX benchmarking.

Generates a labelled payment network so detectors can be measured against KNOWN answers:

  legitimate world   salaried individuals, merchants (huge fan-in), payment aggregators (fast pass-through,
                     the classic false-positive trap), landlords/families (round-amount transfers)
  criminal world     N rings, each: victims -> layer-1 mules -> layer-2 mules -> collector -> cash-out
  complaints         only a fraction of victims complain, and each complaint names only the first account
                     the victim paid (exactly what a real NCRP complaint contains)

`evasion` controls how hard the criminals try to dodge simple rules:
    0.0  naive  - big round transfers, no structuring
    1.0  evasive - amounts structured under the 50,000 reporting threshold, jittered timing, extra hops

DISCLOSURE: this is a synthetic world authored by us. Results show how well each method covers the
typologies encoded here - they are NOT a claim about performance on real bank data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

START = pd.Timestamp("2024-03-01")
DAYS = 30


def _ts(rng, day, hour_lo=8, hour_hi=22):
    return START + pd.Timedelta(days=int(day), hours=float(rng.uniform(hour_lo, hour_hi)))


def simulate(seed: int = 0, n_people: int = 900, n_merchants: int = 40, n_aggregators: int = 5,
             n_rings: int = 6, evasion: float = 0.5, complaint_rate: float = 0.35,
             stealth: float = 0.5, n_traders: int = 30, n_crowdfunds: int = 8):
    rng = np.random.default_rng(seed)
    tx, labels, role = [], {}, {}

    def add(s, r, amt, t, ip=None, city=None):
        tx.append((s, r, round(float(amt), 2), t, ip or f"ip_{rng.integers(1, 5000)}", city or "CITY"))

    people = [f"P{seed}_{i:04d}" for i in range(n_people)]
    merchants = [f"M{seed}_{i:03d}" for i in range(n_merchants)]
    aggs = [f"AG{seed}_{i:02d}" for i in range(n_aggregators)]
    for a in people + merchants + aggs:
        labels[a], role[a] = 0, "LEGIT"

    # ── legitimate traffic ──
    for p in people:
        for _ in range(rng.poisson(9)):
            d = rng.integers(0, DAYS)
            if rng.random() < 0.55:
                add(p, rng.choice(merchants), rng.lognormal(6.6, 0.9), _ts(rng, d))
            else:
                add(p, rng.choice(people), rng.lognormal(6.9, 1.0), _ts(rng, d))
        if rng.random() < 0.25:                      # rent / family: round amounts, big
            add(p, rng.choice(people), rng.choice([10000, 15000, 20000, 25000, 40000, 60000]),
                _ts(rng, rng.integers(0, DAYS)))
    for m in merchants:                              # settle to a bank-like sink once a week
        for w in range(4):
            add(m, f"SETTLE_{m}", rng.uniform(30000, 120000), _ts(rng, w * 7 + 6, 2, 6))
    for ag in aggs:                                  # aggregators: heavy inflow, forwarded within hours
        for _ in range(rng.integers(60, 120)):
            d = rng.integers(0, DAYS)
            t = _ts(rng, d)
            amt = rng.lognormal(7.2, 0.8)
            add(rng.choice(people), ag, amt, t)
            add(ag, f"SETTLE_{ag}", amt * 0.98, t + pd.Timedelta(minutes=float(rng.uniform(20, 180))))

    # affluent / very active legitimate customers: big salary credits, big purchases, many transactions
    for p in rng.choice(people, size=int(0.22 * n_people), replace=False):
        add(f"SAL{seed}_{p}", p, rng.uniform(40000, 150000), _ts(rng, rng.integers(0, 3)))
        labels[f"SAL{seed}_{p}"], role[f"SAL{seed}_{p}"] = 0, "LEGIT"
        for _ in range(int(rng.integers(6, 30))):
            if rng.random() < 0.5:
                add(p, rng.choice(merchants), rng.lognormal(8.3, 0.9), _ts(rng, rng.integers(0, DAYS)))
            else:
                add(p, rng.choice(people), rng.lognormal(8.0, 1.0), _ts(rng, rng.integers(0, DAYS)))

    # marketplace sellers: one-off payments from strangers (fresh senders), money then spent slowly
    for p in rng.choice(people, size=int(0.07 * n_people), replace=False):
        for _ in range(int(rng.integers(1, 4))):
            stranger = f"STR{seed}_{rng.integers(0, 10**7)}"
            labels[stranger], role[stranger] = 0, "VICTIM"      # external counterparty, not scored
            add(stranger, p, rng.lognormal(9.0, 0.8), _ts(rng, rng.integers(0, DAYS)))
        for _ in range(int(rng.integers(1, 4))):
            add(p, rng.choice(people + merchants), rng.lognormal(8.5, 0.8), _ts(rng, rng.integers(3, DAYS)))

    # shared-device noise: families / offices / PG hostels share one IP (so "same IP" is NOT proof of a ring)
    for g in range(60):
        grp = rng.choice(people, size=int(rng.integers(3, 8)), replace=False)
        ipg = f"nat{seed}_{g}"
        for a in grp:
            for _ in range(int(rng.integers(1, 4))):
                add(a, rng.choice(merchants), rng.lognormal(6.5, 0.8), _ts(rng, rng.integers(0, DAYS)), ip=ipg)

    # hard negatives #1: small traders - round amounts, fast onward payment to suppliers, many inbound customers
    for i in range(n_traders):
        tr = f"TR{seed}_{i:03d}"
        labels[tr], role[tr] = 0, "LEGIT"
        sup = f"SUP{seed}_{i:03d}"
        labels[sup], role[sup] = 0, "LEGIT"
        for _ in range(int(rng.integers(25, 70))):
            t = _ts(rng, rng.integers(0, DAYS))
            amt = float(rng.choice([2000, 3000, 5000, 7500, 10000, 20000]))
            add(rng.choice(people), tr, amt, t)
            if rng.random() < 0.6:
                add(tr, sup, amt * 0.95, t + pd.Timedelta(minutes=float(rng.uniform(15, 240))))

    # hard negatives #2: crowdfunding / wedding / chit-fund collections - big FRESH fan-in, bulk forward in a day
    for i in range(n_crowdfunds):
        cf = f"CF{seed}_{i:03d}"
        labels[cf], role[cf] = 0, "LEGIT"
        d = int(rng.integers(2, DAYS - 3))
        tot = 0.0
        for _ in range(int(rng.integers(30, 90))):
            amt = float(rng.choice([500, 1000, 2000, 5000, 10000]))
            add(rng.choice(people), cf, amt, _ts(rng, d + rng.integers(0, 2)), ip=f"ip_{rng.integers(1, 5000)}")
            tot += amt
        add(cf, rng.choice(people), tot * 0.97, _ts(rng, d + 2))

    # ── criminal rings ──
    complaints = []
    cid = 0
    for k in range(n_rings):
        l1 = [f"MU{seed}_{k}_L1_{i:02d}" for i in range(rng.integers(8, 15))]
        l2 = [f"MU{seed}_{k}_L2_{i:02d}" for i in range(rng.integers(3, 6))]
        col = [f"MU{seed}_{k}_COL_{i}" for i in range(rng.integers(1, 3))]
        out = f"MU{seed}_{k}_OUT"
        for a in l1: labels[a], role[a] = 1, "MULE_L1"
        for a in l2: labels[a], role[a] = 1, "MULE_L2"
        for a in col: labels[a], role[a] = 1, "COLLECTOR"
        labels[out], role[out] = 1, "CASHOUT"
        shared_ips = [f"ring{seed}_{k}_ip{j}" for j in range(2)]
        day0 = int(rng.integers(3, DAYS - 6))
        cap = 49000 if evasion >= 0.5 else 10 ** 9
        for m in l1:
            n_vic = int(rng.integers(1, 5))
            got = 0.0
            tfirst = _ts(rng, day0 + rng.integers(0, 3))
            for _ in range(n_vic):
                v = f"VIC{seed}_{k}_{cid:05d}"
                amt = float(np.clip(rng.lognormal(9.2, 0.9), 2000, 90000))
                t = tfirst + pd.Timedelta(minutes=float(rng.uniform(0, 600)))
                add(v, m, amt, t)
                got += amt
                labels[v], role[v] = 0, "VICTIM"
                if rng.random() < complaint_rate:
                    complaints.append({
                        "complaint_id": f"C{seed}-{cid:05d}", "victim_id": v, "reported_account": m,
                        "amount_lost": amt, "timestamp": t + pd.Timedelta(hours=float(rng.uniform(6, 96))),
                        "fraud_type": str(rng.choice(["UPI_COLLECT_FRAUD", "DIGITAL_ARREST", "INVESTMENT_SCAM"])),
                        "channel": "NCRP_PORTAL", "reported_phone": f"98765{k:05d}", "city": "CITY"})
                cid += 1
            stealthy = rng.random() < stealth
            if stealthy:   # a "real person's" account lent to the ring: holds funds for days, mixes in normal life
                for _ in range(int(rng.integers(6, 14))):
                    add(m, rng.choice(merchants), rng.lognormal(6.6, 0.9), _ts(rng, rng.integers(0, DAYS)))
                    add(rng.choice(people), m, rng.lognormal(6.9, 0.9), _ts(rng, rng.integers(0, DAYS)))
                tfwd = tfirst + pd.Timedelta(hours=float(rng.uniform(8, 80)))
                remaining = got * float(rng.uniform(0.5, 0.9))
            else:
                tfwd = tfirst + pd.Timedelta(minutes=float(rng.uniform(30, 90 + 400 * evasion)))
                remaining = got * 0.97
            dest = rng.choice(l2)
            while remaining > 1:
                piece = min(remaining, rng.uniform(0.5, 1.0) * cap) if cap < 10 ** 8 else remaining
                ipx = str(rng.choice(shared_ips)) if rng.random() < 0.5 else f"ip_{rng.integers(1, 5000)}"
                add(m, dest, piece, tfwd, ip=ipx)
                remaining -= piece
                tfwd += pd.Timedelta(minutes=float(rng.uniform(2, 25)))
        for m in l2:
            tin = _ts(rng, day0 + 3)
            bal = rng.uniform(80000, 300000)
            for _ in range(int(rng.integers(2, 5))):
                piece = min(bal / 3, cap)
                add(m, rng.choice(col), piece, tin + pd.Timedelta(hours=float(rng.uniform(1, 8 + 12 * evasion))),
                    ip=str(rng.choice(shared_ips)))
        for c in col:
            tc = _ts(rng, day0 + 4)
            for _ in range(int(rng.integers(2, 4))):
                add(c, out, rng.uniform(0.6, 1.0) * min(400000, cap * 6), tc + pd.Timedelta(hours=float(rng.uniform(1, 10))),
                    ip=str(rng.choice(shared_ips)))

    df = pd.DataFrame(tx, columns=["sender_id", "receiver_id", "amount", "timestamp", "sender_ip", "sender_city"])
    df["sender_phone"], df["case_id"], df["transfer_type"] = "UNKNOWN", "SIM", "DIGITAL"
    df["receiver_ip"] = "UNKNOWN"
    df = df.sort_values("timestamp").reset_index(drop=True)
    comp = pd.DataFrame(complaints)
    for a in set(df["sender_id"]) | set(df["receiver_id"]):
        labels.setdefault(a, 0)
        role.setdefault(a, "LEGIT")
    truth = pd.DataFrame({"account_id": list(labels), "is_mule": list(labels.values()),
                          "role": [role[a] for a in labels]})
    # real investigations are incomplete: ~4% of true mules were never found, so they sit in the data labelled 0
    undiscovered = truth.index[(truth["is_mule"] == 1) & (rng.random(len(truth)) < 0.04)]
    truth.loc[undiscovered, "is_mule"] = 0
    return df, comp, truth
