import os, cv2, time, sqlite3
from collections import deque, Counter
from datetime import datetime
from inference import get_model
from alerts import send_alert

API_KEY    = os.environ.get("ROBOFLOW_API_KEY", "YOUR_ROBOFLOW_API_KEY")
MODEL_ID   = "your-project/1"
DB_FILE    = "gate_log.db"
SNAP_DIR   = "snapshots"
CONF_MIN   = 0.70      # minimum average confidence to act
WINDOW     = 10        # frames used for smoothing
LOITER_SEC = 15        # non-authorized presence longer than this = alert
ALERT_COOLDOWN = 30    # seconds between phone alerts of the same type
EVIDENCE_DECISIONS = {"ACCESS DENIED", "NOTIFY OWNER", "LOITERING ALERT"}

os.makedirs(SNAP_DIR, exist_ok=True)

# --- Database setup (adds the snapshot column to an older database) ---
conn = sqlite3.connect(DB_FILE)
conn.execute("""CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    label         TEXT NOT NULL,
    confidence    REAL NOT NULL,
    decision      TEXT NOT NULL,
    snapshot_path TEXT
)""")
cols = [r[1] for r in conn.execute("PRAGMA table_info(events)")]
if "snapshot_path" not in cols:
    conn.execute("ALTER TABLE events ADD COLUMN snapshot_path TEXT")
conn.commit()

def log_event(label, conf, decision, snapshot_path=None):
    conn.execute(
        "INSERT INTO events (timestamp, label, confidence, decision, snapshot_path) "
        "VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), label, round(conf, 3),
         decision, snapshot_path))
    conn.commit()

# --- Model and state ---
model = get_model(model_id=MODEL_ID, api_key=API_KEY)
history = deque(maxlen=WINDOW)
presence_start = None
last_logged = None
last_alert = {}

def decide(label, conf):
    if conf < CONF_MIN:
        return "WAITING", (200, 200, 200)
    if label == "authorized":
        return "ACCESS GRANTED", (0, 200, 0)
    if label in ("visitor", "delivery-person"):
        return "NOTIFY OWNER", (0, 165, 255)
    # unknown, facecovered, photo-spoof, loitering
    return "ACCESS DENIED", (0, 0, 255)

# --- Main loop ---
cap = cv2.VideoCapture(0)
while True:
    ok, frame = cap.read()
    if not ok:
        break

    result = model.infer(frame)[0]
    history.append((result.top, result.confidence))

    # Smoothing: majority label over the last WINDOW frames
    labels = [l for l, _ in history]
    label = Counter(labels).most_common(1)[0][0]
    conf = sum(c for l, c in history if l == label) / labels.count(label)
    decision, color = decide(label, conf)

    # Loitering: non-authorized presence persisting over time
    if label != "authorized" and conf >= CONF_MIN:
        presence_start = presence_start or time.time()
        if time.time() - presence_start > LOITER_SEC:
            decision, color = "LOITERING ALERT", (0, 0, 255)
    else:
        presence_start = None

    # Log only when the decision changes
    if decision != last_logged and decision != "WAITING":
        snap = None
        if decision in EVIDENCE_DECISIONS:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snap = f"{SNAP_DIR}/{stamp}_{label}.jpg"
            cv2.imwrite(snap, frame)          # frame is still clean here
            if time.time() - last_alert.get(decision, 0) > ALERT_COOLDOWN:
                send_alert(f"{decision}: {label} ({conf:.0%}) at "
                           f"{datetime.now():%H:%M:%S}", snap)
                last_alert[decision] = time.time()
        log_event(label, conf, decision, snap)
        last_logged = decision

    cv2.putText(frame, f"{label} ({conf:.0%})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, decision, (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
    cv2.imshow("Smart Gate", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
conn.close()