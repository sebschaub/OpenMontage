import threading, time
from runner import config as config_mod, app as app_mod, worker
from runner.queue import JobQueue

def build_app(start_loop=True):
    cfg = config_mod.load()
    queue = JobQueue(cfg.db_path)
    queue.recover_orphans(cfg.max_attempts)
    application = app_mod.make_app(cfg, queue)
    if start_loop:
        def loop():
            while True:
                if not worker.run_once(cfg, queue):
                    time.sleep(2)
        threading.Thread(target=loop, daemon=True).start()
    return application
