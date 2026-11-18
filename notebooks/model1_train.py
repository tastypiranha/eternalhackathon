import glob, json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, ConfusionMatrixDisplay

# ===================== CONFIG (edit if needed) =====================
RAW_DIR      = "data/raw/beef_enose"
DATASET_NAME = "Electronic nose dataset for beef quality monitoring (Wijaya et al.)"
DATASET_URL  = "https://data.mendeley.com/datasets/mwmhh766fc"
LABEL_CANDIDATES = ["class", "Class", "label", "Label", "CLASS"]
TVC_CANDIDATES   = ["TVC", "tvc", "Total Viable Count", "Microbial Population", "microbial population"]
DROP_COLUMNS     = ["minute", "Minute", "time", "Time", "timestamp", "No", "no", "index", "Unnamed: 0"]
# If only TVC (log CFU/g) exists, classes are made with these approximate cut-offs:
TVC_BINS   = [-np.inf, 3, 4, 5, np.inf]
TVC_LABELS = ["excellent", "good", "acceptable", "spoiled"]
OUT_JSON = "backend/data/model1_results.json"
OUT_IMG  = "frontend/public/model"
# ===================================================================

os.makedirs(OUT_IMG, exist_ok=True)
files = sorted(glob.glob(f"{RAW_DIR}/**/*.csv", recursive=True) + glob.glob(f"{RAW_DIR}/**/*.xls*", recursive=True))
assert files, f"No data files found in {RAW_DIR}"
frames = []
for f in files:
    df = pd.read_csv(f) if f.endswith(".csv") else pd.read_excel(f)
    df["__group"] = os.path.basename(f)          # one group per file (= per beef cut)
    frames.append(df)
data = pd.concat(frames, ignore_index=True)
data.columns = [str(c).strip() for c in data.columns]

label_col = next((c for c in LABEL_CANDIDATES if c in data.columns), None)
tvc_col   = next((c for c in TVC_CANDIDATES if c in data.columns), None)
if label_col:
    y = data[label_col].astype(str).str.strip().str.lower()
elif tvc_col:
    y = pd.cut(data[tvc_col].astype(float), bins=TVC_BINS, labels=TVC_LABELS).astype(str)
else:
    raise SystemExit(f"No label or TVC column. Columns are: {data.columns.tolist()}")

exclude = set(DROP_COLUMNS) | {label_col, tvc_col, "__group"}
X = data[[c for c in data.columns if c not in exclude]].select_dtypes(include=[np.number])
mask = X.notna().all(axis=1) & y.notna() & (y != "nan")
X, y, groups = X[mask], y[mask], data.loc[mask, "__group"]
print("Samples:", len(X), "Features:", X.columns.tolist()); print(y.value_counts())

model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
n_groups = groups.nunique()
if n_groups >= 3:
    # Honest validation: train on some beef cuts, test on a cut the model has never seen
    validation = f"leave-one-group-out style GroupKFold ({min(5, n_groups)} folds, grouped by beef cut / file)"
    y_true, y_pred = [], []
    for tr, te in GroupKFold(n_splits=min(5, n_groups)).split(X, y, groups):
        model.fit(X.iloc[tr], y.iloc[tr])
        y_pred += list(model.predict(X.iloc[te])); y_true += list(y.iloc[te])
else:
    validation = "random stratified 70/30 split (WARNING: neighbouring time samples may inflate accuracy)"
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
    model.fit(Xtr, ytr); y_pred = list(model.predict(Xte)); y_true = list(yte)

acc = accuracy_score(y_true, y_pred)
f1  = f1_score(y_true, y_pred, average="macro")
classes = [c for c in TVC_LABELS if c in set(y_true)] or sorted(set(y_true))
print(f"Accuracy={acc:.3f}  Macro-F1={f1:.3f}  ({validation})")

# Simpler business question: is it spoiled, or still sellable?
bin_true = [t == "spoiled" for t in y_true]
bin_pred = [p == "spoiled" for p in y_pred]
binary_acc = accuracy_score(bin_true, bin_pred)
# Off by at most one stage (e.g. "good" predicted as "excellent")
order = {c: i for i, c in enumerate(TVC_LABELS)}
within_one = float(np.mean([abs(order.get(t, 0) - order.get(p, 0)) <= 1 for t, p in zip(y_true, y_pred)]))
print(f"Spoiled-vs-sellable accuracy={binary_acc:.3f}  Within-one-stage={within_one:.3f}")

# Confusion matrix
cm = confusion_matrix(y_true, y_pred, labels=classes)
ConfusionMatrixDisplay(cm, display_labels=classes).plot(cmap="Reds", colorbar=False)
plt.title("Model 1 – spoilage stage (real e-nose data)"); plt.tight_layout()
plt.savefig(f"{OUT_IMG}/confusion_matrix.png", dpi=150); plt.close()

# Feature importance (fit on all data)
model.fit(X, y)
imp = pd.Series(model.feature_importances_, index=X.columns).sort_values()
imp.tail(10).plot(kind="barh", color="#E23744")
plt.title("Which sensors matter most"); plt.tight_layout()
plt.savefig(f"{OUT_IMG}/feature_importance.png", dpi=150); plt.close()

# Spoilage curve: top gas sensor over time for the first beef cut, coloured by class
top = imp.index[-1]
g0 = groups.iloc[0]
sub = X[groups == g0].reset_index(drop=True); lab = y[groups == g0].reset_index(drop=True)
colors = {"excellent": "#16A34A", "good": "#EAB308", "acceptable": "#F97316", "spoiled": "#DC2626"}
plt.figure(figsize=(8, 3.5))
plt.scatter(sub.index, sub[top], c=[colors.get(v, "#6B7280") for v in lab], s=4)
plt.xlabel("Minutes since start"); plt.ylabel(f"{top} sensor reading")
plt.title(f"Gas sensor signal shifts as beef spoils (beef cut {g0.replace('.csv', '')}; green=excellent → red=spoiled)", fontsize=10); plt.tight_layout()
plt.savefig(f"{OUT_IMG}/spoilage_curve.png", dpi=150); plt.close()

result = {
    "available": True,
    "dataset_name": DATASET_NAME,
    "dataset_url": DATASET_URL,
    "task": "Classify spoilage stage from gas sensor + temperature + humidity readings",
    "n_samples": int(len(X)), "n_features": int(X.shape[1]),
    "classes": classes,
    "model": "RandomForestClassifier(n_estimators=200)",
    "validation": validation,
    "accuracy": round(float(acc), 3), "macro_f1": round(float(f1), 3),
    "binary_accuracy": round(float(binary_acc), 3),
    "within_one_stage": round(within_one, 3),
    "chance_accuracy": round(1 / max(1, len(classes)), 3),
    "top_features": imp.index[::-1][:3].tolist(),
    "images": ["/model/confusion_matrix.png", "/model/feature_importance.png", "/model/spoilage_curve.png"],
    "notes": "Real lab data. Shows that low-cost gas sensors can detect spoilage stage.",
}
json.dump(result, open(OUT_JSON, "w"), indent=2)
print("Saved", OUT_JSON)
