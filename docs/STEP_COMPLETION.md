# 12-Step Completion Report

The project has been rerun for the corrected binary `AI` vs `HUMAN` task using
`data/raw/labeled_text.xlsx` as the supervised label source.

| Step | Status | Output |
|---|---|---|
| 1. Data loading | Complete | `experiments/*/data/full_labeled_dataset.csv` |
| 2. Label verification | Complete | `experiments/*/results/experiment_summary.json` |
| 3. Preprocessing | Complete | `experiments/*/data/clean_train.csv`, `clean_val.csv`, `clean_test.csv` |
| 4. EDA | Complete | `experiments/*/eda/figures/`, `experiments/*/eda/reports/` |
| 5. Baseline ML models | Complete | Logistic Regression, LinearSVC, RandomForest, XGBoost in `experiments/*/models/traditional_ml/` |
| 6. Deep learning | Complete | `experiments/*/models/deep_learning/BiLSTM_Keras.keras` |
| 7. Tokenization | Complete | `experiments/*/data/train_tok.pkl`, `val_tok.pkl`, `test_tok.pkl` |
| 8. XLM-R fine-tuning | Complete | `experiments/*/models/transformers/xlm-roberta-base/` |
| 9. Evaluation | Complete | `experiments/*/evaluation/reports/step9_metrics.csv` |
| 10. XAI | Complete | `experiments/*/xai/outputs/` |
| 11. Results comparison | Complete | `experiments/full_12_step_run_summary.json` |
| 12. Paper/report | Complete | `paper/research_paper.md` |

## Best Result

| Experiment | Family | Model | Accuracy | F1 |
|---|---|---|---:|---:|
| Stopwords included | Traditional ML | LinearSVC_TFIDF | 0.9431 | 0.9431 |

## Transformer Notes

XLM-R was fine-tuned from `xlm-roberta-base` with CPU-friendly settings: one epoch, `max_length=128`,
classifier head and final encoder block trainable. A lightweight `MiniTransformer_Keras` model was
also trained from scratch and saved under `experiments/*/models/transformers/`.
