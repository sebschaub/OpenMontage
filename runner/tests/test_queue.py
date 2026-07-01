from runner.queue import JobQueue

def test_enqueue_claim_and_complete(tmp_path):
    q = JobQueue(str(tmp_path / "q.db"))
    q.enqueue("j1", "reel", 5210, {"pipeline": "reel"})
    assert q.depth() == 1
    job = q.claim_next()
    assert job["id"] == "j1" and job["status"] == "running"
    assert job["spec"]["pipeline"] == "reel" and job["attempts"] == 1
    assert q.claim_next() is None            # nothing else pending
    q.mark_done("j1", 1.23, "https://x/v.mp4")
    assert q.get("j1")["status"] == "done" and q.get("j1")["cost_usd"] == 1.23

def test_fifo_order(tmp_path):
    q = JobQueue(str(tmp_path / "q.db"))
    q.enqueue("a", "reel", None, {}); q.enqueue("b", "reel", None, {})
    assert q.claim_next()["id"] == "a"

def test_recover_orphans_requeues_under_max(tmp_path):
    q = JobQueue(str(tmp_path / "q.db"))
    q.enqueue("j", "reel", None, {}); q.claim_next()       # now running, attempts=1
    q.recover_orphans(max_attempts=2)
    assert q.get("j")["status"] == "pending"
    q.claim_next()                                         # attempts=2
    q.recover_orphans(max_attempts=2)
    assert q.get("j")["status"] == "failed"

def test_requeue_returns_to_pending_keeping_attempts(tmp_path):
    q = JobQueue(str(tmp_path / "q.db"))
    q.enqueue("j", "reel", None, {}); q.claim_next()      # running, attempts=1
    q.requeue("j")
    j = q.get("j")
    assert j["status"] == "pending" and j["attempts"] == 1
    assert q.claim_next()["id"] == "j"                    # claimable again
