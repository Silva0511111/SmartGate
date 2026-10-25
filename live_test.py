import os, sys, cv2, time, sqlite3
from collections import Counter
from datetime import datetime
from inference import get_model

API_KEY   = os.environ.get("ROBOFLOW_API_KEY", "YOUR_ROBOFLOW_API_KEY")
MODEL_ID  = "your-project/1"
DB_FILE   = "gate_log.db"
CONF_MIN  = 0.70     # keep identical to smart_gate.py
READY_SEC = 3        # time to step into position
TRIAL_SEC = 3        # recording time per trial
TARGET    = 20       # trials per class

CLASSES = ["authorized", "unknown", "visitor", "delivery-person",
           "facecovered", "photo-spoof", "loitering"]
EXPECTED = {"authorized": "ACCESS GRANTED",
            "visitor": "NOTIFY OWNER",
            "delivery-person": "NOTIFY OWNER"}   # every other class: ACCESS DENIED

def expected_for(cls):
    return EXPECTED.get(cls, "ACCESS DENIED")

def decide(label, conf):   # keep identical to smart_gate.py
    if conf < CONF_MIN:
        return "WAITING"
    if label == "authorized":
        return "ACCESS GRANTED"
    if label in ("visitor", "delivery-person"):
        return "NOTIFY OWNER"
    return "ACCESS DENIED"

def put(img, text, y, color=(255, 255, 255), scale=0.7):
    cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2)

def summary(conn):
    print(f"\n{'Class':<18}{'Trials':>7}{'Correct':>9}{'Accuracy':>10}{'No decision':>13}")
    all_n = all_ok = 0
    for c in CLASSES:
        n, ok, wait = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(correct),0), "
            "COALESCE(SUM(decision='WAITING'),0) FROM live_trials WHERE actual=?",
            (c,)).fetchone()
        acc = f"{ok / n:.0%}" if n else "n/a"
        print(f"{c:<18}{n:>7}{ok:>9}{acc:>10}{wait:>13}")
        all_n += n
        all_ok += ok
    if all_n:
        print(f"{'OVERALL':<18}{all_n:>7}{all_ok:>9}{all_ok / all_n:>10.0%}")
    non_auth = conn.execute(
        "SELECT COUNT(*) FROM live_trials WHERE actual != 'authorized'").fetchone()[0]
    fa = conn.execute(
        "SELECT COUNT(*) FROM live_trials WHERE actual != 'authorized' "
        "AND decision = 'ACCESS GRANTED'").fetchone()[0]
    auth = conn.execute(
        "SELECT COUNT(*) FROM live_trials WHERE actual = 'authorized'").fetchone()[0]
    fr = conn.execute(
        "SELECT COUNT(*) FROM live_trials WHERE actual = 'authorized' "
        "AND decision != 'ACCESS GRANTED'").fetchone()[0]
    print(f"\nFalse accepts (non-authorized granted): {fa}/{non_auth}")
    print(f"False rejects (authorized not granted): {fr}/{auth}")

def run_trial(cap, model):
    # Phase 1: get ready (no inference)
    start = time.time()
    while time.time() - start < READY_SEC:
        ok, frame = cap.read()
        if not ok:
            return None
        put(frame, f"GET READY: {READY_SEC - (time.time() - start):.0f}", 40, (0, 255, 255), 1.0)
        cv2.imshow("Live Test", frame)
        cv2.waitKey(1)
    # Phase 2: record predictions
    preds = []
    start = time.time()
    while time.time() - start < TRIAL_SEC:
        ok, frame = cap.read()
        if not ok:
            break
        r = model.infer(frame)[0]
        preds.append((r.top, r.confidence))
        put(frame, f"RECORDING {TRIAL_SEC - (time.time() - start):.1f}s", 40, (0, 0, 255), 1.0)
        cv2.imshow("Live Test", frame)
        cv2.waitKey(1)
    if not preds:
        return None
    labels = [l for l, _ in preds]
    label = Counter(labels).most_common(1)[0][0]
    conf = sum(c for l, c in preds if l == label) / labels.count(label)
    return label, conf, decide(label, conf)

# --- Database ---
conn = sqlite3.connect(DB_FILE)
conn.execute("""CREATE TABLE IF NOT EXISTS live_trials (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    actual     TEXT NOT NULL,
    predicted  TEXT NOT NULL,
    confidence REAL NOT NULL,
    decision   TEXT NOT NULL,
    expected   TEXT NOT NULL,
    correct    INTEGER NOT NULL
)""")
conn.commit()

if len(sys.argv) > 1 and sys.argv[1] == "summary":
    summary(conn)
    conn.close()
    sys.exit()

model = get_model(model_id=MODEL_ID, api_key=API_KEY)
counts = {c: conn.execute("SELECT COUNT(*) FROM live_trials WHERE actual=?",
                          (c,)).fetchone()[0] for c in CLASSES}
cap = cv2.VideoCapture(0)
current = 0
message, msg_color = "Pick a class (1-7), then press SPACE", (255, 255, 255)

while True:
    ok, frame = cap.read()
    if not ok:
        break
    cls = CLASSES[current]
    put(frame, f"[{current + 1}] {cls}   trials: {counts[cls]}/{TARGET}", 30, (0, 255, 0))
    put(frame, "1-7 class | SPACE run trial | u undo last | q quit", 60, scale=0.55)
    put(frame, message, 95, msg_color, 0.6)
    cv2.imshow("Live Test", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif ord("1") <= key <= ord("7"):
        current = key - ord("1")
        message, msg_color = f"Class set to {CLASSES[current]}", (255, 255, 255)
    elif key == ord("u"):
        conn.execute("DELETE FROM live_trials WHERE id = "
                     "(SELECT MAX(id) FROM live_trials WHERE actual = ?)", (cls,))
        conn.commit()
        counts[cls] = conn.execute("SELECT COUNT(*) FROM live_trials WHERE actual=?",
                                   (cls,)).fetchone()[0]
        message, msg_color = f"Removed last {cls} trial", (0, 255, 255)
    elif key == 32:  # SPACE
        out = run_trial(cap, model)
        if out is None:
            message, msg_color = "Trial failed (camera). Try again", (0, 0, 255)
            continue
        label, conf, decision = out
        expected = expected_for(cls)
        correct = int(decision == expected)
        conn.execute(
            "INSERT INTO live_trials (timestamp, actual, predicted, confidence, "
            "decision, expected, correct) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), cls, label,
             round(conf, 3), decision, expected, correct))
        conn.commit()
        counts[cls] += 1
        message = f"{label} ({conf:.0%}) -> {decision}  [{'CORRECT' if correct else 'WRONG'}]"
        msg_color = (0, 200, 0) if correct else (0, 0, 255)

cap.release()
cv2.destroyAllWindows()
summary(conn)
conn.close()