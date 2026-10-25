import os, random, shutil

SRC = "dataset"
DST = "split"
RATIOS = {"train": 0.70, "valid": 0.20, "test": 0.10}
SEED = 42
EXTS = (".jpg", ".jpeg", ".png")

random.seed(SEED)
if os.path.exists(DST):
    shutil.rmtree(DST)

print(f"{'Class':<18}{'train':>7}{'valid':>7}{'test':>7}")
for cls in sorted(os.listdir(SRC)):
    folder = os.path.join(SRC, cls)
    if not os.path.isdir(folder):
        continue
    files = [f for f in os.listdir(folder) if f.lower().endswith(EXTS)]
    random.shuffle(files)

    n = len(files)
    n_train = int(n * RATIOS["train"])
    n_valid = int(n * RATIOS["valid"])
    parts = {
        "train": files[:n_train],
        "valid": files[n_train:n_train + n_valid],
        "test":  files[n_train + n_valid:],
    }
    for part, items in parts.items():
        out = os.path.join(DST, part, cls)
        os.makedirs(out, exist_ok=True)
        for f in items:
            shutil.copy(os.path.join(folder, f), os.path.join(out, f))
    print(f"{cls:<18}{len(parts['train']):>7}{len(parts['valid']):>7}{len(parts['test']):>7}")