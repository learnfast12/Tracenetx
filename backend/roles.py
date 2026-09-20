"""Structural role classifier: account -> role, from transaction-graph shape only.
Never reads account names, so renaming an account cannot change its role."""
import statistics
import pandas as pd


def assign_roles(df: pd.DataFrame) -> dict:
    d = df[["sender_id", "receiver_id", "amount"]].copy()
    d["amount"] = pd.to_numeric(d["amount"], errors="coerce").fillna(0)
    d = d[d["sender_id"] != d["receiver_id"]]

    ids = set(d["sender_id"]) | set(d["receiver_id"])
    out_amt = d.groupby("sender_id")["amount"].sum().to_dict()
    in_amt = d.groupby("receiver_id")["amount"].sum().to_dict()
    out_deg = d.groupby("sender_id")["receiver_id"].nunique().to_dict()
    in_deg = d.groupby("receiver_id")["sender_id"].nunique().to_dict()
    senders_of = d.groupby("receiver_id")["sender_id"].apply(set).to_dict()

    def fwd(a):
        i = in_amt.get(a, 0)
        return out_amt.get(a, 0) / i if i else 0

    # CRIMINAL: pure origin of funds (nothing comes in), big fan-out, big volume
    med_out = statistics.median(out_amt.values()) if out_amt else 0
    sources = {a for a in ids
               if in_deg.get(a, 0) == 0 and out_deg.get(a, 0) >= 2
               and out_amt.get(a, 0) >= 2 * med_out}

    # RECRUITER: fed directly by a source, fans out to many accounts
    recruiters = {a for a in ids - sources
                  if out_deg.get(a, 0) >= 3 and senders_of.get(a, set()) & sources}

    # INTERMEDIARY (hawala / shell): many senders in, nearly everything forwarded out
    agg = {a for a in ids - sources - recruiters
           if in_deg.get(a, 0) >= 3 and out_deg.get(a, 0) >= 1
           and 0.85 <= fwd(a) <= 1.15}

    # DEALER: the convergence point that the intermediaries themselves feed into
    dealer = None
    if len(agg) >= 2:
        top = max(agg, key=lambda a: in_amt.get(a, 0))
        if senders_of.get(top, set()) & (agg - {top}):
            dealer = top

    # CRYPTO / exit: terminal account fed only by the dealer
    crypto = {a for a in ids
              if dealer and out_deg.get(a, 0) == 0
              and senders_of.get(a, set()) == {dealer}}

    roles = {}
    for a in ids:
        if a in sources:
            roles[a] = "CRIMINAL"
        elif a in recruiters:
            roles[a] = "RECRUITER"
        elif a == dealer:
            roles[a] = "DEALER"
        elif a in agg:
            roles[a] = "INTERMEDIARY"
        elif a in crypto:
            roles[a] = "CRYPTO"
        else:
            roles[a] = "MULE"
    return roles
