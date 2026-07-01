import os, json
from runner import worker
from runner.queue import JobQueue
from runner.config import Config

def _cfg(tmp): return Config("s",8088,1800,2,"","b","","","http://pub",
                             str(tmp), str(tmp/"projects"), str(tmp/"q.db"))

class Deps:
    def __init__(self, tmp):
        self.tmp = tmp; self.callbacks = []
    def run_agent(self, cfg, alias, ws, brief, profile, cap, timeout):
        os.makedirs(os.path.join(ws, "renders"), exist_ok=True)
        open(os.path.join(ws, "renders", "final.mp4"), "wb").write(b"\x00"*10)
        from runner.agent import AgentResult; return AgentResult(True, 0.5, "")
    def ensure_final(self, ws, profile):
        from runner.render import RenderResult
        return RenderResult(True, os.path.join(ws, "renders", "final.mp4"),
                            {"assets": [{"cost_usd": 0.2}]})
    def upload(self, cfg, path, key): return f"http://pub/{key}"
    def send(self, cfg, url, payload): self.callbacks.append(payload); return True

def test_process_job_success(tmp_path):
    cfg = _cfg(tmp_path); q = JobQueue(cfg.db_path); d = Deps(tmp_path)
    q.enqueue("j1", "reel", 5210, {"pipeline": "reel", "callbackUrl": "https://b/cb",
              "budgetCapUsd": 2.0, "inputs": {"title": "t"}})
    assert worker.run_once(cfg, q, d) is True
    job = q.get("j1")
    assert job["status"] == "done" and job["cost_usd"] == 0.7   # 0.5 agent + 0.2 media
    assert d.callbacks[0]["status"] == "done" and d.callbacks[0]["url"].endswith("j1.mp4")
    assert not os.path.exists(os.path.join(cfg.projects_dir, "j1"))   # workspace purged

def test_run_once_empty_returns_false(tmp_path):
    cfg = _cfg(tmp_path); q = JobQueue(cfg.db_path)
    assert worker.run_once(cfg, q, Deps(tmp_path)) is False

def test_process_job_render_fail_marks_failed(tmp_path):
    cfg = _cfg(tmp_path); q = JobQueue(cfg.db_path); d = Deps(tmp_path)
    from runner.render import RenderResult
    d.ensure_final = lambda ws, profile: RenderResult(False, None, {}, error="no render")
    q.enqueue("j2", "reel", None, {"pipeline": "reel", "callbackUrl": "https://b/cb",
              "budgetCapUsd": 2.0, "inputs": {}})
    worker.run_once(cfg, q, d)
    assert q.get("j2")["status"] == "failed"
    assert d.callbacks[0]["status"] == "failed"

def test_process_job_bad_pipeline_fails_without_raising(tmp_path):
    # An unknown/absent pipeline alias must NOT propagate out of run_once
    # (it would crash the poll loop and strand the job as 'running'). It must
    # be caught, marked failed, and reported via callback.
    cfg = _cfg(tmp_path); q = JobQueue(cfg.db_path); d = Deps(tmp_path)
    q.enqueue("j3", "bogus", None, {"pipeline": "bogus",
              "callbackUrl": "https://b/cb", "inputs": {}})
    assert worker.run_once(cfg, q, d) is True          # returns, does not raise
    assert q.get("j3")["status"] == "failed"
    assert d.callbacks[0]["status"] == "failed"
