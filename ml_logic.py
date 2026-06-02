# ml_logic.py

import pymongo
import re
import requests
from dotenv import load_dotenv
import os

load_dotenv()

# MongoDB setup
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client["docdetails"]
symptom_collection = db["symptom_specialty"]
doctors_collection = db["doctors"]  # NEW: used to fetch specialties

def get_specialty_for_symptom(user_input):
    user_input = user_input.lower().strip()
    keywords = re.findall(r'\w+', user_input)

    # Step 1: Check MongoDB for any keyword match in symptom_specialty
    for keyword in keywords:
        match = symptom_collection.find_one({
            "symptom": {"$regex": f"{keyword}", "$options": "i"}
        })
        if match:
            return match["specialty"]

    # Step 2: Fallback - check Wikipedia summary
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(user_input)}"
        response = requests.get(url)
        if response.status_code != 200:
            return "General Physician"
        summary = response.json().get("extract", "")
    except Exception:
        return "General Physician"

    # Step 3: Dynamically get known specialties from DB
    known_specialties = doctors_collection.distinct("specialty")

    # Step 4: Check for any specialty keyword in Wikipedia summary
    summary_lower = summary.lower()
    for specialty in known_specialties:
        if specialty.lower().split()[0] in summary_lower:
            # Step 5: Learn this new mapping
            if not symptom_collection.find_one({"symptom": user_input}):
                symptom_collection.insert_one({
                    "symptom": user_input,
                    "specialty": specialty
                })
            return specialty

    return "General Physician"
