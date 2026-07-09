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

def test_extract_json_array_handles_bracket_inside_string():
    # A translated element containing a stray "]" must not desync the depth count.
    assert localize._extract_json_array('["a]b", "cd"]') == ["a]b", "cd"]

def test_extract_json_array_strips_fence():
    assert localize._extract_json_array('```json\n["x", "y"]\n```') == ["x", "y"]

def test_extract_json_array_prose_wrapped_with_bracket_in_string():
    # Exercises the string-aware fallback scan specifically: prose around the
    # fence means the fast-path whole-text json.loads can't apply directly,
    # so the depth-counting scan must still skip "]" inside quoted values.
    text = 'Sure, here is the translation:\n```json\n["a]b", "cd"]\n```\nHope that helps!'
    assert localize._extract_json_array(text) == ["a]b", "cd"]

def test_extract_json_array_no_array_raises():
    import pytest
    with pytest.raises(ValueError):
        localize._extract_json_array("Sorry, I can't help with that.")

import os
from runner import localize

def test_synthesize_narration_tts_per_section_then_concat(tmp_path):
    script={"sections":[{"id":"s0","text":"Uno","start_seconds":0},
                        {"id":"s1","text":"Dos","start_seconds":5}]}
    tts_calls=[]
    def fake_tts(inputs):
        tts_calls.append(inputs); open(inputs["output_path"],"wb").write(b"\x00")
        class R: success=True; error=None
        return R()
    concat_calls={}
    def fake_concat(parts, out_path):
        concat_calls["parts"]=parts; open(out_path,"wb").write(b"\x00")
    asset=localize.synthesize_narration(script,"es-ES",str(tmp_path),tts=fake_tts,concat=fake_concat)
    assert asset["id"]=="narration-full" and asset["type"]=="narration"
    assert asset["path"].endswith("assets/audio/narration_full.mp3")
    assert [c["language_code"] for c in tts_calls]==["es-ES","es-ES"]
    assert tts_calls[0]["voice"]==localize.LANG_VOICE["es-ES"]
    # concat received (path, start_seconds) per section in order
    assert [p[1] for p in concat_calls["parts"]]==[0,5]

def test_synthesize_narration_unknown_lang_raises(tmp_path):
    import pytest
    with pytest.raises(KeyError):
        localize.synthesize_narration({"sections":[{"text":"x"}]},"xx-XX",str(tmp_path),
                                      tts=lambda i:None, concat=lambda p,o:None)

from runner import localize

def test_narration_to_captions_maps_word_timestamps():
    def fake_transcribe(inputs):
        assert inputs["language"]=="es"
        class R:
            success=True
            data={"word_timestamps":[{"word":"Casi","start":0.1,"end":0.5},
                                     {"word":"dos","start":0.5,"end":0.8}]}
        return R()
    caps=localize.narration_to_captions("/x/narration_full.mp3","es",transcribe=fake_transcribe)
    assert caps==[{"word":"Casi","startMs":100,"endMs":500},
                  {"word":"dos","startMs":500,"endMs":800}]

def test_narration_to_captions_empty_when_no_words():
    def fake_transcribe(inputs):
        class R: success=True; data={"word_timestamps":[]}
        return R()
    assert localize.narration_to_captions("/x.mp3","es",transcribe=fake_transcribe)==[]
