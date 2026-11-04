#!/usr/bin/env python3
r"""耳朵 E2 聲調分類(PLAN_工作室v2_2026-10-31 §6.3;本機 CPU、0 token)。
特徵:每字區間的 F0(librosa pyin,換成相對整句中位數的半音)取 10 點 + 斜率/範圍/有聲比 + 能量 3 點 + 長度,
      加前後各半字寬的 10 點輪廓、前後字的 5 點輪廓與高低差(聲調靠上下文);分類器 HistGradientBoosting,五類 1–4、5=輕聲。
訓練資料:build/<tag>/tts_cosy3|tts/NNN.qc.json(另加 tmp/c0、tmp/tts_speedup)品管通過(passed)且有 say_t(逐字時間)的句子,依 wav_sha1 去重;
標籤:pypinyin TONE3(詞級、tone_sandhi、輕聲記 5),只取「非多音字」——pypinyin 有異讀、pron_rules 收錄、
      教育部辭典多讀音(tts_moe)的字一律不進訓練(推論時照樣估);
      例外:NEUTRAL 虛詞(的了著得…)詞級讀輕聲時收 '5',否則輕聲類沒有資料。留出 10% 句子(wav_sha1 雜湊)給 ear_e2_eval.py。
python -X utf8 pipeline/senses/ear_e2_tone.py --build-data [--jobs 12]   抽特徵 -> tmp/ear_e2/dataset.pkl(增量)
python -X utf8 pipeline/senses/ear_e2_tone.py --train                     訓練(留出 10%)-> tts_models/ear_e2_tone.pkl
(tts_env_chattts 的 python)
"""
import argparse
import functools
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np

PIPE = Path(__file__).resolve().parent.parent
for _p in (PIPE, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import paths  # noqa: E402
import ear_e2_align as AL  # noqa: E402

SR, HOP = 16000, 160
HOP_S = HOP / SR
FMIN, FMAX = 60.0, 450.0
TONES = ["1", "2", "3", "4", "5"]
MODEL = paths.TTS_MODELS / "ear_e2_tone.pkl"
WORK = paths.TMP / "ear_e2"
DATASET = WORK / "dataset.pkl"
CACHE_DIRS = ("tts_cosy3", "tts")
EXTRA_DIRS = ("c0", "tts_speedup")
HAN = re.compile(r"[㐀-鿿豈-﫿]+")
FEAT_VER = "f2"   # f2:加前後各半字寬的 10 點輪廓(對齊格點 0.08 秒,邊界不準);輕聲虛詞收標籤
NEUTRAL = frozenset("的了著得地們嗎呢吧啊呀嘛子麼過")   # 詞級拼音為輕聲時收進訓練(多音字例外:只收輕聲那一讀)


# ------------------------------------------------------------ 標籤
@functools.lru_cache(maxsize=None)
def poly_chars():
    """不進訓練的字:pron_rules 收錄 + 教育部多讀音字(有辭典檔才有)。pypinyin 異讀另在 is_poly 判。"""
    s = set()
    try:
        import tts_cosy_text as CT
        s |= set(CT.RULE_CHARS)
    except Exception as e:  # noqa: BLE001
        print(f"警告:讀不到 pron_rules({e})", file=sys.stderr)
    try:
        import tts_moe
        s |= {c for c, v in tts_moe.load_pron().items() if len(v) > 1}
    except Exception:  # noqa: BLE001
        pass
    return frozenset(s)


@functools.lru_cache(maxsize=None)
def is_poly(ch):
    from pypinyin import Style, pinyin
    if ch in poly_chars():
        return True
    return len(set(pinyin(ch, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0])) > 1


def tone_of(py):
    """tone3 拼音 -> '1'..'5'(沒有數字當輕聲)。"""
    return py[-1] if py and py[-1] in "12345" else "5"


def char_tones(text):
    """原文 -> 每字 pypinyin tone3(非漢字 None);詞級 + 三聲變調。"""
    from pypinyin import Style, lazy_pinyin
    out = [None] * len(text)
    for m in HAN.finditer(text):
        py = lazy_pinyin(m.group(), style=Style.TONE3, neutral_tone_with_five=True, tone_sandhi=True)
        if len(py) == len(m.group()):
            out[m.start():m.end()] = py
    return out


def labels(text):
    """每字訓練標籤('1'..'5' 或 None:非漢字、多音字;NEUTRAL 虛詞詞級讀輕聲時例外收 '5')。"""
    out = []
    for ch, p in zip(text, char_tones(text)):
        if p is None:
            out.append(None)
        elif ch in NEUTRAL and tone_of(p) == "5":
            out.append("5")
        else:
            out.append(None if is_poly(ch) else tone_of(p))
    return out


# ------------------------------------------------------------ 特徵
def load_audio(path):
    import librosa
    x, _ = librosa.load(str(path), sr=SR, mono=True)
    return x


def contours(x):
    """整句 -> (半音 F0 [nan=無聲], 能量 dB 相對全句最大, 中位數 Hz)。"""
    import librosa
    f0, vflag, _ = librosa.pyin(x, fmin=FMIN, fmax=FMAX, sr=SR, frame_length=1024, hop_length=HOP)
    f0 = np.where(vflag, f0, np.nan)
    med = float(np.nanmedian(f0)) if np.any(~np.isnan(f0)) else 120.0
    st = 12 * np.log2(f0 / med)
    rms = librosa.feature.rms(y=x, frame_length=640, hop_length=HOP)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-5))
    db = db - db.max()
    n = min(len(st), len(db))
    return st[:n], db[:n], med


def _resample(v, n):
    v = v[~np.isnan(v)]
    if len(v) < 3:
        return np.full(n, np.nan)
    return np.interp(np.linspace(0, len(v) - 1, n), np.arange(len(v)), v)


def _seg(arr, s, e, trim=0.1):
    a, b = int(s / HOP_S), int(np.ceil(e / HOP_S))
    b = max(b, a + 1)
    w = b - a
    a2, b2 = a + int(w * trim), b - int(w * trim)
    if b2 - a2 < 2:
        a2, b2 = a, b
    return arr[a2:min(b2, len(arr))]


def _char_base(st, db, s, e):
    seg = _seg(st, s, e)
    c10 = _resample(seg, 10)
    w10 = _resample(_seg(st, max(0.0, s - 0.5 * (e - s)), e + 0.5 * (e - s), trim=0.0), 10)
    v = seg[~np.isnan(seg)]
    voiced = len(v) / max(len(seg), 1)
    if len(v) >= 3:
        slope = np.polyfit(np.arange(len(v)) * HOP_S, v, 1)[0]
        stats = [np.mean(v), slope, v.max() - v.min(), np.argmin(v) / len(v), np.argmax(v) / len(v), v[-1] - v[0]]
    else:
        stats = [np.nan] * 6
    eg = _seg(db, s, e, trim=0.0)
    e3 = _resample(eg, 3) if len(eg) >= 3 else np.full(3, np.nan)
    return c10, np.array(stats + [voiced, e - s, float(np.mean(eg)) if len(eg) else np.nan]), np.concatenate([e3, w10])


@functools.lru_cache(maxsize=1)
def feature_names():
    return ([f"c{j}" for j in range(10)] + ["mean", "slope", "range", "argmin", "argmax", "delta", "voiced", "dur", "edb"]
            + [f"e{j}" for j in range(3)] + [f"w{j}" for j in range(10)] + [f"p{j}" for j in range(5)] + [f"n{j}" for j in range(5)]
            + ["d_prev", "d_next", "gap_prev", "gap_next", "brk_next", "dur_rel", "pos", "f0_med", "f0_std"])


def features(x, spans):
    """音檔 + [(字, 起, 迄)] -> (位置清單, 特徵矩陣):只算有時間的漢字。"""
    st, db, med = contours(x)
    idx = [i for i, (ch, s, e) in enumerate(spans) if s is not None and e is not None and HAN.fullmatch(ch)]
    if not idx:
        return [], np.zeros((0, len(feature_names())), np.float32)
    base = {i: _char_base(st, db, spans[i][1], max(spans[i][2], spans[i][1] + 0.03)) for i in idx}
    dmed = float(np.median([spans[i][2] - spans[i][1] for i in idx]))
    sstd = float(np.nanstd(st)) if np.any(~np.isnan(st)) else 0.0
    nan5 = np.full(5, np.nan)
    rows = []
    for k, i in enumerate(idx):
        c10, stats, e3 = base[i]
        p, n = (idx[k - 1] if k else None), (idx[k + 1] if k + 1 < len(idx) else None)
        pc = base[p][0][::2] if p is not None else nan5
        nc = base[n][0][::2] if n is not None else nan5
        pm = base[p][1][0] if p is not None else np.nan
        nm = base[n][1][0] if n is not None else np.nan
        gap_prev = spans[i][1] - spans[p][2] if p is not None else 1.0
        gap_next = spans[n][1] - spans[i][2] if n is not None else 1.0
        brk_next = 1.0 if n is None or n != i + 1 else 0.0   # 後面接標點/非漢字
        ctx = [stats[0] - pm, nm - stats[0], gap_prev, gap_next, brk_next,
               (spans[i][2] - spans[i][1]) / max(dmed, 1e-3), k / max(len(idx) - 1, 1), med, sstd]
        rows.append(np.concatenate([c10, stats, e3, pc, nc, ctx]))
    return idx, np.vstack(rows).astype(np.float32)


# ------------------------------------------------------------ 資料集
def _qc_files():
    for d in sorted(p for p in paths.BUILD.iterdir() if p.is_dir()):
        for sub in CACHE_DIRS:
            if (d / sub).is_dir():
                yield from sorted((d / sub).glob("*.qc.json"))
    for sub in EXTRA_DIRS:   # C0 試配、語速實驗的成品句(同樣過品管才收)
        if (paths.TMP / sub).is_dir():
            yield from sorted((paths.TMP / sub).rglob("*.qc.json"))


def iter_cache():
    """品管通過、有 say_t 的句子 -> (鍵, wav 路徑, 文字, spans, wav_sha1)。"""
    for q in _qc_files():
        stem = q.name[:-len(".qc.json")]
        wav = q.with_name(f"{stem}.wav")
        try:
            qc = json.loads(q.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not qc.get("passed") or not wav.exists():
            continue
        text, spans = AL.from_qc(qc)
        if spans:
            key = q.with_name(stem).relative_to(paths.ROOT).as_posix()
            yield key, wav, text, spans, qc.get("wav_sha1") or key


def _extract(job):
    key, wav, text, spans, sha = job
    try:
        idx, X = features(load_audio(wav), spans)
    except Exception as e:  # noqa: BLE001
        return sha, {"key": key, "err": str(e)}
    lab = labels(text)
    return sha, {"key": key, "text": text, "pos": idx, "X": X, "y": [lab[i] for i in idx]}


def holdout(sha):
    import hashlib
    return int(hashlib.sha1(sha.encode()).hexdigest()[:8], 16) % 10 == 0


def load_dataset():
    if DATASET.exists():
        d = pickle.loads(DATASET.read_bytes())
        if d.get("ver") == FEAT_VER:
            return d
    return {"ver": FEAT_VER, "items": {}}


def build_data(jobs=12):
    from concurrent.futures import ProcessPoolExecutor
    WORK.mkdir(parents=True, exist_ok=True)
    ds = load_dataset()
    todo, seen = [], set(ds["items"])
    for job in iter_cache():
        if job[4] not in seen:
            seen.add(job[4])
            todo.append(job)
    print(f"已有 {len(ds['items'])} 句,新抽 {len(todo)} 句", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for k, (sha, it) in enumerate(ex.map(_extract, todo, chunksize=4), 1):
            ds["items"][sha] = it
            if k % 100 == 0:
                print(f"  {k}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    DATASET.write_bytes(pickle.dumps(ds))
    errs = [it["key"] for it in ds["items"].values() if "err" in it]
    print(f"資料集 {len(ds['items'])} 句(錯誤 {len(errs)} {', '.join(errs[:5])})-> {DATASET}")
    return ds


def stack(ds, part):
    """part = 'train' | 'test' -> (X, y, 句數)。只取有標籤的字。"""
    Xs, ys, n = [], [], 0
    for sha, it in ds["items"].items():
        if "err" in it or holdout(sha) != (part == "test"):
            continue
        keep = [k for k, t in enumerate(it["y"]) if t is not None]
        if not keep:
            continue
        n += 1
        Xs.append(it["X"][keep])
        ys += [it["y"][k] for k in keep]
    if not Xs:
        return np.zeros((0, len(feature_names())), np.float32), np.array([]), 0
    return np.vstack(Xs), np.array(ys), n


def train():
    from sklearn.ensemble import HistGradientBoostingClassifier
    ds = load_dataset()
    X, y, n = stack(ds, "train")
    if not len(y):
        sys.exit("資料集是空的:先跑 --build-data")
    print(f"訓練 {n} 句、{len(y)} 字;各調 " + " ".join(f"{t}:{int((y == t).sum())}" for t in TONES), flush=True)
    clf = HistGradientBoostingClassifier(max_iter=600, learning_rate=0.06, max_leaf_nodes=48,
                                         l2_regularization=1.0, early_stopping=True, random_state=0)
    clf.fit(X, y)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    MODEL.write_bytes(pickle.dumps({"clf": clf, "feat_ver": FEAT_VER, "names": feature_names(),
                                    "n_sent": n, "n_char": int(len(y)), "trained": time.strftime("%Y-%m-%d %H:%M")}))
    print(f"模型 -> {MODEL}(iter {clf.n_iter_})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-data", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    if a.build_data:
        build_data(a.jobs)
    if a.train:
        train()
    if not (a.build_data or a.train):
        ap.print_help()


if __name__ == "__main__":
    main()
