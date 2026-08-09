"""
classifier.py
Loads the trained Logistic Regression model and vectorizer,
predicts whether a given news text matches FAKE or REAL writing style,
and explains the decision using top contributing words.
"""

import joblib
import numpy as np

model = joblib.load("model/fake_news_model.pkl")
vectorizer = joblib.load("model/vectorizer.pkl")

feature_names = np.array(vectorizer.get_feature_names_out())
coefficients = model.coef_[0]


def predict_with_ml(news_text, top_n=5):
    """
    Predicts style pattern using trained ML classifier when external source checks fail.
    Returns verdict 'Unverified' with pattern signal notes so true events are not falsely mislabeled.
    """
    text_tfidf = vectorizer.transform([news_text])
    prediction = model.predict(text_tfidf)[0]
    probabilities = model.predict_proba(text_tfidf)[0]
    confidence = max(probabilities) * 100

    pattern_verdict = "Real" if prediction == "REAL" else "Fake"

    nonzero_indices = text_tfidf.nonzero()[1]
    word_contributions = []
    for idx in nonzero_indices:
        word = feature_names[idx]
        tfidf_score = text_tfidf[0, idx]
        weight = coefficients[idx]
        contribution = tfidf_score * weight
        word_contributions.append((word, contribution))

    if pattern_verdict == "Fake":
        word_contributions.sort(key=lambda x: x[1])
    else:
        word_contributions.sort(key=lambda x: -x[1])

    top_words = [w for w, c in word_contributions[:top_n] if abs(c) > 0]

    explanation = (
        f"No live source or trusted news article could be retrieved to verify this claim directly, "
        f"so this result comes from a style/pattern-based machine learning model instead of source-grounded fact-checking. "
        f"The model detected phrasing pattern similarities to {pattern_verdict.lower()} news writing with {confidence:.2f}% confidence."
    )

    if top_words:
        words_str = ", ".join(top_words)
        reason_flagged = (
            f"The vocabulary pattern words that influenced this statistical check were: {words_str}. "
            f"These words resemble phrasing patterns seen in {'fake' if pattern_verdict == 'Fake' else 'real'} "
            f"articles in the offline training dataset, based purely on writing style rather than verifying real-world events. "
            f"Because live sources were unavailable, treat this as an unverified pattern warning and check official news sources."
        )
    else:
        reason_flagged = (
            f"No strongly influential vocabulary words were found. Because live sources were unavailable, "
            f"treat this as an unverified result and check official news sources."
        )

    return {
        "verdict": "Unverified",
        "confidence": f"{confidence:.2f}%",
        "confidence_percent": round(confidence),
        "misleading_percentage": None,
        "highlighted_claim": "",
        "consensus_fact": "",
        "reason_flagged": reason_flagged,
        "explanation": explanation,
        "sources_checked": ["ML Classifier (style/pattern-based, no external source verification)"],
        "api_used": "ML Classifier (Local Model)"
    }


if __name__ == "__main__":
    sample = "Scientists have confirmed that the earth is flat and NASA has been hiding this for decades."
    result = predict_with_ml(sample)
    for k, v in result.items():
        print(f"{k}: {v}")