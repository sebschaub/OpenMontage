import uuid
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from runner import pipelines

class JobRequest(BaseModel):
    pipeline: str
    callbackUrl: str | None = None
    articleId: int | None = None
    mediaProfile: str | None = None
    budgetCapUsd: float = 2.0
    inputs: dict = {}

def make_app(cfg, queue) -> FastAPI:
    app = FastAPI()

    def _auth(secret: str | None):
        if secret != cfg.runner_secret:
            raise HTTPException(status_code=401, detail="bad secret")

    @app.post("/generate-video", status_code=202)
    def generate(req: JobRequest, x_runner_secret: str | None = Header(default=None)):
        _auth(x_runner_secret)
        try:
            pipelines.resolve(req.pipeline)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        job_id = uuid.uuid4().hex
        queue.enqueue(job_id, req.pipeline, req.articleId, req.model_dump())
        return {"jobId": job_id}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, x_runner_secret: str | None = Header(default=None)):
        _auth(x_runner_secret)
        job = queue.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="no such job")
        return job

    @app.get("/health")
    def health():
        return {"ok": True, "queueDepth": queue.depth(), "running": queue.running_count()}

    return app
