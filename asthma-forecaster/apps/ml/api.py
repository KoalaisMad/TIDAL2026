"""
Minimal FastAPI app for the ML backend (uvicorn api:app).
Risk/flare prediction is also invoked by the Next.js API routes via Python subprocess.
"""
from fastapi import FastAPI

app = FastAPI(title="Asthma ML API")


@app.get("/")
def root():
    return {"service": "asthma-ml", "status": "ok"}
