# 3-minute demo script (PS-01)

**Before you start:** `docker start neo4j` (wait 20 s) → backend → frontend. Open `localhost:8001/health` — expect `"status":"ok"`.
Have a backup screen recording ready in case the venue network or laptop misbehaves.

**0:00 — The problem (20 s).** "Banks catch mules with fixed thresholds. Criminals split transfers under the limit; honest traders trip the rules.
We measured it: tuned rules rank mules barely better than chance (AUROC ~0.6)."

**0:20 — Prioritised leads (40 s).** *Investigation tab.* "27 complaints, 12 accounts named. We don't just list them — we rank.
Top lead is **DEALER1**, an account **no victim ever paid**. It got there because victim money, traced forward in time, converges on it:
₹2.37 lakh from 26 complaints." Point at the three sub-score bars: ML, complaints, baseline. "Nothing is a black box."

**1:00 — Money trail + timeline (50 s).** Click **Timeline + money trail** on DEALER1. "Money in, money out within hours — the dwell time is the signature.
Red diamonds are complaints. Below: the heaviest chain from a victim-hit mule through the shell company to the dealer, with timestamps and traceable amounts."

**1:50 — Why we trust it (30 s).** Open `/ml/model-info`. "The model is trained on labelled simulated rings and *scores* your data — it never learns from the data it judges.
SHAP tells the investigator *why* each account scored high." Show the Spider Map: roles come from graph shape, not from account names.

**2:20 — Hand-off to law enforcement (30 s).** Click **Incident report (PDF)** on INC-001 → print preview. "One page: victims, loss, accounts, the chain, the timeline, recommended action —
and a plain-language note that these are leads, not proof."

**2:50 — Close (10 s).** "On a held-out synthetic benchmark an investigator reviews ~90 accounts to find 80% of mules, versus ~900 with rules.
It's synthetic; real-data validation with a bank partner is our next step."

## Likely judge questions
- *"Is the benchmark real?"* No — synthetic, disclosed on `/benchmark` and in the README. Same simulator trains the model, but test networks are different accounts and rings.
- *"Do complaints improve accuracy?"* Barely on AUROC. They drive prioritisation and find collectors the classifier alone can't justify.
- *"What if Neo4j is down?"* App degrades; only graph views are disabled (`/health` says so).
- *"Can criminals just rename accounts?"* Roles and scores never read account names — tests enforce this for roles.
