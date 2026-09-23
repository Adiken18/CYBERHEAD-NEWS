# CYBERHEAD News - ML Category Classification

## What has been completed

- Reviewed **183 cybersecurity articles**.
- **173 articles** are used for ML training.
- **10 articles** were excluded because they were mixed-topic, promotional, webinar, event, or press-release content.
- Articles are classified into 7 categories:
  - Vulnerabilities
  - Other cybersecurity news
  - Other malware
  - Data breaches
  - Phishing
  - Ransomware
  - DDoS

## Training data

The reviewed dataset is stored at:

```text
ml/data/training_articles_reviewed.csv
```

The model uses the article **title + full article text**.

## ML models tested

The training script is:

```text
ml/training/train_category.py
```

Text is converted into numerical features using **TF-IDF**.

Four machine-learning models were compared using the same dataset and the same cross-validation process:

- Multinomial Naive Bayes
- Logistic Regression
- Linear SVM
- Random Forest

### Results

| Model | Accuracy | Macro F1 |
|---|---:|---:|
| Naive Bayes | 55.2% | 0.235 |
| Logistic Regression | 78.5% | 0.637 |
| Linear SVM | 78.5% | **0.639** |
| Random Forest | 76.2% | 0.576 |

**Linear SVM** was selected because it had the highest Macro F1 score.

Macro F1 was used because the dataset is imbalanced and some categories have fewer examples than others.

## Saved model

The trained model and its results are stored in:

```text
ml/saved_models/category_model.joblib
ml/saved_models/category_model_metrics.json
```

The website does **not** retrain the model every time it runs. It loads the saved `.joblib` model and uses it to classify new articles.

## Backend integration

The backend classifier is:

```text
backend/app/category_classifier.py
```

It:

1. Gets extracted articles that do not yet have a category.
2. Loads the trained Linear SVM model.
3. Predicts the article category.
4. Saves the predicted category into `cyberhead.db`.

All **183 existing articles** have now been classified successfully.

## Current pipeline

```text
Collect article
      ↓
Extract full text
      ↓
Detect / enrich CVEs
      ↓
ML category classification
      ↓
Save category to SQLite
```

## Current limitation

The training dataset currently has very few examples for:

```text
Ransomware: 2
DDoS: 1
```

These categories should be improved later with more reviewed training examples.

**Next step is to add tag  because category is too broad.**