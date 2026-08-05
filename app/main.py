from fastapi import FastAPI

app = FastAPI(title="Protocol Deviation Triage Agent")


@app.get("/health")
def health():
    return {"status": "ok"}
