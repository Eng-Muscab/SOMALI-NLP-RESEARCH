# Balanced Dataset Refresh Report

## Dataset

- Source labeled dataset: `data/raw/labeled text.xlsx`
- Supplemental EDA dataset: `data/raw/full_dataset.xlsx`
- Clean labeled rows: 11509
- Label counts: AI=5816, HUMAN=5693
- Minority class after cleaning: `HUMAN` (only 123 fewer rows than AI, so the dataset is now close to balanced).

## Best New Result

- Experiment: `experiment_1_stopwords_included`
- Model: `LinearSVC_TFIDF`
- Accuracy: 0.9444
- Precision: 0.9446
- Recall: 0.9444
- F1-score: 0.9444
- ROC-AUC: 0.9859

## Previous vs Balanced Results

The table below compares models that exist in both the previous committed result tables and the refreshed balanced-dataset tables. Negative deltas are expected for some models because the new held-out test set is larger and less skewed, making the evaluation harder and more realistic.

| experiment | family | model | accuracy_previous | accuracy_balanced | accuracy_delta | precision_previous | precision_balanced | precision_delta | recall_previous | recall_balanced | recall_delta | f1_previous | f1_balanced | f1_delta | macro_f1_previous | macro_f1_balanced | macro_f1_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| experiment_1_stopwords_included | traditional_ml | LinearSVC_TFIDF | 0.9631 | 0.9444 | -0.0187 | 0.9632 | 0.9446 | -0.0186 | 0.9631 | 0.9444 | -0.0187 | 0.9631 | 0.9444 | -0.0187 | 0.9631 | 0.9444 | -0.0187 |
| experiment_2_stopwords_removed | traditional_ml | LinearSVC_TFIDF | 0.9529 | 0.9299 | -0.0230 | 0.9530 | 0.9301 | -0.0229 | 0.9529 | 0.9299 | -0.0230 | 0.9529 | 0.9299 | -0.0230 | 0.9529 | 0.9299 | -0.0230 |
| experiment_1_stopwords_included | traditional_ml | LogisticRegression_TFIDF | 0.9506 | 0.9270 | -0.0236 | 0.9509 | 0.9295 | -0.0214 | 0.9506 | 0.9270 | -0.0236 | 0.9505 | 0.9270 | -0.0235 | 0.9505 | 0.9270 | -0.0235 |
| experiment_1_stopwords_included | transformers | MiniTransformer_Keras | 0.9443 | 0.9201 | -0.0242 | 0.9444 | 0.9201 | -0.0243 | 0.9443 | 0.9201 | -0.0242 | 0.9443 | 0.9201 | -0.0242 | 0.9443 | 0.9201 | -0.0242 |
| experiment_2_stopwords_removed | traditional_ml | LogisticRegression_TFIDF | 0.9482 | 0.9184 | -0.0298 | 0.9484 | 0.9207 | -0.0277 | 0.9482 | 0.9184 | -0.0298 | 0.9481 | 0.9183 | -0.0298 | 0.9481 | 0.9183 | -0.0298 |
| experiment_1_stopwords_included | deep_learning | BiLSTM_Keras | 0.9286 | 0.9160 | -0.0126 | 0.9286 | 0.9178 | -0.0108 | 0.9286 | 0.9160 | -0.0126 | 0.9286 | 0.9160 | -0.0126 | 0.9286 | 0.9160 | -0.0126 |
| experiment_2_stopwords_removed | transformers | MiniTransformer_Keras | 0.9294 | 0.9131 | -0.0163 | 0.9295 | 0.9132 | -0.0163 | 0.9294 | 0.9131 | -0.0163 | 0.9293 | 0.9131 | -0.0162 | 0.9293 | 0.9131 | -0.0162 |
| experiment_2_stopwords_removed | deep_learning | BiLSTM_Keras | 0.9357 | 0.9091 | -0.0266 | 0.9357 | 0.9102 | -0.0255 | 0.9357 | 0.9091 | -0.0266 | 0.9357 | 0.9090 | -0.0267 | 0.9357 | 0.9090 | -0.0267 |
| experiment_1_stopwords_included | traditional_ml | RandomForest_TFIDF | 0.9051 | 0.8981 | -0.0070 | 0.9055 | 0.9048 | -0.0007 | 0.9051 | 0.8981 | -0.0070 | 0.9047 | 0.8977 | -0.0070 | 0.9047 | 0.8978 | -0.0069 |
| experiment_2_stopwords_removed | traditional_ml | RandomForest_TFIDF | 0.8941 | 0.8923 | -0.0018 | 0.8945 | 0.8973 | 0.0028 | 0.8941 | 0.8923 | -0.0018 | 0.8936 | 0.8920 | -0.0016 | 0.8936 | 0.8921 | -0.0015 |
| experiment_1_stopwords_included | traditional_ml | XGBoost_TFIDF | 0.9404 | 0.8807 | -0.0597 | 0.9405 | 0.8884 | -0.0521 | 0.9404 | 0.8807 | -0.0597 | 0.9404 | 0.8802 | -0.0602 | 0.9404 | 0.8803 | -0.0601 |
| experiment_2_stopwords_removed | deep_learning | BiLSTM_FastText | 0.8957 | 0.8709 | -0.0248 | 0.8958 | 0.8715 | -0.0243 | 0.8957 | 0.8709 | -0.0248 | 0.8954 | 0.8709 | -0.0245 | 0.8954 | 0.8709 | -0.0245 |
| experiment_2_stopwords_removed | traditional_ml | XGBoost_TFIDF | 0.9349 | 0.8715 | -0.0634 | 0.9350 | 0.8817 | -0.0533 | 0.9349 | 0.8715 | -0.0634 | 0.9349 | 0.8707 | -0.0642 | 0.9349 | 0.8708 | -0.0641 |
| experiment_1_stopwords_included | deep_learning | BiLSTM_Word2Vec | 0.8965 | 0.8680 | -0.0285 | 0.8966 | 0.8757 | -0.0209 | 0.8965 | 0.8680 | -0.0285 | 0.8962 | 0.8674 | -0.0288 | 0.8962 | 0.8675 | -0.0287 |
| experiment_2_stopwords_removed | deep_learning | BiLSTM_Word2Vec | 0.8698 | 0.8657 | -0.0041 | 0.8699 | 0.8662 | -0.0037 | 0.8698 | 0.8657 | -0.0041 | 0.8696 | 0.8656 | -0.0040 | 0.8696 | 0.8657 | -0.0039 |
| experiment_1_stopwords_included | deep_learning | BiLSTM_FastText | 0.8871 | 0.8570 | -0.0301 | 0.8872 | 0.8573 | -0.0299 | 0.8871 | 0.8570 | -0.0301 | 0.8870 | 0.8570 | -0.0300 | 0.8870 | 0.8570 | -0.0300 |

## Minority-Class Performance (`HUMAN`)

Because `HUMAN` remains the smaller class after cleaning, this table reports the refreshed per-class scores for `HUMAN`. Recall is the most important signal here: higher recall means fewer human-written texts are incorrectly flagged as AI.

| experiment | model | minority_class | precision | recall | f1 | support |
| --- | --- | --- | --- | --- | --- | --- |
| experiment_1_stopwords_included | LinearSVC_TFIDF | HUMAN | 0.9356 | 0.9532 | 0.9443 | 854 |
| experiment_2_stopwords_removed | LinearSVC_TFIDF | HUMAN | 0.9217 | 0.9379 | 0.9298 | 854 |
| experiment_1_stopwords_included | LogisticRegression_TFIDF | HUMAN | 0.8965 | 0.9637 | 0.9289 | 854 |
| experiment_2_stopwords_removed | LogisticRegression_TFIDF | HUMAN | 0.8888 | 0.9543 | 0.9204 | 854 |
| experiment_1_stopwords_included | MiniTransformer_Keras | HUMAN | 0.9192 | 0.9192 | 0.9192 | 854 |
| experiment_1_stopwords_included | BiLSTM_Keras | HUMAN | 0.8900 | 0.9473 | 0.9178 | 854 |
| experiment_2_stopwords_removed | MiniTransformer_Keras | HUMAN | 0.9103 | 0.9145 | 0.9124 | 854 |
| experiment_2_stopwords_removed | BiLSTM_Keras | HUMAN | 0.9308 | 0.8817 | 0.9056 | 854 |
| experiment_1_stopwords_included | RandomForest_TFIDF | HUMAN | 0.8517 | 0.9614 | 0.9032 | 854 |
| experiment_2_stopwords_removed | RandomForest_TFIDF | HUMAN | 0.8516 | 0.9473 | 0.8969 | 854 |
| experiment_1_stopwords_included | XGBoost_TFIDF | HUMAN | 0.8326 | 0.9496 | 0.8873 | 854 |
| experiment_2_stopwords_removed | XGBoost_TFIDF | HUMAN | 0.8179 | 0.9520 | 0.8799 | 854 |
| experiment_1_stopwords_included | BiLSTM_Word2Vec | HUMAN | 0.8207 | 0.9379 | 0.8754 | 854 |
| experiment_2_stopwords_removed | BiLSTM_FastText | HUMAN | 0.8549 | 0.8899 | 0.8721 | 854 |
| experiment_2_stopwords_removed | BiLSTM_Word2Vec | HUMAN | 0.8510 | 0.8829 | 0.8667 | 854 |
| experiment_1_stopwords_included | BiLSTM_FastText | HUMAN | 0.8453 | 0.8700 | 0.8575 | 854 |

## Interpretation

- Balancing increased the training data from the old 5,869 cleaned rows to 11,509 cleaned rows and nearly equalized AI/HUMAN support.
- The best refreshed model is still `LinearSVC_TFIDF`, which indicates TF-IDF character/word features remain strong for Somali AI-vs-human classification.
- Several headline F1-scores are lower than the old run, especially for stopwords-removed models. This is a more trustworthy result: the larger balanced test split reduces the artificial advantage caused by the old dataset distribution.
- Minority-class (`HUMAN`) recall is now explicit in every classification report, so false AI accusations against human text can be tracked directly.
- Stopwords included performs best overall in the refreshed run, suggesting Somali function words still carry useful stylistic signal for this task.
