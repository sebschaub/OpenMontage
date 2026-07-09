from runner import localize

def _fixture():
    ed = {
        "cuts": [
            {"type":"hero_title","text":"The World in Numbers","subtitle":"zero-key showcase"},
            {"type":"stat_card","stat":"8.1B","subtitle":"people on one planet"},
            {"type":"bar_chart","title":"Megacity population",
             "chartData":[{"label":"Tokyo","value":37},{"label":"Delhi","value":33}]},
            {"type":"comparison","title":"Before vs after","leftLabel":"Old","rightLabel":"New",
             "leftValue":"12%","rightValue":"88%"},
            {"type":"text_card","text":"Human-scale decisions.",
             "backgroundImage":"/abs/assets/images/x.jpg","source":"vid-1"},
        ],
        "overlays":[{"type":"section_title","text":"Cities","subtitle":"dense hubs",
                     "label":"generated with","providers":["Runway","Pika"]}],
        "captions":[{"word":"Old","startMs":0,"endMs":100}],
        "audio":{"narration":{"segments":[{"asset_id":"n0","start_seconds":0}]}},
    }
    script = {"title":"World","sections":[{"id":"s0","text":"Nearly two thousand percent."}]}
    return ed, script

def test_collect_gathers_only_translatable_text():
    ed, script = _fixture()
    strings = localize.collect_strings(ed, script)
    assert "The World in Numbers" in strings
    assert "people on one planet" in strings
    assert "Tokyo" in strings and "Delhi" in strings
    assert "Old" in strings and "New" in strings
    assert "Human-scale decisions." in strings
    assert "Cities" in strings and "generated with" in strings
    assert "Runway" in strings and "Pika" in strings
    assert "World" in strings and "Nearly two thousand percent." in strings
    # numbers, asset paths, ids, enums, captions NOT collected
    for bad in ("8.1B","12%","88%","/abs/assets/images/x.jpg","vid-1","hero_title","n0"):
        assert bad not in strings

def test_apply_writes_back_in_order():
    ed, script = _fixture()
    strings = localize.collect_strings(ed, script)
    translations = [s.upper() for s in strings]        # fake "translation"
    localize.apply_translations(ed, script, translations)
    assert ed["cuts"][0]["text"] == "THE WORLD IN NUMBERS"
    assert ed["cuts"][2]["chartData"][0]["label"] == "TOKYO"
    assert ed["overlays"][0]["providers"][0] == "RUNWAY"
    assert script["sections"][0]["text"] == "NEARLY TWO THOUSAND PERCENT."
    # untouched
    assert ed["cuts"][1]["stat"] == "8.1B"
    assert ed["cuts"][4]["backgroundImage"] == "/abs/assets/images/x.jpg"

def test_apply_length_mismatch_raises():
    ed, script = _fixture()
    import pytest
    with pytest.raises(ValueError):
        localize.apply_translations(ed, script, ["too", "few"])

import json as _json
from runner import localize

class _Proc:
    def __init__(self, out): self.returncode=0; self.stdout=out; self.stderr=""

def test_translate_strings_parses_json_array():
    captured={}
    def fake_runner(cmd, **kw):
        captured["cmd"]=cmd
        prompt=cmd[cmd.index("-p")+1]
        assert "es-ES" in prompt and "JSON array" in prompt
        return _Proc(_json.dumps({"result": '["Hola","Mundo"]'}))
    out=localize.translate_strings(["Hi","World"], "es-ES", runner=fake_runner)
    assert out==["Hola","Mundo"]
    assert "--model" in captured["cmd"] and "haiku" in captured["cmd"]

def test_translate_strings_wrong_count_raises():
    def fake_runner(cmd, **kw): return _Proc(_json.dumps({"result":'["only one"]'}))
    import pytest
    with pytest.raises(ValueError):
        localize.translate_strings(["a","b"], "es-ES", runner=fake_runner)

def test_translate_strings_empty_is_noop():
    calls={"n":0}
    def fake_runner(cmd, **kw): calls["n"]+=1; return _Proc("{}")
    assert localize.translate_strings([], "es-ES", runner=fake_runner)==[]
    assert calls["n"]==0
