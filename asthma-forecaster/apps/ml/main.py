import os
from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.environ["MONGODB_URI"])
db = client["asthma"]

app = FastAPI()


class PredictRequest(BaseModel):
    userId: str
    date: str  # YYYY-MM-DD


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/predict")
def predict(req: PredictRequest):
    # minimal: look up checkin and return a simple risk based on rescueUsed
    checkin = db.checkins.find_one({"userId": req.userId, "date": req.date}) or {}
    rescue_used = bool(checkin.get("rescueUsed", False))
    symptom = float(checkin.get("symptomScore", 0))

    risk = 0.1 + (0.25 if rescue_used else 0.0) + (0.05 * symptom)
    risk = min(risk, 0.95)

    drivers = []
    if rescue_used:
        drivers.append({"feature": "rescueUsed_t", "contribution": 0.25})
    if symptom > 0:
        drivers.append({"feature": "symptomScore_t", "contribution": 0.05 * symptom})

    return {"risk": risk, "drivers": drivers}
