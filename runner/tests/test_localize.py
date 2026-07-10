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
    # one TTS call per non-empty section, each fed the (already-translated) text;
    # eleven_multilingual_v2 infers the language from the text (no voice/lang args)
    assert [c["text"] for c in tts_calls]==["Uno","Dos"]
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

import os
from runner import localize

def test_rebase_asset_paths_rewrites_manifest_and_cut_paths():
    # Archived projects carry absolute paths from the ORIGINAL (now-purged) render
    # workspace, e.g. /opt/openmontage/projects/{original_job}/assets/images/scene-6.jpg.
    old_img = "/opt/openmontage/projects/OLDJOB/assets/images/x.jpg"
    old_music = "/opt/openmontage/projects/OLDJOB/assets/audio/bed.mp3"
    ed = {
        "cuts": [{"type": "text_card", "text": "Hello",
                  "backgroundImage": old_img, "source": "vid-1"}],
        "audio": {"music": {"src": old_music}},
    }
    am = {"assets": [{"id": "img0", "type": "image", "path": old_img}]}
    new_ws = "/work/newjob"

    ed2, am2 = localize._rebase_asset_paths(ed, am, new_ws)

    manifest_path = am2["assets"][0]["path"]
    cut_bg = ed2["cuts"][0]["backgroundImage"]
    for p in (manifest_path, cut_bg):
        assert p.startswith(new_ws)
        assert p.endswith("assets/images/x.jpg")
        assert "OLDJOB" not in p
    assert manifest_path == os.path.join(new_ws, "assets", "images", "x.jpg")
    assert cut_bg == os.path.join(new_ws, "assets", "images", "x.jpg")
    # non-path cut field (an id, not an asset path) is left alone
    assert ed2["cuts"][0]["source"] == "vid-1"
    # absolute audio src (e.g. a music bed) is rebased too
    assert ed2["audio"]["music"]["src"] == os.path.join(new_ws, "assets", "audio", "bed.mp3")

def test_rebase_asset_paths_leaves_non_asset_paths_untouched():
    ed = {"cuts": [{"type": "text_card", "text": "Hello"}]}
    am = {"assets": [{"id": "n0", "type": "narration", "path": "/old/en.mp3"}]}
    ed2, am2 = localize._rebase_asset_paths(ed, am, "/work/newjob")
    # no "/assets/" substring in the path -> left as-is (e.g. narration gets
    # rewritten later by synthesize_narration, not by the rebase step)
    assert am2["assets"][0]["path"] == "/old/en.mp3"

import json, os
from runner import localize

# Non-narration asset paths in the archive point at the ORIGINAL (purged) render
# workspace — e.g. /opt/openmontage/projects/OLDJOB/assets/images/x.jpg — and must
# get rebased onto the new localize workspace (see _rebase_asset_paths).
_OLD_IMG = "/opt/openmontage/projects/OLDJOB/assets/images/x.jpg"

def _write_project(ws):
    os.makedirs(os.path.join(ws,"artifacts")); os.makedirs(os.path.join(ws,"assets","audio"))
    ed={"cuts":[{"type":"text_card","text":"Hello","out_seconds":9,
                 "backgroundImage":_OLD_IMG}],
        "captions":[{"word":"Hello","startMs":0,"endMs":900}],
        "audio":{"narration":{"segments":[{"asset_id":"en0","start_seconds":0}]}},
        "renderer_family":"explainer-data"}
    am={"version":"1.0","assets":[{"id":"en0","type":"narration","path":"/old/en.mp3"},
                                   {"id":"img0","type":"image","path":_OLD_IMG}]}
    script={"title":"T","sections":[{"id":"s0","text":"Hello world","start_seconds":0}]}
    json.dump(ed, open(os.path.join(ws,"artifacts","edit_decisions.json"),"w"))
    json.dump(am, open(os.path.join(ws,"artifacts","asset_manifest.json"),"w"))
    json.dump(script, open(os.path.join(ws,"artifacts","script.json"),"w"))

class _Cfg: pass

def test_localize_project_produces_spanish_render_inputs(tmp_path):
    ws=str(tmp_path/"job")
    def fake_extract(tar, dest): _write_project(dest)              # stand in for download+extract
    def fake_download(cfg,key,local): open(local,"wb").write(b"x"); return local
    def fake_translate(strings, lang): return [s+"-ES" for s in strings]
    def fake_tts(inputs):
        open(inputs["output_path"],"wb").write(b"\x00")
        return type("R",(),{"success":True,"error":None})()
    def fake_concat(parts,out): open(out,"wb").write(b"\x00")
    def fake_transcribe(inputs):
        return type("R",(),{"success":True,
            "data":{"word_timestamps":[{"word":"Hola","start":0.0,"end":0.9}]}})()
    localize.localize_project(_Cfg(), ws, "projects/job.tar.gz", "es-ES",
        download=fake_download, extract=fake_extract, translate=fake_translate,
        tts=fake_tts, transcribe=fake_transcribe, concat=fake_concat)
    ed=json.load(open(os.path.join(ws,"artifacts","edit_decisions.json")))
    assert ed["cuts"][0]["text"]=="Hello-ES"
    assert ed["captions"]==[{"word":"Hola","startMs":0,"endMs":900}]
    assert ed["audio"]["narration"]["segments"]==[{"asset_id":"narration-full","start_seconds":0}]
    # non-narration asset paths (image backgrounds, b-roll, music) must survive
    # the whole pipeline rebased onto THIS workspace, not the purged original one.
    bg = ed["cuts"][0]["backgroundImage"]
    assert bg.startswith(ws) and bg.endswith("assets/images/x.jpg") and "OLDJOB" not in bg
    am=json.load(open(os.path.join(ws,"artifacts","asset_manifest.json")))
    assert any(a["id"]=="narration-full" for a in am["assets"])
    img = next(a for a in am["assets"] if a["id"]=="img0")
    assert img["path"]==os.path.join(ws,"assets","images","x.jpg")

def _write_project_no_captions(ws):
    # Mirrors _write_project but omits "captions" entirely — this is what real
    # runner-rendered reels archive, since they stop before the compose-time
    # caption step (see localize_project's had_captions guard).
    os.makedirs(os.path.join(ws,"artifacts")); os.makedirs(os.path.join(ws,"assets","audio"))
    ed={"cuts":[{"type":"text_card","text":"Hello","out_seconds":9,
                 "backgroundImage":_OLD_IMG}],
        "audio":{"narration":{"segments":[{"asset_id":"en0","start_seconds":0}]}},
        "renderer_family":"explainer-data"}
    am={"version":"1.0","assets":[{"id":"en0","type":"narration","path":"/old/en.mp3"},
                                   {"id":"img0","type":"image","path":_OLD_IMG}]}
    script={"title":"T","sections":[{"id":"s0","text":"Hello world","start_seconds":0}]}
    json.dump(ed, open(os.path.join(ws,"artifacts","edit_decisions.json"),"w"))
    json.dump(am, open(os.path.join(ws,"artifacts","asset_manifest.json"),"w"))
    json.dump(script, open(os.path.join(ws,"artifacts","script.json"),"w"))

def test_localize_project_skips_caption_regen_when_no_original_captions(tmp_path):
    # Runner-rendered reels have no captions[] in their archived edit_decisions.
    # localize_project must NOT try to transcribe/regenerate captions for them —
    # doing so would require faster-whisper (not installed on the worker) and
    # would add captions the original reel never had.
    ws=str(tmp_path/"job")
    def fake_extract(tar, dest): _write_project_no_captions(dest)
    def fake_download(cfg,key,local): open(local,"wb").write(b"x"); return local
    def fake_translate(strings, lang): return [s+"-ES" for s in strings]
    def fake_tts(inputs):
        open(inputs["output_path"],"wb").write(b"\x00")
        return type("R",(),{"success":True,"error":None})()
    def fake_concat(parts,out): open(out,"wb").write(b"\x00")
    transcribe_calls={"n":0}
    def fake_transcribe(inputs):
        transcribe_calls["n"]+=1
        raise AssertionError("transcribe should not be called when the original reel had no captions")
    localize.localize_project(_Cfg(), ws, "projects/job.tar.gz", "es-ES",
        download=fake_download, extract=fake_extract, translate=fake_translate,
        tts=fake_tts, transcribe=fake_transcribe, concat=fake_concat)

    assert transcribe_calls["n"]==0

    ed=json.load(open(os.path.join(ws,"artifacts","edit_decisions.json")))
    assert "captions" not in ed
    # everything else still happens as normal
    assert ed["cuts"][0]["text"]=="Hello-ES"
    assert ed["audio"]["narration"]["segments"]==[{"asset_id":"narration-full","start_seconds":0}]
    bg = ed["cuts"][0]["backgroundImage"]
    assert bg.startswith(ws) and bg.endswith("assets/images/x.jpg") and "OLDJOB" not in bg
    am=json.load(open(os.path.join(ws,"artifacts","asset_manifest.json")))
    assert any(a["id"]=="narration-full" for a in am["assets"])
    img = next(a for a in am["assets"] if a["id"]=="img0")
    assert img["path"]==os.path.join(ws,"assets","images","x.jpg")

def test_localize_duration_guard_retries_then_raises(tmp_path, monkeypatch):
    ws=str(tmp_path/"job")
    def fake_extract(tar,dest): _write_project(dest)
    def fake_download(cfg,key,local): open(local,"wb").write(b"x"); return local
    def fake_tts(inputs): open(inputs["output_path"],"wb").write(b"\x00"); \
        return type("R",(),{"success":True,"error":None})()
    def fake_concat(parts,out): open(out,"wb").write(b"\x00")
    def fake_transcribe(inputs): return type("R",(),{"success":True,"data":{"word_timestamps":[]}})()
    calls={"n":0}
    def fake_translate(strings,lang): calls["n"]+=1; return [s+"-ES" for s in strings]
    monkeypatch.setattr(localize, "_probe_seconds", lambda p: 999.0)   # always too long
    import pytest
    with pytest.raises(RuntimeError, match="exceeds video"):
        localize.localize_project(_Cfg(), ws, "projects/job.tar.gz", "es-ES",
            download=fake_download, extract=fake_extract, translate=fake_translate,
            tts=fake_tts, transcribe=fake_transcribe, concat=fake_concat)
    assert calls["n"]>=2   # initial + tighter retry
