def _default_poster(url, json, headers):
    import httpx
    return httpx.post(url, json=json, headers=headers, timeout=30)

def send(cfg, callback_url, payload, poster=None):
    poster = poster or _default_poster
    try:
        resp = poster(callback_url, payload, {"Authorization": f"Bearer {cfg.callback_secret}"})
        return 200 <= resp.status_code < 300
    except Exception:
        return False
