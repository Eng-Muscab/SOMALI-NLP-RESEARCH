# Somali NLP Research

This project is based on the labeled binary dataset in:

- `data/raw/labeled text.xlsx`

The active task is **AI vs HUMAN Somali text classification**. The larger
`data/raw/full_dataset.xlsx` is kept as supplemental/reference data for EDA/category analytics, but
the supervised labels used for model training come from `labeled text.xlsx`.

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
| AI | 5693 |
| HUMAN | 5693 |
| Total | 11386 |

Split layout per experiment:

| Split | Rows |
|---|---:|
| Train | 7970 |
| Validation | 1708 |
| Test | 1708 |
| Full final training set | 11386 |

Metrics and confusion matrices are computed on the held-out test split. The saved `.joblib` model
artifacts are then refit on the full dataset (`train + validation + test`) so final models use all
available labeled rows.

## Rebuild

Run the complete default experiment pipeline:

```powershell
.\.venv\Scripts\python.exe experiments\run_full_12_steps.py --skip-xlm-r
.\.venv\Scripts\python.exe experiments\run_completion_pass.py --skip-transformers --skip-tuning --force
```

This refreshes preprocessing, EDA, traditional ML, Keras BiLSTM, MiniTransformer, Word2Vec/FastText
BiLSTM models, evaluation reports, confusion matrices, ROC curves, XAI outputs, and result tables.

## Current Full 12-Step Results

The full project runner trains all required model families: baseline ML models, BiLSTM, a
lightweight transformer, and XLM-R fine-tuning:

```powershell
.\.venv\Scripts\python.exe experiments\run_full_12_steps.py
```

| Experiment | Family | Model | Accuracy | F1 |
|---|---|---|---:|---:|
| Stopwords included | Traditional ML | LinearSVC_TFIDF | **0.9479** | **0.9479** |
| Stopwords included | Traditional ML | LogisticRegression_TFIDF | 0.9321 | 0.9320 |
| Stopwords removed | Traditional ML | LinearSVC_TFIDF | 0.9221 | 0.9221 |
| Stopwords removed | Traditional ML | LogisticRegression_TFIDF | 0.9016 | 0.9013 |
| Stopwords included | Transformer | MiniTransformer_Keras | 0.8970 | 0.8964 |
| Stopwords included | Deep Learning | BiLSTM_Keras | 0.8964 | 0.8963 |
| Stopwords removed | Transformer | MiniTransformer_Keras | 0.8952 | 0.8951 |
| Stopwords removed | Deep Learning | BiLSTM_Keras | 0.8870 | 0.8869 |
| Stopwords included | Deep Learning | BiLSTM_Word2Vec | 0.8788 | 0.8788 |
| Stopwords included | Traditional ML | RandomForest_TFIDF | 0.8730 | 0.8724 |
| Stopwords included | Deep Learning | BiLSTM_FastText | 0.8694 | 0.8694 |
| Stopwords included | Traditional ML | XGBoost_TFIDF | 0.8642 | 0.8634 |
| Stopwords removed | Traditional ML | RandomForest_TFIDF | 0.8513 | 0.8508 |
| Stopwords removed | Deep Learning | BiLSTM_FastText | 0.8507 | 0.8497 |
| Stopwords removed | Deep Learning | BiLSTM_Word2Vec | 0.8501 | 0.8495 |
| Stopwords removed | Transformer | AfriBERTa_FineTuned | 0.8396 | 0.8394 |
| Stopwords included | Transformer | SomBERTa_FineTuned | 0.8384 | 0.8379 |
| Stopwords included | Transformer | AfriBERTa_FineTuned | 0.8361 | 0.8359 |
| Stopwords removed | Traditional ML | XGBoost_TFIDF | 0.8320 | 0.8300 |
| Stopwords removed | Transformer | SomBERTa_FineTuned | 0.8308 | 0.8298 |
| Stopwords removed | Transformer | AfroXLMR_FineTuned | 0.7974 | 0.7968 |
| Stopwords included | Transformer | AfroXLMR_FineTuned | 0.7652 | 0.7650 |
| Stopwords included | Transformer | XLMRoberta_FineTuned | 0.7213 | 0.7095 |
| Stopwords removed | Transformer | XLMRoberta_FineTuned | 0.6979 | 0.6950 |
| Stopwords removed | Transformer | mBERT_FineTuned | 0.6593 | 0.6508 |
| Stopwords included | Transformer | mBERT_FineTuned | 0.6440 | 0.6431 |

Best model: **LinearSVC_TFIDF, stopwords included — 94.79% accuracy, F1 0.948, ROC-AUC 0.990** on
the held-out 1,708-sample test set. `LinearSVC_TFIDF` tops both experiments.

Keeping Somali stopwords beats removing them for 10 of the 13 benchmarked models — including every traditional-ML model and every BiLSTM variant — under the expanded 483-word list, since it strips common content words in addition to grammatical function words. The 3 weakest fine-tuned transformers (AfroXLMR, mBERT, AfriBERTa) move the other way by 0.4-3.2 points, but all sit well below the champion: trained for a single CPU-budgeted epoch, they never learned to use the function-word signal in the first place.

All numbers above are recomputed from `evaluation/reports/classification_report_*.csv` by
`experiments/verify_paper_numbers.py`, which also fails if a report and its ROC curve came from
different fits. Run it to re-audit the paper, README and web app against the artifacts:

```powershell
.\.venv\Scripts\python.exe -m experiments.verify_paper_numbers
```

Detailed outputs:

- `experiments/experiment_1_stopwords_included/results/`
- `experiments/experiment_2_stopwords_removed/results/`
- `experiments/full_12_step_run_summary.json`

## Key Visualizations & Research Figures

### 1. Dataset Class & Category Distribution
| Class Distribution (AI vs HUMAN) | Category Distribution (Domains) |
|---|---|
| ![Class Distribution](paper/converted_chapter_v_figures/fig5_3_class_distribution.png) | ![Category Distribution](paper/converted_chapter_v_figures/fig5_4_category_distribution.png) |

### 2. Model Performance & Evaluation Curves
| Best Model (Logistic Regression Confusion Matrix) | Fine-Tuned SomBERTa ROC Curve |
|---|---|
| ![Logistic Regression Confusion Matrix](paper/converted_chapter_v_figures/fig5_1_cm_logreg_exp1.png) | ![SomBERTa ROC Curve](paper/converted_chapter_v_figures/fig5_5_roc_curve_somberta.png) |

### 3. Explainable AI (SHAP Feature Importance)
![SHAP Summary Plot](paper/converted_chapter_v_figures/fig5_6_shap_summary_plot.png)
