from fastapi import FastAPI

app = FastAPI(title="Catalyst Agent Tool Layer")

@app.get("/health")
def health():
    return {"status": "ok"}
