import os, csv, time
import cv2
import numpy as np
from inference import get_model

API_KEY  = "YOUR_ROBOFLOW_API_KEY"
MODEL_ID = "your-project/1"
TEST_DIR = os.path.join("split", "test")
EXTS = (".jpg", ".jpeg", ".png")

t0 = time.perf_counter()
model = get_model(model_id=MODEL_ID, api_key=API_KEY)
load_time = time.perf_counter() - t0
model.infer(np.zeros((224, 224, 3), dtype=np.uint8))  # warm-up, not timed
times = []

classes = sorted(d for d in os.listdir(TEST_DIR)
                 if os.path.isdir(os.path.join(TEST_DIR, d)))
matrix = {a: {p: 0 for p in classes} for a in classes}  # matrix[actual][predicted]
rows = []

for actual in classes:
    folder = os.path.join(TEST_DIR, actual)
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(EXTS):
            continue
        img = cv2.imread(os.path.join(folder, f))
        if img is None:
            continue
        t = time.perf_counter()
        r = model.infer(img)[0]
        times.append(time.perf_counter() - t)
        pred = r.top
        if pred not in matrix[actual]:
            matrix[actual][pred] = 0
        matrix[actual][pred] += 1
        rows.append([f, actual, pred, f"{r.confidence:.3f}"])

total = len(rows)
correct = sum(matrix[c].get(c, 0) for c in classes)
print(f"\nTEST ACCURACY: {correct}/{total} = {correct / total:.1%}\n")

print(f"{'Class':<18}{'Correct':>8}{'Total':>7}{'Accuracy':>10}")
for c in classes:
    tot = sum(matrix[c].values())
    ok = matrix[c].get(c, 0)
    acc = f"{ok / tot:.1%}" if tot else "n/a"
    print(f"{c:<18}{ok:>8}{tot:>7}{acc:>10}")

print("\nCONFUSION MATRIX (rows = actual, columns = predicted)")
print(f"{'':<18}" + "".join(f"{c[:9]:>11}" for c in classes))
for a in classes:
    print(f"{a:<18}" + "".join(f"{matrix[a].get(p, 0):>11}" for p in classes))

with open("evaluation_results.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["file", "actual", "predicted", "confidence"])
    w.writerows(rows)
print("\nPer-image results saved to evaluation_results.csv")

if times:
    avg_ms = 1000 * sum(times) / len(times)
    print("\nEFFICIENCY")
    print(f"Model load time:      {load_time:.2f} s")
    print(f"Images timed:         {len(times)}")
    print(f"Avg inference time:   {avg_ms:.1f} ms per image")
    print(f"Fastest / slowest:    {1000*min(times):.1f} / {1000*max(times):.1f} ms")
    print(f"Throughput:           {1000/avg_ms:.1f} images per second")