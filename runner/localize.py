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
