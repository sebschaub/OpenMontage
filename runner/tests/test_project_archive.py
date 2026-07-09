import os, json
from runner import project_archive as pa

def _mk(ws):
    os.makedirs(os.path.join(ws,"artifacts")); os.makedirs(os.path.join(ws,"assets","images"))
    os.makedirs(os.path.join(ws,"renders"))
    json.dump({"cuts":[]}, open(os.path.join(ws,"artifacts","edit_decisions.json"),"w"))
    open(os.path.join(ws,"assets","images","a.jpg"),"wb").write(b"\xff\xd8")
    open(os.path.join(ws,"renders","final.mp4"),"wb").write(b"\x00"*10)

def test_archive_then_extract_roundtrip(tmp_path):
    src=str(tmp_path/"job1"); _mk(src)
    tar=str(tmp_path/"job1.tar.gz"); out=pa.archive_project(src, tar)
    assert out==tar and os.path.getsize(tar)>0
    dst=str(tmp_path/"restored"); pa.extract_project(tar, dst)
    assert json.load(open(os.path.join(dst,"artifacts","edit_decisions.json")))=={"cuts":[]}
    assert open(os.path.join(dst,"assets","images","a.jpg"),"rb").read()==b"\xff\xd8"
    # renders/ is excluded from the archive (regenerated on localize)
    assert not os.path.exists(os.path.join(dst,"renders","final.mp4"))
