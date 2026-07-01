import json, subprocess
from dataclasses import dataclass
from runner import pipelines

@dataclass
class AgentResult:
    ok: bool
    cost_usd: float
    log_tail: str

def run_agent(cfg, alias, workspace, brief_path, profile, budget_cap, timeout_sec, runner=subprocess.run):
    prompt = pipelines.build_prompt(alias, brief_path, workspace, profile, budget_cap)
    cmd = ["claude", "-p", prompt, "--permission-mode", "bypassPermissions",
           "--output-format", "json"]
    try:
        proc = runner(cmd, cwd=cfg.openmontage_dir, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return AgentResult(False, 0.0, f"agent timed out after {timeout_sec}s")
    cost, ok = 0.0, proc.returncode == 0
    try:
        data = json.loads(proc.stdout or "{}")
        cost = float(data.get("total_cost_usd", 0.0) or 0.0)
        if data.get("is_error"):
            ok = False
    except (ValueError, TypeError):
        pass
    tail = ((proc.stdout or "")[-1500:] + "\n" + (proc.stderr or "")[-1500:]).strip()
    return AgentResult(ok, cost, tail)
