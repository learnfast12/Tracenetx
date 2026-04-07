from neo4j import GraphDatabase
import pandas as pd

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")
driver = GraphDatabase.driver(URI, auth=AUTH)

def init_db():
    df = pd.read_csv("transactions.csv")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        for _, row in df.iterrows():
            session.run("""
                MERGE (s:Account {id: $sender})
                MERGE (r:Account {id: $receiver})
                CREATE (s)-[:TRANSFER {
                    amount: $amount,
                    timestamp: $timestamp,
                    sender_ip: $ip,
                    sender_phone: $phone,
                    sender_city: $city,
                    case_id: $case_id
                }]->(r)
            """, sender=row["sender_id"], receiver=row["receiver_id"],
                 amount=float(row["amount"]), timestamp=row["timestamp"],
                 ip=row["sender_ip"], phone=str(row["sender_phone"]),
                 city=row["sender_city"], case_id=row["case_id"])

def get_graph_data(case_id=None):
    with driver.session() as session:
        if case_id:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER {case_id: $case_id}]->(r:Account)
                RETURN s.id as source, r.id as target,
                       t.amount as amount, t.sender_ip as ip, t.sender_city as city
            """, case_id=case_id)
        else:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                RETURN s.id as source, r.id as target,
                       t.amount as amount, t.sender_ip as ip, t.sender_city as city
            """)
        nodes = set()
        edges = []
        for record in result:
            nodes.add(record["source"])
            nodes.add(record["target"])
            edges.append({"source": record["source"], "target": record["target"],
                          "amount": record["amount"], "ip": record["ip"], "city": record["city"]})
        from risk import calculate_risk
        return {
            "nodes": [{"id": n, "risk": calculate_risk(n)} for n in nodes],
            "edges": edges
        }

def get_account_details(account_id: str):
    with driver.session() as session:
        incoming = session.run("""
            MATCH (s:Account)-[t:TRANSFER]->(r:Account {id: $id})
            RETURN s.id as sender, t.amount as amount,
                   t.sender_ip as ip, t.sender_city as city, t.timestamp as timestamp
        """, id=account_id).data()
        outgoing = session.run("""
            MATCH (s:Account {id: $id})-[t:TRANSFER]->(r:Account)
            RETURN r.id as receiver, t.amount as amount, t.timestamp as timestamp
        """, id=account_id).data()
        return {
            "id": account_id,
            "incoming": incoming,
            "outgoing": outgoing,
            "total_incoming": sum(r["amount"] for r in incoming),
            "total_outgoing": sum(r["amount"] for r in outgoing)
        }
