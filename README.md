# Somali NLP Research

This project is based on the labeled binary dataset in:

- `data/raw/labeled_text.xlsx`

The active task is **AI vs HUMAN Somali text classification**. The larger
`data/raw/full_dataset.csv` is kept as supplemental/reference data, but the supervised labels used
for model training come from `labeled_text.xlsx`.

## Experiments

The two canonical experiment folders are:

- `experiments/experiment_1_stopwords_included/`
- `experiments/experiment_2_stopwords_removed/`

Each experiment contains its own data splits, trained models, evaluation reports, figures, XAI
outputs, and final result summaries.

## Installation and Setup (For Cloning the Repository)

If you are cloning this repository for the first time, follow these steps to set up the environment and download the trained models:

### 1. Install Git LFS (Large File Storage)
The trained model weights (e.g., `.safetensors`, `.keras`, `.joblib`, `.model`) are stored using Git LFS.
- Install Git LFS on your system (if not already installed).
- Run the following command once in your terminal:
  ```bash
  git lfs install
  ```
- Clone the repository:
  ```bash
  git clone <repository-url>
  cd somali-nlp-research
  ```
- If the model files did not download automatically during cloning, run the following to pull them:
  ```bash
  git lfs pull
  ```

### 2. Create a Virtual Environment
It is highly recommended to use a local virtual environment:
```bash
# Create the environment
python -m venv .venv

# Activate it:
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
Install all required Python libraries:
```bash
pip install -r requirements.txt
```

### 4. Verify Model Setup
You can run the model evaluation script to verify that the models have loaded and run correctly:
```bash
python experiments/reevaluate_saved_models.py
```

## Dataset

After cleaning, conflict removal, and duplicate removal:

| Label | Rows |
|---|---:|
| AI | 2985 |
| HUMAN | 2884 |
| Total | 5869 |

Split layout per experiment:

| Split | Rows |
|---|---:|
| Train | 4109 |
| Validation | 881 |
| Test | 879 |
| Full final training set | 5869 |

Metrics and confusion matrices are computed on the held-out test split. The saved `.joblib` model
artifacts are then refit on the full dataset (`train + validation + test`) so final models use all
available labeled rows.

## Rebuild

Run the complete default experiment pipeline:

```powershell
.\.venv\Scripts\python.exe experiments\run_balanced_experiments.py --stage traditional --task label --sampling full
```

Default models:

- `LogisticRegression_TFIDF`
- `LinearSVC_TFIDF`

Optional slower models:

```powershell
.\.venv\Scripts\python.exe experiments\run_balanced_experiments.py --stage traditional --task label --sampling full --include-random-forest
.\.venv\Scripts\python.exe experiments\run_balanced_experiments.py --stage traditional --task label --sampling full --include-xgboost
```

## Current Full 12-Step Results

The full project runner trains all required model families: baseline ML models, BiLSTM, a
lightweight transformer, and XLM-R fine-tuning:

```powershell
.\.venv\Scripts\python.exe experiments\run_full_12_steps.py
```

| Experiment | Family | Model | Accuracy | F1 |
|---|---|---|---:|---:|
| Stopwords included | Traditional ML | LinearSVC_TFIDF | 0.9431 | 0.9431 |
| Stopwords removed | Traditional ML | LinearSVC_TFIDF | 0.9329 | 0.9329 |
| Stopwords included | Transformer | MiniTransformer_Keras | 0.9261 | 0.9261 |
| Stopwords included | Traditional ML | LogisticRegression_TFIDF | 0.9226 | 0.9224 |
| Stopwords removed | Traditional ML | LogisticRegression_TFIDF | 0.9215 | 0.9213 |
| Stopwords removed | Deep Learning | BiLSTM_Keras | 0.9124 | 0.9122 |
| Stopwords included | Deep Learning | BiLSTM_Keras | 0.9067 | 0.9065 |
| Stopwords included | Traditional ML | RandomForest_TFIDF | 0.9044 | 0.9040 |
| Stopwords removed | Traditional ML | XGBoost_TFIDF | 0.9022 | 0.9017 |
| Stopwords removed | Traditional ML | RandomForest_TFIDF | 0.9010 | 0.9006 |
| Stopwords included | Traditional ML | XGBoost_TFIDF | 0.8976 | 0.8973 |
| Stopwords removed | Transformer | MiniTransformer_Keras | 0.8862 | 0.8851 |
| Stopwords included | Transformer | XLMRoberta_FineTuned | 0.7645 | 0.7642 |
| Stopwords removed | Transformer | XLMRoberta_FineTuned | 0.7418 | 0.7361 |

XLM-R was fine-tuned with CPU-friendly settings: classifier head and final encoder block trainable,
one epoch, and `max_length=128`.

Detailed outputs:

- `experiments/experiment_1_stopwords_included/results/`
- `experiments/experiment_2_stopwords_removed/results/`
- `experiments/full_12_step_run_summary.json`
