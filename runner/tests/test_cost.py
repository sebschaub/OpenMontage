from runner.cost import total_cost

def test_sums_agent_and_media():
    am = {"assets": [{"cost_usd": 0.1698}, {"cost_usd": 0.0}, {"cost_usd": 0.05}]}
    assert total_cost(0.80, am) == round(0.80 + 0.2198, 4)

def test_tolerates_missing_costs():
    am = {"assets": [{"id": "x"}, {"cost_usd": None}, {"cost_usd": "n/a"}]}
    assert total_cost(0.5, am) == 0.5

def test_empty_manifest():
    assert total_cost(1.0, {}) == 1.0
