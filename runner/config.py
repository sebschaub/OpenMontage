import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    runner_secret: str
    runner_port: int
    job_timeout_sec: int
    max_attempts: int
    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    public_base: str
    openmontage_dir: str
    projects_dir: str
    db_path: str

def load() -> Config:
    secret = os.environ.get("RUNNER_SECRET")
    if not secret:
        raise RuntimeError("RUNNER_SECRET is required")
    om = os.environ.get("OPENMONTAGE_DIR", "/opt/openmontage")
    return Config(
        runner_secret=secret,
        runner_port=int(os.environ.get("RUNNER_PORT", "8088")),
        job_timeout_sec=int(os.environ.get("JOB_TIMEOUT_SEC", "1800")),
        max_attempts=int(os.environ.get("MAX_ATTEMPTS", "2")),
        s3_endpoint=os.environ.get("S3_ENDPOINT", ""),
        s3_bucket=os.environ.get("S3_BUCKET", ""),
        s3_access_key=os.environ.get("S3_ACCESS_KEY", ""),
        s3_secret_key=os.environ.get("S3_SECRET_KEY", ""),
        public_base=os.environ.get("RUNNER_PUBLIC_BASE", ""),
        openmontage_dir=om,
        projects_dir=os.path.join(om, "projects"),
        db_path=os.environ.get("RUNNER_DB", os.path.join(om, "runner", "runner.db")),
    )
