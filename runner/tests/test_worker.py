import os, json
from runner import worker
from runner.queue import JobQueue
from runner.config import Config

def _cfg(tmp, max_attempts=2):
    return Config("s", 8088, 1800, max_attempts, "", "b", "", "", "http://pub",
                  str(tmp), str(tmp / "projects"), str(tmp / "q.db"))

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
    assert not os.path.exists(os.path.join(cfg.projects_dir, "j1"))   # purged on success

def test_run_once_empty_returns_false(tmp_path):
    cfg = _cfg(tmp_path); q = JobQueue(cfg.db_path)
    assert worker.run_once(cfg, q, Deps(tmp_path)) is False

def test_failure_requeues_while_attempts_remain(tmp_path):
    cfg = _cfg(tmp_path, max_attempts=2); q = JobQueue(cfg.db_path); d = Deps(tmp_path)
    from runner.render import RenderResult
    d.ensure_final = lambda ws, profile: RenderResult(False, None, {}, error="silent")
    q.enqueue("j2", "reel", None, {"pipeline": "reel", "callbackUrl": "https://b/cb",
              "budgetCapUsd": 2.0, "inputs": {}})
    worker.run_once(cfg, q, d)                 # attempt 1 of 2
    assert q.get("j2")["status"] == "pending"  # requeued, not failed
    assert d.callbacks == []                    # no terminal callback yet
    assert not os.path.exists(os.path.join(cfg.projects_dir, "j2"))   # workspace cleaned for retry

def test_failure_is_terminal_at_max_attempts(tmp_path):
    cfg = _cfg(tmp_path, max_attempts=1); q = JobQueue(cfg.db_path); d = Deps(tmp_path)
    from runner.render import RenderResult
    d.ensure_final = lambda ws, profile: RenderResult(False, None, {}, error="silent")
    q.enqueue("j3", "reel", None, {"pipeline": "reel", "callbackUrl": "https://b/cb",
              "budgetCapUsd": 2.0, "inputs": {}})
    worker.run_once(cfg, q, d)                 # attempt 1 == max 1 -> terminal
    assert q.get("j3")["status"] == "failed"
    assert d.callbacks[0]["status"] == "failed"
    assert os.path.exists(os.path.join(cfg.projects_dir, "j3"))       # preserved for diagnosis

def test_bad_pipeline_fails_without_raising(tmp_path):
    cfg = _cfg(tmp_path, max_attempts=1); q = JobQueue(cfg.db_path); d = Deps(tmp_path)
    q.enqueue("j4", "bogus", None, {"pipeline": "bogus",
              "callbackUrl": "https://b/cb", "inputs": {}})
    assert worker.run_once(cfg, q, d) is True   # returns, does not raise
    assert q.get("j4")["status"] == "failed"
    assert d.callbacks[0]["status"] == "failed"

def test_reel_success_archives_project_and_callbacks_projecturl(tmp_path, monkeypatch):
    cfg=type("C",(),{"projects_dir":str(tmp_path),"max_attempts":2,"job_timeout_sec":1800})()
    # a reel job whose render "succeeds": stub ensure_final to drop a script.json + final
    sent={}
    class Q:
        def claim_next(self): return {"id":"job9","attempts":1,
            "spec":{"pipeline":"reel","callbackUrl":"http://cb","articleId":42,"inputs":{}}}
        def mark_done(self, jid, cost, url): sent["done"]=(jid,cost,url)
        def requeue(self, jid): pass
        def mark_failed(self, jid, e): pass
    def fake_run_agent(*a, **k): return type("A",(),{"ok":True,"cost_usd":0.0,"log_tail":""})()
    def fake_ensure_final(ws, profile):
        os.makedirs(os.path.join(ws,"artifacts"),exist_ok=True)
        json.dump({"sections":[]}, open(os.path.join(ws,"artifacts","script.json"),"w"))
        os.makedirs(os.path.join(ws,"renders"),exist_ok=True)
        open(os.path.join(ws,"renders","final.mp4"),"wb").write(b"\x00")
        return type("R",(),{"ok":True,"final_path":os.path.join(ws,"renders","final.mp4"),
                            "asset_manifest":{},"error":None})()
    uploads=[]
    def fake_upload(cfg, path, key, **kw): uploads.append(key); return f"https://pub/{key}"
    def fake_send(cfg, url, payload): sent["cb"]=payload
    deps=type("D",(),{"run_agent":staticmethod(fake_run_agent),
                      "ensure_final":staticmethod(fake_ensure_final),
                      "upload":staticmethod(fake_upload),"send":staticmethod(fake_send)})()
    worker.run_once(cfg, Q(), deps)
    assert any(k.startswith("projects/job9") for k in uploads)   # project archived
    assert sent["cb"]["projectUrl"].startswith("https://pub/projects/job9")
