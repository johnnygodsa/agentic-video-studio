#!/usr/bin/env python3
r"""LLM 函式層:用 `claude -p` 當函式呼叫(走 Max 訂閱)。規格:pipeline\docs\director_ab.md §1。

call(tag, fn, prompt, ...) 跑一次;call_escalating 同模型失敗 2 次改 Opus,Opus 再失敗回 ok=False;用量上限不重試。
每次呼叫(含失敗)寫 director.log_call;原始輸出存 tmp\llm\<tag>\<時間>_<fn>.json(除錯用,不進 git)。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402

# 別名 haiku 會解析到舊模型,一律傳完整 ID
MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
DEFAULT_TOOLS = ("Read", "Grep", "Glob")
NO_TOOLS = ("Agent", "Task")  # subagent 不巢狀
LIMIT_RE = re.compile(r"usage limit|rate.?limit|limit reached|hit your .{0,30}limit|too many requests", re.I)
SHORT_TEXT = 400  # 正常回覆也可能提到 rate limit:沒標 is_error 時只看這個長度內的回覆
# 實測 2026-10-31:--agent 下 --json-schema 不生效(代理 tools 白名單濾掉 StructuredOutput,structured_output 不出現),
# 所以 schema 也寫進 prompt、回覆文字取 JSON、schema_miss 自己驗;旗標留著(無 --agent 時有效)。
SCHEMA_TAIL = "\n\n最後一則訊息只輸出一個 JSON 物件,不加說明、不包程式碼區塊,符合此 JSON Schema:\n"
TYPES = {"integer": int, "string": str, "boolean": bool, "number": (int, float), "array": list, "object": dict}


@dataclass
class Result:
    ok: bool = False
    text: str = ""
    data: dict | None = None
    rc: int = 0
    model: str = ""
    usage: dict = field(default_factory=dict)
    secs: float = 0.0
    error: str = ""
    limited: bool = False


def _exe():
    return shutil.which("claude") or "claude"


def build_cmd(model_id, *, agent=None, effort=None, tools=DEFAULT_TOOLS, schema=None, allowed=None):
    """allowed = --allowedTools 規則(可含 `Bash(python -X utf8 pipeline/x.py:*)` 這類樣式,每條一個參數);None = 同 tools。"""
    names = ",".join(t for t in tools if t not in NO_TOOLS)
    cmd = [_exe(), "-p", "--output-format", "json", "--no-session-persistence", "--model", model_id]
    if effort:
        cmd += ["--effort", effort]
    if agent:
        cmd += ["--agent", agent]
    cmd += ["--tools", names, "--allowedTools"]
    cmd += [a for a in allowed if not a.startswith(NO_TOOLS)] if allowed else [names]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema, ensure_ascii=True)]
    return cmd


def _spawn(cmd, prompt, timeout, cwd):
    """跑 claude,prompt 走 stdin。回傳 (rc, stdout, stderr);逾時 rc=None。"""
    try:
        r = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        return None, "", f"逾時 {timeout} 秒"
    except OSError as e:
        return -1, "", f"無法執行 claude:{e}"
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _envelope(out):
    """--output-format json 的結果物件:dict,或事件陣列裡最後一個 type=result。解析不了回 None。"""
    try:
        d = json.loads(out)
    except ValueError:
        return None
    if isinstance(d, list):
        d = next((x for x in reversed(d) if isinstance(x, dict) and x.get("type") == "result"), None)
    return d if isinstance(d, dict) else None


def parse_json_text(text):
    """從回覆文字取 JSON 物件(可包在 ``` 內或前後有說明);取不到回 None。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    for cand in ([m.group(1)] if m else []) + [text, text[text.find("{"):text.rfind("}") + 1]]:
        try:
            d = json.loads(cand)
        except ValueError:
            continue
        if isinstance(d, dict):
            return d
    return None


def schema_miss(schema, data, path=""):
    """驗 required 與欄位型別(含陣列元素);回第一個不符的欄位路徑或 None。"""
    for k in schema.get("required") or []:
        if not isinstance(data, dict) or k not in data:
            return f"{path}{k}"
    for k, sub in (schema.get("properties") or {}).items():
        v = data.get(k) if isinstance(data, dict) else None
        t = TYPES.get(sub.get("type"))
        if v is not None and t and (not isinstance(v, t) or (t is int and isinstance(v, bool))):
            return f"{path}{k}"
        if isinstance(v, list):
            for i, x in enumerate(v):
                m = schema_miss(sub.get("items") or {}, x, f"{path}{k}[{i}].")
                if m:
                    return m
    return None


def _is_limited(rc, env, out, err):
    text = str((env or {}).get("result") or "")
    failed = rc != 0 or env is None or env.get("is_error")
    if failed:
        return (env or {}).get("api_error_status") == 429 or bool(LIMIT_RE.search(f"{text}\n{out[:2000]}\n{err[:2000]}"))
    return len(text) <= SHORT_TEXT and bool(LIMIT_RE.search(text))


def _interpret(rc, out, err, model_id, schema, secs):
    env = _envelope(out)
    r = Result(rc=-1 if rc is None else rc, model=model_id, secs=round(secs, 1))
    if env:
        r.text = str(env.get("result") or "")
        r.usage = env.get("usage") or {}
    r.limited = rc is not None and _is_limited(rc, env, out, err)
    if rc is None:
        r.error = err
    elif r.limited:
        r.error = "用量上限"
    elif rc != 0:
        r.error = f"結束碼 {rc}:{(err or out).strip()[-300:]}"
    elif env is None:
        r.error = f"輸出不是 JSON:{out.strip()[:200]}"
    elif env.get("is_error"):
        r.error = f"is_error:{r.text[:300]}"
    elif schema is not None:
        r.data = env.get("structured_output")
        if not isinstance(r.data, dict):
            r.data = parse_json_text(r.text)
        miss = schema_miss(schema, r.data) if r.data is not None else None
        if r.data is None:
            r.error = "取不到符合 schema 的 JSON"
        elif miss:
            r.error = f"JSON 不符 schema:{miss}"
    r.ok = not r.error
    return r


def _save_raw(tag, fn, rc, out, err):
    d = P.TMP / "llm" / tag
    d.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}_{fn}.json"
    (d / name).write_text(out if out.strip() else json.dumps({"rc": rc, "stderr": err}, ensure_ascii=False), encoding="utf-8")


def _log(tag, fn, r, agent, seg):
    import director as D
    u = r.usage
    tin = int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
    D.log_call(tag, fn, r.model, tin, int(u.get("output_tokens") or 0), int(u.get("cache_read_input_tokens") or 0),
               secs=r.secs, ok=r.ok, seg=seg, agent=agent)


def call(tag, fn, prompt, *, agent=None, model="sonnet", effort=None, tools=DEFAULT_TOOLS,
         schema=None, seg=None, timeout=1800, validate=None, cwd=None, allowed=None):
    """跑一次。validate(result) 回字串 = 失敗原因(call_escalating 下一次附進 prompt)。"""
    model_id = MODELS.get(model, model)
    cmd = build_cmd(model_id, agent=agent, effort=effort, tools=tools, schema=schema, allowed=allowed)
    if schema is not None:
        prompt += SCHEMA_TAIL + json.dumps(schema, ensure_ascii=False)
    t0 = time.time()
    rc, out, err = _spawn(cmd, prompt, timeout, str(cwd or P.ROOT))
    r = _interpret(rc, out, err, model_id, schema, time.time() - t0)
    _save_raw(tag, fn, rc, out, err)
    if r.ok and validate:
        why = validate(r)
        if why:
            r.ok, r.error = False, why
    _log(tag, fn, r, agent, seg)
    return r


def call_escalating(tag, fn, prompt, **kw):
    """同模型失敗 2 次 → Opus;Opus 再失敗回 ok=False;用量上限立刻回(不換模型硬跑)。"""
    model = kw.pop("model", "sonnet")
    seq = [model, model] + ([] if MODELS.get(model, model) == MODELS["opus"] else ["opus"])
    text, r = prompt, None
    for m in seq:
        r = call(tag, fn, text, model=m, **kw)
        if r.ok or r.limited:
            return r
        text = f"{prompt}\n\n上一次失敗原因:{r.error}\n修正後重做。"
    return r
