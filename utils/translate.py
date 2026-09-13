import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_MAX_SEGMENT = 1300


def _has_chinese(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _translate_sync(text: str) -> str:
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": "my",
        "dt": "t",
        "q": text,
    }
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, list) and data and isinstance(data[0], list):
        chunks = []
        for seg in data[0]:
            if isinstance(seg, list) and seg and seg[0]:
                chunks.append(seg[0])
        return "".join(chunks)
    return text


def _translate_chunk(text: str) -> str:
    if len(text) <= _MAX_SEGMENT:
        return _translate_sync(text)
    pieces = []
    i = 0
    while i < len(text):
        pieces.append(_translate_sync(text[i:i + _MAX_SEGMENT]))
        i += _MAX_SEGMENT
    return "".join(pieces)


def _translate_mymemory_sync(text: str) -> str:
    def one(t: str) -> str:
        params = {"q": t, "langpair": "zh-CN|my"}
        url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        trans = (data.get("responseData") or {}).get("translatedText")
        if trans and isinstance(trans, str):
            return trans
        raise RuntimeError("MyMemory returned empty result")

    if len(text) <= 480:
        return one(text)
    out = []
    for i in range(0, len(text), 480):
        out.append(one(text[i:i + 480]))
    return "".join(out)


async def translate_to_burmese(text: str) -> str:
    """Translate Chinese text to Burmese. Non-Chinese text is returned unchanged."""
    if not text or not _has_chinese(text):
        return text
    try:
        result = await asyncio.to_thread(_translate_chunk, text)
        return result.strip() or text
    except Exception as e:
        logging.warning("Google translate failed (%s), trying MyMemory", e)
    try:
        result = await asyncio.to_thread(_translate_mymemory_sync, text)
        return result.strip() or text
    except Exception as e:
        logging.warning("MyMemory translate failed, keeping original: %s", e)
        return text