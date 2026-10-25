import sqlite3, random
from datetime import datetime, timedelta

CLASSES = ["authorized", "unknown", "visitor", "delivery-person",
           "facecovered", "photo-spoof", "loitering"]
EXPECTED = {"authorized": "ACCESS GRANTED", "visitor": "NOTIFY OWNER",
            "delivery-person": "NOTIFY OWNER"}
DECISIONS = ["ACCESS GRANTED", "ACCESS DENIED", "NOTIFY OWNER", "LOITERING ALERT"]

conn = sqlite3.connect("demo_log.db")
conn.executescript("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, label TEXT NOT NULL,
    confidence REAL NOT NULL, decision TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS live_trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, actual TEXT NOT NULL,
    predicted TEXT NOT NULL, confidence REAL NOT NULL, decision TEXT NOT NULL,
    expected TEXT NOT NULL, correct INTEGER NOT NULL);
DELETE FROM events;
DELETE FROM live_trials;
""")

now = datetime.now()
for i in range(25):
    cls = random.choice(CLASSES)
    decision = EXPECTED.get(cls, "ACCESS DENIED")
    ts = (now - timedelta(minutes=5 * (25 - i))).isoformat(timespec="seconds")
    conn.execute("INSERT INTO events (timestamp, label, confidence, decision) VALUES (?,?,?,?)",
                 (ts, cls, round(random.uniform(0.72, 0.98), 3), decision))

for cls in CLASSES:
    expected = EXPECTED.get(cls, "ACCESS DENIED")
    for _ in range(20):
        good = random.random() < 0.85
        decision = expected if good else random.choice([d for d in DECISIONS if d != expected])
        predicted = cls if good else random.choice([c for c in CLASSES if c != cls])
        conn.execute("INSERT INTO live_trials (timestamp, actual, predicted, confidence, "
                     "decision, expected, correct) VALUES (?,?,?,?,?,?,?)",
                     (now.isoformat(timespec="seconds"), cls, predicted,
                      round(random.uniform(0.7, 0.98), 3), decision, expected, int(good)))
conn.commit()
conn.close()
print("demo_log.db created with fake data")