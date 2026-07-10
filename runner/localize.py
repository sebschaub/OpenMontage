import re

_CUT_STR_FIELDS = ("text","stat","subtitle","title","heroSubtitle","leftLabel","rightLabel",
                   "leftValue","rightValue","centerLabel","centerValue","xLabel","yLabel",
                   "progressLabel","terminalTitle","prompt")
_CUT_LIST_FIELDS = ("steps","screenshotSteps")
_OVERLAY_STR_FIELDS = ("text","subtitle","label")
# Trailing optional single magnitude-unit letter (K/M/B/T, either case) so
# abbreviated stat values like "8.1B" or "1.2m" are still recognized as
# purely numeric and excluded from translation, same as "34%" or "12%".
_NUMERIC = re.compile(r"^[\d\s.,%+\-x/$€£]+[KMBTkmbt]?$")

def _translatable(v):
    return isinstance(v, str) and v.strip() != "" and not _NUMERIC.match(v.strip())

def iter_text_slots(ed, script):
    """Yield (container, key) for every translatable on-screen/narration string,
    in a stable order. collect_strings and apply_translations both walk this."""
    for cut in (ed.get("cuts") or []):
        for k in _CUT_STR_FIELDS:
            if k in cut and _translatable(cut[k]): yield (cut, k)
        for k in _CUT_LIST_FIELDS:
            lst = cut.get(k)
            if isinstance(lst, list):
                for i, v in enumerate(lst):
                    if _translatable(v): yield (lst, i)
        for datum in (cut.get("chartData") or []):
            if isinstance(datum, dict) and _translatable(datum.get("label")): yield (datum, "label")
        for ser in (cut.get("chartSeries") or []):
            if isinstance(ser, dict) and _translatable(ser.get("label")): yield (ser, "label")
    for ov in (ed.get("overlays") or []):
        for k in _OVERLAY_STR_FIELDS:
            if k in ov and _translatable(ov[k]): yield (ov, k)
        prov = ov.get("providers")
        if isinstance(prov, list):
            for i, v in enumerate(prov):
                if _translatable(v): yield (prov, i)
    if _translatable(script.get("title")): yield (script, "title")
    for sec in (script.get("sections") or []):
        if _translatable(sec.get("text")): yield (sec, "text")

def collect_strings(ed, script):
    return [c[k] for c, k in iter_text_slots(ed, script)]

def apply_translations(ed, script, translations):
    slots = list(iter_text_slots(ed, script))
    if len(slots) != len(translations):
        raise ValueError(f"translation count {len(translations)} != slot count {len(slots)}")
    for (c, k), t in zip(slots, translations):
        c[k] = t

import json, subprocess

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

def _extract_json_array(text):
    """Pull the first JSON array out of the model's text (tolerates prose/fences).

    Fast path: the whole (fence-stripped) text is itself a JSON array — this is
    the common case since the prompt asks for ONLY a JSON array, and json.loads
    is inherently correct about brackets inside quoted strings.

    Fallback: prose surrounds the array. Scan from the first "[", but track
    whether we're inside a JSON string (honoring backslash escapes) so that
    "[" / "]" inside translated string values don't perturb the depth count.
    """
    candidate = text.strip()
    m = _FENCE_RE.match(candidate)
    if m:
        candidate = m.group(1).strip()
    try:
        parsed = json.loads(candidate)
    except ValueError:
        parsed = None
    if isinstance(parsed, list):
        return parsed

    s = text.find("[")
    if s == -1: raise ValueError("no JSON array in translation output")
    depth = 0
    in_string = False
    escaped = False
    for i in range(s, len(text)):
        ch = text[i]
        if in_string:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': in_string = False
            continue
        if ch == '"': in_string = True
        elif ch == "[": depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[s:i+1])
    raise ValueError("unterminated JSON array in translation output")

def translate_strings(strings, target_language, runner=subprocess.run):
    if not strings:
        return []
    prompt = (
        f"Translate each item of this JSON array into {target_language}. "
        "Return ONLY a JSON array of the same length, in the same order — no prose, no code fences.\n"
        "Rules: keep each translation AT MOST the character length of its source (prefer shorter); "
        "preserve numbers, %, URLs, and brand/product names verbatim; natural, idiomatic phrasing.\n\n"
        + json.dumps(strings, ensure_ascii=False)
    )
    cmd = ["claude", "-p", prompt, "--permission-mode", "bypassPermissions",
           "--model", "haiku", "--output-format", "json"]
    proc = runner(cmd, capture_output=True, text=True, timeout=300)
    data = json.loads(proc.stdout or "{}")
    result = data.get("result", proc.stdout or "")
    out = _extract_json_array(result if isinstance(result, str) else json.dumps(result))
    if len(out) != len(strings):
        raise ValueError(f"translation returned {len(out)} items for {len(strings)} inputs")
    return [str(x) for x in out]

import os

# eleven_multilingual_v2 speaks the language of the input text, so ONE voice
# (ElevenLabs default, Rachel) covers every target language — no per-language
# voice map. Google Cloud TTS was the original design, but the worker has no
# Cloud TTS credential; ElevenLabs is the working multilingual provider (also
# what the reel pipeline + the first Spanish dub use). The translated
# script.json text drives the spoken language. SUPPORTED_LANGUAGES guards typos.
SUPPORTED_LANGUAGES = {"es-ES", "fr-FR", "de-DE", "pt-BR", "pt-PT"}

def synthesize_narration(script, language, workspace, tts=None, concat=None):
    if language not in SUPPORTED_LANGUAGES:
        raise KeyError(f"unsupported language: {language!r}")
    if tts is None:
        from tools.audio.elevenlabs_tts import ElevenLabsTTS
        tts = ElevenLabsTTS().execute
    if concat is None:
        from runner.render import _ffmpeg_concat_narration as concat
    audio_dir = os.path.join(workspace, "assets", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    parts = []
    for i, sec in enumerate(script.get("sections") or []):
        text = (sec.get("text") or "").strip()
        if not text:
            continue
        out = os.path.join(audio_dir, f"loc_narration_{i}.mp3")
        res = tts({"text": text, "output_path": out})   # eleven_multilingual_v2 default
        if not getattr(res, "success", False):
            raise RuntimeError(f"TTS failed for section {i}: {getattr(res,'error','?')}")
        parts.append((out, sec.get("start_seconds", 0)))
    full = os.path.join(audio_dir, "narration_full.mp3")
    concat(parts, full)
    return {"id": "narration-full", "type": "narration", "path": full}

def narration_to_captions(narration_path, iso_lang, transcribe=None):
    if transcribe is None:
        from tools.analysis.transcriber import Transcriber
        transcribe = Transcriber().execute
    res = transcribe({"input_path": narration_path, "language": iso_lang})
    if not getattr(res, "success", False):
        raise RuntimeError(f"transcription failed: {getattr(res,'error','?')}")
    words = (getattr(res, "data", {}) or {}).get("word_timestamps") or []
    return [{"word": w["word"], "startMs": int(round(w["start"]*1000)),
             "endMs": int(round(w["end"]*1000))} for w in words]

def _video_duration(ed):
    outs = [c.get("out_seconds", 0) for c in (ed.get("cuts") or [])]
    return (max(outs) + 1) if outs else 0

def _rebase_asset_paths(ed, am, workspace):
    """Archived projects carry absolute paths from the ORIGINAL (now-purged)
    render workspace. After extract, every asset lives at {workspace}/assets/<suffix>.
    Rewrite manifest paths + every absolute cut/audio asset field onto this
    workspace so the render resolves them. (arcname='assets' guarantees the layout.)"""
    def rebase(p):
        if isinstance(p, str) and "/assets/" in p:
            return os.path.join(workspace, "assets", p.split("/assets/", 1)[1])
        return p
    for a in (am.get("assets") or []):
        if a.get("path"):
            a["path"] = rebase(a["path"])
    for cut in (ed.get("cuts") or []):
        for k, v in list(cut.items()):
            if isinstance(v, str):
                cut[k] = rebase(v)          # backgroundImage/backgroundVideo/source/etc.
    audio = ed.get("audio") or {}
    for block in audio.values():
        if isinstance(block, dict) and isinstance(block.get("src"), str):
            block["src"] = rebase(block["src"])
    return ed, am

def localize_project(cfg, workspace, project_url, language, *,
                     download=None, extract=None, translate=None,
                     tts=None, transcribe=None, concat=None):
    from runner import storage, project_archive
    download = download or storage.download
    extract = extract or project_archive.extract_project
    translate = translate or (lambda s, l: translate_strings(s, l))
    iso = language.split("-")[0]

    # 1. fetch + unpack the archived reel project
    key = project_url.split("/", 3)[-1] if project_url.startswith("http") else project_url
    tar = os.path.join(workspace, "_project.tar.gz")
    os.makedirs(workspace, exist_ok=True)
    download(cfg, key, tar)
    extract(tar, workspace)

    art = os.path.join(workspace, "artifacts")
    ed = json.load(open(os.path.join(art, "edit_decisions.json")))
    am = json.load(open(os.path.join(art, "asset_manifest.json")))
    script = json.load(open(os.path.join(art, "script.json")))

    # Runner-rendered reels stop before the compose-time caption step, so their
    # archived edit_decisions has no captions[] at all — only regenerate captions
    # for projects that originally had them (see caption regen below).
    had_captions = bool(ed.get("captions"))

    # archived asset paths point at the (now-purged) original render workspace —
    # rebase them onto this workspace before anything else touches them.
    ed, am = _rebase_asset_paths(ed, am, workspace)

    # 2. translate on-screen text + narration script (length-constrained)
    strings = collect_strings(ed, script)
    apply_translations(ed, script, translate(strings, language))

    # 3. re-TTS narration; 4. concat happens inside synthesize_narration
    narration = synthesize_narration(script, language, workspace, tts=tts, concat=concat)
    am.setdefault("assets", [])
    am["assets"] = [a for a in am["assets"] if a.get("type") != "narration"] + [narration]
    ed.setdefault("audio", {}).setdefault("narration", {})
    ed["audio"]["narration"]["segments"] = [{"asset_id": "narration-full", "start_seconds": 0}]

    # duration guard: narration must fit the fixed video length
    dur = _probe_seconds(narration["path"])
    if dur > _video_duration(ed) + 0.75:
        # one tighter retry, then give up rather than ship clipped audio
        tighter = translate([s for s in (sec.get("text","") for sec in script["sections"])], language)
        for sec, t in zip(script["sections"], tighter):
            sec["text"] = t
        narration = synthesize_narration(script, language, workspace, tts=tts, concat=concat)
        dur = _probe_seconds(narration["path"])
        if dur > _video_duration(ed) + 0.75:
            raise RuntimeError(f"translated narration {dur:.1f}s exceeds video {_video_duration(ed)}s")

    # 5. regenerate captions from the target-language narration — but only if
    # the original reel had captions in the first place.
    if had_captions:
        # Original reel carried word-level captions → regenerate them from the
        # target-language narration so they match the new audio.
        try:
            ed["captions"] = narration_to_captions(narration["path"], iso, transcribe=transcribe)
        except Exception as e:
            # Transcriber unavailable (e.g. faster-whisper not installed): ship the
            # localized reel WITHOUT captions rather than hard-failing or keeping
            # mistimed source-language captions.
            print(f"caption regen skipped ({e}); dropping original captions")
            ed.pop("captions", None)
    # Reels rendered by the runner stop before the compose-time caption step, so
    # they have no captions[] — nothing to regenerate; leave it absent to match the original.

    json.dump(ed, open(os.path.join(art, "edit_decisions.json"), "w"))
    json.dump(am, open(os.path.join(art, "asset_manifest.json"), "w"))

def _probe_seconds(path):
    import subprocess
    try:
        p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                            "-of","csv=p=0", path], capture_output=True, text=True, timeout=60)
        return float((p.stdout or "0").strip() or 0)
    except Exception:
        return 0.0
