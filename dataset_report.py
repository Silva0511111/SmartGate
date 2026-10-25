import os, hashlib, cv2

ROOT = "dataset"
MIN_PER_CLASS = 100
EXTS = (".jpg", ".jpeg", ".png")

total, hashes, duplicates, unreadable = 0, {}, [], []
print(f"{'Class':<18}{'Images':>8}  Status")
print("-" * 40)

for cls in sorted(os.listdir(ROOT)):
    folder = os.path.join(ROOT, cls)
    if not os.path.isdir(folder):
        continue
    files = [f for f in os.listdir(folder) if f.lower().endswith(EXTS)]
    for f in files:
        path = os.path.join(folder, f)
        if cv2.imread(path) is None:
            unreadable.append(path)
            continue
        with open(path, "rb") as fh:
            h = hashlib.md5(fh.read()).hexdigest()
        if h in hashes:
            duplicates.append((path, hashes[h]))
        else:
            hashes[h] = path
    status = "OK" if len(files) >= MIN_PER_CLASS else f"need {MIN_PER_CLASS - len(files)} more"
    print(f"{cls:<18}{len(files):>8}  {status}")
    total += len(files)

print("-" * 40)
print(f"{'TOTAL':<18}{total:>8}")
print(f"Unreadable files: {len(unreadable)}")
for p in unreadable:
    print("  ", p)
print(f"Duplicate images: {len(duplicates)}")
for a, b in duplicates:
    print(f"   {a}  ==  {b}")