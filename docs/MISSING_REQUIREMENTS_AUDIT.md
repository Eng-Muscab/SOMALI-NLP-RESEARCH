# Missing Requirements Audit

Source checked:

- `docs/NLP_Research_Project_Notes.pdf`
- `experiments/experiment_1_stopwords_included/`
- `experiments/experiment_2_stopwords_removed/`

## Overall Status

The PDF-required model variants and documentation items have been completed through
`experiments/run_completion_pass.py`.

## Completed In Both Experiments

| Requirement | Status |
|---|---|
| Data collection from labeled file | Complete |
| Text and label column checks | Complete |
| Duplicate/empty row removal | Complete |
| 70/15/15 train/validation/test split | Complete |
| Clean train/val/test files | Complete |
| EDA class distribution | Complete |
| EDA word frequency/top words | Complete |
| EDA sentence length chart | Complete |
| TF-IDF feature engineering | Complete |
| Logistic Regression | Complete |
| Linear SVM | Complete |
| Random Forest | Complete |
| XGBoost | Complete |
| Accuracy, precision, recall, F1, macro-F1 | Complete |
| Confusion matrices | Complete |
| BiLSTM baseline | Complete |
| BiLSTM + Word2Vec embeddings | Complete |
| BiLSTM + FastText embeddings | Complete |
| XLM-RoBERTa fine-tuning | Complete |
| mBERT fine-tuning | Complete |
| SomBERTa fine-tuning | Complete |
| AfroXLMR fine-tuning | Complete |
| AfriBERTa fine-tuning | Complete |
| GridSearchCV tuning for baseline ML | Complete |
| Package-level SHAP and LIME | Complete |
| Result comparison | Complete |
| Research discussion/paper draft | Complete |

## Partially Complete

| Requirement | Current state | What remains |
|---|---|---|
| Annotation & label verification | Labels normalized to `AI`/`HUMAN`; invalid/conflicting duplicates removed | Inter-annotator agreement is documented in `docs/inter_annotator_agreement.md`. The source file has only one `Label` column, so agreement cannot be computed. |
| Hugging Face tokenization | Tokenizers are used during transformer fine-tuning | Persist standalone `input_ids` and `attention_mask` files only if the marking scheme explicitly requires them |

## Model Rows Per Experiment

Each experiment now contains 13 evaluated model rows:

- `LogisticRegression_TFIDF`
- `LinearSVC_TFIDF`
- `RandomForest_TFIDF`
- `XGBoost_TFIDF`
- `BiLSTM_Keras`
- `BiLSTM_Word2Vec`
- `BiLSTM_FastText`
- `MiniTransformer_Keras`
- `XLMRoberta_FineTuned`
- `mBERT_FineTuned`
- `SomBERTa_FineTuned`
- `AfroXLMR_FineTuned`
- `AfriBERTa_FineTuned`

## How To Reproduce The Completion Pass

```bash
py -3.12 experiments/run_completion_pass.py
```

Useful flags:

- `--only-experiment experiment_1_stopwords_included`
- `--skip-transformers`
- `--skip-embeddings`
- `--skip-tuning`
- `--skip-xai`
