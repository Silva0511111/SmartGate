import cv2, csv, time
from collections import deque, Counter
from datetime import datetime
from inference import get_model

API_KEY    = "YOUR_ROBOFLOW_API_KEY"
MODEL_ID   = "your-project/1"
CONF_MIN   = 0.70      # minimum average confidence to act
WINDOW     = 10        # frames used for smoothing
LOITER_SEC = 15        # non-authorized presence longer than this = alert

model = get_model(model_id=MODEL_ID, api_key=API_KEY)
history = deque(maxlen=WINDOW)
presence_start = None
last_logged = None

def decide(label, conf):
    if conf < CONF_MIN:
        return "WAITING", (200, 200, 200)
    if label == "authorized":
        return "ACCESS GRANTED", (0, 200, 0)
    if label in ("visitor", "delivery-person"):
        return "NOTIFY OWNER", (0, 165, 255)
    # unknown, facecovered, photo-spoof, loitering
    return "ACCESS DENIED", (0, 0, 255)

def log_event(label, conf, decision):
    with open("access_log.csv", "a", newline="") as f:
        csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"),
                                label, f"{conf:.2f}", decision])

cap = cv2.VideoCapture(0)
prev = time.time()
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
    if label not in ("authorized",) and conf >= CONF_MIN:
        presence_start = presence_start or time.time()
        if time.time() - presence_start > LOITER_SEC:
            decision, color = "LOITERING ALERT", (0, 0, 255)
    else:
        presence_start = None

    # Log only when the decision changes
    if decision != last_logged and decision != "WAITING":
        log_event(label, conf, decision)
        last_logged = decision

    cv2.putText(frame, f"{label} ({conf:.0%})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, decision, (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
    now = time.time()
    fps = 1 / (now - prev)
    prev = now
    cv2.putText(frame, f"{fps:.1f} FPS", (10, 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.imshow("Smart Gate", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()