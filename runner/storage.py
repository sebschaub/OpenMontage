def _make_client(cfg):
    import boto3
    return boto3.client("s3", endpoint_url=cfg.s3_endpoint,
                        aws_access_key_id=cfg.s3_access_key,
                        aws_secret_access_key=cfg.s3_secret_key)

def upload(cfg, local_path, key, content_type="video/mp4", client=None):
    client = client or _make_client(cfg)
    client.upload_file(Filename=local_path, Bucket=cfg.s3_bucket, Key=key,
                       ExtraArgs={"ContentType": content_type})
    return f"{cfg.public_base}/{key}"

def download(cfg, key, local_path, client=None):
    import os
    client = client or _make_client(cfg)
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    client.download_file(Bucket=cfg.s3_bucket, Key=key, Filename=local_path)
    return local_path
