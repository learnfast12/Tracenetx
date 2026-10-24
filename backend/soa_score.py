"""
soa_score.py - explainable, label-free mule-risk ranking over the C-DAC statements.

Usage:
    python3 soa_score.py [soa_out_dir] [top_n]

Reads  soa_edges.csv + soa_holder_flows.csv (from soa_loader.py)
Writes soa_ranked.csv  (one row per statement holder, with score + plain-English reasons)

No labels exist in this dataset, so this is UNSUPERVISED behavioural scoring, not a trained
classifier. Every score is a weighted average of percentile ranks, and every reason is a rule
a human investigator can check by hand.
"""
import sys

import numpy as np
import pandas as pd

WEIGHTS = {            # feature -> (weight, human reason)
    "passthrough": (0.30, "money in ~ money out (pass-through account)"),
    "fast_dwell":  (0.20, "credits are moved on within hours"),
    "fan":         (0.20, "many distinct counterparties (fan-in/fan-out)"),
    "burst":       (0.15, "bursty activity (peak day far above normal)"),
    "round":       (0.05, "unusually many round-number amounts"),
    "shared":      (0.10, "counterparties shared with another statement holder"),
}


def unify(edges, flows):
    h = edges.sender_id.astype(str).str.startswith("H_")
    out = edges[h].assign(holder=edges.sender_id[h], dir="OUT", cp=edges.receiver_id[h])
    inn = edges[~h].assign(holder=edges.receiver_id[~h], dir="IN", cp=edges.sender_id[~h])
    e = pd.concat([out, inn])[["holder", "dir", "amount", "timestamp", "cp", "transfer_type"]]
    f_out = flows[flows.debit > 0].assign(dir="OUT", amount=lambda d: d.debit)
    f_in = flows[flows.credit > 0].assign(dir="IN", amount=lambda d: d.credit)
    f = pd.concat([f_out, f_in]).rename(columns={"holder_id": "holder", "channel": "transfer_type"})
    f["cp"] = np.nan
    f = f[["holder", "dir", "amount", "timestamp", "cp", "transfer_type"]]
    u = pd.concat([e, f], ignore_index=True)
    u["ts"] = pd.to_datetime(u["timestamp"], errors="coerce")
    u.loc[(u.ts.dt.year < 2015) | (u.ts.dt.year > 2026), "ts"] = pd.NaT     # scrambled dates -> ignore
    return u


def median_dwell_hours(g):
    """median hours from a credit to the next debit; NaN if timestamps unusable."""
    g = g.dropna(subset=["ts"]).sort_values("ts")
    cr, dr = g[g.dir == "IN"][["ts"]], g[g.dir == "OUT"][["ts"]]
    if len(cr) < 20 or len(dr) < 20:
        return np.nan
    m = pd.merge_asof(cr, dr.rename(columns={"ts": "next_debit"}), left_on="ts", right_on="next_debit",
                      direction="forward")
    return ((m.next_debit - m.ts).dt.total_seconds() / 3600).median()


def features(u, shared_cps):
    rows = []
    for hid, g in u.groupby("holder"):
        tin, tout = g[g.dir == "IN"].amount.sum(), g[g.dir == "OUT"].amount.sum()
        has_cp = g.cp.notna().any()
        day = g.dropna(subset=["ts"]).groupby(g.ts.dt.date).size()
        rows.append({
            "holder": hid, "txns": len(g), "total_in": round(tin), "total_out": round(tout),
            "passthrough": (min(tin, tout) / max(tin, tout)) if max(tin, tout) > 0 else 0.0,
            "dwell_h": median_dwell_hours(g),
            "cp_in": g[(g.dir == "IN")].cp.nunique() if has_cp else np.nan,
            "cp_out": g[(g.dir == "OUT")].cp.nunique() if has_cp else np.nan,
            "burst": (day.max() / max(day.median(), 1)) if len(day) > 10 else np.nan,
            "round": ((g.amount >= 1000) & (g.amount % 1000 == 0)).mean(),
            "shared": g.cp.isin(shared_cps).mean() if has_cp else np.nan,
            "graph_coverage": "yes" if has_cp else "no (behaviour only)",
        })
    return pd.DataFrame(rows)


def score(F):
    F = F.copy()
    F["fan_raw"] = (F.cp_in.fillna(0) + F.cp_out.fillna(0)) / F.txns.clip(lower=1)
    F["fast_dwell_raw"] = -np.log1p(F.dwell_h)               # shorter dwell = higher risk
    raw = {"passthrough": F.passthrough, "fast_dwell": F.fast_dwell_raw, "fan": F.fan_raw,
           "burst": F.burst, "round": F["round"], "shared": F.shared}
    pct = pd.DataFrame({k: v.rank(pct=True) for k, v in raw.items()})   # NaN stays NaN (feature unavailable)
    w = pd.Series({k: WEIGHTS[k][0] for k in WEIGHTS})
    avail = pct.notna() * w
    F["risk_score"] = (100 * (pct.fillna(0) * w).sum(axis=1) / avail.sum(axis=1)).round(1)
    F["reasons"] = [
        "; ".join(WEIGHTS[k][1] for k in WEIGHTS if pd.notna(pct.loc[i, k]) and pct.loc[i, k] >= 0.75) or "no standout signal"
        for i in F.index]
    F["signals_used"] = avail.gt(0).sum(axis=1)
    return F.sort_values("risk_score", ascending=False)


def main(d="soa_out", top=15):
    E = pd.read_csv(f"{d}/soa_edges.csv")
    Fl = pd.read_csv(f"{d}/soa_holder_flows.csv")
    u = unify(E, Fl)
    # counterparties seen under 2+ holders
    cp_h = u.dropna(subset=["cp"]).groupby("cp").holder.nunique()
    shared = set(cp_h[cp_h > 1].index)
    R = score(features(u, shared))
    cols = ["holder", "risk_score", "txns", "total_in", "total_out", "passthrough", "dwell_h", "graph_coverage",
            "signals_used", "reasons"]
    R[cols].to_csv(f"{d}/soa_ranked.csv", index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    print(R[cols].head(top).round(2).to_string(index=False))
    print(f"\n{len(R)} holders scored -> {d}/soa_ranked.csv")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "soa_out", int(sys.argv[2]) if len(sys.argv) > 2 else 15)
