#!/usr/bin/env python3
r"""B4 讀音決定的確定性寫入(flow v3;PLAN_token重設計_2026-11-03 §2(b) B2;規格 docs\director_ab.md「B4 v3」)。

apply(decisions, tag=None) -> {"added": [...], "errors": [...]}:decisions = pron-review 回的結構化決定,每筆一個 dict:
  {kind:"rule",     char, words:[詞..] | re:"正規式", py, pos?:[位置..], model_default?(新字才要), unverified:true, note}  -> pron_rules.json 該字 rules 末尾(新字 = 新條目)
  {kind:"word",     word, py, note}                                                                                  -> cosy_pron.json 詞條
  {kind:"term",     word, py | action:"direct", note}                                                                -> cosy_terms.json(寫法;direct = 加進 _direct 直送清單)
  {kind:"sub_word", word}                                                                                            -> sub_words.txt 檔尾一行
  {kind:"backlog",  word(=字), context(=語境詞), action, reason}                                                     -> projects\<tag>\pron_apply.json 的 backlog(gate_b4.backlog_pending 判已處理)
只新增,既有鍵值不動;寫前驗:py 的 [..] token 都在 CosyVoice tokenizer(tts_cosy_text 同一份,沒有 tokenizer 檔就略過)、re 可編譯、詞含該字且 pos 對得上;
錯的條目進 errors 不寫。整檔原子寫(同目錄暫存檔 + os.replace),寫後用 director_ab._only_added 自驗,不符就還原。
讀音檔路徑走 director_ab._pron_path(測試 monkeypatch 它,不動真檔)。
record_seen(tag, items):把 pron-review 本輪看過的條目記進 pron_apply.json 的 decided 帳本(pron_pre 之後不再列)。
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import paths as P  # noqa: E402

TOKEN_RE = re.compile(r"(\[[^\[\]\s]+\])")
KINDS = ("rule", "word", "term", "sub_word", "backlog")
NL, CRLF = "\n", "\r\n"


def _DA():
    import director_ab
    return director_ab


def _path(name):
    return _DA()._pron_path(name)


def _tokens():
    """CosyVoice tokenizer 的拼音 token;沒有 tokenizer 檔回 None(略過驗證)。"""
    import tts_cosy_text as CT
    return CT._tokenizer_tokens() if CT.TOKENIZER_PY.exists() else None


def _bad_py(py, have):
    if not isinstance(py, str) or not py.strip():
        return "py 空白"
    miss = sorted(set(TOKEN_RE.findall(py)) - have) if have is not None else []
    return f"拼音 token 不存在:{miss}" if miss else None


def _rd(f):
    return Path(f).read_bytes().decode("utf-8")      # 不經換行轉換(sub_words.txt 是 CRLF)


def _dump(d, nl):
    return json.dumps(d, ensure_ascii=False, indent=1) + ("\n" if nl else "")


def _atomic(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


def _note(tag, d):
    n = (d.get("note") or d.get("reason") or "").strip()
    return f"{date.today().isoformat()} 讀音審 {tag or ''}{(' ' + n) if n else ''}".strip()


def _rule_entry(d, tag, have, rules):
    ch = d.get("char")
    if not (isinstance(ch, str) and len(ch) == 1):
        return None, "rule 的 char 要單一字"
    bad = _bad_py(d.get("py"), have)
    if bad:
        return None, f"{ch}:{bad}"
    words, rx = d.get("words"), d.get("re")
    if bool(words) == bool(rx):
        return None, f"{ch}:words 與 re 要擇一"
    r = {}
    if words:
        if not (isinstance(words, list) and all(isinstance(w, str) and ch in w for w in words)):
            return None, f"{ch}:words 每個詞都要含「{ch}」"
        pos = d.get("pos")
        if pos is not None:
            if not (isinstance(pos, list) and all(isinstance(o, int) and all(0 <= o < len(w) and w[o] == ch for w in words) for o in pos)):
                return None, f"{ch}:pos 對不上詞裡的「{ch}」"
            r["pos"] = pos
        r = {"words": words, "py": d["py"], **r}
    else:
        try:
            re.compile(rx)
        except re.error as e:
            return None, f"{ch}:re 不能編譯:{e}"
        r = {"re": rx, "py": d["py"]}
    cur = (rules.get(ch) or {}).get("rules") or []
    if any((x.get("words") == r.get("words") and x.get("re") == r.get("re") and x.get("py") == r["py"]) for x in cur):
        return None, f"{ch}:同樣的規則已存在"
    r["unverified"] = True
    r["note"] = _note(tag, d)
    return r, None


def apply(decisions, tag=None):
    """見檔頭。回傳 {"added": [{file, entry}], "errors": [str]}。"""
    DA = _DA()
    added, errors = [], []
    have = _tokens()
    files = {}     # 檔名 -> [舊文字, 新資料, 結尾換行]
    backlog = []

    def doc(name):
        if name not in files:
            f = _path(name)
            if not f.exists():
                raise FileNotFoundError(name)
            t = _rd(f)
            files[name] = {"old": t, "text": t, "data": json.loads(t) if name.endswith(".json") else None, "nl": t.endswith(NL)}
        return files[name]

    for d in decisions or []:
        try:
            k = d.get("kind")
            if k == "rule":
                rules = doc("pron_rules.json")["data"]
                r, err = _rule_entry(d, tag, have, rules)
                if err:
                    errors.append(err)
                    continue
                ch = d["char"]
                if ch not in rules:
                    if not d.get("model_default") or _bad_py(d["model_default"], have):
                        errors.append(f"{ch}:新字要給可用的 model_default")
                        continue
                    rules[ch] = {"model_default": d["model_default"], "always": False, "rules": []}
                rules[ch].setdefault("rules", []).append(r)
                added.append({"file": "pipeline\\pron_rules.json", "entry": f"{ch}.rules += {json.dumps(r, ensure_ascii=False)}"})
            elif k == "word":
                w = d.get("word")
                pron = doc("cosy_pron.json")["data"]
                bad = _bad_py(d.get("py"), have)
                if not isinstance(w, str) or not w or bad:
                    errors.append(f"word {w}:{bad or 'word 空白'}")
                elif w in pron:
                    errors.append(f"word {w}:cosy_pron.json 已有此詞,不改既有")
                else:
                    pron[w] = d["py"]
                    added.append({"file": "pipeline\\cosy_pron.json", "entry": f"{w} -> {d['py']}"})
            elif k == "term":
                w = d.get("word")
                terms = doc("cosy_terms.json")["data"]
                if not isinstance(w, str) or not w:
                    errors.append("term:word 空白")
                elif d.get("action") == "direct":
                    if w in (terms.get("_direct") or []):
                        errors.append(f"term {w}:_direct 已有")
                    else:
                        terms.setdefault("_direct", []).append(w)
                        terms.setdefault("_log", {}).setdefault(w, _note(tag, d))
                        added.append({"file": "pipeline\\cosy_terms.json", "entry": f"_direct += {w}"})
                elif not isinstance(d.get("py"), str) or not d["py"].strip():
                    errors.append(f"term {w}:py(寫法)空白")
                elif w in terms:
                    errors.append(f"term {w}:cosy_terms.json 已有此詞,不改既有")
                else:
                    terms[w] = d["py"]
                    terms.setdefault("_log", {}).setdefault(w, _note(tag, d))
                    added.append({"file": "pipeline\\cosy_terms.json", "entry": f"{w} -> {d['py']}"})
            elif k == "sub_word":
                w = (d.get("word") or "").strip()
                r = doc("sub_words.txt")
                if not w or re.search(r"\s", w):
                    errors.append(f"sub_word {w!r}:要單一詞、不含空白")
                elif w in r["text"].split():
                    errors.append(f"sub_word {w}:sub_words.txt 已有")
                else:
                    t = r["text"]
                    eol = CRLF if CRLF in t else NL
                    r["text"] = t + ("" if t.endswith(NL) or not t else eol) + w + eol
                    added.append({"file": "pipeline\\sub_words.txt", "entry": w})
            elif k == "backlog":
                if not d.get("word") or not d.get("context"):
                    errors.append("backlog:word/context 空白")
                else:
                    backlog.append({x: d.get(x) or "" for x in ("word", "context", "action", "reason")})
            else:
                errors.append(f"不認得的 kind:{k}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{d.get('kind')} {d.get('char') or d.get('word')}:{type(e).__name__} {e}")
    _write_all(DA, files, added, errors)
    if tag and (added or backlog):
        f = P.PROJECTS / tag / "pron_apply.json"
        cur = _read(f) or {"added": [], "backlog": []}
        cur.setdefault("added", []).extend(added)
        cur.setdefault("backlog", []).extend(backlog)
        _atomic(f, json.dumps(cur, ensure_ascii=False, indent=1))
    return {"added": added, "errors": errors, "backlog": backlog}


def _write_all(DA, files, added, errors):
    """逐檔原子寫;寫後重讀自驗(json 用 _only_added、sub_words 驗原文是前綴),不符就還原該檔並把該檔的 added 挪進 errors。"""
    for name, r in files.items():
        f = _path(name)
        new = _dump(r["data"], r["nl"]) if name.endswith(".json") else r["text"]
        if new == r["old"]:
            continue
        _atomic(f, new)
        try:
            back = _rd(f)
            ok = DA._only_added(json.loads(r["old"]), json.loads(back)) if name.endswith(".json") else back.startswith(r["old"])
        except (OSError, ValueError):
            ok = False
        if not ok:
            _atomic(f, r["old"])
            lost = [a for a in added if a["file"].endswith(name)]
            for a in lost:
                added.remove(a)
            errors.append(f"{name} 寫後自驗不是「只新增」,已還原({len(lost)} 條作廢)")


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def record_seen(tag, items):
    """pron-review 本輪看過的條目(已決/可疑,不含未決)記進 decided 帳本:{kind, char, word, status}。回傳新增筆數。"""
    f = P.PROJECTS / tag / "pron_apply.json"
    cur = _read(f) or {"added": [], "backlog": []}
    have = {(x.get("kind"), x.get("char") or "", x.get("word") or "") for x in cur.get("decided") or []}
    new = []
    for i in items or []:
        if i.get("status") not in ("已決", "可疑") or i.get("kind") not in ("poly", "seam", "english"):
            continue
        k = (i["kind"], i.get("char") or "", i.get("word") or "")
        if k not in have:
            have.add(k)
            new.append({"kind": k[0], "char": k[1], "word": k[2], "status": i["status"]})
    if new:
        cur.setdefault("decided", []).extend(new)
        _atomic(f, json.dumps(cur, ensure_ascii=False, indent=1))
    return len(new)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    tag_ = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(apply(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), tag_), ensure_ascii=False, indent=1))
