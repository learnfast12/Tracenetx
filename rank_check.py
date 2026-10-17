import json, urllib.request
from collections import Counter

r = json.load(urllib.request.urlopen("http://localhost:8001/ml/analyze", timeout=600))
res = sorted(r["results"], key=lambda x: -x["risk_score"])
n = len(res)
print("accounts scored:", n)
print("by level:", dict(Counter(x["risk_level"] for x in res)))

planted = {"ACC_9001": "dealer", "ACC_9002": "sink", **{f"ACC_{i}": "ring" for i in range(1000, 1006)}}
print(f"\nplanted accounts (rank out of {n}):")
for rank, x in enumerate(res, 1):
    if x["account_id"] in planted:
        print(f"  #{rank:<5} {x['account_id']}  {planted[x['account_id']]:<7} score={x['risk_score']}  {x['risk_level']}")

print("\ntop 10:")
for x in res[:10]:
    print(" ", x["account_id"], x["risk_score"], x["risk_level"])

top20 = {x["account_id"] for x in res[:20]}
print("\nplanted in top 20:", len(top20 & set(planted)), "of", len(planted))
