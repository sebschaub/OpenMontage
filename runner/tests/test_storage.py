from runner import storage
from runner.config import Config

def _cfg(): return Config("s",8088,1800,2,"https://s3","vpn-video","ak","sk",
                          "https://cdn.example","/opt/openmontage","/p","/tmp/q.db")

def test_upload_calls_put_and_returns_url(tmp_path):
    f = tmp_path / "v.mp4"; f.write_bytes(b"x")
    calls = {}
    class FakeClient:
        def upload_file(self, Filename, Bucket, Key, ExtraArgs=None):
            calls.update(Filename=Filename, Bucket=Bucket, Key=Key, ExtraArgs=ExtraArgs)
    url = storage.upload(_cfg(), str(f), "videos/j1.mp4", client=FakeClient())
    assert url == "https://cdn.example/videos/j1.mp4"
    assert calls["Bucket"] == "vpn-video" and calls["Key"] == "videos/j1.mp4"
    assert calls["ExtraArgs"]["ContentType"] == "video/mp4"
