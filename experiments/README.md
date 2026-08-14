# Binary Label Experiments

This folder contains the two canonical AI-vs-HUMAN retraining experiments based on
`data/raw/labeled text.xlsx`.

## Task

The active supervised task is binary classification:

- `AI`
- `HUMAN`

`data/raw/full_dataset.xlsx` is kept as supplemental/reference data only. It is not the source of the
training labels for the default pipeline.

## Experiments

- `experiment_1_stopwords_included/`: clean text with Somali function words kept.
- `experiment_2_stopwords_removed/`: clean text with selected Somali function words removed.

Each experiment contains:

- `data/`: full labeled dataset plus train, validation, and test splits.
- `models/traditional_ml/`: trained model artifacts.
- `evaluation/reports/`: metrics, classification reports, and parameter tables.
- `evaluation/figures/`: confusion matrices.
- `xai/outputs/`: feature importance, error samples, and local HTML explanations.
- `results/`: final comparison tables and best-model summaries.

## Run

Full 12-step project run:

```powershell
.\.venv\Scripts\python.exe experiments\run_full_12_steps.py --skip-xlm-r
.\.venv\Scripts\python.exe experiments\run_completion_pass.py --skip-transformers --skip-tuning --force
```

Traditional ML only:

```powershell
.\.venv\Scripts\python.exe experiments\run_balanced_experiments.py --stage traditional --task label --sampling full
```

Full runner models:

- `LogisticRegression_TFIDF`
- `LinearSVC_TFIDF`
- `RandomForest_TFIDF`
- `XGBoost_TFIDF`
- `BiLSTM_Keras`
- `BiLSTM_Word2Vec`
- `BiLSTM_FastText`
- `MiniTransformer_Keras`
- `XLMRoberta_FineTuned` when pretrained transformer fine-tuning is not skipped
