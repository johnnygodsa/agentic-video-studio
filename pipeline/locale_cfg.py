"""地區慣例開關(公開庫可關):repo 根 studio.json 的 "locale" 區塊;檔案不存在 = 預設值(本工作室慣例全開)。

  enabled(key)        -> bool   例:enabled("price_local_currency")
  get(key, default)   -> 值
  section(name)       -> dict   studio.json 任一頂層區塊原樣(不套 DEFAULTS、不快取),例:section("llm")

鍵:
  price_local_currency  bool  美金價格同句/同畫面要附本地幣(script_lint T08,預設 True)
  local_currency_regex  str   本地幣的辨識 regex(預設台幣 NT$/台幣/TWD)
  local_currency_name   str   警告訊息用的幣名(預設「台幣」)
  regional_terms        bool  改句代理(line_fix)要求在地用語(預設 True;用語名稱見 regional_terms_name)
  regional_terms_name   str   在地用語名稱(預設「台灣用語」)
"""
import json
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CFG = REPO / "studio.json"

DEFAULTS = {
    "price_local_currency": True,
    "local_currency_regex": r"NT\s?\$|NT\s?\d|台幣|新台幣|臺幣|NTD|TWD",
    "local_currency_name": "台幣",
    "regional_terms": True,
    "regional_terms_name": "台灣用語",
}


@lru_cache(maxsize=1)
def _load():
    try:
        d = json.loads(CFG.read_text(encoding="utf-8")).get("locale") or {}
    except (OSError, ValueError):
        d = {}
    return {**DEFAULTS, **{k: v for k, v in d.items() if k in DEFAULTS}}


def get(key, default=None):
    return _load().get(key, default)


def enabled(key):
    return bool(_load().get(key))


def section(name):
    """studio.json 頂層區塊 name(dict);檔案不存在、壞掉或不是物件 = {}。不快取:改檔或測試換 CFG 立即生效。"""
    try:
        d = json.loads(CFG.read_text(encoding="utf-8")).get(name)
    except (OSError, ValueError, AttributeError):
        d = None
    return dict(d) if isinstance(d, dict) else {}
