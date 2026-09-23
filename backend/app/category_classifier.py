from pathlib import Path
import argparse

import joblib

from app.database import (
    get_articles_for_category_classification,
    save_article_category,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "ml"
    / "saved_models"
    / "category_model.joblib"
)


_model = None


def get_model():
    global _model

    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Category model not found: {MODEL_PATH}"
            )

        _model = joblib.load(MODEL_PATH)

    return _model


def predict_category(title, text):
    model = get_model()

    title = title or ""
    text = text or ""

    combined_text = f"{title} {text}".strip()

    if not combined_text:
        return None

    prediction = model.predict(
        [combined_text]
    )[0]

    return str(prediction)


def classify_articles(limit=20):

    articles = get_articles_for_category_classification(
        limit=limit
    )

    if not articles:
        print(
            "No articles are waiting for category classification."
        )
        return

    classified = 0
    failed = 0

    for article in articles:

        article_id = article["id"]
        title = article["title"]

        text = (
            article["full_content"]
            or article["content"]
            or ""
        )

        try:
            category = predict_category(
                title,
                text
            )

            if category is None:
                print(
                    f"SKIPPED: article {article_id}; no text."
                )
                failed += 1
                continue

            save_article_category(
                article_id,
                category
            )

            print(
                f"SUCCESS: article {article_id}; "
                f"{category}"
            )

            classified += 1

        except Exception as error:
            print(
                f"ERROR: article {article_id}; "
                f"{error}"
            )

            failed += 1

    print("\n--- CATEGORY CLASSIFICATION SUMMARY ---")
    print(f"Classified: {classified}")
    print(f"Failed/skipped: {failed}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=20
    )

    args = parser.parse_args()

    classify_articles(
        limit=args.limit
    )