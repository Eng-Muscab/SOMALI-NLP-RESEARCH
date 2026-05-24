# STEP 6 Run Guide (BiLSTM + FastText + Word2Vec)

## 1) Activate Python 3.12 venv (recommended)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install tensorflow
```

## 2) Run FastText only

```powershell
python models/deep_learning/step6_train_bilstm.py --embedding fasttext
```

## 3) Run Word2Vec only

```powershell
python models/deep_learning/step6_train_bilstm.py --embedding word2vec
```

## 4) Run both (default)

```powershell
python models/deep_learning/step6_train_bilstm.py --embedding both
```

## 5) Expected outputs

- `models/deep_learning/training_logs/bilstm_fasttext_training_log.csv`
- `models/deep_learning/training_logs/bilstm_word2vec_training_log.csv`
- `models/deep_learning/checkpoints/bilstm_fasttext_best.weights.h5`
- `models/deep_learning/checkpoints/bilstm_word2vec_best.weights.h5`
- `models/deep_learning/model_comparison_metrics.csv`
