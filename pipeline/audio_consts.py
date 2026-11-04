"""BGM 常數與純函式的單一來源(build.py / make_version.py / sci/make_film.py 都從這裡 import)。
只放常數與不碰檔案系統/ffmpeg 的算法(曲側檔讀取除外);響度量測(track_db / track_win_db)仍在 build.py。
"""
import json
import zlib
from pathlib import Path

DEFAULT_BGM = "Lightless_Dawn.mp3"  # 舊預設:只在沒給 --bgm、--channel 也查不到 spec.json 的 channel 時退回
# 定案曲(CLAUDE.md「BGM 音量」節末,2026-10-21);偏移在同名 .json 側檔,build 自動套用
BGM_BY_CHANNEL = {
    "ChannelA": ["ai_C2_light.wav"],
    "ChannelB": ["ai_D2_reflective.wav"],
    "科普": ["ai_E1_mystery.wav", "ai_E2_mystery.wav", "ai_E3_mystery.wav"],  # 第三頻道三首依 tag 雜湊輪用
}

BGM_BELOW_VOICE_DB = 5.7       # 預設算法(2026-10-18 cod2026 sample3 使用者定案):BGM 3 秒窗 p90 = 配音 RMS - 5.7 dB
BGM_PEAK_BELOW_VOICE_DB = 5.0  # BGM 最大 3 秒窗至少比配音低這麼多(超過就整首再壓:大聲段落不蓋配音)
BGM_DYN_P90_P10_DB, BGM_DYN_MAX_P50_DB = 8.0, 5.0   # 動態警告門檻

BGM_REF_DB = -26.0           # 舊算法 --bgm-vol 的基準響度:Lightless Dawn 整首的有聲 RMS(使用者是聽這首定的 25%)
BGM_NORM_MIN, BGM_NORM_MAX = 0.05, 2.0


def channel_kind(channel):
    """頻道名(--channel 或 spec.json 的 channel:ChannelA/ChannelA、ChannelB/ChannelB、ChannelC/ChannelC)-> BGM_BY_CHANNEL 的鍵;不認得 = None。"""
    c = channel or ""
    if "ChannelA" in c:
        return "ChannelA"
    if "ChannelB" in c:
        return "ChannelB"
    if "ChannelC" in c or "ChannelC" in c:
        return "科普"
    return None


def bgm_for_channel(channel, tag):
    """頻道名 -> 定案 BGM 檔名;不認得頻道 = None。第三頻道三首以 tag 的 crc32 取餘輪用(穩定,同一支片每版都同一首)。"""
    kind = channel_kind(channel)
    if not kind:
        return None
    names = BGM_BY_CHANNEL[kind]
    return names[zlib.crc32(tag.encode("utf-8")) % len(names)]


def bgm_gain_db(voice_db, win, extra_db=0.0):
    """預設 BGM 增益 dB:回傳 (增益 dB, 套用條款 'p90'|'peak')。win = (p10, p50, p90, max) 3 秒窗響度。"""
    p10, p50, p90, mx = win
    g_p90 = voice_db - BGM_BELOW_VOICE_DB - p90
    g_pk = voice_db - BGM_PEAK_BELOW_VOICE_DB - mx
    which = "p90" if g_p90 <= g_pk else "peak"
    return min(g_p90, g_pk) + extra_db, which


def bgm_gain_auto(voice_db, win, extra_db=0.0):
    """預設 BGM 增益:回傳 (線性增益, 增益 dB, 套用條款 'p90'|'peak')。win = track_win_db 結果。"""
    g, which = bgm_gain_db(voice_db, win, extra_db)
    return 10 ** (g / 20), g, which


def bgm_norm(db):
    """BGM 響度對齊倍率:把量到的 db 拉到 BGM_REF_DB,再乘 --bgm-vol 才是實際音量。
    各曲原始響度差很多(Volatile Reaction -9 / Lightless Dawn -26),不對齊的話同樣 25% 會差 16 dB。"""
    if db is None:
        return 1.0
    return min(BGM_NORM_MAX, max(BGM_NORM_MIN, 10 ** ((BGM_REF_DB - db) / 20)))


def bgm_sidecar(path):
    """曲子的同名 .json 側檔(AI 生成曲:使用者定案的 bgm_db 偏移與出處);沒有或讀不了回 {}。"""
    try:
        return json.loads(Path(path).with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def sidecar_db(side):
    """側檔 dict 的 bgm_db(相對預設算法的偏移 dB;與命令列 --bgm-db 疊加);沒有回 0.0。"""
    try:
        return float(side.get("bgm_db") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def bgm_sidecar_db(path):
    return sidecar_db(bgm_sidecar(path))


def sidecar_duck(side):
    """有側檔(含 bgm_db)的曲子才閃避(配音時壓低 BGM);側檔 duck:false 可關。"""
    return bool(side.get("bgm_db") is not None and side.get("duck", True))
