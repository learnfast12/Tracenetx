from neo4j import GraphDatabase
import pandas as pd
from collections import defaultdict

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")
driver = GraphDatabase.driver(URI, auth=AUTH)

class GraphIntelligence:

    def reverse_chain_analysis(self, account_id: str):
        """Trace backwards from exit point to find coordinator"""
        with driver.session() as session:
            result = session.run("""
                MATCH path = (source:Account)-[:TRANSFER*1..5]->(target:Account {id: $id})
                RETURN [node in nodes(path) | node.id] as chain,
                       [rel in relationships(path) | rel.amount] as amounts,
                       length(path) as hops
                ORDER BY hops DESC
                LIMIT 10
            """, id=account_id)

            chains = []
            for record in result:
                chains.append({
                    "chain": record["chain"],
                    "amounts": record["amounts"],
                    "hops": record["hops"],
                    "entry_point": record["chain"][0],
                    "exit_point": record["chain"][-1]
                })

            return {
                "target_account": account_id,
                "reverse_chains": chains,
                "total_chains_found": len(chains),
                "analysis": f"Found {len(chains)} inbound chains. Coordinator likely at entry points."
            }

    def community_detection(self):
        """Find mule clusters converging to same destination"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[:TRANSFER]->(hub:Account)
                WITH hub, collect(s.id) as senders, count(*) as inbound
                WHERE inbound >= 2
                RETURN hub.id as coordinator,
                       senders,
                       inbound
                ORDER BY inbound DESC
                LIMIT 10
            """)

            communities = []
            for record in result:
                communities.append({
                    "coordinator": record["coordinator"],
                    "mule_accounts": record["senders"],
                    "inbound_count": record["inbound"],
                    "threat_level": "CRITICAL" if record["inbound"] >= 4 else "HIGH"
                })

            return {
                "communities_detected": len(communities),
                "clusters": communities,
                "analysis": f"Detected {len(communities)} mule clusters converging to coordinator nodes"
            }

    def coordination_detection(self):
        """Detect synchronized transaction timing — coordination signal"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                RETURN t.timestamp as timestamp,
                       s.id as sender,
                       r.id as receiver,
                       t.amount as amount
                ORDER BY t.timestamp
            """)

            records = result.data()
            if not records:
                return {"coordinated_bursts": [], "analysis": "No coordination detected"}

            df = pd.DataFrame(records)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')

            # Find accounts transferring within same 2-hour window
            bursts = []
            for i, row in df.iterrows():
                window_start = row['timestamp']
                window_end = window_start + pd.Timedelta(hours=2)
                window_txns = df[
                    (df['timestamp'] >= window_start) &
                    (df['timestamp'] <= window_end)
                ]
                if len(window_txns) >= 3:
                    bursts.append({
                        "window_start": str(window_start),
                        "window_end": str(window_end),
                        "accounts_involved": list(window_txns['sender'].unique()),
                        "transaction_count": len(window_txns),
                        "total_amount": float(window_txns['amount'].sum()),
                        "alert": "COORDINATION SIGNAL — multiple accounts transacting in same 2hr window"
                    })

            unique_bursts = []
            seen = set()
            for b in bursts:
                key = b['window_start'][:13]
                if key not in seen:
                    seen.add(key)
                    unique_bursts.append(b)

            return {
                "coordinated_bursts": unique_bursts[:5],
                "total_bursts_detected": len(unique_bursts),
                "analysis": f"Detected {len(unique_bursts)} coordination windows"
            }

    def batch_recruitment_detection(self):
        """Find accounts opened same time, same location — recruitment batch"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                RETURN s.id as account,
                       t.sender_city as city,
                       t.sender_ip as ip,
                       t.timestamp as timestamp
            """)

            records = result.data()
            if not records:
                return {"recruitment_batches": [], "analysis": "No batches detected"}

            df = pd.DataFrame(records)

            # Group by city + IP — same location = possible recruitment batch
            batches = df.groupby(['city', 'ip']).agg(
                accounts=('account', lambda x: list(set(x))),
                count=('account', 'nunique')
            ).reset_index()

            recruitment_batches = []
            for _, row in batches[batches['count'] >= 2].iterrows():
                recruitment_batches.append({
                    "city": row['city'],
                    "shared_ip": row['ip'],
                    "accounts": row['accounts'],
                    "account_count": row['count'],
                    "alert": f"BATCH RECRUITMENT — {row['count']} accounts from same city+IP"
                })

            return {
                "recruitment_batches": recruitment_batches,
                "total_batches": len(recruitment_batches),
                "analysis": f"Found {len(recruitment_batches)} potential recruitment batches"
            }

    def convergence_analysis(self):
        """Find the lieutenant — account receiving from multiple independent clusters"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[:TRANSFER*1..3]->(hub:Account)
                WITH hub, collect(DISTINCT s.id) as sources, count(DISTINCT s) as source_count
                WHERE source_count >= 3
                RETURN hub.id as potential_lieutenant,
                       sources,
                       source_count
                ORDER BY source_count DESC
                LIMIT 5
            """)

            lieutenants = []
            for record in result:
                lieutenants.append({
                    "account": record["potential_lieutenant"],
                    "connected_sources": record["sources"],
                    "source_count": record["source_count"],
                    "threat": "LIEUTENANT NODE — receives from multiple independent chains"
                })

            return {
                "potential_lieutenants": lieutenants,
                "analysis": f"Identified {len(lieutenants)} potential lieutenant/coordinator nodes"
            }

    def identity_fusion(self):
        """Link accounts sharing IP, phone, or city"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s1:Account)-[t1:TRANSFER]->(x)
                MATCH (s2:Account)-[t2:TRANSFER]->(y)
                WHERE s1.id <> s2.id
                AND t1.sender_ip = t2.sender_ip
                RETURN s1.id as account1,
                       s2.id as account2,
                       t1.sender_ip as shared_ip,
                       t1.sender_city as city
                LIMIT 20
            """)

            fusions = []
            seen = set()
            for record in result:
                key = tuple(sorted([record['account1'], record['account2']]))
                if key not in seen:
                    seen.add(key)
                    fusions.append({
                        "account1": record['account1'],
                        "account2": record['account2'],
                        "shared_ip": record['shared_ip'],
                        "city": record['city'],
                        "alert": "IDENTITY FUSION — accounts share same IP address"
                    })

            return {
                "identity_links": fusions,
                "total_links": len(fusions),
                "analysis": f"Found {len(fusions)} identity fusion links across accounts"
            }

    def full_intelligence_report(self, account_id: str = None):
        """Run all intelligence layers and return complete report"""
        report = {
            "community_detection": self.community_detection(),
            "coordination_detection": self.coordination_detection(),
            "batch_recruitment": self.batch_recruitment_detection(),
            "convergence_analysis": self.convergence_analysis(),
            "identity_fusion": self.identity_fusion(),
        }
        if account_id:
            report["reverse_chain"] = self.reverse_chain_analysis(account_id)

        return report

# Global instance
graph_intel = GraphIntelligence()
