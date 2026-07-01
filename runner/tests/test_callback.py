from runner import callback
from runner.config import Config

def _cfg(): return Config("sek",8088,1800,2,"","b","","","p","/o","/p","/tmp/q.db")

def test_send_posts_with_secret_and_returns_true():
    seen = {}
    class Resp: status_code = 200
    def poster(url, json, headers):
        seen.update(url=url, json=json, headers=headers); return Resp()
    ok = callback.send(_cfg(), "https://b/cb", {"jobId": "j1", "status": "done"}, poster=poster)
    assert ok is True
    assert seen["headers"]["X-Runner-Secret"] == "sek"
    assert seen["json"]["jobId"] == "j1"

def test_send_false_on_error():
    class Resp: status_code = 500
    assert callback.send(_cfg(), "https://b/cb", {}, poster=lambda *a, **k: Resp()) is False
