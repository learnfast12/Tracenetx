"""Deterministic synthetic complaints for the demo network (python3 generate_complaints.py).
Victim IDs are opaque tokens; no personal data. Amounts never exceed what the account received."""
import csv
import os
import random
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(404)

# account -> (number of complaints, scammer phone shared across the accounts that use it)
PLAN = {
    "ACC_4521": (3, "9876500001"), "ACC_7832": (2, "9876500001"), "ACC_2341": (2, "9876500001"),
    "ACC_9876": (3, "9876500002"), "ACC_6123": (2, "9876500002"), "ACC_8834": (2, "9876500002"),
    "ACC_3312": (3, "9876500003"), "ACC_5567": (2, "9876500003"), "ACC_1198": (2, "9876500003"),
    "ACC_4407": (2, "9876500004"), "ACC_6691": (1, "9876500004"), "ACC_2278": (1, "9876500004"),
}
FRAUD = ["UPI_COLLECT_FRAUD", "DIGITAL_ARREST", "INVESTMENT_SCAM", "JOB_SCAM", "KYC_FRAUD", "LOAN_APP_FRAUD"]
CHANNEL = ["NCRP_PORTAL", "HELPLINE_1930", "BANK_BRANCH"]
CITY = ["Chennai", "Pune", "Patna", "Lucknow", "Hyderabad", "Jaipur", "Kolkata", "Bengaluru"]

rows, vic = [], 0
t0 = datetime(2024, 1, 15, 12, 0)
for acc, (n, phone) in PLAN.items():
    for _ in range(n):
        vic += 1
        rows.append({
            "complaint_id": f"NCRP-24-{1000 + len(rows)}",
            "victim_id": f"VIC_{vic:04d}",
            "reported_account": acc,
            "amount_lost": rng.choice([8000, 12000, 15000, 20000, 25000, 30000, 40000]),
            "timestamp": (t0 + timedelta(hours=rng.randint(2, 120))).strftime("%Y-%m-%d %H:%M:%S"),
            "fraud_type": rng.choice(FRAUD),
            "channel": rng.choice(CHANNEL),
            "reported_phone": phone,
            "city": rng.choice(CITY),
        })

# one repeat victim hit twice, plus an account that is NOT in the transaction graph
rows.append({**rows[0], "complaint_id": "NCRP-24-9001", "amount_lost": 10000, "timestamp": "2024-01-19 10:30:00"})
rows.append({"complaint_id": "NCRP-24-9002", "victim_id": "VIC_9999", "reported_account": "ACC_UNLISTED_77",
             "amount_lost": 18000, "timestamp": "2024-01-18 15:00:00", "fraud_type": "KYC_FRAUD",
             "channel": "HELPLINE_1930", "reported_phone": "UNKNOWN", "city": "Mumbai"})

rows.sort(key=lambda r: r["timestamp"])
with open(os.path.join(BASE, "complaints.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"wrote {len(rows)} complaints")
