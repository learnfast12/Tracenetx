"""Graph evidence score (0-100) from transaction structure only. Never reads account names.
Blended with the ML score so a structural hub can't come out 'Safe'."""
import pandas as pd
from roles import assign_roles


def graph_evidence(df: pd.DataFrame) -> dict:
    d = df[["sender_id", "receiver_id", "amount"]].copy()
    d["amount"] = pd.to_numeric(d["amount"], errors="coerce").fillna(0)
    d = d[d["sender_id"] != d["receiver_id"]]

    ids = set(d["sender_id"]) | set(d["receiver_id"])
    in_amt = d.groupby("receiver_id")["amount"].sum()
    out_amt = d.groupby("sender_id")["amount"].sum()
    in_deg = d.groupby("receiver_id")["sender_id"].nunique()
    out_deg = d.groupby("sender_id")["receiver_id"].nunique()
    roles = assign_roles(df)

    vol = pd.Series({a: in_amt.get(a, 0) + out_amt.get(a, 0) for a in ids})
    vol_pct = vol.rank(pct=True) * 100

    out = {}
    for a in ids:
        i, o = in_amt.get(a, 0), out_amt.get(a, 0)
        di, do = in_deg.get(a, 0), out_deg.get(a, 0)
        fwd = o / i if i else 0
        s_pass = max(0, 1 - abs(1 - fwd) / 0.5) * 100 if di >= 2 else 0   # near-total pass-through
        s_source = 100 if di == 0 and do >= 2 else 0                        # pure origin of funds
        s_fan = min(max(di / 4, do / 6), 1) * 100                           # fan-in / fan-out
        s_role = 0 if roles[a] == "MULE" else 100                           # structural role found
        score = 0.30 * vol_pct[a] + 0.25 * max(s_pass, s_source) + 0.20 * s_fan + 0.25 * s_role
        out[a] = {"score": round(float(score), 2), "role": roles[a]}
    return out
