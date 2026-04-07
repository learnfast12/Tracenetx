import pandas as pd
df = pd.read_csv("transactions.csv")

def calculate_risk(account_id: str):
    score = 0
    flags = []
    incoming = df[df["receiver_id"] == account_id]
    outgoing = df[df["sender_id"] == account_id]

    # Flag 1: sends to 3+ accounts (structuring) +35
    unique_receivers = outgoing["receiver_id"].nunique()
    if unique_receivers >= 3:
        score += 35
        flags.append(f"Sends to {unique_receivers} accounts (structuring)")

    # Flag 2: receives from 2+ senders sharing same IP +30
    if len(incoming) >= 2:
        unique_ips = incoming["sender_ip"].nunique()
        if unique_ips == 1:
            score += 30
            flags.append("Multiple senders share same IP")

    # Flag 3: rapid outgoing bursts +20
    if len(outgoing) >= 2:
        try:
            times = pd.to_datetime(outgoing["timestamp"]).sort_values()
            span = (times.iloc[-1] - times.iloc[0]).total_seconds() / 60
            if span <= 60:
                score += 20
                flags.append(f"Rapid transfers in {int(span)} mins")
        except:
            pass

    # Flag 4: high total outgoing volume +15
    total_out = outgoing["amount"].sum()
    if total_out > 100000:
        score += 15
        flags.append(f"Total outflow ₹{int(total_out/1000)}K")

    # Flag 5: multi-city pattern +10
    if len(outgoing) >= 2:
        cities = outgoing["sender_city"].nunique()
        if cities >= 2:
            score += 10
            flags.append(f"Transactions across {cities} cities")

    if score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {"score": min(score, 100), "level": level, "flags": flags}
