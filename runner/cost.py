def total_cost(agent_cost_usd: float, asset_manifest: dict) -> float:
    media = 0.0
    for a in (asset_manifest or {}).get("assets", []):
        c = a.get("cost_usd")
        if isinstance(c, (int, float)):
            media += c
    return round(float(agent_cost_usd or 0.0) + media, 4)
