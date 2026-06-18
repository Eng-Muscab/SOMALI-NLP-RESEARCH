import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from web.backend.services.ml_service import ml_service

print("=== Discovered Models ===")
models = ml_service.list_models()
print(f"Total models loaded: {len(models)}")
for model in models:
    model_data = ml_service.models[model]
    print(f"- {model} (Type: {model_data['type']})")

print("\n=== Testing Predictions ===")
test_text = "This is a sample Somali text."
for model in models:
    try:
        result = ml_service.predict(test_text, model_key=model)
        print(f"[{model}] Prediction: {result['prediction']}, Confidence: {result['confidence']}")
    except Exception as e:
        print(f"[{model}] Failed: {str(e)}")

print("\n=== Finished Backend Integration Test ===")
