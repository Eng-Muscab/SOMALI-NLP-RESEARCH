# Qorshaha Team-ka (NLP Research Project)

Document-kan waa sharaxaad kooban oo ku salaysan `NLP_Research_Project_Notes.pdf` si team-ku u wada fahmo *hawsha* iyo *hab-raaca*.

## Qof 1 — Data & Preprocessing (Branch: `qof1-data-preprocessing`)

- **Step 1 — Data Collection**
  - Soo ururi dataset-ka
  - Hubi `text` column iyo `label` column
  - Ka saar duplicates iyo empty rows
  - Kala saar dataset-ka: 70% Train, 15% Validation, 15% Test
  - Kaydi `train.csv`, `val.csv`, `test.csv` (ama u dhig magacyada repo-ga)
- **Step 2 — Annotation & Label Verification**
  - Dib u eeg labels-ka, sax khaladaadka
  - Isticmaal hal annotation format
  - Samee inter-annotator agreement (haddii ay jiraan annotators badan)
  - Kaydi labels-ka finalka ah
- **Step 3 — Preprocessing**
  - Lowercasing, remove duplicates, remove unnecessary symbols
  - Text normalization + tokenization
  - Kaydi `clean_train.csv`, `clean_val.csv`, `clean_test.csv` gudaha `data/processed/`
- **Step 7 — Tokenization (Hugging Face)**
  - Tijaabi tokenizer (tusaale XLM-R)
  - Samee `input_ids` iyo `attention_masks`
  - Document tokenizer settings (max_length, truncation, padding)

## Qof 2 — EDA & Traditional ML (Branch: `qof2-eda-ml`)

- **Step 4 — EDA**
  - Class distribution
  - Word/token frequency
  - Sentence length analysis
  - Charts (matplotlib/seaborn) → `eda/figures/`
- **Step 5 — Traditional ML Models**
  - TF‑IDF feature engineering
  - Word n‑grams & character n‑grams
  - Train: Logistic Regression, Linear SVM, Random Forest, XGBoost (haddii la isticmaalo)
  - Hyperparameter tuning (GridSearchCV)
  - Evaluate: Accuracy, Precision, Recall, F1-score

## Qof 3 — Deep Learning & Transformers (Branch: `qof3-deeplearning`)

- **Step 6 — Deep Learning**
  - Build BiLSTM architecture
  - Isticmaal Word2Vec & FastText embeddings
  - Train/validate
  - Ka hortag overfitting: Dropout, Early Stopping
  - Save training logs gudaha `models/deep_learning/training_logs/`
- **Step 8 — Transformer Fine-tuning**
  - Fine-tune: mBERT, XLM-R, SomBERTa, AfroXLMR, AfriBERTa
  - Save best checkpoint gudaha `models/transformers/checkpoints/`
  - Soo saar table isbarbardhig (accuracy/metrics)

## Qof 4 — Evaluation, XAI & Paper (Branch: `qof4-evaluation`)

- **Step 9 — Evaluation**
  - Evaluate models-ka oo dhan
  - Metrics: Accuracy, Precision, Recall, F1
  - Confusion matrix + figures → `evaluation/figures/`
- **Step 10 — XAI**
  - Implement SHAP + LIME
  - Feature importance + error analysis
- **Step 11 — Model Comparison**
  - Compare ML, DL, Transformers
  - Aqoonsi best model + strengths/weaknesses
  - Update `results/all_models_comparison.csv` iyo `results/best_model_summary.md`
- **Step 12 — Discussion & Final Paper**
  - Write findings, challenges, future work, conclusion
  - Update `paper/research_paper.md`

## Isku-xirnaanta (Dependencies)

- Dadka oo dhan waxay ku tiirsan yihiin `data/processed/clean_*.csv` iyo `config.yaml` settings.
- Ka hor EDA/Models/Evaluation: hubi columns-ka `text_column` iyo `label_column` inay isku mid yihiin dhammaan notebooks.
