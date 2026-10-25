import os, cv2
from inference import get_model

API_KEY  = "YOUR_ROBOFLOW_API_KEY"
MODEL_ID = "your-project/1"
IN_DIR, OUT_DIR = "demo_input", "demo_output"
EXTS = (".jpg", ".jpeg", ".png")

os.makedirs(IN_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
model = get_model(model_id=MODEL_ID, api_key=API_KEY)

files = [f for f in sorted(os.listdir(IN_DIR)) if f.lower().endswith(EXTS)]
if not files:
    print(f"Put some images in '{IN_DIR}' first.")

for f in files:
    img = cv2.imread(os.path.join(IN_DIR, f))
    if img is None:
        continue
    r = model.infer(img)[0]
    text = f"{r.top} ({r.confidence:.0%})"
    cv2.rectangle(img, (0, 0), (img.shape[1], 40), (0, 0, 0), -1)
    cv2.putText(img, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                0.9, (0, 255, 0), 2)
    cv2.imwrite(os.path.join(OUT_DIR, f), img)
    print(f"{f:<30} -> {text}")