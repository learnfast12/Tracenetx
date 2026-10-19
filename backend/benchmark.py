"""Reproducible benchmark: TraceNetX vs the threshold rules the problem statement says banks use today.

    python3 benchmark.py                 # full run, prints a table, writes benchmark_results.json
    python3 benchmark.py --quick         # 1 seed per setting (smoke test)

Protocol (no leakage):
  * train on simulated networks with seeds {1,2}; test on DIFFERENT networks with seeds {11,12,13}
    (different accounts, different rings - the model never sees a test account)
  * victims and settlement sinks are external parties and are not scored
  * two criminal behaviours: naive (evasion 0.0) and evasive (evasion 1.0: structuring under the cap)
  * four detectors:  Threshold rules | ML behavioural | + graph structure | + complaint taint (full TraceNetX)

DISCLOSURE: the world is synthetic and authored by us (see simulator.py). It measures typology coverage,
not real-world accuracy.
"""
import json
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

warnings.filterwarnings("ignore")

from features import BEHAVIOURAL, COMPLAINT, STRUCTURAL, build_features
from simulator import simulate

TRAIN_SEEDS, TEST_SEEDS = [1, 2], [11, 12, 13]


# ── baseline: what banks run today ───────────────────────────────────────────────────────────
GRID = {"single": [20000, 30000, 50000, 75000, 100000], "count": [5, 8, 10, 15, 20],
        "daysum": [50000, 100000, 200000, 300000]}


def rule_inputs(df: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    t = df[["sender_id", "amount", "timestamp"]].copy()
    t["day"] = pd.to_datetime(t["timestamp"]).dt.floor("D")
    daily = t.groupby(["sender_id", "day"])["amount"].agg(["sum", "size"]).groupby("sender_id").max()
    f = feats.set_index("account_id")
    return pd.DataFrame({"single": f["max_out"], "count": daily["size"].reindex(f.index).fillna(0),
                         "daysum": daily["sum"].reindex(f.index).fillna(0)})


def apply_rules(inp: pd.DataFrame, th: dict) -> pd.Series:
    hits = ((inp["single"] >= th["single"]).astype(int) + (inp["count"] >= th["count"]).astype(int)
            + (inp["daysum"] >= th["daysum"]).astype(int))
    margin = (inp["single"] / th["single"] + inp["count"] / th["count"] + inp["daysum"] / th["daysum"]) / 3
    return hits + margin / (margin.max() + 1e-9) * 0.5      # rank by hits, then by how far past the thresholds


def tune_thresholds(train_inputs: pd.DataFrame, y: np.ndarray) -> dict:
    """Give the baseline its best shot: pick the 3 thresholds that maximise F1 on the TRAINING networks."""
    best, best_f1 = None, -1.0
    for a in GRID["single"]:
        for b in GRID["count"]:
            for c in GRID["daysum"]:
                flag = ((train_inputs["single"] >= a) | (train_inputs["count"] >= b) | (train_inputs["daysum"] >= c)).to_numpy()
                tp = (flag & (y == 1)).sum()
                f1 = 2 * tp / max(flag.sum() + y.sum(), 1)
                if f1 > best_f1:
                    best, best_f1 = {"single": a, "count": b, "daysum": c}, f1
    return best


# ── data helpers ─────────────────────────────────────────────────────────────────────────────
def scorable(truth: pd.DataFrame) -> set:
    ok = truth[(truth["role"] != "VICTIM") & (~truth["account_id"].str.startswith("SETTLE_"))]
    return set(ok["account_id"])


def make(seed, evasion, **sim_kw):
    df, comp, truth = simulate(seed=seed, evasion=evasion, **sim_kw)
    feats = build_features(df, comp)
    keep = scorable(truth)
    feats = feats[feats["account_id"].isin(keep)].merge(truth[["account_id", "is_mule"]], on="account_id").reset_index(drop=True)
    return df, comp, feats, rule_inputs(df, feats)


def fit_predict(train, test, cols):
    import lightgbm as lgb
    import xgboost as xgb
    X, y = train[cols].to_numpy(float), train["is_mule"].to_numpy()
    spw = (len(y) - y.sum()) / max(y.sum(), 1)
    m1 = xgb.XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9,
                           scale_pos_weight=spw, eval_metric="logloss", n_jobs=2, random_state=0, verbosity=0)
    m2 = lgb.LGBMClassifier(n_estimators=250, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9,
                            scale_pos_weight=spw, n_jobs=2, random_state=0, verbose=-1)
    m1.fit(X, y)
    m2.fit(X, y)
    Xt = test[cols].to_numpy(float)
    return (m1.predict_proba(Xt)[:, 1] + m2.predict_proba(Xt)[:, 1]) / 2, m1


def metrics(y, s, flag=None):
    y, s = np.asarray(y), np.asarray(s, float)
    k = int(y.sum())
    order = np.argsort(-s, kind="stable")
    topk = y[order][:k]
    cum = np.cumsum(y[order])
    need = int(np.searchsorted(cum, 0.8 * k) + 1)       # accounts an investigator reads to recover 80% of mules
    out = {"auroc": float(roc_auc_score(y, s)), "avg_precision": float(average_precision_score(y, s)),
           "precision_at_k": float(topk.mean()), "recall@k": float(topk.sum() / k),
           "reviewed_for_80pct_recall": need, "pool": int(len(y)), "mules": k}
    if flag is not None:
        flag = np.asarray(flag).astype(bool)
        tp = int((flag & (y == 1)).sum())
        out["flag_precision"] = float(tp / max(flag.sum(), 1))
        out["flag_recall"] = float(tp / k)
        out["flag_false_positives"] = int((flag & (y == 0)).sum())
    return out


SETTINGS = [
    ("naive criminals", dict(evasion=0.0)),
    ("evasive criminals (structuring under the cap)", dict(evasion=1.0)),
    ("STRESS: every mule stealthy + structuring, 50% complaint rate", dict(evasion=1.0, stealth=1.0, complaint_rate=0.5)),
]
DETECTORS = ["Threshold rules (tuned)", "ML behavioural", "ML + graph structure", "TraceNetX full (+complaint taint)"]


def run(quick=False):
    train_seeds = TRAIN_SEEDS[:1] if quick else TRAIN_SEEDS
    test_seeds = TEST_SEEDS[:1] if quick else TEST_SEEDS
    results = {}
    for label, kw in SETTINGS:
        tr = [make(s, **kw) for s in train_seeds]
        train = pd.concat([x[2] for x in tr], ignore_index=True)
        train_inp = pd.concat([x[3] for x in tr], ignore_index=True)
        th = tune_thresholds(train_inp, train["is_mule"].to_numpy())
        per = {k: [] for k in DETECTORS}
        for s in test_seeds:
            df, comp, test, inp = make(s, **kw)
            y = test["is_mule"].to_numpy()
            sc = apply_rules(inp, th).reindex(test["account_id"]).to_numpy()
            per[DETECTORS[0]].append(metrics(y, sc, flag=(sc >= 1)))
            for name, cols in zip(DETECTORS[1:], [BEHAVIOURAL, BEHAVIOURAL + STRUCTURAL,
                                                  BEHAVIOURAL + STRUCTURAL + COMPLAINT]):
                p, _ = fit_predict(train, test, cols)
                per[name].append(metrics(y, p, flag=p >= 0.5))
        results[label] = {name: {k: round(float(np.mean([r[k] for r in runs])), 3) for k in runs[0]}
                          for name, runs in per.items()}
        results[label]["_settings"] = {"train_seeds": train_seeds, "test_seeds": test_seeds,
                                       "tuned_thresholds": th, "train_rows": int(len(train))}
    return results


def show(results):
    for setting, table in results.items():
        print(f"\n=== {setting} ===")
        print(f"{'detector':38} {'AUROC':>6} {'AvgPrec':>8} {'P@k':>6} {'Recall@k':>9} {'read for 80%':>13} {'flag P':>7} {'flag R':>7} {'flag FP':>8}")
        for name, m in table.items():
            if name.startswith("_"):
                continue
            print(f"{name:38} {m['auroc']:>6.3f} {m['avg_precision']:>8.3f} {m['precision_at_k']:>6.3f} "
                  f"{m['recall@k']:>9.3f} {m['reviewed_for_80pct_recall']:>13.0f} {m.get('flag_precision', 0):>7.3f} "
                  f"{m.get('flag_recall', 0):>7.3f} {m.get('flag_false_positives', 0):>8.0f}")
        print(f"baseline thresholds tuned on training networks: {table['_settings']['tuned_thresholds']}")
        any_m = next(v for k, v in table.items() if not k.startswith("_"))
        print(f"(pool {any_m['pool']:.0f} accounts per test network, {any_m['mules']:.0f} true mules)")


if __name__ == "__main__":
    res = run(quick="--quick" in sys.argv)
    show(res)
    with open("benchmark_results.json", "w") as fh:
        json.dump(res, fh, indent=1)
    print("\nwrote benchmark_results.json")
