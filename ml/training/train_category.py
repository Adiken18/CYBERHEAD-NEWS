from pathlib import Path
from collections import Counter
import json

import joblib
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier

from sklearn.model_selection import StratifiedKFold, cross_validate


# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "training_articles_reviewed.csv"
)

MODEL_PATH = (
    PROJECT_ROOT
    / "ml"
    / "saved_models"
    / "category_model.joblib"
)

METRICS_PATH = (
    PROJECT_ROOT
    / "ml"
    / "saved_models"
    / "category_model_metrics.json"
)


# --------------------------------------------------
# LOAD REVIEWED DATA
# --------------------------------------------------

data = pd.read_csv(
    DATASET_PATH,
    encoding="utf-8-sig"
)

data = data[
    data["review_status"] == "reviewed"
].copy()


# --------------------------------------------------
# PREPARE TEXT
# --------------------------------------------------

data["title"] = data["title"].fillna("")
data["text"] = data["text"].fillna("")

data["combined_text"] = (
    data["title"]
    + " "
    + data["text"]
)

X = data["combined_text"]
y = data["primary_category_label"]


print("\n--- TRAINING DATA ---")
print(f"Articles: {len(data)}")

print("\n--- CATEGORY DISTRIBUTION ---")
print(y.value_counts())


# --------------------------------------------------
# PREPARE EVALUATION DATA
# --------------------------------------------------
#
# DDoS currently has only one reviewed example.
#
# A class with one example cannot be properly used
# in stratified cross-validation.
#
# It will still be included when we train the final
# model later.
# --------------------------------------------------

category_counts = Counter(y)

evaluation_categories = [
    category
    for category, count in category_counts.items()
    if count >= 2
]

evaluation_data = data[
    data["primary_category_label"].isin(
        evaluation_categories
    )
].copy()

X_eval = evaluation_data["combined_text"]
y_eval = evaluation_data["primary_category_label"]


smallest_category = (
    y_eval.value_counts().min()
)

number_of_folds = min(
    3,
    smallest_category
)

print(
    f"\nCross-validation folds: "
    f"{number_of_folds}"
)


cross_validation = StratifiedKFold(
    n_splits=number_of_folds,
    shuffle=True,
    random_state=42
)


# --------------------------------------------------
# MODELS TO COMPARE
# --------------------------------------------------

models = {

    "Naive Bayes":
        MultinomialNB(),

    "Logistic Regression":
        LogisticRegression(
            max_iter=2000,
            class_weight="balanced"
        ),

    "Linear SVM":
        LinearSVC(
            class_weight="balanced"
        ),

    "Random Forest":
        RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42
        )
}


# --------------------------------------------------
# EVALUATION METRICS
# --------------------------------------------------

scoring = {
    "accuracy": "accuracy",
    "precision": "precision_macro",
    "recall": "recall_macro",
    "f1": "f1_macro"
}


results = {}


print("\n--- MODEL COMPARISON ---")


for model_name, classifier in models.items():

    pipeline = Pipeline([

        (
            "tfidf",
            TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=10000
            )
        ),

        (
            "classifier",
            classifier
        )
    ])


    scores = cross_validate(
        pipeline,
        X_eval,
        y_eval,
        cv=cross_validation,
        scoring=scoring
    )


    model_result = {
        "accuracy":
            scores["test_accuracy"].mean(),

        "precision_macro":
            scores["test_precision"].mean(),

        "recall_macro":
            scores["test_recall"].mean(),

        "f1_macro":
            scores["test_f1"].mean()
    }


    results[model_name] = model_result


    print(f"\n{model_name}")

    print(
        f"Accuracy:  "
        f"{model_result['accuracy']:.3f}"
    )

    print(
        f"Precision: "
        f"{model_result['precision_macro']:.3f}"
    )

    print(
        f"Recall:    "
        f"{model_result['recall_macro']:.3f}"
    )

    print(
        f"F1-score:  "
        f"{model_result['f1_macro']:.3f}"
    )


# --------------------------------------------------
# SELECT BEST MODEL
# --------------------------------------------------
#
# Macro F1 is used because the dataset is imbalanced.
# --------------------------------------------------

best_model_name = max(
    results,
    key=lambda name: results[name]["f1_macro"]
)


print("\n--- BEST MODEL ---")

print(best_model_name)

print(
    f"Macro F1: "
    f"{results[best_model_name]['f1_macro']:.3f}"
)


# --------------------------------------------------
# TRAIN FINAL MODEL
# --------------------------------------------------
#
# Final training uses ALL reviewed articles.
#
# This includes DDoS and Ransomware even though
# those classes have very few examples.
# --------------------------------------------------

final_model = Pipeline([

    (
        "tfidf",
        TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=10000
        )
    ),

    (
        "classifier",
        models[best_model_name]
    )
])


final_model.fit(
    X,
    y
)


# --------------------------------------------------
# SAVE MODEL
# --------------------------------------------------

MODEL_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)

joblib.dump(
    final_model,
    MODEL_PATH
)


# --------------------------------------------------
# SAVE METRICS
# --------------------------------------------------

metrics_output = {
    "training_articles": int(len(data)),

    "category_distribution": {
        str(key): int(value)
        for key, value
        in y.value_counts().items()
    },

    "cross_validation_folds": int(number_of_folds),

    "evaluation_note": (
        "Categories with fewer than two examples "
        "were excluded from cross-validation but "
        "included in final model training."
    ),

    "models": {
        model_name: {
            metric_name: float(metric_value)
            for metric_name, metric_value
            in model_metrics.items()
        }
        for model_name, model_metrics
        in results.items()
    },

    "best_model": str(best_model_name)
}


with open(
    METRICS_PATH,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        metrics_output,
        file,
        indent=4
    )


print("\n--- MODEL SAVED ---")
print(MODEL_PATH)

print("\n--- METRICS SAVED ---")
print(METRICS_PATH)