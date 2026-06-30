import os
from runner import config

def test_load_reads_env_and_defaults(monkeypatch):
    monkeypatch.setenv("RUNNER_SECRET", "s3cr3t")
    monkeypatch.setenv("S3_BUCKET", "vpn-video")
    monkeypatch.delenv("JOB_TIMEOUT_SEC", raising=False)
    cfg = config.load()
    assert cfg.runner_secret == "s3cr3t"
    assert cfg.s3_bucket == "vpn-video"
    assert cfg.job_timeout_sec == 1800          # default
    assert cfg.max_attempts == 2                 # default
    assert cfg.projects_dir.endswith("/projects")

def test_load_requires_secret(monkeypatch):
    monkeypatch.delenv("RUNNER_SECRET", raising=False)
    try:
        config.load(); assert False, "should have raised"
    except RuntimeError as e:
        assert "RUNNER_SECRET" in str(e)
