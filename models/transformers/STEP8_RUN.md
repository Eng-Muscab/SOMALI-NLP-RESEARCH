# STEP 8 Run Guide (Transformer Fine-tuning)

## 1) Environment setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

If you are on CPU-only machine, use:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 2) Quick smoke test (small subset, 1 epoch)

```powershell
python models/transformers/step8_finetune_transformers.py --model mbert --quick
```

## 3) Full run (all required models)

```powershell
python models/transformers/step8_finetune_transformers.py --model all
```

## 4) Run model-by-model (optional)

```powershell
python models/transformers/step8_finetune_transformers.py --model xlmr
python models/transformers/step8_finetune_transformers.py --model somberta --trust-remote-code
python models/transformers/step8_finetune_transformers.py --model afroxlmr
python models/transformers/step8_finetune_transformers.py --model afriberta
```

## 5) Expected outputs

- Training logs:
  - `models/transformers/training_logs/mbert_training_log.csv`
  - `models/transformers/training_logs/xlmr_training_log.csv`
  - `models/transformers/training_logs/somberta_training_log.csv`
  - `models/transformers/training_logs/afroxlmr_training_log.csv`
  - `models/transformers/training_logs/afriberta_training_log.csv`
- Best checkpoints:
  - `models/transformers/checkpoints/<model_key>/best/`
- Comparison tables:
  - `models/transformers/model_comparison_metrics.csv`
  - `results/transformers_model_comparison.csv`
