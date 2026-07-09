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

# Google Cloud TTS voices per target language. Neural2 = broadly available + cheap
# ($16/1M chars). VALIDATE names against the live voices list before shipping
# (see deploy task); wrong ids 400 from the API.
LANG_VOICE = {
    "es-ES": "es-ES-Neural2-B",
    "fr-FR": "fr-FR-Neural2-B",
    "de-DE": "de-DE-Neural2-B",
    "pt-BR": "pt-BR-Neural2-B",
    "pt-PT": "pt-PT-Wavenet-B",
}

def synthesize_narration(script, language, workspace, tts=None, concat=None):
    if tts is None:
        from tools.audio.google_tts import GoogleTTS
        tts = GoogleTTS().execute
    if concat is None:
        from runner.render import _ffmpeg_concat_narration as concat
    voice = LANG_VOICE[language]            # KeyError on unsupported language
    audio_dir = os.path.join(workspace, "assets", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    parts = []
    for i, sec in enumerate(script.get("sections") or []):
        text = (sec.get("text") or "").strip()
        if not text:
            continue
        out = os.path.join(audio_dir, f"loc_narration_{i}.mp3")
        res = tts({"text": text, "voice": voice, "language_code": language,
                   "audio_encoding": "MP3", "output_path": out})
        if not getattr(res, "success", False):
            raise RuntimeError(f"TTS failed for section {i}: {getattr(res,'error','?')}")
        parts.append((out, sec.get("start_seconds", 0)))
    full = os.path.join(audio_dir, "narration_full.mp3")
    concat(parts, full)
    return {"id": "narration-full", "type": "narration", "path": full}
