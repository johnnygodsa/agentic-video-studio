#!/usr/bin/env python3
r"""片頭音效(程式合成,不用外部素材)。對齊 scenes\intro.js 的時間表:
0.0–0.4 五張字牌逐張彈入、0.7「?」牌落地、0.8–1.4 鴿子走進來、1.8 副標出現、2.1 聳肩。
用法:python -X utf8 pipeline\sci\make_sfx.py  → channel\sfx\intro_A.wav / intro_B.wav / intro_C.wav(各 3.0 秒、48 kHz 單聲道)
A 木琴上行加叮一聲;B 紙片啪聲加悶響;C 兩者疊在一起(各降音量)。亂數固定種子,同一版程式輸出逐位元組相同。"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths as P

SR, DUR = 48000, 3.0
TILES = [0.0, 0.1, 0.2, 0.3, 0.4]
T_LAND, T_SUB, T_SHRUG = 0.7, 1.8, 2.1
STEPS = [0.85, 1.0, 1.15, 1.3]                     # 鴿子腳步
NOTES = [523.25, 587.33, 659.25, 783.99, 880.0]    # C5 D5 E5 G5 A5(五聲音階上行)


def put(buf, t, x):
    i = int(t * SR)
    x = x[: max(0, len(buf) - i)]
    buf[i:i + len(x)] += x


def env(n, a=0.004, tau=0.08):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / tau)


def marimba(f, d=0.32, g=0.5):
    n = int(d * SR); t = np.arange(n) / SR
    return g * env(n, tau=0.09) * (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t / 0.02))


def slap(rng, d=0.07, g=0.5, lo=1200, hi=5200):
    n = int(d * SR)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / SR)
    X[(fr < lo) | (fr > hi)] = 0
    return g * env(n, a=0.001, tau=0.018) * np.fft.irfft(X, n) * 3


def thump(d=0.22, g=0.8, f0=120, f1=48):
    n = int(d * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.04)
    return g * env(n, a=0.002, tau=0.07) * np.sin(2 * np.pi * np.cumsum(f) / SR)


def slide(f0, f1, d=0.28, g=0.3):
    n = int(d * SR); t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (t / d)
    return g * np.sin(np.pi * t / d) * np.sin(2 * np.pi * np.cumsum(f) / SR)


def make(kind):
    rng = np.random.default_rng(402)
    b = np.zeros(int(DUR * SR))
    tone, paper = kind in "AC", kind in "BC"
    k = 0.7 if kind == "C" else 1.0
    for i, t in enumerate(TILES):
        if tone:
            put(b, t, marimba(NOTES[i], g=0.5 * k))
        if paper:
            put(b, t, slap(rng, g=0.55 * k, lo=1000 + 250 * i, hi=4500 + 400 * i))
    put(b, T_LAND, thump(g=0.85 * k))
    if tone:
        put(b, T_LAND, marimba(1046.5, d=0.6, g=0.45 * k))          # C6 叮
    if paper:
        put(b, T_LAND, slap(rng, d=0.12, g=0.7 * k, lo=500, hi=3500))
    for t in STEPS:
        put(b, t, slap(rng, d=0.03, g=0.12, lo=2500, hi=7000))       # 腳步:很輕的點
    put(b, T_SUB, slap(rng, g=0.35 * k) if not tone else marimba(659.25, d=0.2, g=0.3 * k))
    put(b, T_SHRUG, slide(520, 330))                                # 聳肩:往下滑的短音
    return np.clip(b / max(1.0, np.abs(b).max() / 0.7), -1, 1)


def make_outro():
    b = np.zeros(int(1.6 * SR))
    for i, t in enumerate(TILES):
        put(b, t, marimba(NOTES[i], g=0.5))
    put(b, 0.5, marimba(1046.5, d=0.6, g=0.45))    # 「?」牌彈入:C6 叮
    put(b, 0.6, slide(520, 330))                   # 聳肩
    return np.clip(b / max(1.0, np.abs(b).max() / 0.7), -1, 1)


def main():
    out = P.ROOT / "channel" / "sfx"
    out.mkdir(parents=True, exist_ok=True)
    # 定案:A(2026-10-11 使用者選定)。intro.wav 給片頭;outro.wav 給結語字牌(五張牌加「?」彈入,無落地悶響、腳步)
    for name, x in (("intro", make("A")), ("outro", make_outro())):
        x = (x * 32767).astype("<i2")
        with wave.open(str(out / f"{name}.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes())
        print(f"{name}.wav peak {np.abs(x).max() / 32767:.2f}")


if __name__ == "__main__":
    main()
