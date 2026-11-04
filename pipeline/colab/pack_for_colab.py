#!/usr/bin/env python3
r"""Colab 配音打包與匯回(channel/_archive/plans/PLAN_COLAB配音_2026-10-28.md T1);不需顯示卡、不載模型,只用標準函式庫與既有 pipeline 模組。

python -X utf8 pipeline\colab\pack_for_colab.py <tag> [--out tmp\colab\colab_<tag>.zip] [--img-prefix <前綴>_]
    打包 C 段「凍結前」的配音所需檔案給 Colab。擋項(任一不過就不打包、印原因、結束碼 2):
      projects\<tag>\freeze.json 存在(凍結後禁新合成,不因跑在雲端而放寬);
      script_txt2json / script_lint 有擋項;tts_terms --engine cosy3 有未登錄英文詞(同 make_version 配音前的步驟)。
    zip 內路徑相對 repo 根(解壓到 /content/CV 即可設 CLAUDE_VIDEO_ROOT):
      pipeline\**(排除 tests\ __pycache__\ tts_bakeoff\ tools\sync_kc*)、<tag>\script.txt、<tag>\script.json(本機先轉好)、
      cosy_voice\ref_b.wav + ref_b.txt、build\<tag>\tts_cosy3\**(現有快取;排除 _cosy_work* _jobs*.json *.log _resume*)、空檔 .video_root。
    不放:tts_env_* tts_models raw images anim bgm、其他 tag、channel\board.json(build --tts-only 路徑不讀它)。
python -X utf8 pipeline\colab\pack_for_colab.py --import <tts_<tag>.zip>
    只收 build/<tag>/tts_cosy3/**(擋絕對路徑與 ..)寫回本機 build\<tag>\tts_cosy3\。合併規則(以「配音單位」= 同主檔名的
    .wav/.key/.qc.json/.trim.* 為單位):本機與 zip 的 .key 音檔鍵不同(文字已改,本機是舊的)-> 一律用 zip 的;
    鍵相同時:zip 內 .qc.json passed=true -> 覆蓋本機整組;passed 非 true -> 本機已 passed=true 就保留本機,
    否則寫入 zip 的(留最佳者,tts_qc.json 才列得出未過原因)。底線開頭的工作檔(_cosy_work* _jobs* _resume* _qc_base*)與 *.log 不收。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import freeze as FZ  # noqa: E402
import paths as P  # noqa: E402
import tts_key as TK  # noqa: E402

PACK_EXIT = 2
PIPE_EXCLUDE_DIRS = {"tests", "__pycache__", "tts_bakeoff"}
CACHE_ENGINE = "cosy3"


def log(msg):
    print(msg, flush=True)


# ---------- 打包 ----------

def _py():
    """檢查腳本用的 python:優先配音環境(script_lint 等可能要 jieba),沒有就用目前的。"""
    return str(P.TTS_ENV) if Path(P.TTS_ENV).exists() else sys.executable


def gate_cmds(tag, img_prefix):
    """打包前擋項指令(名稱, 指令)。與 make_version 配音前三步同呼叫方式。"""
    py, pipe = _py(), P.REPO / "pipeline"
    return [
        ("txt2json", [py, "-X", "utf8", str(pipe / "script_txt2json.py"), f"{tag}/script.txt", f"{tag}/script.json",
                      "--img-prefix", img_prefix]),
        ("script_lint", [py, "-X", "utf8", str(pipe / "script_lint.py"), tag]),
        ("tts_terms", [py, "-X", "utf8", str(pipe / "tts_terms.py"), tag, "--engine", CACHE_ENGINE]),
    ]


def run_gates(tag, img_prefix):
    """跑擋項;回傳問題清單(空 = 全過)。"""
    problems = []
    for name, cmd in gate_cmds(tag, img_prefix):
        r = subprocess.run(cmd, cwd=P.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if r.returncode:
            tail = [l.strip() for l in ((r.stdout or "") + (r.stderr or "")).splitlines() if l.strip()][-5:]
            problems.append(f"{name} 失敗(結束碼 {r.returncode}):" + " / ".join(tail))
    return problems


def pipeline_files(repo):
    """pipeline\\** 的 (檔案路徑, zip 內路徑);排除 tests\\ __pycache__\\ tts_bakeoff\\ tools\\sync_kc* 與 .pyc。"""
    base = repo / "pipeline"
    for f in sorted(base.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(repo).as_posix()
        parts = f.relative_to(base).parts
        if PIPE_EXCLUDE_DIRS & set(parts[:-1]) or f.suffix == ".pyc":
            continue
        if parts[0] == "tools" and f.name.startswith("sync_kc"):
            continue
        yield f, rel


def _cache_skip(name):
    return name.startswith(("_cosy_work", "_resume", "_jobs")) or name.endswith(".log")


def cache_files(tag):
    """build\\<tag>\\tts_cosy3\\** 現有快取(含 sub\\ 子目錄);排除工作檔。"""
    d = P.tts_dir(tag, CACHE_ENGINE)
    if not d.is_dir():
        return
    for f in sorted(d.rglob("*")):
        rel_parts = f.relative_to(d).parts
        if f.is_file() and not any(_cache_skip(p) for p in rel_parts):
            yield f, f"build/{tag}/{d.name}/" + "/".join(rel_parts)


def collect(tag, cache=True):
    """回傳 [(來源檔, zip 內路徑)] 與警告清單;缺必要檔(script / 參考音)丟 FileNotFoundError。"""
    repo, warns, items = P.REPO, [], []
    items += list(pipeline_files(repo))
    if not (repo / "pipeline" / "colab" / "colab_run.py").exists():
        warns.append("pipeline\\colab\\colab_run.py 尚不存在(T3 才做),zip 內沒有它,Colab 端還不能執行")
    for name in ("script.txt", "script.json"):
        f = repo / tag / name
        if not f.is_file():
            raise FileNotFoundError(f"找不到 {f}")
        items.append((f, f"{tag}/{name}"))
    ref = Path(P.COSY_REF)
    for f in (ref, ref.with_suffix(".txt")):
        if not f.is_file():
            raise FileNotFoundError(f"找不到參考音檔 {f}")
        items.append((f, f"cosy_voice/{f.name}"))
    wt = P.ROOT / "tts_models" / "hub" / "pengzhendong" / "wetext"   # CosyVoice 文字正規化(約 50 MB);Colab 連不到 modelscope.cn
    if (wt / "zh").is_dir():
        items += [(f, "tts_models/hub/pengzhendong/wetext/" + f.relative_to(wt).as_posix())
                  for f in sorted(wt.rglob("*")) if f.is_file()]
    else:
        warns.append(f"{wt} 不存在:Colab 端 CosyVoice 會沒有文字正規化,唸法可能跟本機不同")
    # --no-cache:Drive 上已有 tts_<tag>.zip(第 1b 格接上),zip 才小於瀏覽器上傳上限
    cached = list(cache_files(tag)) if cache else []
    if cache and not cached:
        warns.append(f"build\\{tag}\\tts_cosy3 沒有現有快取(Colab 會整批重錄)")
    items += cached
    return items, warns


def refreeze_reason(tag, refreeze_ok=False):
    """已凍結時允許打包的理由(文字),沒有理由回 None。"""
    if refreeze_ok or os.environ.get("CV_REFREEZE_OK") == "1":
        return "--refreeze-ok"
    try:
        if FZ.check(tag):
            return "配音文本與凍結檔不符(文案已改)"
    except Exception:  # 解析失敗等:不放行
        return None
    return None


def pack(tag, out=None, img_prefix=None, gates=True, cache=True, refreeze_ok=False):
    """打包;回傳 (結束碼, zip 路徑或 None)。"""
    fz = FZ.freeze_path(tag)
    if fz.exists():
        why = refreeze_reason(tag, refreeze_ok)
        if not why:
            log(f"拒絕打包:{tag} 已凍結({fz})且配音文本未變。凍結後任何新合成一律中止,不因跑在雲端而放寬;"
                "改旁白後(文本與凍結檔不符)會自動放行,或加 --refreeze-ok;錄完需 make_version --tts-review 全命中再 freeze.py --refreeze。")
            return PACK_EXIT, None
        log(f"注意:{tag} 已凍結,因「{why}」放行打包;只應重錄鍵不符的句子,錄完照 --tts-review 全命中、新合成 0 再 --refreeze。")
    if not (P.REPO / tag / "script.txt").is_file():
        log(f"拒絕打包:找不到 {P.REPO / tag / 'script.txt'}")
        return PACK_EXIT, None
    if gates:
        problems = run_gates(tag, img_prefix or f"{tag}_")
        if problems:
            log("拒絕打包:配音前檢查有擋項,請先在本機改文案(Colab 不處理文案問題):")
            for p in problems:
                log("  - " + p)
            return PACK_EXIT, None
    try:
        items, warns = collect(tag, cache)
    except FileNotFoundError as e:
        log(f"拒絕打包:{e}")
        return PACK_EXIT, None
    out = Path(out) if out else P.TMP / "colab" / f"colab_{tag}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in items:
            zf.write(src, arc)
        zf.writestr(P.ROOT_MARKER, b"")
    os.replace(part, out)
    for w in warns:
        log("警告:" + w)
    log(f"已打包 {len(items) + 1} 個檔、{out.stat().st_size / 1048576:.1f} MB -> {out}")
    return 0, out


# ---------- 匯回 ----------

def _unsafe(name):
    n = name.replace("\\", "/")
    return n.startswith("/") or re.match(r"^[A-Za-z]:", n) is not None or ".." in n.split("/")


def _stem(name):
    return name.split(".", 1)[0]


def _passed(raw):
    try:
        return json.loads(raw).get("passed") is True
    except (ValueError, AttributeError):
        return False


def _key_audio(raw):
    try:
        return TK.audio_part(raw.decode("utf-8", errors="replace").strip())
    except (AttributeError, ValueError):
        return ""


def _stale_local(zf, files, d, stem):
    """本機該單位的 .key 音檔鍵與 zip 的不同 = 本機是舊文字的檔,應被 zip 取代。"""
    zk = next((n for n, f in files if f == stem + ".key"), None)
    lk = d / (stem + ".key")
    if zk is None or not lk.is_file():
        return False
    return _key_audio(zf.read(zk)) != _key_audio(lk.read_bytes())


def _unit_skip(name):
    return name.startswith("_") or name.endswith(".log")


def import_zip(zip_path):
    """匯回 Colab 配音結果;回傳 dict(tag, written, kept, failed)。zip 不合法丟 ValueError(尚未寫入任何檔)。"""
    zp = Path(zip_path)
    if not zp.is_file():
        raise ValueError(f"找不到 zip: {zp}")
    with zipfile.ZipFile(zp) as zf:
        names = [i.filename for i in zf.infolist() if not i.is_dir()]
        bad = [n for n in names if _unsafe(n)]
        if bad:
            raise ValueError(f"zip 內有絕對路徑或 .. 的項目,整包拒收:{bad[:5]}")
        entries, tags = {}, set()
        for n in names:
            parts = n.replace("\\", "/").split("/")
            if len(parts) < 4 or parts[0] != "build" or parts[2] != P.TTS_SUBDIR[CACHE_ENGINE]:
                continue
            rel = parts[3:]
            if any(_unit_skip(p) for p in rel[:-1]) or _unit_skip(rel[-1]):
                continue
            tags.add(parts[1])
            entries[n] = (parts[1], rel)
        if not entries:
            raise ValueError(f"zip 內沒有 build/<tag>/{P.TTS_SUBDIR[CACHE_ENGINE]}/ 的配音檔")
        if len(tags) != 1:
            raise ValueError(f"zip 內有多個 tag {sorted(tags)},一次只匯一個")
        tag = tags.pop()
        log(f"匯回 tag: {tag}")
        dest = P.tts_dir(tag, CACHE_ENGINE)
        groups = {}   # (子目錄, 主檔名) -> [(zip 項目, 檔名)]
        for n, (_, rel) in entries.items():
            groups.setdefault((tuple(rel[:-1]), _stem(rel[-1])), []).append((n, rel[-1]))
        written = kept = 0
        failed = []
        for (sub, stem), files in sorted(groups.items()):
            d = dest.joinpath(*sub)
            label = "/".join((*sub, stem))
            zq = next((n for n, f in files if f == stem + ".qc.json"), None)
            z_ok = zq is not None and _passed(zf.read(zq))
            lq = d / (stem + ".qc.json")
            l_ok = lq.is_file() and _passed(lq.read_bytes())
            l_has = (d / (stem + ".wav")).is_file()
            stale = _stale_local(zf, files, d, stem)
            if z_ok or stale or (not l_ok and (zq is not None or not l_has)):
                d.mkdir(parents=True, exist_ok=True)
                keep_names = {f for _, f in files}
                for old in d.glob(glob_escape(stem) + ".*"):     # 換掉整組:本機同主檔名但 zip 沒有的舊檔(例如舊 .trim.wav)一併清掉
                    if old.is_file() and _stem(old.name) == stem and old.name not in keep_names:
                        old.unlink()
                for n, f in files:
                    (d / f).write_bytes(zf.read(n))
                written += 1
                if not z_ok:     # 以實際寫入的 zip 版本為準
                    failed.append(label)
            else:
                kept += 1
                if not l_ok:
                    failed.append(label)
    failed.sort(key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)])
    log(f"寫入 {written}、保留本機 {kept}、未過 {len(failed)} 句:{failed}")
    return dict(tag=tag, written=written, kept=kept, failed=failed)


def glob_escape(s):
    return re.sub(r"([\[\]*?])", r"[\1]", s)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Colab 配音打包與匯回(channel/_archive/plans/PLAN_COLAB配音_2026-10-28.md T1)")
    ap.add_argument("tag", nargs="?", help="要打包的片名 tag(與 --import 擇一)")
    ap.add_argument("--out", help=r"zip 輸出路徑,預設 tmp\colab\colab_<tag>.zip")
    ap.add_argument("--img-prefix", help="script_txt2json 的圖片前綴,預設 <tag>_(只影響 script.json 的圖名,不影響配音)")
    ap.add_argument("--no-cache", action="store_true", help="不打包 build\\<tag>\\tts_cosy3 現有快取(Drive 上已有 tts_<tag>.zip 時用)")
    ap.add_argument("--refreeze-ok", action="store_true", help="已凍結的片改旁白後允許打包(只重錄鍵不符的句子)")
    ap.add_argument("--import", dest="import_zip", metavar="ZIP", help=r"匯回 Colab 做好的 tts_<tag>.zip 到 build\<tag>\tts_cosy3\\")
    a = ap.parse_args(argv)
    if bool(a.tag) == bool(a.import_zip):
        ap.error("請給 <tag>(打包)或 --import <zip>(匯回),二選一")
    if a.import_zip:
        try:
            res = import_zip(a.import_zip)
        except ValueError as e:
            log(f"拒絕匯回:{e}")
            return PACK_EXIT
        t = res["tag"]
        log(f"下一步:python -X utf8 pipeline\\make_version.py --tag {t} --ver <ver> --tts-review --freeze"
            "(全部命中快取、0 新合成 -> 自動凍結)")
        if res["failed"]:
            log("未過的句子照 3_製作 §5「改寫重錄」處理(改 script.txt 後重新打包上傳)。")
        return 0
    return pack(a.tag, a.out, a.img_prefix, cache=not a.no_cache, refreeze_ok=a.refreeze_ok)[0]


if __name__ == "__main__":
    sys.exit(main())
