"""Deviation-from-normal-behaviour scoring (PS-01: "deviations from normal account behaviour").

Per account we measure how far its largest transaction and its busiest hour sit from a baseline:
  * basis "own_history"     - account has >= MIN_HISTORY transactions: compared with its own other activity
  * basis "peer_population" - too little history: compared with all accounts in the dataset
Uses robust statistics (median / MAD), so a single huge transfer cannot hide itself in the mean.
Never reads account names.
"""
import numpy as np
import pandas as pd

MIN_HISTORY = 6


def _robust_z(x: float, ref: np.ndarray) -> float:
    ref = np.asarray(ref, dtype=float)
    if len(ref) == 0:
        return 0.0
    med = np.median(ref)
    mad = np.median(np.abs(ref - med)) * 1.4826
    if mad < 1e-9:
        mad = max(np.std(ref), 1e-9) if np.std(ref) > 0 else max(abs(med) * 0.1, 1.0)
    return float((x - med) / mad)


def baseline_deviation(df: pd.DataFrame) -> dict:
    t = df[["sender_id", "receiver_id", "amount", "timestamp"]].copy()
    t["amount"] = pd.to_numeric(t["amount"], errors="coerce").fillna(0.0)
    t["ts"] = pd.to_datetime(t["timestamp"], errors="coerce")
    t = t[t["sender_id"] != t["receiver_id"]]

    # one row per (account, transaction) from the account's point of view
    a = pd.concat([
        t.assign(account=t["sender_id"], direction="out"),
        t.assign(account=t["receiver_id"], direction="in"),
    ])[["account", "amount", "ts", "direction"]].sort_values("ts")

    peer_amounts = a["amount"].to_numpy()
    burst = {}
    for acc, g in a.groupby("account"):
        times = g["ts"].dropna().sort_values().to_numpy()
        best = 1
        j = 0
        for i in range(len(times)):
            while times[i] - times[j] > np.timedelta64(1, "h"):
                j += 1
            best = max(best, i - j + 1)
        burst[acc] = best
    peer_burst = np.array(list(burst.values()), dtype=float)

    out = {}
    for acc, g in a.groupby("account"):
        n = len(g)
        biggest = float(g["amount"].max())
        if n >= MIN_HISTORY:
            others = g["amount"].sort_values().to_numpy()[:-1]   # everything except the largest
            z_amt, basis = _robust_z(biggest, others), "own_history"
        else:
            z_amt, basis = _robust_z(biggest, peer_amounts), "peer_population"
        z_burst = _robust_z(float(burst[acc]), peer_burst)

        flags = []
        if z_amt >= 3:
            flags.append(f"Largest transfer ({biggest:,.0f}) is {z_amt:.1f}x robust-sigma above its {basis.replace('_', ' ')} baseline")
        if z_burst >= 3 and burst[acc] >= 3:
            flags.append(f"{burst[acc]} transactions inside one hour, {z_burst:.1f}x robust-sigma above typical accounts")

        # latency between money arriving and money leaving
        ins, outs = g[g["direction"] == "in"]["ts"].dropna(), g[g["direction"] == "out"]["ts"].dropna()
        latency_min = None
        if len(ins) and len(outs):
            gaps = [(o - ins[ins <= o].max()).total_seconds() / 60 for o in outs if (ins <= o).any()]
            if gaps:
                latency_min = round(float(np.median(gaps)), 1)
                if latency_min <= 90:
                    flags.append(f"Funds leave a median {latency_min:.0f} min after arriving (rapid pass-through)")

        # log-compressed so one extreme outlier cannot saturate every account at 100
        def squash(z):
            return min(1.0, np.log1p(max(z, 0.0)) / np.log1p(20))
        score = 45 * squash(z_amt) + 35 * squash(z_burst) + (20 if latency_min is not None and latency_min <= 90 else 0)
        out[acc] = {
            "baseline_score": round(score, 1),
            "basis": basis,
            "transactions": int(n),
            "amount_z": round(z_amt, 2),
            "burst_z": round(z_burst, 2),
            "max_txns_in_1h": int(burst[acc]),
            "pass_through_latency_min": latency_min,
            "flags": flags,
        }
    return out
