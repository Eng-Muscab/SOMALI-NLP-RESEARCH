# XAI Outputs

Generated from `LinearSVC_TFIDF` for the binary `AI` vs `HUMAN` task.

- `shap_like_feature_importance.csv`: lightweight linear proxy (legacy).
- `shap/shap_global_importance.csv`: package-level SHAP mean absolute values.
- `shap/shap_summary_plot.svg`: SHAP summary plot from the `shap` package.
- `lime/lime_explanation_*.html`: local explanations from the `lime` package.
- `error_analysis_sample.csv`: held-out test errors for review.
