# Somali NLP Research

This repository contains an end-to-end workflow for a Somali NLP research project: data collection → annotation checks → preprocessing → EDA → modeling (traditional ML, deep learning, transformers) → evaluation → explainability (XAI) → results → paper write-up.

## Sharaxaad (Af‑Somali)

Repo-gan waa project cilmi‑baaris (research) oo ku saabsan NLP-ga Af‑Somaliga. Ujeedadu waa in la helo hab‑socod dhamaystiran oo laga bilaabo xog ururin ilaa natiijooyin la isbarbar dhigo iyo warqad cilmiyeed (paper).

## Hab-raac (Team Workflow)

Waxaan leenahay hab-raac 4 qof ah (Data/Preprocessing → EDA/Traditional ML → Deep Learning/Transformers → Evaluation/XAI/Paper). Qorshaha faahfaahsan eeg: `docs/TEAM_PLAN.md`.

## Project Structure

- `data/`
  - `raw/` original datasets (e.g., `dataset.csv`)
  - `processed/` cleaned splits (`clean_train.csv`, `clean_val.csv`, `clean_test.csv`)
      - Train:      4,200  (70%)
      - Validation:   900  (15%)
      - Test:      900  (15%)
  - `annotations/` label checks / verification (`label_verification.csv`)
- `preprocessing/` notebooks + utilities (e.g., `utils/text_cleaner.py`)
- `eda/` exploratory analysis + `figures/`
- `models/`
  - `traditional_ml/` classic ML baselines + `results/`
  - `deep_learning/` BiLSTM / FastText / Word2Vec notebooks + `training_logs/`
  - `transformers/` mBERT/XLM-R/SomBERTa/AfroXLMR/AfriBERTa notebooks + `checkpoints/`
- `evaluation/` evaluation notebook + `figures/`
- `xai/` SHAP/LIME notebooks
- `results/` aggregated comparisons + best-model summary
- `paper/` research paper draft + `figures/`

## Folders (Sharaxaad Kooban)

- `data/`: xogta (raw, processed, annotations).
- `preprocessing/`: nadiifin/diyaarin xog (cleaning), tokenization, iyo tools-ka.
- `eda/`: falanqayn hordhac (EDA) + sawirro.
- `models/`: tijaabooyinka moodooyinka (traditional ML, deep learning, transformers).
- `evaluation/`: qiimeyn (metrics, confusion matrix, iwm) + figures.
- `xai/`: sharaxaad moodal (SHAP/LIME).
- `results/`: isbarbardhig dhammaan models + summary-ga best model.
- `paper/`: qorista warqadda cilmiyeed + figures.

## Qaybinta Shaqada Team-ka (Branches)

- `qof1-data-preprocessing`: `data/`, `preprocessing/` (xog ururin, annotation check, preprocessing, tokenization).
- `qof2-eda-ml`: `eda/`, `models/traditional_ml/` (EDA + ML baselines + feature engineering).
- `qof3-deeplearning`: `models/deep_learning/` (BILSTM/FastText/Word2Vec + training logs).
- `qof4-evaluation`: `evaluation/`, `results/` (evaluation + isku-dubarid natiijooyin; XAI haddii la qoondeeyo).

## Setup

### Ka hor inta aadan bilaabin (Muhiim)

Si aad uga fogaato qaladka `Failed to build gensim` (ama `failed-wheel-build-for-install`), fadlan isticmaal:

- **Python 3.12 ama 3.11 (Recommended)**
- Ha isticmaalin **Python 3.14** waqtigan, sababtoo ah packages qaar (tusaale `gensim`) mararka qaar ma laha wheels diyaar ah, markaas `pip` wuxuu isku dayaa inuu source ka build-gareeyo Windows oo uu ku fashilmo.

Hubi Python versions-ka kuu rakiban:

```powershell
py -0p
```

Haddii aad haysato Python 3.12, hubi version-ka:

```powershell
py -3.12 -V
```

### 1) Create a virtual environment

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) (Optional) Jupyter

```powershell
jupyter lab
```

## Configuration

Project settings can be stored in `config.yaml` (paths, seeds, model names, etc.). You can keep it simple and edit as needed for your experiments.

Talo (Af‑Somali): `config.yaml` ku qor *paths* iyo *settings* si team-ku u wada isticmaalo hal meel (reproducible), halkii notebook walba laga kala qori lahaa.

## Recommended Workflow (Notebooks)

1. `preprocessing/01_data_collection.ipynb`
2. `preprocessing/02_annotation_check.ipynb`
3. `preprocessing/03_preprocessing.ipynb`
4. `eda/04_eda.ipynb`
5. `models/traditional_ml/05_traditional_ml.ipynb`
6. `models/deep_learning/06_bilstm.ipynb`, `06_fasttext.ipynb`, `06_word2vec.ipynb`
7. `preprocessing/07_tokenization.ipynb`
8. `models/transformers/08_*.ipynb`
9. `evaluation/09_evaluation.ipynb`
10. `xai/10_shap.ipynb`, `xai/10_lime.ipynb`

## Outputs

- Place plots in each module’s `figures/` folder.
- Save transformer checkpoints in `models/transformers/checkpoints/`.
- Summaries and comparisons go in `results/`.

## Notes

- Large files (datasets, checkpoints) should typically be ignored by git or stored via external storage.
- If you face Windows install issues for `torch`/`transformers`, install PyTorch first (matching your CUDA/CPU), then install the remaining requirements.
