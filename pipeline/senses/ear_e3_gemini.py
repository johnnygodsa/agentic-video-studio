#!/usr/bin/env python3
r"""耳朵 E3:音訊模型審聽(Gemini API),逐句把配音 wav + 參考文字 + 期望讀音送去聽,回結構化診斷。
(PLAN_工作室v2_2026-10-31.md §6.3 E3;定位是「多一隻耳」,不是唯一閘門,人耳仍是最後一關。)

用法(用配音環境 python:tts_env_chattts\Scripts\python.exe -X utf8 pipeline\senses\ear_e3_gemini.py ...)
  單句   --wav <f> --text <t> [--expect '{"12":"zhe5"}']
  整片   --tag <tag> --ver <ver> [--lines 1-3,7] [--redo]     -> projects\<tag>\ear_e3_<ver>.json / .md(斷點續跑)
  真值   --truth channel\taste\ear\truth.json [--out f.json]  -> 壞例召回、好例誤報表
  共用   --model gemini-2.5-pro  --fallback-model gemini-2.5-flash(空字串 = 不備援)  --rpm 5  --mock  --no-expect
金鑰只從環境變數 GEMINI_API_KEY 讀(不進 git、不印出);--mock 不打 API、不需金鑰。

--expect 格式:{"位置":"拼音"}(位置 = 參考文字字元位置,從 0 起算)或 [{"pos":12,"char":"著","pinyin":"zhe5"}]。
--tag 模式沒給時,自動用 tts_g2p.expected(規則表/詞表指定的多音字讀音,不含 default 來源);載入失敗就略過。
音檔:每行 build\<tag>\<tts_dir>\NNN.line.wav(多子句行)否則 NNN.trim.wav,再退 NNN.wav;文字取 timeline_tts.json / timeline.json 的 lines。
真值檔格式(容錯,另一代理建):{"items":[...]} 或直接 list;每筆 {id, wav 或 tag+idx, text, label:"bad"|"good",
  expect?, defects?:[{char,pos,kind}]}(defects 也可叫 bad / issues;label 也可叫 verdict)。
  壞例命中 = 模型 issues(發音/停頓/清晰度/英文詞)有同 char、同 pos、或同 kind 之一;沒列 defects 的壞例 = 模型判不過或有 issue 即命中。
  好例誤報 = 模型 overall_pass=false(另列「任何 issue」的嚴格誤報率)。上線門檻:召回 ≥80%、誤報 ≤10%(PLAN §6.3)。

呼叫方式(官方文件,2026-10-31 查):
  - 端點 REST generateContent:POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent,
    標頭 x-goog-api-key;parts 放 inlineData{mimeType:"audio/wav",data:base64} 或 fileData{fileUri,mimeType};
    generationConfig.responseMimeType="application/json" 要 JSON;回傳 usageMetadata 記 token。
  - 音訊輸入:inline 整個請求上限 20 MB(含 prompt);大檔或要重用用 Files API(resumable 上傳、單檔 2 GB、專案 20 GB、
    保留 48 小時)。音訊 32 token/秒(1 分鐘 = 1920)。支援 wav/mp3/aiff/aac/ogg/flac 等。本程式 ≤30 秒 inline,超過走 Files API。
  - 官方範例現在以新的 Interactions API(/v1beta/interactions,模型例 gemini-3.8-flash)為主;generateContent 仍在
    API 參考中,本程式用它。要改 Interactions:input=[{type:"audio",data|uri,mime_type},{type:"text",text}]、response_format=schema。
  - 免費層:模型價格表 Free Tier 欄為「Free of charge」(含 gemini-2.5-pro / 2.5-flash;免費層資料會被用來改進產品);
    各模型 RPM/TPM/RPD 數字不在靜態文件,要到 AI Studio 的 rate-limit 頁看(依專案、午夜太平洋時間重置 RPD)。
    2.5 系列「僅限過去用過的使用者」仍可用、未棄用;2.0 Flash 已 shut down。付費 2.5 Pro:輸入 $1.25 / 輸出 $10 每百萬 token(<=200k)。
  - 網址:https://ai.google.dev/gemini-api/docs/audio 、/rate-limits 、/models 、/pricing 、/files 、https://ai.google.dev/api/generate-content
  - 沒用 google-genai SDK:pip --dry-run 顯示會把 tts_env_chattts 的 pydantic 2.11.9->2.14.2、typing_extensions 升級
    (gradio 5.46 等依賴會受影響;torch 不動),所以改用標準函式庫 urllib 直接打 REST,零新增依賴。
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import wave
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

BASE = "https://generativelanguage.googleapis.com"
DEFAULT_MODEL = "gemini-2.5-pro"
FALLBACK_MODEL = "gemini-2.5-flash"
INLINE_MAX_SEC = 30.0
KEY_ENV = "GEMINI_API_KEY"
PRON_KINDS = ("tone", "polyphone", "extra", "missing", "slur")
PAUSE_KINDS = ("runon", "too_long", "misplaced")
CLARITY_KINDS = ("robotic", "clipping", "noise")
RETRYABLE = (429, 500, 502, 503, 504)

_sleep = time.sleep      # 測試可換掉


# ------------------------------------------------------------ prompt
SCHEMA_TEXT = """{
 "pronunciation": {"score": 1到5的整數, "issues": [{"char": "讀錯的字", "pos": 該字在參考文字的位置(從0起算), "heard_as_pinyin": "你聽到的拼音(帶調號數字,如 zhu4)", "expected_pinyin": "應讀拼音", "kind": "tone|polyphone|extra|missing|slur"}]},
 "pauses": {"score": 1到5, "issues": [{"after_char": "停頓(或該停沒停)位置前一個字", "kind": "runon|too_long|misplaced"}]},
 "rate": {"score": 1到5},
 "clarity": {"score": 1到5, "issues": ["robotic|clipping|noise"]},
 "english_terms": [{"term": "參考文字中的英文詞或縮寫", "ok": true或false, "heard_as": "你實際聽到的唸法"}],
 "overall_pass": true或false,
 "rationale": "一句話總結"
}"""


def build_prompt(text, expect=None):
    exp = ""
    if expect:
        rows = "\n".join(f"- 第 {e['pos']} 字「{e.get('char') or ''}」應讀 {e['pinyin']}" for e in expect)
        exp = f"\n\n期望讀音(多音字位置 -> 拼音,位置從 0 起算):\n{rows}\n請特別確認這些位置實際唸成什麼。"
    return (
        "你是台灣國語(標準華語)配音的聽審員。下面這段音訊是 AI 合成的旁白,請只憑「聽到的聲音」審,"
        "不要照參考文字腦補;文字只是這句應該唸的內容。\n\n"
        f"參考文字:{text}\n"
        "(參考文字裡的阿拉伯數字、符號可以唸成合理的中文數字或英文,不算錯;一般輕聲、變調不算錯。)"
        f"{exp}\n\n"
        "請逐項判斷:\n"
        "1. 發音:有無讀錯聲調、多音字讀成另一個讀音、多唸(extra)、漏唸或吞字(missing)、連音含糊(slur)。\n"
        "2. 停頓:逗號、句號處該停有沒有停(逗號連讀 runon)、停太久(too_long)、停在不該停的地方(misplaced)。\n"
        "3. 語速:1 太慢或太快、5 自然。\n"
        "4. 清晰度:電音機械感(robotic)、爆音或截斷(clipping)、雜訊(noise)。\n"
        "5. 英文詞:參考文字中的英文詞或縮寫,逐一列出實際聽到的唸法;沒有英文詞就給空陣列。\n"
        "分數 1 到 5(5 最好)。沒有明顯問題 overall_pass 才給 true;有任何你有把握的錯讀、吞字、逗號連讀、電音就給 false。"
        "不確定的不要列為 issue。\n\n"
        f"只回一個 JSON 物件(不要 markdown、不要多餘文字),格式:\n{SCHEMA_TEXT}")


# ------------------------------------------------------------ 解析與正規化
def parse_json_text(raw):
    """模型回的文字 -> dict;容忍 ```json 圍欄與前後多餘文字。失敗丟 ValueError。"""
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I).strip()
    try:
        d = json.loads(s)
    except ValueError:
        a, b = s.find("{"), s.rfind("}")
        if a < 0 or b <= a:
            raise ValueError("回應不是 JSON")
        d = json.loads(s[a:b + 1])
    if not isinstance(d, dict):
        raise ValueError("回應 JSON 不是物件")
    return d


def _score(v):
    try:
        return max(1, min(5, int(round(float(v)))))
    except (TypeError, ValueError):
        return None


def _pos(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _lst(v):
    return v if isinstance(v, list) else []


def normalize(d):
    """補齊欄位、分數夾到 1–5、issues 統一成 dict;overall_pass 缺或非布林時由分數與 issues 推。"""
    p = d.get("pronunciation") if isinstance(d.get("pronunciation"), dict) else {}
    q = d.get("pauses") if isinstance(d.get("pauses"), dict) else {}
    r = d.get("rate") if isinstance(d.get("rate"), dict) else {}
    c = d.get("clarity") if isinstance(d.get("clarity"), dict) else {}
    pi = [dict(char=str(i.get("char") or ""), pos=_pos(i.get("pos")), heard_as_pinyin=str(i.get("heard_as_pinyin") or ""),
               expected_pinyin=str(i.get("expected_pinyin") or ""), kind=str(i.get("kind") or ""))
          for i in _lst(p.get("issues")) if isinstance(i, dict)]
    qi = [dict(after_char=str(i.get("after_char") or ""), kind=str(i.get("kind") or ""))
          for i in _lst(q.get("issues")) if isinstance(i, dict)]
    ci = [str(i.get("kind") if isinstance(i, dict) else i) for i in _lst(c.get("issues"))]
    et = [dict(term=str(i.get("term") or ""), ok=bool(i.get("ok", True)), heard_as=str(i.get("heard_as") or ""))
          for i in _lst(d.get("english_terms")) if isinstance(i, dict)]
    out = dict(pronunciation=dict(score=_score(p.get("score")), issues=pi),
               pauses=dict(score=_score(q.get("score")), issues=qi), rate=dict(score=_score(r.get("score"))),
               clarity=dict(score=_score(c.get("score")), issues=ci), english_terms=et,
               overall_pass=d.get("overall_pass"), rationale=str(d.get("rationale") or ""))
    if not isinstance(out["overall_pass"], bool):
        s = [x for x in (out["pronunciation"]["score"], out["pauses"]["score"]) if x is not None]
        out["overall_pass"] = bool(s) and min(s) >= 4 and not (pi or qi or ci)
    return out


def flat_issues(res):
    """各類 issues 攤平成 [{kind,char,pos,src}],給真值比對與計數用。"""
    out = [dict(kind=i["kind"], char=i["char"], pos=i["pos"], src="pron") for i in res["pronunciation"]["issues"]]
    out += [dict(kind=i["kind"], char=i["after_char"], pos=None, src="pause") for i in res["pauses"]["issues"]]
    out += [dict(kind=k, char="", pos=None, src="clarity") for k in res["clarity"]["issues"]]
    out += [dict(kind="english", char=e["term"], pos=None, src="english") for e in res["english_terms"] if not e["ok"]]
    return out


# ------------------------------------------------------------ 期望讀音
def norm_expect(exp, text=""):
    """--expect / 真值的期望讀音 -> [{pos,char,pinyin}](依位置排序);空或無法解析回 []。"""
    if isinstance(exp, str):
        exp = json.loads(exp) if exp.strip() else None
    out = []
    if isinstance(exp, dict):
        for k, v in exp.items():
            pos = _pos(k)
            if pos is not None and v:
                out.append(dict(pos=pos, char=text[pos] if 0 <= pos < len(text) else "", pinyin=str(v)))
    elif isinstance(exp, list):
        for e in exp:
            if isinstance(e, dict) and _pos(e.get("pos")) is not None and (e.get("pinyin") or e.get("expected_pinyin")):
                pos = _pos(e["pos"])
                out.append(dict(pos=pos, char=e.get("char") or (text[pos] if 0 <= pos < len(text) else ""),
                                pinyin=str(e.get("pinyin") or e.get("expected_pinyin"))))
    return sorted(out, key=lambda e: e["pos"])


def auto_expect(text):
    """tts_g2p.expected(規則/詞表指定的多音字讀音;default 來源略過);模組載入或執行失敗回 []。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import tts_g2p
        ex = tts_g2p.expected(text)
    except Exception:  # noqa: BLE001
        return []
    return [dict(pos=p, char=ch, pinyin=rd) for p, (ch, rd, src) in sorted(ex.items()) if src != "default"]


# ------------------------------------------------------------ HTTP / 速率 / 重試
class ApiError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status, self.body = status, body


def _http(url, data=None, headers=None, method="POST", timeout=180):
    """-> (status, headers(dict 小寫鍵), bytes);HTTP 錯誤丟 ApiError,連線錯誤丟 ApiError(0)。"""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode("utf-8", "replace")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(0, f"連線失敗:{type(e).__name__}") from None


class RateLimiter:
    def __init__(self, rpm):
        self.gap = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self.last = 0.0

    def wait(self):
        d = self.last + self.gap - time.monotonic()
        if d > 0:
            _sleep(d)
        self.last = time.monotonic()


def _retry_delay(err, attempt):
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', err.body or "")
    return min(90.0, float(m.group(1)) + 1) if m else 2.0 * (2 ** attempt)


def with_retry(fn, tries=3):
    for a in range(tries):
        try:
            return fn()
        except ApiError as e:
            if e.status not in RETRYABLE and e.status != 0 or a == tries - 1:
                raise
            _sleep(_retry_delay(e, a))


def api_key():
    k = os.environ.get(KEY_ENV, "").strip()
    if not k:
        sys.exit(f"沒有環境變數 {KEY_ENV}(要真的呼叫 API 才需要;測試請加 --mock)")
    return k


def wav_seconds(p):
    try:
        with wave.open(str(p), "rb") as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError, OSError):
        return os.path.getsize(p) / 32000.0     # 非 wav:粗估


def mime_of(p):
    return {".wav": "audio/wav", ".mp3": "audio/mp3", ".flac": "audio/flac", ".ogg": "audio/ogg",
            ".m4a": "audio/m4a", ".aac": "audio/aac"}.get(Path(p).suffix.lower(), "audio/wav")


def upload_file(path, key):
    """Files API resumable 上傳 -> (file name, uri, mimeType);等到 ACTIVE。"""
    data, mime = Path(path).read_bytes(), mime_of(path)
    _, h, _ = _http(f"{BASE}/upload/v1beta/files", json.dumps({"file": {"display_name": Path(path).name}}).encode(),
                    {"x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                     "X-Goog-Upload-Header-Content-Length": str(len(data)), "X-Goog-Upload-Header-Content-Type": mime,
                     "Content-Type": "application/json"})
    _, _, body = _http(h["x-goog-upload-url"], data, {"Content-Length": str(len(data)), "X-Goog-Upload-Offset": "0",
                                                      "X-Goog-Upload-Command": "upload, finalize"})
    f = json.loads(body)["file"]
    for _ in range(15):
        if f.get("state", "ACTIVE") == "ACTIVE":
            break
        _sleep(2)
        f = json.loads(_http(f"{BASE}/v1beta/{f['name']}", headers={"x-goog-api-key": key}, method="GET")[2])
    return f["name"], f["uri"], f.get("mimeType", mime)


def delete_file(name, key):
    try:
        _http(f"{BASE}/v1beta/{name}", headers={"x-goog-api-key": key}, method="DELETE", timeout=30)
    except ApiError:
        pass


def _generate(model, wav, prompt, key):
    """打一次 generateContent -> (回應文字, usage dict)。"""
    fname = None
    if wav_seconds(wav) <= INLINE_MAX_SEC:
        audio = {"inlineData": {"mimeType": mime_of(wav), "data": base64.b64encode(Path(wav).read_bytes()).decode()}}
    else:
        fname, uri, mime = upload_file(wav, key)
        audio = {"fileData": {"fileUri": uri, "mimeType": mime}}
    body = {"contents": [{"role": "user", "parts": [audio, {"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 8192}}
    try:
        _, _, raw = _http(f"{BASE}/v1beta/models/{model}:generateContent", json.dumps(body).encode(),
                          {"x-goog-api-key": key, "Content-Type": "application/json"})
    finally:
        if fname:
            delete_file(fname, key)
    d = json.loads(raw)
    parts = ((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    u = d.get("usageMetadata") or {}
    usage = dict(prompt=u.get("promptTokenCount", 0), output=u.get("candidatesTokenCount", 0),
                 thoughts=u.get("thoughtsTokenCount", 0), total=u.get("totalTokenCount", 0))
    if not text:
        raise ApiError(200, "空回應:" + str((d.get("promptFeedback") or d.get("candidates") or ""))[:200])
    return text, usage


def mock_text(wav, text):
    """--mock 的固定回應(不打 API)。"""
    return json.dumps(dict(
        pronunciation=dict(score=5, issues=[]), pauses=dict(score=5, issues=[]), rate=dict(score=5),
        clarity=dict(score=5, issues=[]), english_terms=[], overall_pass=True, rationale="mock:固定回應,未實際審聽"),
        ensure_ascii=False)


def call_model(wav, text, expect, args, limiter=None):
    """一句的審聽 -> dict(result 正規化後, usage, model, mock);主模型重試用盡才換備援;全失敗丟 ApiError/ValueError。"""
    prompt = build_prompt(text, expect)
    if args.mock:
        sec = wav_seconds(wav)
        return dict(result=normalize(parse_json_text(mock_text(wav, text))), model="mock", mock=True,
                    usage=dict(prompt=int(sec * 32 + len(prompt) // 2), output=120, thoughts=0, total=int(sec * 32 + len(prompt) // 2) + 120))
    key = api_key()
    models = [args.model] + ([args.fallback_model] if args.fallback_model and args.fallback_model != args.model else [])
    last = None
    for m in models:
        def once():
            if limiter:
                limiter.wait()
            return _generate(m, wav, prompt, key)
        try:
            raw, usage = with_retry(once)
            return dict(result=normalize(parse_json_text(raw)), model=m, mock=False, usage=usage)
        except (ApiError, ValueError) as e:
            last = e
    raise last


# ------------------------------------------------------------ 整片
def parse_lines(spec):
    """'1-3,7' -> {1,2,3,7};None -> None(全部)。"""
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def line_wav(tag, idx):
    d = paths.tts_dir(tag)
    for suf in (".line.wav", ".trim.wav", ".wav"):
        p = d / f"{idx:03d}{suf}"
        if p.exists():
            return p
    return None


def tag_lines(tag):
    """[(idx, text)];timeline_tts.json 優先,退 timeline.json。"""
    for n in ("timeline_tts.json", "timeline.json"):
        f = paths.build_dir(tag) / n
        if f.exists():
            return [(int(ln["idx"]), ln["text"]) for ln in json.loads(f.read_text(encoding="utf-8")).get("lines", [])]
    sys.exit(f"找不到 {paths.build_dir(tag)}\\timeline_tts.json")


def sha1_of(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def run_tag(args, call=None):
    """整片逐句審聽,每句做完就寫檔(斷點續跑:已有同音檔同模式的結果跳過,--redo 強制重審)。回傳 out json 路徑。"""
    call = call or call_model
    tag, ver = args.tag, args.ver
    out = paths.PROJECTS / tag / f"ear_e3_{ver}.json"
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    data.setdefault("meta", {})
    data["meta"].update(tag=tag, ver=ver, model=args.model)
    res = data.setdefault("results", {})
    want, limiter = parse_lines(args.lines), RateLimiter(0 if args.mock else args.rpm)
    todo, skipped = 0, 0
    for idx, text in tag_lines(tag):
        if want is not None and idx not in want:
            continue
        wav = line_wav(tag, idx)
        if wav is None:
            res[str(idx)] = dict(idx=idx, text=text, error="找不到音檔")
            continue
        sha, old = sha1_of(wav), res.get(str(idx))
        if old and not old.get("error") and old.get("wav_sha1") == sha and bool(old.get("mock")) == bool(args.mock) and not args.redo:
            skipped += 1
            continue
        exp = norm_expect(args.expect, text) if args.expect else ([] if args.no_expect else auto_expect(text))
        rec = dict(idx=idx, text=text, wav=paths.rel(wav), wav_sha1=sha, expect=exp, ts=datetime.now().isoformat(timespec="seconds"))
        try:
            rec.update(call(wav, text, exp, args, limiter))
        except (ApiError, ValueError) as e:
            rec["error"] = str(e)[:300]
        res[str(idx)] = rec
        save_json(out, data)
        todo += 1
        print(f"句 {idx:>3}: " + (f"錯誤 {rec['error']}" if rec.get("error") else
              f"{'過' if rec['result']['overall_pass'] else '未過'} 發音{rec['result']['pronunciation']['score']} "
              f"停頓{rec['result']['pauses']['score']} issues {len(flat_issues(rec['result']))}"), flush=True)
    save_json(out, data)
    out.with_suffix(".md").write_text(summary_md(data), encoding="utf-8")
    print(f"完成:新審 {todo} 句、跳過 {skipped} 句 -> {out}")
    return out


def summary_md(data):
    m, res = data["meta"], data.get("results", {})
    recs = sorted(res.values(), key=lambda r: r["idx"])
    ok = [r for r in recs if not r.get("error")]
    fails = [r for r in ok if not r["result"]["overall_pass"]]
    errs = [r for r in recs if r.get("error")]
    kinds = {}
    for r in ok:
        for i in flat_issues(r["result"]):
            kinds[f"{i['src']}:{i['kind']}"] = kinds.get(f"{i['src']}:{i['kind']}", 0) + 1
    tok = {k: sum((r.get("usage") or {}).get(k, 0) for r in ok) for k in ("prompt", "output", "thoughts", "total")}
    mocks = sum(1 for r in ok if r.get("mock"))
    L = [f"# E3 審聽 {m['tag']} {m['ver']}", "",
         f"- 模型:{m.get('model')}(實際用到:{', '.join(sorted({r.get('model', '?') for r in ok})) or '無'})"
         + (f";其中 {mocks} 句是 mock(未實際審聽)" if mocks else ""),
         f"- 已審 {len(ok)} 句、未過 {len(fails)} 句、錯誤 {len(errs)} 句",
         f"- token:輸入 {tok['prompt']}、輸出 {tok['output']}、思考 {tok['thoughts']}、合計 {tok['total']}",
         f"- issues 計數:" + (",".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "無"), ""]
    if fails:
        L += ["## 未過句(優先聽)", "", "| 句 | 發音 | 停頓 | 清晰 | 問題 | 摘要 |", "|---|---|---|---|---|---|"]
        for r in sorted(fails, key=lambda r: (r["result"]["pronunciation"]["score"] or 9, r["idx"])):
            x = r["result"]
            iss = ";".join(f"{i['char'] or '-'}@{i['pos'] if i['pos'] is not None else '-'}:{i['kind']}"
                           for i in flat_issues(x)) or "-"
            L.append(f"| {r['idx']} | {x['pronunciation']['score']} | {x['pauses']['score']} | {x['clarity']['score']} | {iss} | {x['rationale'][:60]} |")
        L.append("")
    if errs:
        L += ["## 錯誤句", ""] + [f"- 句 {r['idx']}:{r['error']}" for r in errs] + [""]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------ 真值
def load_truth(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    items = d.get("items", d.get("cases", [])) if isinstance(d, dict) else d
    out = []
    for n, it in enumerate(items):
        label = str(it.get("label") or it.get("verdict") or it.get("kind") or "").lower()
        label = "bad" if label in ("bad", "壞", "壞例", "fail", "false") else "good" if label in ("good", "好", "好例", "pass", "ok", "true") else ""
        defects = it.get("defects") or it.get("bad") or it.get("issues") or []
        if isinstance(defects, dict):
            defects = [defects]
        defects = [d for d in defects if isinstance(d, dict)]
        if not defects and label == "bad" and (it.get("char") or it.get("issue")):
            # channel	aste\ear	ruth.json 的扁平欄位:issue「讀音:…」「斷句」「英文詞」…;char/pos 只在讀音類有
            defects = [dict(char=it.get("char") or "", pos=it.get("pos"), srcs=issue_srcs(str(it.get("issue") or "")))]
        out.append(dict(id=it.get("id", n + 1), wav=it.get("wav") or it.get("audio"), tag=it.get("tag"),
                        idx=it.get("idx") or it.get("line"), text=it.get("text", ""),
                        expect=it.get("expect"), label=label, defects=defects))
    return out


def issue_srcs(issue):
    """真值 issue 文字 -> 可算命中的 issue 來源集合(讀音類另需 char/pos 相符)。"""
    srcs = set()
    if any(k in issue for k in ("斷句", "停頓")):
        srcs.add("pause")
    if "英文" in issue:
        srcs.add("english")
    if any(k in issue for k in ("多唸", "吞音", "漏唸", "雜音", "數字")):
        srcs |= {"pron", "clarity"}
    return sorted(srcs)


def defect_hit(defect, issues):
    ch, pos, kind = defect.get("char") or "", _pos(defect.get("pos")), defect.get("kind") or ""
    srcs = set(defect.get("srcs") or [])
    if srcs and any(i["src"] in srcs for i in issues):
        return True
    for i in issues:
        if ch and i["char"] and (ch in i["char"] or i["char"] in ch):
            return True
        if pos is not None and i["pos"] == pos:
            return True
        if kind and i["kind"] == kind:
            return True
    return False


def judge_item(item, res):
    """-> dict(hit:壞例是否命中 / None, fa:好例是否誤報 / None, fa_strict)。"""
    iss = flat_issues(res)
    if item["label"] == "bad":
        hit = any(defect_hit(d, iss) for d in item["defects"]) if item["defects"] else (not res["overall_pass"] or bool(iss))
        return dict(hit=hit, hit_loose=(not res["overall_pass"] or bool(iss)), fa=None, fa_strict=None)
    if item["label"] == "good":
        return dict(hit=None, fa=not res["overall_pass"], fa_strict=bool(iss) or not res["overall_pass"])
    return dict(hit=None, fa=None, fa_strict=None)


def truth_stats(rows):
    """rows = [dict(label, hit, fa, fa_strict)] -> 召回、誤報率(分母 0 回 None)。"""
    bad = [r for r in rows if r["label"] == "bad"]
    good = [r for r in rows if r["label"] == "good"]
    rate = lambda a, n: (sum(1 for r in a if r) / n) if n else None  # noqa: E731
    return dict(n_bad=len(bad), n_good=len(good), recall=rate([r["hit"] for r in bad], len(bad)),
                recall_loose=rate([r.get("hit_loose") for r in bad], len(bad)),
                fa=rate([r["fa"] for r in good], len(good)), fa_strict=rate([r["fa_strict"] for r in good], len(good)))


def run_truth(args, call=None):
    call = call or call_model
    items = load_truth(paths.find(args.truth))
    limiter, rows, dump = RateLimiter(0 if args.mock else args.rpm), [], []
    for it in items:
        wav = paths.find(it["wav"]) if it["wav"] else (line_wav(it["tag"], int(it["idx"])) if it["tag"] and it["idx"] else None)
        if not wav or not Path(wav).exists():
            print(f"[{it['id']}] 找不到音檔,略過")
            continue
        exp = norm_expect(it["expect"], it["text"]) if it["expect"] else []
        try:
            r = call(wav, it["text"], exp, args, limiter)
        except (ApiError, ValueError) as e:
            print(f"[{it['id']}] 錯誤:{str(e)[:120]}")
            continue
        j = judge_item(it, r["result"])
        rows.append(dict(label=it["label"], **j))
        dump.append(dict(id=it["id"], label=it["label"], **j, result=r["result"], usage=r.get("usage")))
        mark = ("命中" if j["hit"] else "漏抓") if it["label"] == "bad" else ("誤報" if j["fa"] else "OK") if it["label"] == "good" else "?"
        iss = ";".join(f"{i['char'] or '-'}:{i['kind']}" for i in flat_issues(r["result"])) or "-"
        print(f"[{it['id']}] {it['label'] or '?':<4} {mark:<3} pass={r['result']['overall_pass']} {iss}  {it['text'][:24]}")
    st = truth_stats(rows)
    pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"  # noqa: E731
    print(f"\n壞例 {st['n_bad']} 筆:召回 {pct(st['recall'])}(門檻 ≥80%)")
    print(f"好例 {st['n_good']} 筆:誤報 {pct(st['fa'])}(門檻 ≤10%;任何 issue 的嚴格誤報 {pct(st['fa_strict'])})")
    if args.out:
        save_json(paths.out_file(args.out), dict(stats=st, items=dump))
    return st


# ------------------------------------------------------------ CLI
def build_parser():
    ap = argparse.ArgumentParser(description="E3 Gemini 審聽")
    ap.add_argument("--wav")
    ap.add_argument("--text")
    ap.add_argument("--expect", help='期望讀音 JSON,例 {"12":"zhe5"}')
    ap.add_argument("--tag")
    ap.add_argument("--ver")
    ap.add_argument("--lines", help="例 1-3,7")
    ap.add_argument("--redo", action="store_true", help="已有結果也重審")
    ap.add_argument("--truth", help="ground truth json(channel\\taste\\ear\\truth.json)")
    ap.add_argument("--out", help="--truth 結果另存 json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fallback-model", default=FALLBACK_MODEL, help="主模型重試用盡後改用;空字串 = 不備援")
    ap.add_argument("--rpm", type=float, default=5, help="每分鐘最多幾次呼叫(0 = 不限)")
    ap.add_argument("--mock", action="store_true", help="不打 API,回固定 JSON")
    ap.add_argument("--no-expect", action="store_true", help="--tag 模式不自動帶期望讀音")
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.truth:
        run_truth(a)
    elif a.tag:
        if not a.ver:
            ap.error("--tag 要搭配 --ver")
        run_tag(a)
    elif a.wav and a.text:
        exp = norm_expect(a.expect, a.text) if a.expect else []
        r = call_model(a.wav, a.text, exp, a, RateLimiter(0 if a.mock else a.rpm))
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        ap.error("要給 --wav + --text、--tag + --ver、或 --truth")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
