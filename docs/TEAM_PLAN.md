# Qorshaha Team-ka (NLP Research Project)

Document-kan waa sharaxaad kooban (roadmap) si team-ku u wada fahmo hawsha iyo hab-raaca.

## Qof 1 — Data & Preprocessing (Branch: `qof1-data-preprocessing`)

### Deliverables (waxyaabaha qofka 1 soo saarayo)

- Labels final: `data/annotations/labeled_ai_human_final.csv`
- Clean splits:
  - `data/processed/clean_train.csv`
  - `data/processed/clean_val.csv`
  - `data/processed/clean_test.csv`
- Tokenized datasets (si training u fududaato):
  - `data/processed/train_tok.pkl`
  - `data/processed/val_tok.pkl`
  - `data/processed/test_tok.pkl`
- Label mapping (qof walba ha isku mid u isticmaalo):
  - `HUMAN = 0`
  - `AI = 1`
- Tokenizer settings (qof walba ha isku mid u isticmaalo):
  - `model_name = xlm-roberta-base`
  - `max_length = 256`
  - `padding = max_length`
  - `truncation = True`

### Hab-raac (tallaabo-tallaabo)

**STEP 1 — Data Collection**
- Soo ururi dataset-ka
- Hubi text column iyo label column
- Ka saar duplicate rows iyo empty rows
- Dataset kala saar: 70% Train, 15% Validation, 15% Test
- Kaydi train/val/test (ama u dhig magacyada repo-ga)

**STEP 2 — Annotation & Label Verification**
- Dib u eeg labels-ka (waa in ay noqdaan `AI` ama `HUMAN`)
- Ka saar duplicates (Text isku mid ah, label isku mid ah → mid kaliya reeb)
- Haddii Text isku mid ah uu yeesho label kala duwan (conflict) → manual sax
- Kaydi labels final: `data/annotations/labeled_ai_human_final.csv`

**STEP 3 — Preprocessing + Split (clean_*.csv)**
- Text cleaning rules ku qor `preprocessing/utils/text_cleaner.py`
- Orod dataset prep (repo root):
  - `.\.venv\Scripts\python.exe -m preprocessing.prepare_dataset --config config.yaml`
- Waxaa la filayaa in ay soo baxaan:
  - `data/processed/clean_train.csv`
  - `data/processed/clean_val.csv`
  - `data/processed/clean_test.csv`

**STEP 7 — Tokenization (Hugging Face)**
- Notebook: `preprocessing/07_tokenization.ipynb`
- Tokenize `clean_*.csv` → samee `input_ids` iyo `attention_mask`
- Label mapping: `HUMAN=0`, `AI=1`
- Kaydi outputs:
  - `data/processed/train_tok.pkl`
  - `data/processed/val_tok.pkl`
  - `data/processed/test_tok.pkl`

## Qof 2 — EDA & Traditional ML (Branch: `qof2-eda-ml`)

**STEP 4 — Exploratory Data Analysis (EDA)**
- Class distribution chart
- Word frequency analysis
- Most common tokens
- Sentence length analysis
- Visualization charts
- Isticmaal matplotlib iyo seaborn → `eda/figures/`

**STEP 5 — Traditional ML Models**
- TF-IDF feature engineering
- Word n-grams iyo character n-grams
- Train Logistic Regression
- Train Linear SVM
- Train Random Forest (optional)
- Train XGBoost (optional)
- GridSearchCV hyperparameter tuning
- Evaluate using Accuracy, Precision, Recall, F1-score

## Qof 3 — Deep Learning & Transformers (Branch: `qof3-deeplearning`)

**STEP 6 — Deep Learning Models**
- Build BiLSTM architecture
- Isticmaal Word2Vec iyo FastText embeddings
- Train and validate models
- Prevent overfitting using Dropout iyo Early Stopping
- Save training logs → `models/deep_learning/training_logs/`

**STEP 8 — Transformer Fine-tuning**
- Fine-tune mBERT
- Fine-tune XLM-RoBERTa
- Fine-tune SomBERTa, AfroXLMR, AfriBERTa
- Save best checkpoint → `models/transformers/checkpoints/`
- Generate accuracy/metrics comparison table

## Qof 4 — Evaluation, XAI & Research Writing (Branch: `qof4-evaluation`)

**STEP 9 — Evaluation**
- Evaluate all models
- Calculate Accuracy, Precision, Recall, F1-score
- Generate confusion matrix → `evaluation/figures/`

**STEP 10 — Explainable AI (XAI)**
- Implement SHAP
- Implement LIME
- Feature importance analysis
- Error analysis

**STEP 11 — Model Comparison**
- Compare all ML, DL, iyo Transformer models
- Identify best model
- Write strengths iyo weaknesses
- Update:
  - `results/all_models_comparison.csv`
  - `results/best_model_summary.md`

**STEP 12 — Research Discussion & Final Paper**
- Write findings
- Discuss challenges
- Add future work
- Write conclusion
- Update `paper/research_paper.md`

## Isku-xirnaanta (Dependencies)

- Dadka oo dhan waxay ku tiirsan yihiin `data/processed/clean_*.csv` iyo `config.yaml` settings.
- Ka hor EDA/Models/Evaluation: hubi in columns-ka `Text` iyo `Label` (iyo label mapping) ay isku mid yihiin dhammaan notebooks.
