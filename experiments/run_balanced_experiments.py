from __future__ import annotations

import argparse
import html
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

PROJECT_ROOT = next(
    (path for path in [Path(__file__).resolve(), *Path(__file__).resolve().parents] if (path / "config.yaml").exists()),
    None,
)
if PROJECT_ROOT is not None and PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from experiments.run_stopword_ablation import remove_function_words

URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.IGNORECASE)
WS_RE = re.compile(r"\s+")


def clean_text(text: object) -> str:
    if text is None or pd.isna(text):
        return ""
    cleaned = str(text)
    cleaned = URL_RE.sub("", cleaned)
    cleaned = EMAIL_RE.sub("", cleaned)
    cleaned = cleaned.lower()
    cleaned = WS_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return cleaned.strip()


@dataclass(frozen=True)
class LabelSpec:
    label2id: dict[str, int]

    @property
    def id2label(self) -> dict[int, str]:
        return {v: k for k, v in self.label2id.items()}


def find_project_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "config.yaml").exists():
            return path
    raise FileNotFoundError("config.yaml not found")


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def column_letters_to_index(value: str) -> int:
    index = 0
    for char in value:
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def read_xlsx_first_sheet(path: Path) -> pd.DataFrame:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("a:si", ns):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//a:t", ns)))

        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        col_ref_re = re.compile(r"[A-Z]+")
        for row_node in sheet_root.findall(".//a:row", ns):
            row_values: dict[int, str] = {}
            for cell in row_node.findall("a:c", ns):
                ref = cell.attrib.get("r", "")
                match = col_ref_re.match(ref)
                if not match:
                    continue
                col_idx = column_letters_to_index(match.group(0))
                value_node = cell.find("a:v", ns)
                value = "" if value_node is None else value_node.text or ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                row_values[col_idx] = value
            if row_values:
                max_idx = max(row_values)
                rows.append([row_values.get(idx, "") for idx in range(max_idx + 1)])

    if not rows:
        return pd.DataFrame()
    headers = [str(value).strip() for value in rows[0]]
    data_rows = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        data_rows.append(padded[: len(headers)])
    return pd.DataFrame(data_rows, columns=headers)


def load_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        try:
            return pd.read_excel(path)
        except Exception:
            return read_xlsx_first_sheet(path)
    raise ValueError(f"Unsupported data file type: {path}")


def normalize_ai_type(value: object) -> str:
    text = re.sub(r"\s+", " ", "" if pd.isna(value) else str(value).strip().lower())
    cleaned = re.sub(r"[^a-z0-9]+", "", text)
    if not text:
        return "HUMAN"
    if "chatgpt" in cleaned:
        return "ChatGPT"
    if "gemini" in cleaned:
        return "Gemini"
    if any(token in cleaned for token in ("claude", "cloude", "cloud", "cluade")):
        return "Claude"
    return "Other"


def normalize_category(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    aliases = {
        "politics": "Politics",
        "sports": "Sports",
        "education": "Education",
        "business": "Business",
        "technology": "Technology",
        "religion": "Religion",
        "health": "Health",
        "entertainment": "Entertainment",
        "entertiment": "Entertainment",
        "enteritment": "Entertainment",
    }
    return aliases.get(text, text.title() if text else "Unknown")


def normalize_binary_label(value: object) -> str:
    text = re.sub(r"[^a-z]+", "", "" if pd.isna(value) else str(value).strip().lower())
    if text in {"ai", "aigenerated", "machine", "generated"}:
        return "AI"
    if text in {"human", "humangenerated", "real", "original"}:
        return "HUMAN"
    return "Other"


def build_supplemental_category_lookup() -> dict[str, str]:
    """Map cleaned raw/generated article text to normalized category labels."""
    if PROJECT_ROOT is None:
        return {}
    raw_path = PROJECT_ROOT / "data" / "raw" / "full_dataset.xlsx"
    if not raw_path.exists():
        raw_path = PROJECT_ROOT / "data" / "raw" / "full_dataset.csv"
    if not raw_path.exists():
        return {}

    try:
        raw = load_table(raw_path).fillna("")
    except Exception:
        return {}
    if "Category" not in raw.columns:
        return {}

    text_columns = [col for col in ["Text", "Summarize Ai", "Expand Ai"] if col in raw.columns]
    lookup: dict[str, str] = {}
    for _, row in raw.iterrows():
        category = normalize_category(row.get("Category", ""))
        if category == "Unknown":
            continue
        for col in text_columns:
            text = clean_text(row.get(col, ""))
            if text:
                lookup.setdefault(text, category)
    return lookup
def build_labeled_dataset(raw_df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, dict[str, object]]:
    required = {"Text", "Label"}
    missing = sorted(required - set(raw_df.columns))
    if missing:
        raise ValueError(f"Labeled dataset missing columns: {missing}")

    df = raw_df.copy()
    df["Text"] = df["Text"].map(clean_text)
    df["Label"] = df["Label"].map(normalize_binary_label)
    df = df[df["Text"].astype(str).str.strip().str.len() > 0].copy()
    df = df[df["Label"].isin(["AI", "HUMAN"])].copy()

    before_conflict_drop = len(df)
    label_counts_per_text = df.groupby("Text")["Label"].nunique()
    ambiguous_texts = set(label_counts_per_text[label_counts_per_text > 1].index)
    df = df[~df["Text"].isin(ambiguous_texts)].copy()
    ambiguous_rows = before_conflict_drop - len(df)

    before_dedupe = len(df)
    df = df.drop_duplicates(subset=["Text", "Label"], keep="first").reset_index(drop=True)
    duplicate_rows = before_dedupe - len(df)
    df["AiTypeNormalized"] = df["Label"]
    category_lookup = build_supplemental_category_lookup()
    df["CategoryNormalized"] = df["Text"].map(category_lookup).fillna("Unknown")
    df = df[["Text", "Label", "AiTypeNormalized", "CategoryNormalized"]]
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    summary = {
        "raw_rows": int(len(raw_df)),
        "task": "label",
        "label_description": "binary labels: AI, HUMAN",
        "invalid_or_empty_rows": int(len(raw_df) - before_conflict_drop),
        "ambiguous_duplicate_rows_removed": int(ambiguous_rows),
        "same_label_duplicate_rows_removed": int(duplicate_rows),
        "dataset_rows": int(len(df)),
        "label_counts": {k: int(v) for k, v in df["Label"].value_counts().to_dict().items()},
        "category_counts": {k: int(v) for k, v in df["CategoryNormalized"].value_counts().to_dict().items()},
    }
    return df, summary


def build_experiment_dataset(
    raw_df: pd.DataFrame,
    seed: int,
    task: str,
    sampling: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if task == "label":
        return build_labeled_dataset(raw_df, seed)

    required = {"Text", "Ai Type"}
    missing = sorted(required - set(raw_df.columns))
    if missing:
        raise ValueError(f"Raw dataset missing columns: {missing}")

    df = raw_df.copy()
    df["AiTypeNormalized"] = df["Ai Type"].map(normalize_ai_type)
    if "Category" in df.columns:
        df["CategoryNormalized"] = df["Category"].map(normalize_category)
    else:
        df["CategoryNormalized"] = "Unknown"

    df["Text"] = df["Text"].map(clean_text)
    df = df.dropna(subset=["Text"])
    df = df[df["Text"].astype(str).str.strip().str.len() > 0].copy()
    df = df[df["AiTypeNormalized"].isin(["ChatGPT", "Gemini", "Claude", "HUMAN"])].copy()
    df = df.drop_duplicates(subset=["Text"], keep="first").reset_index(drop=True)

    source_counts = df["AiTypeNormalized"].value_counts().to_dict()
    ai_sources = ["ChatGPT", "Gemini", "Claude"]
    sampled_parts = []

    if task == "ai_type":
        valid_ai = df[df["AiTypeNormalized"].isin(ai_sources)].copy()
        if valid_ai.empty:
            raise ValueError(f"Not enough AI source rows to balance dataset. Counts: {source_counts}")
        if sampling == "balanced":
            per_ai_source = min(int(source_counts.get(source, 0)) for source in ai_sources)
            for source in ai_sources:
                sampled_parts.append(
                    valid_ai[valid_ai["AiTypeNormalized"] == source].sample(n=per_ai_source, random_state=seed)
                )
            dataset = pd.concat(sampled_parts, ignore_index=True)
        elif sampling == "full":
            per_ai_source = None
            dataset = valid_ai
        else:
            raise ValueError(f"Unsupported sampling mode: {sampling}")
        label_description = "multiclass AI type labels: ChatGPT, Gemini, Claude"
    elif task == "binary":
        min_ai_source = min(int(source_counts.get(source, 0)) for source in ai_sources)
        human_count = int(source_counts.get("HUMAN", 0))
        per_ai_source = min(min_ai_source, human_count // len(ai_sources))
        if per_ai_source <= 0:
            raise ValueError(
                "Not enough HUMAN rows to build a balanced AI-vs-HUMAN dataset. "
                f"Counts: {source_counts}"
            )
        for source in ai_sources:
            sampled_parts.append(
                df[df["AiTypeNormalized"] == source].sample(n=per_ai_source, random_state=seed)
            )
        sampled_parts.append(
            df[df["AiTypeNormalized"] == "HUMAN"].sample(
                n=per_ai_source * len(ai_sources),
                random_state=seed,
            )
        )
        dataset = pd.concat(sampled_parts, ignore_index=True)
        label_description = "binary labels: AI, HUMAN"
    else:
        raise ValueError(f"Unsupported task: {task}")

    balanced = dataset.copy()
    if task == "ai_type":
        balanced["Label"] = balanced["AiTypeNormalized"]
    else:
        balanced["Label"] = np.where(balanced["AiTypeNormalized"] == "HUMAN", "HUMAN", "AI")
    balanced = balanced[["Text", "Label", "AiTypeNormalized", "CategoryNormalized"]]
    balanced = balanced.sample(frac=1, random_state=seed).reset_index(drop=True)

    summary = {
        "raw_rows": int(len(raw_df)),
        "after_clean_dedup_rows": int(len(df)),
        "source_counts_after_clean_dedup": {k: int(v) for k, v in source_counts.items()},
        "sampling": sampling,
        "per_ai_source": int(per_ai_source) if per_ai_source is not None else None,
        "task": task,
        "label_description": label_description,
        "dataset_rows": int(len(balanced)),
        "label_counts": {
            k: int(v) for k, v in balanced["Label"].value_counts().to_dict().items()
        },
        "ai_type_counts": {
            k: int(v) for k, v in balanced["AiTypeNormalized"].value_counts().to_dict().items()
        },
    }
    return balanced, summary


def stratified_split_by_source(
    df: pd.DataFrame,
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts = []
    val_parts = []
    test_parts = []

    for _, group in df.groupby("Label"):
        group = group.sample(frac=1, random_state=seed)
        n = len(group)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        train_parts.append(group.iloc[:n_train])
        val_parts.append(group.iloc[n_train : n_train + n_val])
        test_parts.append(group.iloc[n_train + n_val :])

    train_df = pd.concat(train_parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    val_df = pd.concat(val_parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    test_df = pd.concat(test_parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    return train_df, val_df, test_df


def write_split_files(
    exp_dir: Path,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    remove_stopwords: bool,
) -> dict[str, object]:
    data_dir = exp_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    out = {}
    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        df = split_df.copy()
        if remove_stopwords:
            df["Text"] = df["Text"].map(remove_function_words)
        df["Text"] = df["Text"].fillna("").astype(str).str.strip()
        df = df[df["Text"].str.len() > 0].copy()
        full_path = data_dir / f"{split_name}.csv"
        clean_path = data_dir / f"clean_{split_name}.csv"
        df.to_csv(full_path, index=False)
        df[["Text", "Label"]].to_csv(clean_path, index=False)
        out[split_name] = {
            "rows": int(len(df)),
            "label_counts": {k: int(v) for k, v in df["Label"].value_counts().to_dict().items()},
            "ai_type_counts": {
                k: int(v) for k, v in df["AiTypeNormalized"].value_counts().to_dict().items()
            },
            "category_counts": {
                k: int(v) for k, v in df["CategoryNormalized"].value_counts().to_dict().items()
            },
        }
    return out


def build_feature_union(max_features: int = 20000) -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word_tfidf",
                TfidfVectorizer(max_features=max_features, ngram_range=(1, 2), analyzer="word", sublinear_tf=True, min_df=2),
            ),
            (
                "char_tfidf",
                TfidfVectorizer(max_features=max_features, ngram_range=(3, 6), analyzer="char_wb", sublinear_tf=True, min_df=2),
            ),
        ]
    )


def build_models(
    seed: int,
    num_labels: int,
    include_xgboost: bool = False,
    include_random_forest: bool = False,
) -> dict[str, tuple[Pipeline, dict[str, list[object]]]]:
    models: dict[str, tuple[Pipeline, dict[str, list[object]]]] = {
        "LogisticRegression_TFIDF": (
            Pipeline(
                [
                    ("features", build_feature_union(max_features=20000)),
                    ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
                ]
            ),
            {"clf__C": [0.5, 1.0, 2.0, 4.0]},
        ),
        "LinearSVC_TFIDF": (
            Pipeline(
                [
                    ("features", build_feature_union(max_features=20000)),
                    ("clf", LinearSVC(class_weight="balanced")),
                ]
            ),
            {"clf__C": [0.5, 1.0, 2.0, 4.0]},
        ),
    }

    if include_random_forest:
        models["RandomForest_TFIDF"] = (
            Pipeline(
                [
                    ("features", TfidfVectorizer(max_features=10000, ngram_range=(1, 2))),
                    ("clf", RandomForestClassifier(n_estimators=120, random_state=seed, class_weight="balanced")),
                ]
            ),
            {"clf__max_depth": [None, 30]},
        )

    if not include_xgboost:
        return models

    try:
        from xgboost import XGBClassifier

        xgb_kwargs = {
            "eval_metric": "mlogloss" if num_labels > 2 else "logloss",
            "random_state": seed,
            "n_jobs": 1,
        }
        if num_labels > 2:
            xgb_kwargs.update({"objective": "multi:softprob", "num_class": num_labels})
        else:
            xgb_kwargs.update({"objective": "binary:logistic"})

        models["XGBoost_TFIDF"] = (
            Pipeline(
                [
                    ("features", TfidfVectorizer(max_features=15000, ngram_range=(1, 2))),
                    ("clf", XGBClassifier(**xgb_kwargs)),
                ]
            ),
            {"clf__max_depth": [3, 5], "clf__learning_rate": [0.05, 0.1]},
        )
    except Exception:
        pass

    return models


def metric_row(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    average = "weighted"
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average=average, zero_division=0
    )
    _mp, _mr, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "macro_f1": float(macro_f1),
    }


def binary_score(model: Pipeline, x_values: list[str]) -> np.ndarray | None:
    if hasattr(model, "predict_proba"):
        scores = model.predict_proba(x_values)
        if getattr(scores, "ndim", 1) == 2 and scores.shape[1] >= 2:
            return np.asarray(scores[:, 1], dtype=float)
    if hasattr(model, "decision_function"):
        scores = model.decision_function(x_values)
        if getattr(scores, "ndim", 1) == 1:
            return np.asarray(scores, dtype=float)
        if scores.shape[1] >= 2:
            return np.asarray(scores[:, 1], dtype=float)
    return None


def save_roc_outputs(
    reports_dir: Path,
    figures_dir: Path,
    model_name: str,
    y_true: np.ndarray,
    y_score: np.ndarray | None,
) -> float | None:
    if y_score is None or len(np.unique(y_true)) != 2:
        return None
    auc_value = float(roc_auc_score(y_true, y_score))
    fpr, tpr, _thresholds = roc_curve(y_true, y_score)
    pd.DataFrame({"fpr": fpr, "tpr": tpr}).to_csv(
        reports_dir / f"roc_curve_{model_name}.csv",
        index=False,
    )
    plt.figure(figsize=(5, 4))
    plt.plot(fpr, tpr, label=f"AUC = {auc_value:.4f}")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
    plt.title(f"ROC Curve: {model_name}")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(figures_dir / f"roc_curve_{model_name}.svg", dpi=180)
    plt.close()
    return auc_value


def save_confusion_matrix(path: Path, y_true: np.ndarray, y_pred: np.ndarray, labels: list[str], title: str) -> None:
    cm = confusion_matrix(y_true, y_pred)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels)
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(str(path), dpi=180)
    plt.close()


def generate_xai_outputs(exp_dir: Path, model_name: str, labels: LabelSpec) -> None:
    model_path = exp_dir / "models" / "traditional_ml" / f"{model_name}.joblib"
    if not model_path.exists():
        return

    model = joblib.load(model_path)
    if not hasattr(model.named_steps.get("clf"), "coef_"):
        return

    data_dir = exp_dir / "data"
    out_dir = exp_dir / "xai" / "outputs"
    lime_dir = out_dir / "lime"
    out_dir.mkdir(parents=True, exist_ok=True)
    lime_dir.mkdir(parents=True, exist_ok=True)

    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    test_df["Text"] = test_df["Text"].fillna("").astype(str).str.strip()
    test_df = test_df[test_df["Text"].str.len() > 0].reset_index(drop=True)

    features = model.named_steps["features"]
    classifier = model.named_steps["clf"]
    feature_names = features.get_feature_names_out()
    feature_names = np.array([name.replace("word_tfidf__", "").replace("char_tfidf__", "") for name in feature_names])
    coef = classifier.coef_
    if coef.shape[0] == 1:
        negative_label = labels.id2label[0]
        positive_label = labels.id2label[1]
        weights = coef[0]
        global_rows = [
            *[
                {"feature": feature_names[idx], "importance": float(-weights[idx]), "class_label": negative_label}
                for idx in np.argsort(weights)[:50]
            ],
            *[
                {"feature": feature_names[idx], "importance": float(weights[idx]), "class_label": positive_label}
                for idx in np.argsort(weights)[-50:][::-1]
            ],
        ]
    else:
        global_rows = []
        for class_id, class_weights in enumerate(coef):
            for idx in np.argsort(class_weights)[-50:][::-1]:
                global_rows.append(
                    {
                        "feature": feature_names[idx],
                        "importance": float(class_weights[idx]),
                        "class_label": labels.id2label[class_id],
                    }
                )
    pd.DataFrame(global_rows).to_csv(out_dir / "shap_like_feature_importance.csv", index=False)

    x_test = test_df["Text"].astype(str).tolist()
    y_true = test_df["Label"].map(labels.label2id).to_numpy(dtype=int)
    y_pred = model.predict(x_test)
    errors = test_df[y_true != y_pred].copy()
    errors["true_label"] = [labels.id2label[int(value)] for value in y_true[y_true != y_pred]]
    errors["predicted_label"] = [labels.id2label[int(value)] for value in y_pred[y_true != y_pred]]
    errors[["Text", "true_label", "predicted_label"]].head(25).to_csv(
        out_dir / "error_analysis_sample.csv",
        index=False,
    )

    x_matrix = features.transform(x_test[:3])
    for row_idx in range(min(3, len(test_df))):
        pred_id = int(y_pred[row_idx])
        if coef.shape[0] == 1:
            class_weights = coef[0] if pred_id == 1 else -coef[0]
        else:
            class_weights = coef[pred_id]
        contributions = x_matrix[row_idx].multiply(class_weights).toarray().ravel()
        top_indices = [idx for idx in np.argsort(contributions)[-12:][::-1] if contributions[idx] > 0]
        rows_html = "\n".join(
            f"<tr><td>{html.escape(feature_names[idx])}</td><td>{contributions[idx]:.4f}</td></tr>"
            for idx in top_indices
        )
        page = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Local Explanation</title>"
            "<style>body{font-family:Arial,sans-serif;max-width:960px;margin:32px auto;line-height:1.5}"
            "table{border-collapse:collapse;width:100%;margin-top:16px}"
            "td,th{border:1px solid #ddd;padding:8px;text-align:left}"
            "th{background:#f3f4f6}</style></head><body>"
            f"<h1>{html.escape(model_name)} explanation</h1>"
            f"<p><strong>True label:</strong> {html.escape(str(test_df.loc[row_idx, 'Label']))}</p>"
            f"<p><strong>Predicted label:</strong> {html.escape(labels.id2label[pred_id])}</p>"
            f"<p>{html.escape(test_df.loc[row_idx, 'Text'][:1200])}</p>"
            "<h2>Top positive features for this prediction</h2>"
            "<table><tr><th>Feature</th><th>Contribution</th></tr>"
            f"{rows_html}</table></body></html>"
        )
        (lime_dir / f"lime_explanation_{row_idx}.html").write_text(page, encoding="utf-8")

    (out_dir / "README.md").write_text(
        "# XAI Outputs\n\n"
        f"Generated from `{model_name}` for the binary `AI` vs `HUMAN` task.\n\n"
        "- `shap_like_feature_importance.csv`: top linear TF-IDF features per class.\n"
        "- `error_analysis_sample.csv`: held-out test errors for review.\n"
        "- `lime/lime_explanation_*.html`: lightweight local explanations for sample predictions.\n",
        encoding="utf-8",
    )


def detect_annotator_columns(df: pd.DataFrame) -> list[str]:
    patterns = (
        r"annotator",
        r"^label[_\s]?\d+$",
        r"^rater",
        r"^judge",
        r"^annotation",
    )
    candidates: list[str] = []
    for column in df.columns:
        normalized = re.sub(r"\s+", "_", str(column).strip().lower())
        if normalized in {"text", "label"}:
            continue
        if any(re.search(pattern, normalized) for pattern in patterns):
            candidates.append(column)
    return candidates


def compute_inter_annotator_agreement(raw_df: pd.DataFrame, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    annotator_columns = detect_annotator_columns(raw_df)
    payload: dict[str, object] = {
        "available_columns": list(raw_df.columns),
        "annotator_columns_detected": annotator_columns,
        "agreement_computed": False,
        "method": None,
        "score": None,
        "note": (
            "Inter-annotator agreement cannot be computed because the labeled dataset does not "
            "contain multiple annotator label columns. Only a single `Label` column is available."
        ),
    }

    if len(annotator_columns) >= 2:
        from sklearn.metrics import cohen_kappa_score

        left = raw_df[annotator_columns[0]].map(normalize_binary_label)
        right = raw_df[annotator_columns[1]].map(normalize_binary_label)
        valid = left.isin(["AI", "HUMAN"]) & right.isin(["AI", "HUMAN"])
        if valid.sum() >= 2:
            kappa = float(cohen_kappa_score(left[valid], right[valid]))
            payload.update(
                {
                    "agreement_computed": True,
                    "method": "cohen_kappa",
                    "score": kappa,
                    "pair": annotator_columns[:2],
                    "rows_used": int(valid.sum()),
                    "note": (
                        f"Cohen's kappa computed between `{annotator_columns[0]}` and "
                        f"`{annotator_columns[1]}` on {int(valid.sum())} rows."
                    ),
                }
            )

    json_path = out_dir / "inter_annotator_agreement.json"
    md_path = out_dir / "inter_annotator_agreement.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(
        "# Inter-Annotator Agreement\n\n"
        f"- Columns in source file: `{', '.join(map(str, payload['available_columns']))}`\n"
        f"- Annotator columns detected: `{', '.join(map(str, annotator_columns)) or 'none'}`\n"
        f"- Agreement computed: `{payload['agreement_computed']}`\n"
        f"- Method: `{payload['method']}`\n"
        f"- Score: `{payload['score']}`\n\n"
        f"{payload['note']}\n",
        encoding="utf-8",
    )
    return payload


def generate_xai_outputs_strict(exp_dir: Path, model_name: str, labels: LabelSpec) -> None:
    model_path = exp_dir / "models" / "traditional_ml" / f"{model_name}.joblib"
    if not model_path.exists():
        return

    model = joblib.load(model_path)
    classifier = model.named_steps.get("clf")
    if classifier is None or not hasattr(classifier, "coef_"):
        return

    import shap
    from lime.lime_text import LimeTextExplainer

    data_dir = exp_dir / "data"
    out_dir = exp_dir / "xai" / "outputs"
    shap_dir = out_dir / "shap"
    lime_dir = out_dir / "lime"
    shap_dir.mkdir(parents=True, exist_ok=True)
    lime_dir.mkdir(parents=True, exist_ok=True)

    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    test_df["Text"] = test_df["Text"].fillna("").astype(str).str.strip()
    test_df = test_df[test_df["Text"].str.len() > 0].reset_index(drop=True)
    x_test = test_df["Text"].astype(str).tolist()
    y_pred = model.predict(x_test)

    features = model.named_steps["features"]
    feature_names = features.get_feature_names_out()
    feature_names = np.array([name.replace("word_tfidf__", "").replace("char_tfidf__", "") for name in feature_names])
    x_matrix = features.transform(x_test[: min(120, len(x_test))])
    if hasattr(x_matrix, "toarray"):
        x_dense = x_matrix.toarray()
    else:
        x_dense = np.asarray(x_matrix)

    # SHAP linear explainer for sparse TF-IDF pipelines
    masker = shap.maskers.Independent(x_dense[:50])
    explainer = shap.LinearExplainer(classifier, masker, feature_names=feature_names)
    shap_values = explainer.shap_values(x_dense[:50])
    if isinstance(shap_values, list):
        shap_stack = np.stack(shap_values, axis=0)
        mean_abs = np.mean(np.abs(shap_stack), axis=(0, 1))
    else:
        mean_abs = np.mean(np.abs(shap_values), axis=0)
    shap_rows = [
        {"feature": feature_names[idx], "mean_abs_shap": float(mean_abs[idx])}
        for idx in np.argsort(mean_abs)[-100:][::-1]
    ]
    pd.DataFrame(shap_rows).to_csv(shap_dir / "shap_global_importance.csv", index=False)
    shap.summary_plot(
        shap_values,
        x_dense[:50],
        feature_names=feature_names,
        show=False,
        max_display=20,
    )
    plt.tight_layout()
    plt.savefig(shap_dir / "shap_summary_plot.svg", dpi=180, bbox_inches="tight")
    plt.close()

    class_names = [labels.id2label[i] for i in sorted(labels.id2label)]
    explainer_lime = LimeTextExplainer(class_names=class_names)

    def predict_proba(texts: list[str]) -> np.ndarray:
        if hasattr(classifier, "decision_function"):
            scores = model.decision_function(texts)
            if scores.ndim == 1:
                probs_pos = 1.0 / (1.0 + np.exp(-scores))
                return np.column_stack([1.0 - probs_pos, probs_pos])
            exp_scores = np.exp(scores - scores.max(axis=1, keepdims=True))
            return exp_scores / exp_scores.sum(axis=1, keepdims=True)
        return model.predict_proba(texts)

    for row_idx in range(min(3, len(test_df))):
        explanation = explainer_lime.explain_instance(
            x_test[row_idx],
            predict_proba,
            num_features=12,
            top_labels=1,
        )
        explanation.save_to_file(str(lime_dir / f"lime_explanation_{row_idx}.html"))

    (out_dir / "README.md").write_text(
        "# XAI Outputs\n\n"
        f"Generated from `{model_name}` for the binary `AI` vs `HUMAN` task.\n\n"
        "- `shap_like_feature_importance.csv`: lightweight linear proxy (legacy).\n"
        "- `shap/shap_global_importance.csv`: package-level SHAP mean absolute values.\n"
        "- `shap/shap_summary_plot.svg`: SHAP summary plot from the `shap` package.\n"
        "- `lime/lime_explanation_*.html`: local explanations from the `lime` package.\n"
        "- `error_analysis_sample.csv`: held-out test errors for review.\n",
        encoding="utf-8",
    )


def remove_stale_model_outputs(
    reports_dir: Path,
    figures_dir: Path,
    model_dir: Path,
    active_model_names: set[str],
) -> None:
    for path in model_dir.glob("*.joblib"):
        if path.stem not in active_model_names:
            path.unlink()
    for path in reports_dir.glob("classification_report_*.*"):
        model_name = path.stem.replace("classification_report_", "")
        if model_name not in active_model_names:
            path.unlink()
    for path in figures_dir.glob("confusion_matrix_*.svg"):
        model_name = path.stem.replace("confusion_matrix_", "")
        if model_name not in active_model_names:
            path.unlink()


def train_traditional_models(
    exp_dir: Path,
    seed: int,
    labels: LabelSpec,
    include_xgboost: bool,
    include_random_forest: bool,
    tune: bool,
) -> list[dict[str, object]]:
    data_dir = exp_dir / "data"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir = exp_dir / "models" / "traditional_ml"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_specs = build_models(
        seed,
        num_labels=len(labels.label2id),
        include_xgboost=include_xgboost,
        include_random_forest=include_random_forest,
    )
    remove_stale_model_outputs(reports_dir, figures_dir, model_dir, set(model_specs))

    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    val_df = pd.read_csv(data_dir / "clean_val.csv", keep_default_na=False)
    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    for df in (train_df, val_df, test_df):
        df["Text"] = df["Text"].fillna("").astype(str).str.strip()
        df.drop(df[df["Text"].str.len() == 0].index, inplace=True)
    train_fit_df = pd.concat([train_df, val_df], ignore_index=True)

    x_train = train_fit_df["Text"].astype(str).tolist()
    y_train = train_fit_df["Label"].map(labels.label2id).to_numpy(dtype=int)
    x_test = test_df["Text"].astype(str).tolist()
    y_test = test_df["Label"].map(labels.label2id).to_numpy(dtype=int)
    final_fit_df = train_fit_df
    x_final = x_train
    y_final = y_train

    rows: list[dict[str, object]] = []
    hyper_rows: list[dict[str, object]] = []
    scoring = "f1_weighted" if len(labels.label2id) > 2 else "f1"
    for model_name, (pipeline, params) in model_specs.items():
        print(f"== {exp_dir.name}: training {model_name} ==")
        if tune:
            search = GridSearchCV(
                estimator=pipeline,
                param_grid=params,
                scoring=scoring,
                cv=3,
                n_jobs=1,
                verbose=0,
            )
            search.fit(x_train, y_train)
            best_model = search.best_estimator_
            best_score = float(search.best_score_)
            best_params = search.best_params_
        else:
            best_params = {key: values[0] for key, values in params.items() if values}
            best_model = pipeline.set_params(**best_params)
            best_model.fit(x_train, y_train)
            best_score = float("nan")
        y_pred = best_model.predict(x_test)
        y_score = binary_score(best_model, x_test)
        roc_auc = save_roc_outputs(reports_dir, figures_dir, model_name, y_test, y_score)

        row = {
            "experiment": exp_dir.name,
            "family": "traditional_ml",
            "model": model_name,
            "evaluation_train_rows": int(len(train_fit_df)),
            "test_rows": int(len(test_df)),
            "final_train_rows": int(len(final_fit_df)),
            "saved_model_train_scope": "train_validation",
            **metric_row(y_test, y_pred),
        }
        if roc_auc is not None:
            row["roc_auc"] = roc_auc
        rows.append(row)
        hyper_rows.append(
            {
                "experiment": exp_dir.name,
                "model": model_name,
                "best_score_cv_f1": best_score,
                "best_params": json.dumps(best_params, sort_keys=True),
                "tuning": "grid_search" if tune else "fixed_default",
                "evaluation_train_rows": int(len(train_fit_df)),
                "final_train_rows": int(len(final_fit_df)),
            }
        )

        final_model = best_model
        final_model.fit(x_final, y_final)
        joblib.dump(final_model, model_dir / f"{model_name}.joblib")
        pd.DataFrame(classification_report(
            y_test,
            y_pred,
            labels=list(labels.id2label.keys()),
            target_names=[labels.id2label[i] for i in sorted(labels.id2label)],
            output_dict=True,
            zero_division=0,
        )).transpose().to_csv(reports_dir / f"classification_report_{model_name}.csv", index_label="label")
        (reports_dir / f"classification_report_{model_name}.txt").write_text(
            classification_report(
                y_test,
                y_pred,
                labels=list(labels.id2label.keys()),
                target_names=[labels.id2label[i] for i in sorted(labels.id2label)],
                zero_division=0,
            ),
            encoding="utf-8",
        )
        save_confusion_matrix(
            figures_dir / f"confusion_matrix_{model_name}.svg",
            y_test,
            y_pred,
            [labels.id2label[i] for i in sorted(labels.id2label)],
            f"{exp_dir.name}: {model_name}",
        )

    pd.DataFrame(rows).sort_values(["accuracy", "f1"], ascending=False).to_csv(
        reports_dir / "traditional_ml_metrics.csv",
        index=False,
    )
    pd.DataFrame(hyper_rows).to_csv(reports_dir / "hyperparameter_tuning.csv", index=False)
    return rows


def write_experiment_config(root: Path, base_cfg: dict, exp_dir: Path) -> Path:
    cfg = dict(base_cfg)
    cfg["paths"] = dict(base_cfg.get("paths", {}))
    cfg["data"] = dict(base_cfg.get("data", {}))
    cfg["paths"]["data_processed_dir"] = str((exp_dir / "data").relative_to(root))
    cfg["paths"]["eda_figures_dir"] = str((exp_dir / "eda" / "figures").relative_to(root))
    cfg["paths"]["traditional_ml_models_dir"] = str((exp_dir / "models" / "traditional_ml").relative_to(root))
    cfg["paths"]["evaluation_reports_dir"] = str((exp_dir / "evaluation" / "reports").relative_to(root))
    cfg["paths"]["evaluation_figures_dir"] = str((exp_dir / "evaluation" / "figures").relative_to(root))
    cfg["paths"]["xai_outputs_dir"] = str((exp_dir / "xai" / "outputs").relative_to(root))
    cfg["paths"]["results_dir"] = str((exp_dir / "results").relative_to(root))
    cfg["data"]["train_file"] = "clean_train.csv"
    cfg["data"]["val_file"] = "clean_val.csv"
    cfg["data"]["test_file"] = "clean_test.csv"
    path = exp_dir / "config.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run labeled text experiments 1 and 2.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out-dir", default="experiments")
    parser.add_argument(
        "--stage",
        choices=["data", "traditional", "all"],
        default="traditional",
        help="data only, traditional ML only after data prep, or all currently local stages.",
    )
    parser.add_argument(
        "--task",
        choices=["label", "ai_type", "binary"],
        default="label",
        help="label trains AI/HUMAN from data.data_labeled; ai_type trains ChatGPT/Gemini/Claude from paths.data_raw.",
    )
    parser.add_argument(
        "--sampling",
        choices=["full", "balanced"],
        default="full",
        help="full uses all valid non-empty rows; balanced downsamples classes to the smallest class.",
    )
    parser.add_argument(
        "--include-xgboost",
        action="store_true",
        help="also run XGBoost. This is optional because it is much slower than the default models.",
    )
    parser.add_argument(
        "--include-random-forest",
        action="store_true",
        help="also run RandomForest. This is optional because it is slower on the full labeled text dataset.",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="run GridSearchCV. Default uses fixed parameters so full retraining finishes quickly.",
    )
    args = parser.parse_args()

    root = find_project_root(Path.cwd())
    cfg = load_config(resolve_path(root, args.config))
    seed = int(cfg.get("project", {}).get("seed", 42))
    raw_path = resolve_path(
        root,
        cfg.get("data", {}).get("dataset_labeled", cfg["paths"]["data_raw"]) if args.task == "label" else cfg["paths"]["data_raw"],
    )
    out_root = root / args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)

    raw_df = load_table(raw_path)
    dataset_df, dataset_summary = build_experiment_dataset(
        raw_df,
        seed,
        task=args.task,
        sampling=args.sampling,
    )
    train_df, val_df, test_df = stratified_split_by_source(
        dataset_df,
        seed=seed,
        train_ratio=float(cfg["split"]["train_ratio"]),
        val_ratio=float(cfg["split"]["val_ratio"]),
    )

    experiments = [
        ("experiment_1_stopwords_included", False, "Clean text with Somali function words kept."),
        ("experiment_2_stopwords_removed", True, "Clean text with selected Somali function words removed."),
    ]
    label_names = sorted(dataset_df["Label"].unique().tolist())
    labels = LabelSpec(label2id={label: idx for idx, label in enumerate(label_names)})
    all_rows: list[dict[str, object]] = []
    experiment_summaries: dict[str, object] = {}
    for name, remove_stopwords, description in experiments:
        exp_dir = out_root / name
        exp_dir.mkdir(parents=True, exist_ok=True)
        split_summary = write_split_files(exp_dir, train_df, val_df, test_df, remove_stopwords)
        results_dir = exp_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        dataset_df.to_csv(exp_dir / "data" / "full_labeled_dataset.csv", index=False)
        dataset_df.to_csv(exp_dir / "data" / "balanced_labeled_dataset.csv", index=False)
        config_path = write_experiment_config(root, cfg, exp_dir)
        experiment_summaries[name] = {
            "description": description,
            "config": str(config_path.relative_to(root)),
            "splits": split_summary,
        }
        if args.stage in {"traditional", "all"}:
            all_rows.extend(
                train_traditional_models(
                    exp_dir,
                    seed,
                    labels,
                    args.include_xgboost,
                    args.include_random_forest,
                    args.tune,
                )
            )

        (exp_dir / "README.md").write_text(
            f"# {name}\n\n"
            f"{description}\n\n"
            "Files:\n"
            "- `data/train.csv`, `data/val.csv`, `data/test.csv`: splits with metadata.\n"
            "- `data/clean_train.csv`, `data/clean_val.csv`, `data/clean_test.csv`: Text/Label model inputs.\n"
            "- `eda/`: exploratory data analysis outputs.\n"
            "- `models/traditional_ml/`: trained traditional ML model artifacts.\n"
            "- `evaluation/`: metrics, classification reports, and confusion matrices.\n"
            "- `xai/`: explainability outputs.\n"
            "- `results/`: final comparison tables and best-model summaries.\n",
            encoding="utf-8",
        )

    if all_rows:
        comparison = pd.DataFrame(all_rows).sort_values(["model", "experiment"])
        for name, _remove_stopwords, _description in experiments:
            exp_dir = out_root / name
            results_dir = exp_dir / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            exp_rows = comparison[comparison["experiment"] == name].copy()
            exp_rows.to_csv(results_dir / "all_models_comparison.csv", index=False)
            comparison.to_csv(results_dir / "two_experiment_model_comparison.csv", index=False)
            best = exp_rows.sort_values(["f1", "accuracy"], ascending=False).iloc[0]
            (results_dir / "best_model_summary.md").write_text(
                "# Best Model Summary\n\n"
                f"- experiment: {best['experiment']}\n"
                f"- family: {best['family']}\n"
                f"- model: {best['model']}\n"
                f"- accuracy: {best['accuracy']:.4f}\n"
                f"- precision: {best['precision']:.4f}\n"
                f"- recall: {best['recall']:.4f}\n"
                f"- f1: {best['f1']:.4f}\n"
                f"- macro_f1: {best.get('macro_f1', best['f1']):.4f}\n\n"
                "Source: `results/all_models_comparison.csv`.\n",
                encoding="utf-8",
            )
            generate_xai_outputs(exp_dir, str(best["model"]), labels)

    for name, _remove_stopwords, _description in experiments:
        exp_dir = out_root / name
        summary = {
            "dataset": dataset_summary,
            "experiment": experiment_summaries[name],
        }
        (exp_dir / "results" / "experiment_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        print("Saved:", exp_dir / "results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

