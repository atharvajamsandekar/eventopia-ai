import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import numpy as np

# -------------------------
# LOAD INTENTS
# -------------------------

with open("intents.json") as file:
    data = json.load(file)

patterns = []
tags = []

# -------------------------
# PREPARE TRAINING DATA
# -------------------------

for intent in data["intents"]:

    for pattern in intent["patterns"]:

        patterns.append(pattern)
        tags.append(intent["tag"])


# -------------------------
# TEXT VECTORISER
# -------------------------

vectorizer = TfidfVectorizer()

X = vectorizer.fit_transform(patterns)


# -------------------------
# TRAIN MODEL
# -------------------------

model = RandomForestClassifier(n_estimators=100, random_state=42)

model.fit(X, tags)


# -------------------------
# INTENT PREDICTION
# -------------------------

def predict_intent(user_input):

    user_input = user_input.lower()

    input_vector = vectorizer.transform([user_input])

    probabilities = model.predict_proba(input_vector)[0]
    best_index = np.argmax(probabilities)
    confidence = probabilities[best_index]
    
    prediction = model.classes_[best_index]

    return prediction, confidence