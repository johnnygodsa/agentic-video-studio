#!/usr/bin/env python3
r"""文案凍結:聽審通過後鎖住「配音文本」(<片名>\script.txt 每句送配音的文字序列的 sha256 = narration_sha),
之後非聽審的 make_version 若發現配音文本被改就中止。畫面欄位(標籤/hl/kit/anim/fx/pause/note/f…)凍結後可自由改;
真正的守門仍是 build --frozen 的配音快取鍵比對。舊凍結(freeze.json 沒有 narration_sha)仍比整檔 sha256。

python -X utf8 pipeline/freeze.py <tag> [--reason "..."]          首次凍結(已凍結會拒絕,要改用 --refreeze)
python -X utf8 pipeline/freeze.py <tag> --refreeze --reason "..."  覆寫(reason 必填:使用者同意的理由)
python -X utf8 pipeline/freeze.py <tag> --status
別名放行閘門(taste T27,2026-10-31):凍結時比對 cosy_terms.json 的 _asr_alias 與基準(上次凍結存的快照 freeze.json["asr_alias"];沒有就用 git HEAD 版)
  新增、且該詞出現在本片旁白 -> 擋下(辨識錯的寫法被加進別名,可能是為了讓某句過品管);確認是正當登錄(新詞音譯、整批登記)才加
  --alias-ok "<理由>" 放行,理由記進 freeze.json["alias_ok"]。
寫 projects\<tag>\freeze.json {narration_sha, sha256(整檔,只作紀錄), frozen_at, reason},並 board.set_stage(tag, "已凍結", force=True)  # 凍結門檻(review_problems)剛過,不被 gate_c 的 listen/ear_e4 項卡住。
make_version 用 check(tag) 取得中止訊息(None = 可繼續)。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402


def script_path(tag):
    return P.REPO / tag / "script.txt"  # 同 make_version 的片名目錄解析


def freeze_path(tag):
    return P.PROJECTS / tag / "freeze.json"


def review_path(tag):
    return P.build_dir(tag) / "tts_review.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def narration_lines(tag):
    """script.txt -> 每句送配音的文字清單(依句序)。與 script_txt2json.main + build.tts_all 同源:
    ln["say"](行尾欄位指定)優先,否則 text 套用 @say 替換後的字串。解析失敗 raise ValueError。"""
    import script_txt2json as T2J
    try:
        _, says, sections, _, defs, _ = T2J.parse(script_path(tag).read_text(encoding="utf-8-sig"))
        out = []
        for sec in sections:
            for ln in T2J.build_lines(sec["rows"], defs):
                say = ln["text"]
                for k, v in says:
                    say = say.replace(k, v)
                out.append(ln.get("say") or say)
    except SystemExit as e:  # txt2json 的錯誤用 sys.exit(訊息)
        raise ValueError(str(e.code)) from None
    return out


def narration_sha(tag):
    """配音文本 hash:每句送配音的文字依句序以 \n 接起來的 sha256;只改畫面欄位不變,改字或 @say 就變。"""
    return hashlib.sha256("\n".join(narration_lines(tag)).encode("utf-8")).hexdigest()


def text_same(tag, rec, old_key="sha256"):
    """配音文本是否與紀錄(freeze.json / tts_review.json)相符的唯一判斷:rec 有 narration_sha 就比它(畫面欄位可改);
    沒有(舊紀錄)才比整檔 sha256(rec[old_key])。script.txt 不存在 = False;解析失敗 raise ValueError。"""
    sp = script_path(tag)
    if not sp.exists():
        return False
    if rec.get("narration_sha"):
        return narration_sha(tag) == rec["narration_sha"]
    return sha256(sp) == rec.get(old_key)


def tts_keys_sha(tag, engine=None):
    """tts_dir(tag, engine) 內全部 *.key 的內容排序後 sha256(沒有任何 key 檔 = 空字串的 sha256)。"""
    d = P.tts_dir(tag, engine)
    keys = sorted(k.read_text(encoding="utf-8", errors="replace") for k in d.glob("*.key")) if d.is_dir() else []
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


class FreezeRefused(Exception):
    """凍結門檻未過;args[0] = 原因清單。"""


def load_review(tag):
    p = review_path(tag)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def review_problems(tag):
    """凍結門檻:回傳未過原因清單(空 = 可凍結)。"""
    try:
        rv = load_review(tag)
    except (OSError, ValueError) as e:
        return [f"tts_review.json 讀不了({type(e).__name__}: {e})"]
    if rv is None:
        return [f"找不到 {review_path(tag)};先跑 make_version --tts-review"]
    out = []
    sp = script_path(tag)
    try:
        bad = not text_same(tag, rv, "script_sha256")
    except ValueError as e:
        bad = True
        out.append(f"script.txt 解析失敗:{e}")
    if bad:
        out.append("配音文本與 tts_review.json 不符(review 後配音文字又改過;重跑 make_version --tts-review)")
    for key, label in (("failed", "品管未過"), ("no_qc", "沒有品管紀錄"), ("timing_errors", "時長預檢錯誤")):
        v = rv.get(key) or []
        if v:
            names = [str(x.get("idx", x)) if isinstance(x, dict) else str(x) for x in v]
            out.append(f"{label} {len(v)} 項:" + "、".join(names[:12]) + ("…" if len(names) > 12 else ""))
    return out


def load(tag):
    p = freeze_path(tag)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def check(tag):
    """已凍結且配音文本不符 -> 回傳中止訊息;未凍結或相符 -> None。
    freeze.json 有 narration_sha 就比它(畫面欄位可改);沒有(舊凍結)才比整檔 sha256。"""
    fz = load(tag)
    if not fz:
        return None
    try:
        if text_same(tag, fz):
            return None
    except ValueError:
        pass  # 解析失敗 -> 視為已改
    day = (fz.get("frozen_at") or "")[:10]
    return (f"配音文本已改(凍結於 {day});改稿需使用者同意,同意後 "
            f"`python -X utf8 pipeline/freeze.py {tag} --refreeze --reason \"<使用者同意的理由>\"`")


def sp_same(tag, fz):
    sp = script_path(tag)
    return sp.exists() and sha256(sp) == fz.get("sha256")


TERMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cosy_terms.json")


def alias_table(path=TERMS_FILE):
    """cosy_terms.json 的 _asr_alias -> {詞: [別名]};讀不了回 {}。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("_asr_alias") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def alias_base(tag):
    """別名基準:上次凍結存的快照(freeze.json["asr_alias"]);沒有就取 git HEAD 版 cosy_terms.json;都沒有 None(不查)。"""
    fz = load(tag)
    if fz and isinstance(fz.get("asr_alias"), dict):
        return fz["asr_alias"]
    try:
        out = subprocess.run(["git", "show", "HEAD:pipeline/cosy_terms.json"], cwd=P.REPO, capture_output=True, timeout=20)
        return (json.loads(out.stdout.decode("utf-8")).get("_asr_alias") or {}) if out.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def alias_added(cur, base):
    """目前的 _asr_alias 相對基準新增的 {詞: [新別名]}。"""
    return {k: [a for a in v if a not in set(base.get(k) or [])] for k, v in cur.items() if [a for a in v if a not in set(base.get(k) or [])]}


def alias_problems(tag, cur=None, base=None, text=None):
    """T27:新增別名且該詞出現在本片旁白 -> 原因清單(空 = 放行)。cur/base/text 可注入(測試用)。"""
    cur = alias_table() if cur is None else cur
    base = alias_base(tag) if base is None else base
    if base is None:
        return []
    added = alias_added(cur, base)
    if not added:
        return []
    if text is None:
        try:
            text = chr(10).join(narration_lines(tag))
        except (ValueError, OSError):
            text = ""
    return [f"_asr_alias 新增別名且本片用到「{k}」:{'、'.join(v)}(辨識錯的寫法被放行品管?確認正當後 --alias-ok \"<理由>\")"
            for k, v in added.items() if re.search(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", text, re.I)]


def freeze(tag, reason, force=False, alias_ok=None):
    """凍結。門檻未過且非 force -> raise FreezeRefused(原因清單);force 時 reason 必填並記入 freeze.json。
    alias_ok = 放行 _asr_alias 新增別名的理由(沒給而本片有新增別名 -> 擋;force 時略過並記錄)。"""
    sp = script_path(tag)
    if not sp.exists():
        raise FileNotFoundError(f"找不到 {sp}")
    problems = review_problems(tag)
    alias = [] if (alias_ok or "").strip() or force else alias_problems(tag)
    if (problems or alias) and not force:
        raise FreezeRefused(problems + alias)
    if force and not (reason or "").strip():
        raise ValueError("--force 必須給 --reason")
    try:
        rv = load_review(tag) or {}
    except (OSError, ValueError):
        rv = {}
    engine = rv.get("engine")
    rec = dict(narration_sha=narration_sha(tag), sha256=sha256(sp), frozen_at=datetime.now().isoformat(timespec="seconds"), reason=reason,
               tts_keys_sha=tts_keys_sha(tag, engine), engine=engine, review_at=rv.get("at"), asr_alias=alias_table())
    if (alias_ok or "").strip():
        rec["alias_ok"] = alias_ok.strip()
    if problems:
        rec.update(forced=True, forced_problems=problems)
    elif rv.get("tts_keys_sha") and rv["tts_keys_sha"] != rec["tts_keys_sha"]:
        print("警告:review 之後配音快取鍵又變過(tts_keys_sha 與 tts_review.json 不同);建議重跑 --tts-review")
    fp = freeze_path(tag)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="文案凍結(見檔頭)")
    ap.add_argument("tag")
    ap.add_argument("--refreeze", action="store_true", help="覆寫既有凍結(--reason 必填)")
    ap.add_argument("--reason", help="凍結理由;--refreeze 時必填(使用者同意改稿的理由)")
    ap.add_argument("--force", action="store_true", help="跳過 tts_review.json 門檻(--reason 必填,記入 freeze.json)")
    ap.add_argument("--alias-ok", metavar="理由", help="放行 cosy_terms _asr_alias 新增別名(T27);理由記進 freeze.json")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    tag = a.tag
    fz = load(tag)
    if a.status:
        if not fz:
            print(f"{tag}:未凍結")
            return
        msg = check(tag)
        if "tts_keys_sha" not in fz:
            kmsg = "配音 keys 無記錄(舊凍結)"
        else:
            kmsg = "配音 keys 相符" if tts_keys_sha(tag, fz.get("engine")) == fz["tts_keys_sha"] else "配音 keys 不符(快取鍵已變)"
        try:
            ncur = narration_sha(tag)
            nmsg = ("narration_sha " + ("相符" if ncur == fz["narration_sha"] else "不符(配音文本已改)")) if fz.get("narration_sha") else "narration_sha 無記錄(舊凍結,比整檔)"
        except (ValueError, OSError) as e:
            nmsg = f"narration_sha 算不出({e})"
        fsha = "整檔 sha256 " + ("相符" if sp_same(tag, fz) else "不符(畫面或文字有改,僅紀錄)")
        print(f"{tag}:凍結於 {fz.get('frozen_at')}|理由 {fz.get('reason')}|" + ("配音文本已改(不符)" if msg else "配音文本相符")
              + f"|{nmsg}|{fsha}"
              + f"|{kmsg}|engine {fz.get('engine')}|review {fz.get('review_at')}" + ("|強制凍結(跳過門檻)" if fz.get("forced") else ""))
        return
    if fz and not a.refreeze:
        sys.exit(f"{tag} 已凍結於 {fz.get('frozen_at')};要覆寫用 --refreeze --reason \"<使用者同意的理由>\"")
    if a.refreeze and not (a.reason or "").strip():
        sys.exit("--refreeze 必須給 --reason(使用者同意改稿的理由)")
    if a.force and not (a.reason or "").strip():
        sys.exit("--force 必須給 --reason(跳過凍結門檻的理由)")
    try:
        rec = freeze(tag, (a.reason or "聽審通過").strip(), force=a.force, alias_ok=a.alias_ok)
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    except FreezeRefused as e:
        sys.exit(f"{tag} 不能凍結:\n  - " + "\n  - ".join(e.args[0])
                 + "\n(清掉後重跑 make_version --tts-review;使用者明示要跳過才加 --force --reason \"…\")")
    if rec.get("forced"):
        print(f"警告:--force 跳過門檻:{'; '.join(rec['forced_problems'])}")
    try:
        import board
        board.set_stage(tag, "已凍結")
    except Exception as e:  # noqa: BLE001  進度板失敗不影響凍結
        print(f"警告:進度板未更新({type(e).__name__}: {e})")
    print(f"{tag}:{'重新' if a.refreeze else ''}凍結 narration_sha {rec['narration_sha'][:12]}… -> {freeze_path(tag)}")


if __name__ == "__main__":
    main()
