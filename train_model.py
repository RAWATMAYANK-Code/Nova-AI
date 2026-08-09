"""
train_model.py
Trains a Logistic Regression model on the fake_or_real_news.csv dataset
and saves it to model/fake_news_model.pkl.
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

print("[1] Loading dataset...")
df = pd.read_csv("data/fake_or_real_news.csv")

print(f"    -> Total rows: {len(df)}")
print(f"    -> Columns: {list(df.columns)}")

# Combine title + text for better context
df["content"] = df["title"].fillna("") + " " + df["text"].fillna("")

X = df["content"]
y = df["label"]

print("\n[2] Splitting into train/test sets...")
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print("\n[3] Running TF-IDF vectorization...")
vectorizer = TfidfVectorizer(stop_words="english", max_df=0.7)
X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

print("\n[4] Training model (Logistic Regression)...")
model = LogisticRegression(max_iter=1000)
model.fit(X_train_tfidf, y_train)

print("\n[5] Evaluating model...")
y_pred = model.predict(X_test_tfidf)
accuracy = accuracy_score(y_test, y_pred)
print(f"    -> Accuracy: {accuracy * 100:.2f}%")
print("\n" + classification_report(y_test, y_pred))

print("\n[6] Saving model and vectorizer...")
os.makedirs("model", exist_ok=True)
joblib.dump(model, "model/fake_news_model.pkl")
joblib.dump(vectorizer, "model/vectorizer.pkl")

print("\nDone! Model saved in the 'model/' folder.")