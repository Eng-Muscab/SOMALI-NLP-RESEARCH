# Team Plan

Project-ku hadda wuxuu ku base-gareysan yahay labeled binary dataset:

- `data/raw/labeled_text.xlsx`

`data/raw/full_dataset.csv` waa supplemental/reference data, laakiin supervised model training-ka
default-ka ah wuxuu ka imanayaa `labeled_text.xlsx`.

## Active Label Format

Task-ka saxda ah waa binary classification:

- `AI`
- `HUMAN`

Clean dataset summary:

- `AI`: 2985
- `HUMAN`: 2884
- Total: 5869

Split:

- Train: 4109
- Validation: 881
- Test: 879

## Canonical Experiment Structure

Experiment kasta wuxuu leeyahay:

```text
data/
eda/
models/
  traditional_ml/
evaluation/
  reports/
  figures/
xai/
  outputs/
results/
```

## QOF 1 - Data & Preprocessing

### STEP 1 - Data Loading

- Isticmaal `data/raw/labeled_text.xlsx`.
- Columns-ka source-of-truth waa `Text` iyo `Label`.
- Normalize labels to `AI` and `HUMAN`.
- Ka saar empty text, invalid labels, conflicting duplicate labels, iyo duplicate rows.
- Kaydi:
  - `experiments/<experiment>/data/full_labeled_dataset.csv`
  - `experiments/<experiment>/data/balanced_labeled_dataset.csv`
  - `experiments/<experiment>/data/train.csv`
  - `experiments/<experiment>/data/val.csv`
  - `experiments/<experiment>/data/test.csv`

### STEP 2 - Label Verification

- Hubi in labels-ku yihiin `AI` ama `HUMAN`.
- Hubi class balance-ka.
- Kaydi summary:
  - `experiments/<experiment>/results/experiment_summary.json`

### STEP 3 - Preprocessing

- Lowercasing
- Remove URLs/emails
- Remove unnecessary symbols
- Normalize whitespace
- Experiment 1: stopwords/function words ha la reebo
- Experiment 2: selected Somali function words ha la saaro
- Kaydi:
  - `experiments/<experiment>/data/clean_train.csv`
  - `experiments/<experiment>/data/clean_val.csv`
  - `experiments/<experiment>/data/clean_test.csv`

## QOF 2 - EDA & Traditional ML

### STEP 4 - EDA

- Class distribution chart
- Word frequency analysis
- Sentence length analysis
- Save figures:
  - `experiments/<experiment>/eda/figures/`

### STEP 5 - Traditional ML

Default models:

- Logistic Regression + TF-IDF
- Linear SVM + TF-IDF

Optional slower models:

- Random Forest + TF-IDF
- XGBoost + TF-IDF

Save outputs:

- `experiments/<experiment>/models/traditional_ml/`
- `experiments/<experiment>/evaluation/reports/`
- `experiments/<experiment>/evaluation/figures/`

## QOF 3 - Optional Deep Learning & Transformers

Deep learning or transformer models can be added later, but their outputs must stay inside each
experiment folder.

## QOF 4 - Evaluation, XAI & Writing

### STEP 9 - Evaluation

- Accuracy
- Precision
- Recall
- F1-score
- Macro-F1
- Confusion matrix
- Save outputs:
  - `experiments/<experiment>/evaluation/reports/`
  - `experiments/<experiment>/evaluation/figures/`

### STEP 10 - XAI

- SHAP-like feature importance
- Local HTML explanations
- Error analysis
- Save outputs:
  - `experiments/<experiment>/xai/outputs/`

### STEP 11-12 - Final Report

- Use `paper/research_paper.md`.
- Report the binary `AI` vs `HUMAN` results, not the old `Ai Type` task.
