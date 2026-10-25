import sqlite3

conn = sqlite3.connect("gate_log.db")

total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
print(f"Total events: {total}\n")

print(f"{'Decision':<20}{'Count':>6}")
for decision, n in conn.execute(
        "SELECT decision, COUNT(*) FROM events GROUP BY decision ORDER BY COUNT(*) DESC"):
    print(f"{decision:<20}{n:>6}")

print("\nLast 10 events")
print(f"{'Time':<21}{'Label':<17}{'Conf':>6}  Decision")
for ts, label, conf, decision in conn.execute(
        "SELECT timestamp, label, confidence, decision FROM events ORDER BY id DESC LIMIT 10"):
    print(f"{ts:<21}{label:<17}{conf:>6.2f}  {decision}")

conn.close()