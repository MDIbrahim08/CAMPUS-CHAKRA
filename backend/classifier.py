"""Edge smart-bin waste classifier (6 classes).

Feature design (all available on the bin itself, no cloud needed):
  * 5 physical sensors: weight, moisture, metal induction, optical transparency, acoustic hardness
  * saturation flags: moisture/metal probes that read a hard 100 are treated as glitches
  * context the bin already knows: its building (B07 food court sees mostly food), hour, weekday
  * missing-sensor count (sensors drop out ~2% of the time) -> handled natively, no row discarded

Two models are produced:
  * FULL  – Random Forest + Extra Trees soft-vote (Raspberry-Pi class gateway)
  * EDGE  – a compact 40-tree forest exported to JSON that runs in pure
            JavaScript / micro-Python on the bin MCU (shown live in the browser)
"""
from __future__ import annotations

import json
import pickle
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold

from . import config as C

F = C.SENSOR_FEATURES
FILL = -1.0


def label_col(df: pd.DataFrame):
    for c in ("category", "waste_class", "label", "true_class"):
        if c in df.columns:
            return c
    return None


def featurize(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in F:
        X[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    X["nna"] = X[F].isna().sum(axis=1)
    for c in ("moisture_pct", "metal_signal"):
        sat = X[c] >= 99.9
        X[c + "_sat"] = sat.astype(int)
        X.loc[sat, c] = np.nan
    if "building_id" in df:
        X["bld"] = pd.to_numeric(df["building_id"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    else:
        X["bld"] = np.nan
    t = pd.to_datetime(df["timestamp"], errors="coerce") if "timestamp" in df else pd.Series(pd.NaT, index=df.index)
    X["hour"] = t.dt.hour
    X["dow"] = t.dt.dayofweek
    return X.astype(float).fillna(FILL)


class EnsembleClassifier:
    def __init__(self, seed=0):
        self.rf = RandomForestClassifier(600, min_samples_leaf=2, max_features=0.5, n_jobs=-1, random_state=seed)
        self.et = ExtraTreesClassifier(800, max_features=0.7, n_jobs=-1, random_state=seed)

    def fit(self, X, y):
        self.rf.fit(X, y); self.et.fit(X, y)
        self.classes_ = self.rf.classes_
        return self

    def predict_proba(self, X):
        return (self.rf.predict_proba(X) + self.et.predict_proba(X)) / 2

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]


def _edge_model(seed=0):
    return RandomForestClassifier(40, max_depth=12, min_samples_leaf=3, max_features=0.6, n_jobs=-1, random_state=seed)


def load_edge_model():
    """Load the compact inference model, training it once when no cache exists."""
    cache_path = C.CACHE_DIR / "edge_classifier.pkl"
    if cache_path.exists():
        with open(cache_path, "rb") as cache_file:
            return pickle.load(cache_file)

    from . import ingest as I

    train = I.load_table("waste_events_train")
    model = _edge_model().fit(featurize(train), train[label_col(train)].values)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(".tmp")
    with open(temporary_path, "wb") as cache_file:
        pickle.dump(model, cache_file)
    temporary_path.replace(cache_path)
    return model


def cross_validate(train: pd.DataFrame, folds=5):
    y = train[label_col(train)].values
    X = featurize(train)
    skf = StratifiedKFold(folds, shuffle=True, random_state=42)
    pf = np.empty(len(y), dtype=object); pe = np.empty(len(y), dtype=object)
    for tr_i, te_i in skf.split(X, y):
        pf[te_i] = EnsembleClassifier().fit(X.iloc[tr_i], y[tr_i]).predict(X.iloc[te_i])
        pe[te_i] = _edge_model().fit(X.iloc[tr_i], y[tr_i]).predict(X.iloc[te_i])
    labels = C.WASTE_CLASSES
    return {
        "full": {"accuracy": round(accuracy_score(y, pf) * 100, 2), "macro_f1": round(f1_score(y, pf, average="macro") * 100, 2),
                 "report": classification_report(y, pf, labels=labels, output_dict=True, zero_division=0),
                 "confusion": confusion_matrix(y, pf, labels=labels).tolist()},
        "edge": {"accuracy": round(accuracy_score(y, pe) * 100, 2), "macro_f1": round(f1_score(y, pe, average="macro") * 100, 2),
                 "confusion": confusion_matrix(y, pe, labels=labels).tolist()},
        "labels": labels, "folds": folds, "n": int(len(y)),
    }


def train_final(train: pd.DataFrame):
    y = train[label_col(train)].values
    X = featurize(train)
    full = EnsembleClassifier().fit(X, y)
    edge = _edge_model().fit(X, y)
    # latency benchmark: single-event inference (worst case, no batching)
    one = X.iloc[[0]]
    t0 = time.perf_counter()
    for _ in range(20):
        full.predict(one)
    lat_full = (time.perf_counter() - t0) / 20 * 1000
    t0 = time.perf_counter()
    for _ in range(50):
        edge.predict(one)
    lat_edge = (time.perf_counter() - t0) / 50 * 1000
    info = {"latency_ms_full": round(lat_full, 2), "latency_ms_edge_python": round(lat_edge, 2),
            "size_kb_full": round(len(pickle.dumps(full)) / 1024, 0), "size_kb_edge": round(len(pickle.dumps(edge)) / 1024, 0),
            "features": list(X.columns),
            "importances": dict(sorted(zip(X.columns, np.round(full.rf.feature_importances_, 4).tolist()), key=lambda kv: -kv[1]))}
    return full, edge, info


def predict(model, df: pd.DataFrame) -> pd.DataFrame:
    X = featurize(df)
    t0 = time.perf_counter()
    proba = model.predict_proba(X)
    dt = (time.perf_counter() - t0) / max(len(df), 1) * 1000
    cls = model.classes_
    out = pd.DataFrame({"event_id": df.get("event_id", pd.Series(range(len(df)))).values,
                        "predicted_class": cls[proba.argmax(1)],
                        "confidence": proba.max(1).round(3)})
    out["route"] = out["predicted_class"].map(C.CIRCULAR_ROUTE)
    out.attrs["ms_per_event"] = dt
    return out


def export_edge_json(edge: RandomForestClassifier, features: list[str]) -> dict:
    """Serialise the compact forest to plain arrays for JS / MCU inference."""
    trees = []
    for est in edge.estimators_:
        t = est.tree_
        trees.append({"f": t.feature.tolist(), "t": np.round(t.threshold, 4).tolist(),
                      "l": t.children_left.tolist(), "r": t.children_right.tolist(),
                      "v": [list(np.round(v[0] / v[0].sum(), 3)) for v in t.value]})
    return {"classes": edge.classes_.tolist(), "features": features, "fill": FILL, "trees": trees}
