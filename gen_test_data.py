import random, csv
from datetime import datetime, timedelta

random.seed(42)
cities = ["Mumbai", "Delhi", "Chennai", "Bengaluru", "Hyderabad", "Kolkata", "Pune"]
accts = [f"ACC_{i}" for i in range(1000, 3000)]
ip_of = {a: f"10.{random.randint(0,20)}.{random.randint(0,255)}.{random.randint(1,254)}" for a in accts}
city_of = {a: random.choice(cities) for a in accts}

# planted mule ring: 6 accounts sharing one IP
ring = accts[:6]
for a in ring:
    ip_of[a] = "172.16.99.7"
dealer, sink = "ACC_9001", "ACC_9002"
ip_of[dealer] = "172.16.99.7"; city_of[dealer] = "Hyderabad"
ip_of[sink] = "203.0.113.5";   city_of[sink] = "Delhi"

t0 = datetime(2026, 1, 1)
rows = []
for i in range(20000):
    s, r = random.sample(accts, 2)
    rows.append([s, r, random.randint(500, 60000),
                 (t0 + timedelta(minutes=i * 7)).strftime("%Y-%m-%d %H:%M:%S"),
                 ip_of[s], city_of[s]])

# planted layering: ring -> dealer -> sink, quick pass-through
for k, a in enumerate(ring):
    ts = t0 + timedelta(days=10, minutes=k * 20)
    rows.append([a, dealer, 95000, ts.strftime("%Y-%m-%d %H:%M:%S"), ip_of[a], city_of[a]])
    rows.append([dealer, sink, 90000, (ts + timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"), ip_of[dealer], city_of[dealer]])

with open("test_dataset_20k.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["sender_id", "receiver_id", "amount", "timestamp", "sender_ip", "sender_city"])
    w.writerows(rows)
print("wrote", len(rows), "rows")
