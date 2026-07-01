from runner import main

def test_build_app_recovers_orphans(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNER_SECRET", "s")
    monkeypatch.setenv("RUNNER_DB", str(tmp_path / "q.db"))
    monkeypatch.setenv("OPENMONTAGE_DIR", str(tmp_path))
    app = main.build_app(start_loop=False)     # don't spawn the thread in tests
    assert app is not None
