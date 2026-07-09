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

def _extract_json_array(text):
    """Pull the first JSON array out of the model's text (tolerates prose/fences)."""
    s = text.find("[");
    if s == -1: raise ValueError("no JSON array in translation output")
    depth = 0
    for i in range(s, len(text)):
        if text[i] == "[": depth += 1
        elif text[i] == "]":
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
