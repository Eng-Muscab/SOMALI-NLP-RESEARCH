"""
Train ALL models for both experiments in one command.
Skips any model that is already trained (file exists).

Usage (from project root):
    python train_all.py                    # train missing models + regenerate outputs
    python train_all.py --force-all        # retrain everything from scratch
    python train_all.py --skip-traditional # skip traditional ML
    python train_all.py --skip-deep        # skip Keras deep learning
    python train_all.py --skip-embedding   # skip Word2Vec/FastText BiLSTMs
    python train_all.py --outputs-only     # only regenerate plots/reports (no training)
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

EXPERIMENTS = [
    "experiment_1_stopwords_included",
    "experiment_2_stopwords_removed",
]

TRADITIONAL_ML_MODELS = [
    "LinearSVC_TFIDF",
    "LogisticRegression_TFIDF",
    "RandomForest_TFIDF",
    "XGBoost_TFIDF",
]

LABEL2ID = {"AI": 0, "HUMAN": 1}
LABEL_NAMES = ["AI", "HUMAN"]


# ── helpers ───────────────────────────────────────────────────────────────────
def _joblib_exists(exp_dir: Path, model_name: str) -> bool:
    return (exp_dir / "models" / "traditional_ml" / f"{model_name}.joblib").exists()


def _keras_exists(exp_dir: Path, subfolder: str, model_name: str) -> bool:
    return (exp_dir / "models" / subfolder / f"{model_name}.keras").exists()


def _tok_exists(exp_dir: Path) -> bool:
    return (exp_dir / "data" / "tokenizer.joblib").exists()


def step(msg: str) -> None:
    print(f"\n  >> {msg}")


# ── output deletion ───────────────────────────────────────────────────────────
def delete_old_outputs(exp_dir: Path) -> None:
    """Delete all old generated images, HTML, and report CSVs."""
    dirs_to_clear = [
        exp_dir / "evaluation" / "figures",
        exp_dir / "xai" / "outputs" / "shap",
        exp_dir / "xai" / "outputs" / "lime",
        exp_dir / "eda" / "figures",
    ]
    file_patterns = ["*.svg", "*.html"]
    report_files = [
        exp_dir / "xai" / "outputs" / "shap_like_feature_importance.csv",
        exp_dir / "xai" / "outputs" / "error_analysis_sample.csv",
        exp_dir / "xai" / "outputs" / "shap" / "shap_global_importance.csv",
    ]

    deleted = 0
    for d in dirs_to_clear:
        if d.exists():
            for pattern in file_patterns:
                for f in d.glob(pattern):
                    f.unlink()
                    deleted += 1
    for f in report_files:
        if f.exists():
            f.unlink()
            deleted += 1
    print(f"  [CLEAN] Deleted {deleted} old output files.")


# ── confusion matrix ──────────────────────────────────────────────────────────
def save_confusion_matrix(path: Path, y_true, y_pred, labels: list[str], title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(y_true, y_pred)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=labels, yticklabels=labels)
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(str(path), dpi=180)
    plt.close()


# ── EDA figures ───────────────────────────────────────────────────────────────
def generate_eda_figures(exp_dir: Path) -> None:
    import re
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data_dir = exp_dir / "data"
    eda_dir  = exp_dir / "eda" / "figures"
    eda_dir.mkdir(parents=True, exist_ok=True)

    try:
        # All three splits: omitting clean_val understated every class count by the
        # size of the validation set, so the chart read 4,839 per class instead of
        # the corpus total of 5,693 and looked like a different dataset.
        train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
        val_df   = pd.read_csv(data_dir / "clean_val.csv",   keep_default_na=False)
        test_df  = pd.read_csv(data_dir / "clean_test.csv",  keep_default_na=False)
        all_df   = pd.concat([train_df, val_df, test_df], ignore_index=True)
        all_df["Text"] = all_df["Text"].fillna("").astype(str).str.strip()
        all_df = all_df[all_df["Text"].str.len() > 0]

        # 1. Class distribution
        counts = all_df["Label"].value_counts()
        plt.figure(figsize=(5, 4))
        ax1 = counts.plot(kind="bar", color=["#4C72B0", "#DD8452"], edgecolor="black")
        ax1.bar_label(ax1.containers[0], fmt='%d', padding=4, fontsize=10, fontweight='bold')
        ax1.set_ylim(0, counts.max() * 1.12)
        plt.title(f"Class Distribution (n = {len(all_df):,})")
        plt.xlabel("Label"); plt.ylabel("Count")
        plt.xticks(rotation=0); plt.tight_layout()
        plt.savefig(eda_dir / "class_distribution.svg", dpi=180)
        plt.close()

        # 2. Sentence length histogram
        all_df["length"] = all_df["Text"].str.split().str.len()
        plt.figure(figsize=(7, 4))
        for label, color in [("AI", "#4C72B0"), ("HUMAN", "#DD8452")]:
            sub = all_df[all_df["Label"] == label]["length"]
            plt.hist(sub, bins=40, alpha=0.6, label=label, color=color)
        plt.title("Sentence Length Distribution (words)")
        plt.xlabel("Word Count"); plt.ylabel("Frequency")
        plt.legend(); plt.tight_layout()
        plt.savefig(eda_dir / "sentence_length_hist.svg", dpi=180)
        plt.close()

        # 3. Top-20 words
        all_tokens: list[str] = []
        for text in all_df["Text"]:
            all_tokens.extend(re.findall(r"\b\w+\b", str(text).lower()))
        from collections import Counter
        top20 = Counter(all_tokens).most_common(20)
        words, freqs = zip(*top20)
        fig3, ax3 = plt.subplots(figsize=(10, 5))
        bars3 = ax3.barh(list(words)[::-1], list(freqs)[::-1], color="#4C72B0")
        ax3.bar_label(bars3, fmt='%d', padding=4, fontsize=8, fontweight='bold')
        ax3.set_xlim(0, max(freqs) * 1.12)
        ax3.set_title("Top 20 Most Frequent Words")
        ax3.set_xlabel("Frequency"); plt.tight_layout()
        plt.savefig(eda_dir / "top20_words.svg", dpi=180)
        plt.close()

        # 4. AI type distribution (from full_dataset.xlsx/csv)
        fd_path = ROOT / "data" / "raw" / "full_dataset.xlsx"
        if not fd_path.exists():
            fd_path = ROOT / "data" / "raw" / "full_dataset.csv"
        if fd_path.exists():
            import re as _re
            if fd_path.suffix.lower() in {".xlsx", ".xlsm"}:
                from experiments.run_balanced_experiments import load_table, normalize_category
                fd = load_table(fd_path).fillna("")
            else:
                fd = pd.read_csv(str(fd_path), keep_default_na=False)
                from experiments.run_balanced_experiments import normalize_category
            if "Ai Type" in fd.columns:
                def _norm(v):
                    t = _re.sub(r"[^a-z]","", str(v).lower())
                    if "chatgpt" in t: return "ChatGPT"
                    if "gemini"  in t: return "Gemini"
                    if any(x in t for x in ("claude","cloude","cluade")): return "Claude"
                    return None
                fd["ai_norm"] = fd["Ai Type"].apply(_norm)
                if "Category" in fd.columns:
                    fd["Category"] = fd["Category"].map(normalize_category)
                    fd = fd[fd["Category"].ne("Unknown")]
                fd_valid = fd[fd["ai_norm"].notna()]

                # AI type distribution pie
                ai_counts = fd_valid["ai_norm"].value_counts()
                plt.figure(figsize=(6,6))
                plt.pie(ai_counts.values, labels=ai_counts.index, autopct="%1.1f%%",
                        colors=["#4C72B0","#DD8452","#55A868"], startangle=90)
                plt.title("AI Type Distribution")
                plt.tight_layout()
                plt.savefig(eda_dir / "ai_type_distribution.svg", dpi=180)
                plt.close()

                # Category distribution (bar)
                if "Category" in fd.columns:
                    cat_counts = fd["Category"].value_counts()
                    plt.figure(figsize=(10,5))
                    ax_cat = cat_counts.plot(kind="bar", color="#4C72B0", edgecolor="black")
                    ax_cat.bar_label(ax_cat.containers[0], fmt='%d', padding=4,
                                     fontsize=9, fontweight='bold')
                    ax_cat.set_ylim(0, cat_counts.max() * 1.12)
                    plt.title("AI-Generated Articles by Category")
                    plt.xlabel("Category"); plt.ylabel("Count")
                    plt.xticks(rotation=45, ha="right"); plt.tight_layout()
                    plt.savefig(eda_dir / "ai_generated_category_distribution.svg", dpi=180)
                    plt.close()

                    # AI type by category (stacked bar)
                    if "ai_norm" in fd_valid.columns:
                        pivot = fd_valid.groupby(["Category","ai_norm"]).size().unstack(fill_value=0)
                        ax_stk = pivot.plot(kind="bar", stacked=True, figsize=(11,5),
                                            color=["#4C72B0","#DD8452","#55A868"])
                        # Add total count label on top of each stacked bar
                        totals = pivot.sum(axis=1)
                        for i, total in enumerate(totals):
                            ax_stk.text(i, total + totals.max() * 0.015, str(int(total)),
                                        ha='center', va='bottom', fontsize=9, fontweight='bold')
                        ax_stk.set_ylim(0, totals.max() * 1.14)
                        plt.title("AI Type by Category")
                        plt.xlabel("Category"); plt.ylabel("Count")
                        plt.xticks(rotation=45, ha="right")
                        plt.legend(title="AI Type"); plt.tight_layout()
                        plt.savefig(eda_dir / "ai_type_by_category.svg", dpi=180)
                        plt.close()

        print(f"  [OK] EDA figures saved to {eda_dir}")
    except Exception as exc:
        print(f"  [WARN] EDA figures failed: {exc}")


# ── traditional ML outputs ────────────────────────────────────────────────────
def generate_traditional_ml_outputs(exp_dir: Path) -> None:
    import joblib
    import pandas as pd
    import numpy as np
    from sklearn.metrics import (
        accuracy_score, f1_score, classification_report,
        precision_recall_fscore_support,
    )

    data_dir    = exp_dir / "data"
    model_dir   = exp_dir / "models" / "traditional_ml"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    test_df["Text"] = test_df["Text"].fillna("").astype(str).str.strip()
    test_df = test_df[test_df["Text"].str.len() > 0].reset_index(drop=True)
    x_test = test_df["Text"].tolist()
    y_test = test_df["Label"].map(LABEL2ID).to_numpy(dtype=int)

    rows = []
    for model_path in sorted(model_dir.glob("*.joblib")):
        name = model_path.stem
        try:
            model = joblib.load(model_path)
            y_pred = model.predict(x_test)

            acc = accuracy_score(y_test, y_pred)
            prec, rec, f1, _ = precision_recall_fscore_support(
                y_test, y_pred, average="weighted", zero_division=0)

            # Confusion matrix
            save_confusion_matrix(
                figures_dir / f"confusion_matrix_{name}.svg",
                y_test, y_pred, LABEL_NAMES,
                f"{exp_dir.name}: {name}",
            )

            # Classification report
            rpt = classification_report(y_test, y_pred, target_names=LABEL_NAMES, zero_division=0)
            (reports_dir / f"classification_report_{name}.txt").write_text(rpt, encoding="utf-8")
            pd.DataFrame(
                classification_report(y_test, y_pred, target_names=LABEL_NAMES,
                                      output_dict=True, zero_division=0)
            ).transpose().to_csv(reports_dir / f"classification_report_{name}.csv", index_label="label")

            rows.append({"model": name, "accuracy": acc,
                         "precision": prec, "recall": rec, "f1": f1})
            print(f"  [OK] {name}  acc={acc:.4f}  f1={f1:.4f}")

            # SHAP/LIME for LinearSVC only
            if name == "LinearSVC_TFIDF":
                _generate_xai(exp_dir, model, model_path, x_test, y_test, y_pred)

        except Exception as exc:
            print(f"  [WARN] {name} output failed: {exc}")

    if rows:
        pd.DataFrame(rows).sort_values("accuracy", ascending=False).to_csv(
            reports_dir / "traditional_ml_metrics.csv", index=False)


def _generate_xai(exp_dir: Path, model, model_path: Path,
                  x_test: list, y_test, y_pred) -> None:
    """SHAP + LIME explanations for a LinearSVC model."""
    import numpy as np
    import pandas as pd

    out_dir  = exp_dir / "xai" / "outputs"
    shap_dir = out_dir / "shap"
    lime_dir = out_dir / "lime"
    shap_dir.mkdir(parents=True, exist_ok=True)
    lime_dir.mkdir(parents=True, exist_ok=True)

    try:
        import shap
        # step may be named "tfidf" or "features" depending on pipeline
        features = model.named_steps.get("features") or model.named_steps.get("tfidf")
        if features is None:
            raise KeyError("No 'features' or 'tfidf' step found in pipeline")
        classifier = model.named_steps["clf"]
        feat_names = features.get_feature_names_out()
        feat_names = np.array([n.replace("word_tfidf__", "").replace("char_tfidf__", "")
                                for n in feat_names])

        x_mat  = features.transform(x_test[:100])
        x_dense = x_mat.toarray() if hasattr(x_mat, "toarray") else np.asarray(x_mat)

        masker     = shap.maskers.Independent(x_dense[:50])
        explainer  = shap.LinearExplainer(classifier, masker, feature_names=feat_names)
        shap_vals  = explainer.shap_values(x_dense[:50])
        mean_abs   = np.mean(np.abs(shap_vals if not isinstance(shap_vals, list)
                                    else np.stack(shap_vals, axis=0)), axis=0)
        if mean_abs.ndim > 1:
            mean_abs = mean_abs.mean(axis=0)

        pd.DataFrame([
            {"feature": feat_names[i], "mean_abs_shap": float(mean_abs[i])}
            for i in np.argsort(mean_abs)[-100:][::-1]
        ]).to_csv(shap_dir / "shap_global_importance.csv", index=False)

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        shap.summary_plot(shap_vals, x_dense[:50], feature_names=feat_names,
                          show=False, max_display=20)
        plt.tight_layout()
        plt.savefig(shap_dir / "shap_summary_plot.svg", dpi=180, bbox_inches="tight")
        plt.close()
        print("  [OK] SHAP outputs generated.")
    except Exception as exc:
        print(f"  [WARN] SHAP failed: {exc}")

    try:
        from lime.lime_text import LimeTextExplainer
        import numpy as np

        classifier = model.named_steps["clf"]
        features   = model.named_steps.get("features") or model.named_steps.get("tfidf")

        def predict_proba(texts):
            if hasattr(classifier, "decision_function"):
                scores = model.decision_function(texts)
                if scores.ndim == 1:
                    p = 1.0 / (1.0 + np.exp(-scores))
                    return np.column_stack([1 - p, p])
                exp_s = np.exp(scores - scores.max(axis=1, keepdims=True))
                return exp_s / exp_s.sum(axis=1, keepdims=True)
            return model.predict_proba(texts)

        explainer = LimeTextExplainer(class_names=LABEL_NAMES)
        # Use the last 3 test articles (most recent)
        lime_data_indices = list(range(max(0, len(x_test) - 3), len(x_test)))
        for out_idx, data_idx in enumerate(lime_data_indices):
            exp = explainer.explain_instance(x_test[data_idx], predict_proba,
                                             num_features=12, top_labels=1)
            exp.save_to_file(str(lime_dir / f"lime_explanation_{out_idx}.html"))
        print("  [OK] LIME explanations generated.")
    except Exception as exc:
        print(f"  [WARN] LIME failed: {exc}")

    # SHAP-like feature importance (lightweight fallback)
    try:
        import numpy as np, pandas as pd
        features   = model.named_steps.get("features") or model.named_steps.get("tfidf")
        classifier = model.named_steps["clf"]
        feat_names = features.get_feature_names_out()
        feat_names = np.array([n.replace("word_tfidf__", "").replace("char_tfidf__", "")
                                for n in feat_names])
        coef = classifier.coef_
        id2label = {0: "AI", 1: "HUMAN"}
        if coef.shape[0] == 1:
            rows = (
                [{"feature": feat_names[i], "importance": float(-coef[0][i]), "class_label": "AI"}
                 for i in np.argsort(coef[0])[:50]]
                + [{"feature": feat_names[i], "importance": float(coef[0][i]), "class_label": "HUMAN"}
                   for i in np.argsort(coef[0])[-50:][::-1]]
            )
        else:
            rows = []
            for ci, cw in enumerate(coef):
                for i in np.argsort(cw)[-50:][::-1]:
                    rows.append({"feature": feat_names[i], "importance": float(cw[i]),
                                 "class_label": id2label.get(ci, str(ci))})
        pd.DataFrame(rows).to_csv(out_dir / "shap_like_feature_importance.csv", index=False)
    except Exception:
        pass

    # Error analysis
    try:
        import pandas as pd
        test_df = pd.read_csv(exp_dir / "data" / "clean_test.csv", keep_default_na=False)
        test_df["Text"] = test_df["Text"].fillna("").astype(str).str.strip()
        test_df = test_df[test_df["Text"].str.len() > 0].reset_index(drop=True)
        y_t = test_df["Label"].map(LABEL2ID).to_numpy(dtype=int)
        y_p = model.predict(test_df["Text"].tolist())
        mask = y_t != y_p
        err = test_df[mask].copy()
        id2label = {0: "AI", 1: "HUMAN"}
        err["true_label"]      = [id2label[v] for v in y_t[mask]]
        err["predicted_label"] = [id2label[v] for v in y_p[mask]]
        err[["Text", "true_label", "predicted_label"]].head(25).to_csv(
            out_dir / "error_analysis_sample.csv", index=False)
    except Exception:
        pass


# ── Keras model outputs ───────────────────────────────────────────────────────
def generate_keras_outputs(exp_dir: Path) -> None:
    import joblib
    import numpy as np
    import pandas as pd
    from tensorflow.keras.preprocessing.sequence import pad_sequences

    data_dir    = exp_dir / "data"
    figures_dir = exp_dir / "evaluation" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    tok_path = data_dir / "tokenizer.joblib"
    if not tok_path.exists():
        print("  [SKIP] No tokenizer found — skip Keras confusion matrices.")
        return

    tok_meta  = joblib.load(tok_path)
    tokenizer = tok_meta["tokenizer"]
    max_len   = tok_meta["max_length"]
    classes   = tok_meta.get("classes", ["AI", "HUMAN"])

    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    test_df["Text"] = test_df["Text"].fillna("").astype(str).str.strip()
    test_df = test_df[test_df["Text"].str.len() > 0].reset_index(drop=True)
    seqs   = tokenizer.texts_to_sequences(test_df["Text"].tolist())
    padded = pad_sequences(seqs, maxlen=max_len, padding="post", truncating="post")
    y_test = test_df["Label"].map(LABEL2ID).to_numpy(dtype=int)

    keras_models = [
        ("deep_learning",  "BiLSTM_Keras"),
        ("transformers",   "MiniTransformer_Keras"),
    ]
    emb_models = [
        ("deep_learning",  "BiLSTM_Word2Vec"),
        ("deep_learning",  "BiLSTM_FastText"),
    ]

    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    # Register TransformerBlock so MiniTransformer_Keras can be loaded
    try:
        from experiments.transformer_block import TransformerBlock as _TB  # noqa: F401
    except Exception:
        pass

    for subfolder, model_name in keras_models + emb_models:
        model_path = exp_dir / "models" / subfolder / f"{model_name}.keras"
        if not model_path.exists():
            continue
        try:
            model  = tf.keras.models.load_model(model_path, compile=False)
            probs  = model.predict(padded, verbose=0)
            y_pred = np.argmax(probs, axis=1)
            save_confusion_matrix(
                figures_dir / f"confusion_matrix_{model_name}.svg",
                y_test, y_pred, LABEL_NAMES,
                f"{exp_dir.name}: {model_name}",
            )
            from sklearn.metrics import accuracy_score, f1_score
            acc = accuracy_score(y_test, y_pred)
            f1  = f1_score(y_test, y_pred, average="weighted")
            print(f"  [OK] {model_name}  acc={acc:.4f}  f1={f1:.4f}")
        except Exception as exc:
            print(f"  [WARN] {model_name} outputs failed: {exc}")


# ── results CSV update ────────────────────────────────────────────────────────
def update_results_csv(exp_dir: Path) -> None:
    """Rebuild all_models_comparison.csv from existing comparison + new metrics."""
    results_dir = exp_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    existing_csv = results_dir / "all_models_comparison.csv"
    if not existing_csv.exists():
        print("  [SKIP] No all_models_comparison.csv to update.")
        return

    import pandas as pd
    df = pd.read_csv(existing_csv)
    df.to_csv(existing_csv, index=False)
    print(f"  [OK] Results CSV preserved: {existing_csv.name}")


# ── full output generation for one experiment ─────────────────────────────────
def generate_all_outputs(exp_dir: Path) -> None:
    step("Deleting old outputs")
    delete_old_outputs(exp_dir)

    step("Generating EDA figures")
    generate_eda_figures(exp_dir)

    step("Generating traditional ML confusion matrices + reports + SHAP/LIME")
    generate_traditional_ml_outputs(exp_dir)

    step("Generating Keras model confusion matrices")
    generate_keras_outputs(exp_dir)


# ── training functions ────────────────────────────────────────────────────────
def train_traditional(exp_dir: Path, seed: int, force: bool) -> None:
    missing = [m for m in TRADITIONAL_ML_MODELS if not _joblib_exists(exp_dir, m)]
    if not force and not missing:
        print("  [SKIP] All traditional ML models already exist.")
        return

    targets = TRADITIONAL_ML_MODELS if force else missing
    print(f"  Training: {', '.join(targets)}")

    import pandas as pd
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline, FeatureUnion
    from sklearn.svm import LinearSVC
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    data_dir    = exp_dir / "data"
    model_dir   = exp_dir / "models" / "traditional_ml"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    val_df   = pd.read_csv(data_dir / "clean_val.csv",   keep_default_na=False)
    test_df  = pd.read_csv(data_dir / "clean_test.csv",  keep_default_na=False)
    for df in (train_df, val_df, test_df):
        df["Text"] = df["Text"].fillna("").astype(str).str.strip()
        df.drop(df[df["Text"].str.len() == 0].index, inplace=True)

    train_fit_df = pd.concat([train_df, val_df], ignore_index=True)
    final_fit_df = train_fit_df

    x_test  = test_df["Text"].astype(str).tolist()
    y_test  = test_df["Label"].map(LABEL2ID).to_numpy(dtype=int)
    x_train = train_fit_df["Text"].astype(str).tolist()
    y_train = train_fit_df["Label"].map(LABEL2ID).to_numpy(dtype=int)
    x_final = final_fit_df["Text"].astype(str).tolist()
    y_final = final_fit_df["Label"].map(LABEL2ID).to_numpy(dtype=int)

    tfidf_union = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                 max_features=20000, sublinear_tf=True, min_df=2)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 6),
                                 max_features=20000, sublinear_tf=True, min_df=2)),
    ])

    specs = {
        "LinearSVC_TFIDF": Pipeline([("tfidf", tfidf_union),
                                     ("clf", LinearSVC(C=2.0, class_weight="balanced",
                                                       max_iter=2000))]),
        "LogisticRegression_TFIDF": Pipeline([("tfidf", tfidf_union),
                                              ("clf", LogisticRegression(C=2.0,
                                                                         class_weight="balanced",
                                                                         max_iter=2000,
                                                                         solver="lbfgs"))]),
        "RandomForest_TFIDF": Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                     max_features=10000, sublinear_tf=True)),
            ("clf", RandomForestClassifier(n_estimators=120, class_weight="balanced",
                                           random_state=seed, n_jobs=-1)),
        ]),
    }

    try:
        from xgboost import XGBClassifier
        specs["XGBoost_TFIDF"] = Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                     max_features=15000, sublinear_tf=True)),
            ("clf", XGBClassifier(random_state=seed, eval_metric="logloss")),
        ])
    except ImportError:
        print("  [WARN] XGBoost not installed — skipping XGBoost_TFIDF")

    for name in targets:
        if name not in specs:
            continue
        t0   = time.time()
        pipe = specs[name]
        pipe.fit(x_train, y_train)
        y_pred = pipe.predict(x_test)
        acc  = accuracy_score(y_test, y_pred)
        f1   = f1_score(y_test, y_pred, average="weighted")
        report = classification_report(y_test, y_pred, target_names=LABEL_NAMES)
        # Save model trained only on train+validation; never fit on held-out test data.
        pipe.fit(x_final, y_final)
        out_path = model_dir / f"{name}.joblib"
        joblib.dump(pipe, out_path)
        (reports_dir / f"classification_report_{name}.txt").write_text(report,
                                                                        encoding="utf-8")
        elapsed = time.time() - t0
        print(f"  [OK] {name}  acc={acc:.4f}  f1={f1:.4f}  ({elapsed:.0f}s)  -> {out_path.name}")


def train_keras_models(exp_dir: Path, force: bool) -> None:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    from experiments.run_full_12_steps import (
        tokenize_with_keras, train_bilstm, train_mini_transformer,
    )

    seed     = 42
    data_dir = exp_dir / "data"

    tok_file = data_dir / "tokenizer.joblib"
    if force or not tok_file.exists():
        print("  [RUN] Building Keras tokenizer ...")
        tokenize_with_keras(exp_dir, max_tokens=30_000, max_length=256)
    else:
        print("  [SKIP] tokenizer.joblib already exists.")

    bilstm_path = exp_dir / "models" / "deep_learning" / "BiLSTM_Keras.keras"
    if force or not bilstm_path.exists():
        print("  [RUN] Training BiLSTM_Keras ...")
        m = train_bilstm(exp_dir, LABEL_NAMES, seed)
        print(f"        acc={m.get('accuracy',0):.4f}  f1={m.get('f1',0):.4f}")
    else:
        print("  [SKIP] BiLSTM_Keras.keras already exists.")

    mini_path = exp_dir / "models" / "transformers" / "MiniTransformer_Keras.keras"
    if force or not mini_path.exists():
        print("  [RUN] Training MiniTransformer_Keras ...")
        m = train_mini_transformer(exp_dir, LABEL_NAMES, seed)
        print(f"        acc={m.get('accuracy',0):.4f}  f1={m.get('f1',0):.4f}")
    else:
        print("  [SKIP] MiniTransformer_Keras.keras already exists.")


def train_embedding_models(exp_dir: Path, force: bool) -> None:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    from experiments.run_completion_pass import train_bilstm_with_embeddings, keras_artifact_exists

    seed = 42
    for emb_type, model_name in [("word2vec", "BiLSTM_Word2Vec"), ("fasttext", "BiLSTM_FastText")]:
        if not force and keras_artifact_exists(exp_dir, model_name):
            print(f"  [SKIP] {model_name}.keras already exists.")
        else:
            print(f"  [RUN] Training {model_name} ...")
            m = train_bilstm_with_embeddings(exp_dir, LABEL_NAMES, seed, emb_type, model_name)
            print(f"        acc={m.get('accuracy',0):.4f}  f1={m.get('f1',0):.4f}")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Train all models + regenerate all outputs.")
    parser.add_argument("--force-all", action="store_true",
                        help="Retrain everything even if models already exist.")
    parser.add_argument("--force-exp", choices=EXPERIMENTS, default=None,
                        help="Force retrain for one specific experiment only.")
    parser.add_argument("--skip-traditional", action="store_true",
                        help="Skip traditional ML training.")
    parser.add_argument("--skip-deep", action="store_true",
                        help="Skip Keras deep learning training.")
    parser.add_argument("--skip-embedding", action="store_true",
                        help="Skip Word2Vec/FastText BiLSTM training.")
    parser.add_argument("--outputs-only", action="store_true",
                        help="Skip all training — only regenerate plots/reports.")
    parser.add_argument("--skip-outputs", action="store_true",
                        help="Skip output generation (train only, no plots).")
    args = parser.parse_args()

    total_start = time.time()
    print("\n" + "=" * 60)
    print("  SOMALI NLP - TRAIN ALL MODELS")
    print("=" * 60)
    print("  Models already trained will be SKIPPED automatically.")
    print("  Use --force-all to retrain everything from scratch.")
    print("  Outputs (plots/reports) regenerated automatically after training.\n")

    for exp_name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp_name
        force   = args.force_all or (args.force_exp == exp_name)

        print(f"\n{'=' * 60}")
        print(f"  EXPERIMENT: {exp_name}")
        print(f"{'=' * 60}")

        if not args.outputs_only:
            if not args.skip_traditional:
                step("Traditional ML  (LinearSVC / LogReg / RandomForest / XGBoost)")
                train_traditional(exp_dir, seed=42, force=force)

            if not args.skip_deep:
                step("Keras Deep Learning  (BiLSTM / MiniTransformer)")
                train_keras_models(exp_dir, force=force)

            if not args.skip_embedding:
                step("Embedding BiLSTMs  (Word2Vec / FastText)")
                train_embedding_models(exp_dir, force=force)

        if not args.skip_outputs:
            step("Regenerating all outputs (plots, reports, XAI)")
            generate_all_outputs(exp_dir)

    elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"  ALL DONE in {elapsed / 60:.1f} minutes")
    print(f"  Restart backend to load new models:")
    print(f"  -> Ctrl+C then re-run uvicorn")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
