import json
from runner import agent
from runner.config import Config

def _cfg(): return Config("s",8088,1800,2,"","b","","","p","/opt/openmontage",
                          "/opt/openmontage/projects","/tmp/q.db")

def test_run_agent_parses_cost_and_builds_command(tmp_path):
    calls = {}
    class R:  # fake CompletedProcess
        returncode = 0
        stdout = json.dumps({"total_cost_usd": 0.91, "is_error": False, "result": "done"})
        stderr = ""
    def fake_run(cmd, **kw):
        calls["cmd"] = cmd; calls["kw"] = kw; return R()
    res = agent.run_agent(_cfg(), "reel", str(tmp_path), str(tmp_path/"brief.json"),
                          "instagram_reels", 2.0, 1800, runner=fake_run)
    assert res.ok is True and res.cost_usd == 0.91
    joined = " ".join(calls["cmd"])
    assert "claude" in joined and "--output-format" in joined and "bypassPermissions" in joined

def test_run_agent_flags_error(tmp_path):
    class R:
        returncode = 1; stdout = "{}"; stderr = "boom"
    res = agent.run_agent(_cfg(), "reel", str(tmp_path), str(tmp_path/"b.json"),
                          "instagram_reels", 2.0, 1800, runner=lambda *a, **k: R())
    assert res.ok is False and "boom" in res.log_tail
