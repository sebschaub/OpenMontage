import os, tarfile

_INCLUDE = ("artifacts", "assets")   # renders/ excluded — regenerated on localize

def archive_project(workspace, out_tar_path):
    os.makedirs(os.path.dirname(out_tar_path) or ".", exist_ok=True)
    with tarfile.open(out_tar_path, "w:gz") as tf:
        for sub in _INCLUDE:
            p = os.path.join(workspace, sub)
            if os.path.isdir(p):
                tf.add(p, arcname=sub)
    return out_tar_path

def extract_project(tar_path, workspace):
    os.makedirs(workspace, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(workspace, filter="data")   # 'data' filter: no absolute/parent paths
