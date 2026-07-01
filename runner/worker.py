import json, os, shutil
from runner import agent as agent_mod, render as render_mod, storage as storage_mod
from runner import callback as callback_mod, cost as cost_mod, pipelines

class Deps:
    run_agent = staticmethod(agent_mod.run_agent)
    ensure_final = staticmethod(render_mod.ensure_final)
    upload = staticmethod(storage_mod.upload)
    send = staticmethod(callback_mod.send)

def _default_deps():
    return Deps()

def run_once(cfg, queue, deps=None) -> bool:
    deps = deps or _default_deps()
    job = queue.claim_next()
    if not job:
        return False
    process_job(cfg, queue, job, deps)
    return True

def process_job(cfg, queue, job, deps):
    job_id = job["id"]; spec = job["spec"]
    ws = os.path.join(cfg.projects_dir, job_id)
    callback_url = spec.get("callbackUrl")
    shutil.rmtree(ws, ignore_errors=True)   # fresh workspace for this attempt
    try:
        alias = spec["pipeline"]; p = pipelines.resolve(alias)
        profile = spec.get("mediaProfile") or p.default_profile
        cap = spec.get("budgetCapUsd", 2.0)
        os.makedirs(ws, exist_ok=True)
        with open(os.path.join(ws, "brief.json"), "w") as f:
            json.dump(spec.get("inputs", {}), f)
        ar = deps.run_agent(cfg, alias, ws, os.path.join(ws, "brief.json"),
                            profile, cap, cfg.job_timeout_sec)
        rr = deps.ensure_final(ws, profile)
        if not rr.ok:
            err = (rr.error or "render failed") + "\n--agent log--\n" + (ar.log_tail or "")
            _fail_or_retry(cfg, queue, job, ws, callback_url, spec, deps, err)
            return
        cost = cost_mod.total_cost(ar.cost_usd, rr.asset_manifest)
        video_url = deps.upload(cfg, rr.final_path, f"videos/{job_id}.mp4")
        queue.mark_done(job_id, cost, video_url)
        _callback(cfg, deps, callback_url, job_id, "done", spec, cost=cost, video_url=video_url)
        shutil.rmtree(ws, ignore_errors=True)   # purge only on success
    except Exception as e:
        _fail_or_retry(cfg, queue, job, ws, callback_url, spec, deps, f"runner error: {e}")

def _fail_or_retry(cfg, queue, job, ws, callback_url, spec, deps, error):
    # Nondeterministic agent output means one bad run may render fine on a retry.
    # Requeue while attempts remain (clean workspace for a fresh attempt); once
    # exhausted, fail terminally and KEEP the workspace for diagnosis.
    if job.get("attempts", 1) < cfg.max_attempts:
        shutil.rmtree(ws, ignore_errors=True)
        queue.requeue(job["id"])
        return
    queue.mark_failed(job["id"], error[:4000])
    _callback(cfg, deps, callback_url, job["id"], "failed", spec, error=error[:1500])

def _callback(cfg, deps, callback_url, job_id, status, spec, *, cost=None, video_url=None, error=None):
    if not callback_url:
        return
    payload = {"jobId": job_id, "status": status, "pipeline": spec.get("pipeline"),
               "articleId": spec.get("articleId"), "costUsd": cost,
               "url": video_url, "error": error}
    deps.send(cfg, callback_url, payload)
