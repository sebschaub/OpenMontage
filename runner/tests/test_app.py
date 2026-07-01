from fastapi.testclient import TestClient
from runner.app import make_app
from runner.queue import JobQueue
from runner.config import Config

def _cfg(tmp): return Config("sek",8088,1800,2,"","b","","","http://pub","/opt/openmontage",
                             "/opt/openmontage/projects", str(tmp/"q.db"))

def _client(tmp):
    cfg = _cfg(tmp); q = JobQueue(cfg.db_path)
    return TestClient(make_app(cfg, q)), q

def test_generate_requires_secret(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/generate-video", json={"pipeline": "reel"})
    assert r.status_code == 401

def test_generate_enqueues_and_returns_job(tmp_path):
    c, q = _client(tmp_path)
    r = c.post("/generate-video", headers={"X-Runner-Secret": "sek"},
               json={"pipeline": "reel", "articleId": 5210,
                     "callbackUrl": "https://b/cb", "inputs": {"title": "t"}})
    assert r.status_code == 202
    jid = r.json()["jobId"]; assert q.get(jid)["status"] == "pending"

def test_generate_rejects_unknown_pipeline(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/generate-video", headers={"X-Runner-Secret": "sek"},
               json={"pipeline": "bogus", "callbackUrl": "https://b/cb"})
    assert r.status_code == 400

def test_health_no_auth(tmp_path):
    c, _ = _client(tmp_path)
    assert c.get("/health").json()["ok"] is True
