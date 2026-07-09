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

from runner import storage

class _Cfg:
    s3_endpoint="e"; s3_bucket="b"; s3_access_key="a"; s3_secret_key="s"; public_base="https://pub"

class _FakeClient:
    def __init__(self): self.up=[]; self.down=[]
    def upload_file(self, Filename, Bucket, Key, ExtraArgs): self.up.append((Filename,Bucket,Key,ExtraArgs))
    def download_file(self, Bucket, Key, Filename): self.down.append((Bucket,Key,Filename))

def test_upload_honors_content_type():
    c=_FakeClient()
    url=storage.upload(_Cfg(), "/tmp/x.tar.gz", "projects/x.tar.gz", content_type="application/gzip", client=c)
    assert url=="https://pub/projects/x.tar.gz"
    assert c.up[0][3]=={"ContentType":"application/gzip"}

def test_upload_defaults_video_mp4():
    c=_FakeClient(); storage.upload(_Cfg(), "/tmp/v.mp4", "videos/v.mp4", client=c)
    assert c.up[0][3]=={"ContentType":"video/mp4"}

def test_download_pulls_key_to_local():
    c=_FakeClient(); out=storage.download(_Cfg(), "projects/x.tar.gz", "/tmp/x.tar.gz", client=c)
    assert out=="/tmp/x.tar.gz"; assert c.down[0]==("b","projects/x.tar.gz","/tmp/x.tar.gz")
