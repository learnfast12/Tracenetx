"""
soa_loader.py - turn the C-DAC statement-of-account (SOA) files into TraceNetX inputs.

Usage:
    python3 soa_loader.py <folder-with-*_SOA.xls*> [out_dir]

Writes (to out_dir, default ./soa_out):
    soa_edges.csv        rows that name a counterparty account -> graph edges
                         (sender_id, receiver_id, amount, timestamp, transfer_type, case_id, ...)
    soa_holder_flows.csv rows with NO counterparty column (files 2,4,5,6) -> holder-level behaviour only
    soa_summary.json     counts per file, so you can sanity check

Privacy: holder names are hashed to ids (H_xxxxxx). Names/PAN never leave the input files.
DO NOT commit the input files or the generated CSVs to git.
"""
import glob
import hashlib
import json
import os
import re
import sys

import pandas as pd

ICORE_REQUIRED = {"Ac_No", "AC_Name", "Dr_Amt", "Cr_Amt", "pstd_dt"}


def holder_id(name) -> str:
    return "H_" + hashlib.sha1(str(name).strip().lower().encode()).hexdigest()[:6].upper()


def channel_of(narr) -> str:
    s = str(narr or "")
    for p in ("UPI", "MMT/IMPS", "IMPS", "NEFT", "RTGS", "ACH", "BIL", "INF", "ATL", "ATM", "CHQ", "CLG"):
        if s.upper().startswith(p):
            return "UPI" if p == "UPI" else ("IMPS" if "IMPS" in p else ("CASH" if p in ("ATL", "ATM") else "DIGITAL"))
    return "DIGITAL"


def num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def parse_ts_icore(s):
    # 24JUL2020:14:10:39
    return pd.to_datetime(s, format="%d%b%Y:%H:%M:%S", errors="coerce")


def read_any(path):
    d = pd.read_excel(path, sheet_name=0, header=None)
    return d


def header_row(d):
    for i in range(min(6, len(d))):
        vals = d.iloc[i].astype(str)
        if vals.str.contains(r"Dr_Amt|DEBIT AMOUNT|Debit_amount|Dr Cr", case=False, regex=True).any():
            return i
    return None


def with_header(d, h):
    out = d.iloc[h + 1:].copy()
    out.columns = [str(c) for c in d.iloc[h]]
    return out.reset_index(drop=True)


def to_rows(path, n):
    """returns (edges_df or None, flows_df or None, label)"""
    d = read_any(path)
    h = header_row(d)
    cols = None if h is None else {str(c) for c in d.iloc[h]}

    # --- ICORE-style (Ac_No per row = counterparty) -----------------------------------------
    if h is not None and ICORE_REQUIRED <= cols:
        t = with_header(d, h)
        hid = t["AC_Name"].map(holder_id)
        dr, cr = num(t["Dr_Amt"]), num(t["Cr_Amt"])
        cp = t["Ac_No"].astype(str).str.replace(r"\.0$", "", regex=True)
        ts = parse_ts_icore(t["pstd_dt"])
        return _edges(hid, cp, dr, cr, ts, t["Narration"], n), None, "icore"

    # --- file-1 style ------------------------------------------------------------------------
    if h is not None and "ACCOUNT NO" in cols:
        t = with_header(d, h)
        hid = t["CUSTOMER NAME"].map(holder_id)
        return _edges(hid, t["ACCOUNT NO"].astype(str), num(t["DEBIT AMOUNT"]), num(t["CREDIT AMOUNT"]),
                      pd.to_datetime(t["TRANSACTION DATE"], errors="coerce"), t["NARRATION"], n), None, "f1"

    # --- file-3 style ------------------------------------------------------------------------
    if h is not None and "Account No" in cols and "Dr Cr" in cols:
        t = with_header(d, h)
        hid = t["Account Name"].map(holder_id)
        amt = num(t["AMOUNT"])
        isd = t["Dr Cr"].astype(str).str.upper().str.startswith("D")
        dr, cr = amt.where(isd, 0.0), amt.where(~isd, 0.0)
        return _edges(hid, t["Account No"].astype(str), dr, cr,
                      pd.to_datetime(t["PSTD DATE"], errors="coerce"), t["TXN PARTICULARS"], n), None, "f3"

    # --- no-counterparty layouts -------------------------------------------------------------
    if h is not None and "Debit_amount" in cols:               # file 6
        t = with_header(d, h)
        hid = t["Customer_Name"].map(holder_id)
        dr, cr = num(t["Debit_amount"]), num(t["Credit_Amount"])
        ts = pd.to_datetime(t["Date_of_transaction"], format="%d-%m-%Y", errors="coerce")
        return None, _flows(hid, dr, cr, ts, t["Narration"], n), "f6"

    # files 2, 4, 5: headerless / odd header. col1=name, then a D/C flag col followed by amount.
    body = d.copy()
    # drop a header-ish first rows (strings in the amount column)
    flag_col = next((c for c in body.columns if body[c].astype(str).str.upper().isin(["D", "C"]).mean() > 0.9), None)
    if flag_col is not None:
        amt_col = flag_col + 1
        body = body[pd.to_numeric(body[amt_col], errors="coerce").notna()]
        hid = body[1].map(holder_id)
        amt = num(body[amt_col])
        isd = body[flag_col].astype(str).str.upper().eq("D")
        dr, cr = amt.where(isd, 0.0), amt.where(~isd, 0.0)
        narr = body[flag_col + 2 if flag_col + 2 in body.columns else flag_col + 1].astype(str)
        # best available date: the 4th column (0-based 3)
        ts = pd.to_datetime(body[3], errors="coerce")
        return None, _flows(hid, dr, cr, ts, narr, n), "headerless"
    return None, None, "UNRECOGNISED"


def _edges(hid, cp, dr, cr, ts, narr, n):
    hid, cp = hid.reset_index(drop=True), cp.reset_index(drop=True)
    dr, cr = dr.reset_index(drop=True), cr.reset_index(drop=True)
    ts, narr = ts.reset_index(drop=True), pd.Series(narr).reset_index(drop=True)
    rows = []
    out = dr > 0
    inn = cr > 0
    a = pd.DataFrame({"sender_id": hid[out], "receiver_id": cp[out], "amount": dr[out],
                      "timestamp": ts[out], "narration": narr[out]})
    b = pd.DataFrame({"sender_id": cp[inn], "receiver_id": hid[inn], "amount": cr[inn],
                      "timestamp": ts[inn], "narration": narr[inn]})
    e = pd.concat([a, b], ignore_index=True)
    e["transfer_type"] = e["narration"].map(channel_of)
    e["case_id"] = f"SOA{n:02d}"
    e["source_file"] = n
    return e.drop(columns=["narration"])


def _flows(hid, dr, cr, ts, narr, n):
    f = pd.DataFrame({"holder_id": hid.reset_index(drop=True), "debit": dr.reset_index(drop=True),
                      "credit": cr.reset_index(drop=True), "timestamp": ts.reset_index(drop=True),
                      "channel": pd.Series(narr).reset_index(drop=True).map(channel_of)})
    f["source_file"] = n
    return f


def main(folder, out_dir="soa_out"):
    os.makedirs(out_dir, exist_ok=True)
    files = [p for p in glob.glob(os.path.join(folder, "*_SOA.xls*")) if not os.path.basename(p).startswith("~$")]
    files.sort(key=lambda p: int(re.search(r"(\d+)_SOA", os.path.basename(p)).group(1)))
    edges, flows, summary = [], [], {}
    for p in files:
        n = int(re.search(r"(\d+)_SOA", os.path.basename(p)).group(1))
        try:
            e, f, kind = to_rows(p, n)
        except Exception as ex:                       # noqa: BLE001  keep going, report at end
            summary[n] = {"error": f"{type(ex).__name__}: {ex}"}
            print(f"[{n:>2}] ERROR {ex}")
            continue
        summary[n] = {"layout": kind, "edge_rows": 0 if e is None else len(e), "flow_rows": 0 if f is None else len(f)}
        print(f"[{n:>2}] {kind:<10} edges={summary[n]['edge_rows']:>7} flows={summary[n]['flow_rows']:>7}")
        if e is not None:
            edges.append(e)
        if f is not None:
            flows.append(f)
    E = pd.concat(edges, ignore_index=True) if edges else pd.DataFrame()
    F = pd.concat(flows, ignore_index=True) if flows else pd.DataFrame()
    if len(E):
        E = E.dropna(subset=["timestamp"]).sort_values("timestamp")
        E["timestamp"] = E["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    E.to_csv(os.path.join(out_dir, "soa_edges.csv"), index=False)
    F.to_csv(os.path.join(out_dir, "soa_holder_flows.csv"), index=False)
    summary["_totals"] = {"edge_rows": len(E), "flow_rows": len(F),
                          "holders": int(pd.concat([E.get("sender_id", pd.Series(dtype=str)),
                                                    E.get("receiver_id", pd.Series(dtype=str))]).str.startswith("H_").sum() and
                                         E["sender_id"].str.startswith("H_").sum() and
                                         E.loc[E["sender_id"].str.startswith("H_"), "sender_id"].nunique()) if len(E) else 0}
    with open(os.path.join(out_dir, "soa_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\nTOTAL edge rows:", len(E), "| holder-flow rows:", len(F), "->", out_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "soa_out")
