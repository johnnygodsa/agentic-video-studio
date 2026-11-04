#!/usr/bin/env python3
r"""路徑集中管理:所有腳本的素材、產出、交付路徑都從這裡取,別處不寫絕對路徑(只用標準函式庫)。

素材根 ROOT 的決定順序:
  1. 環境變數 CLAUDE_VIDEO_ROOT
  2. repo 根(pipeline 的上一層)底下有 chattts_speaker 目錄或 .video_root 標記檔 -> repo 根就是素材根
  3. FALLBACK_ROOT(寫死的路徑之一;另一個是 SHARED = <EXTERNAL_BACKEND>\_shared,環境變數 YT_SHARED_DIR 可改,與 Youtube AD 共用 GPU 鎖等)

ROOT 底下:
  raw\ images\ anim\ bgm\            素材
  chattts_speaker\pt\                音色檔(SPEAKERS)
  cosy_voice\                        CosyVoice3 參考音(COSY_REF)
  tts_env_chattts\ tts_models\       配音環境與模型(TTS_ENV = 其 python.exe)
  projects\<tag>\                    專案檔(clips_<tag>.json、research_<tag>.json)
  build\<tag>\                       快取與中間產物(配音快取在 build\<tag>\tts)
  output\<tag>\                      720p 預覽、notes、QA 圖、完整版成片
  tmp\                               暫存
正式成片交付到使用者的「下載」資料夾(DOWNLOADS,由 Windows 已知資料夾 API 取得),見 deliver.py。

命令列(給 shell 腳本用;路徑一律輸出正斜線、不帶 CR):
  python pipeline/paths.py                 列出全部
  python pipeline/paths.py ROOT            單一路徑
  python pipeline/paths.py clips re9       專案的 clips 檔
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FALLBACK_ROOT = Path(__file__).resolve().parent.parent
SHARED = Path(os.environ.get("YT_SHARED_DIR") or r"<EXTERNAL_BACKEND>\_shared")   # 與 Youtube AD 共用的目錄(gpu_lock.py、xnotify.py 等);第二個寫死路徑,理由與 _shared/xnotify.py 對稱
SPEAKER_DIR = "chattts_speaker"
ROOT_MARKER = ".video_root"   # 副本專案(如 a mirror checkout)沒有 chattts_speaker,改放此標記檔表示 repo 根即素材根


def _root():
    env = os.environ.get("CLAUDE_VIDEO_ROOT")
    if env:
        return Path(env)
    if (REPO / SPEAKER_DIR).is_dir() or (REPO / ROOT_MARKER).is_file():
        return REPO
    return FALLBACK_ROOT


ROOT = Path(os.path.abspath(_root()))
RAW = ROOT / "raw"
IMAGES = ROOT / "images"
ANIM = ROOT / "anim"
BGM = ROOT / "bgm"
SPEAKERS = ROOT / SPEAKER_DIR / "pt"


def venv_python(env_dir):
    """venv 的 python:Windows = Scripts/python.exe,其他(Colab/Linux)= bin/python。"""
    return Path(env_dir) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


TTS_ENV = venv_python(ROOT / "tts_env_chattts")
KAGGLE_ENV = venv_python(ROOT / "tts_env_kaggle")  # Kaggle CLI 2.x(需 Python>=3.11,所以不用 tts_env_chattts);只放 kaggle 套件
TTS_MODELS = ROOT / "tts_models"
COSY_REF = ROOT / "cosy_voice" / "ref_b.wav"  # CosyVoice3 參考音 B(同主檔名 .txt 為逐字稿;2026-10-17 使用者定案)
PROJECTS = ROOT / "projects"
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"
TMP = ROOT / "tmp"
FONT_BOLD = REPO / "fonts" / "NotoSansTC-SubBold.ttf"          # 字幕/卡片/標籤用粗體(wght=700 靜態檔;libass 與 Pillow 都只吃靜態檔)
FONT_REG = REPO / "fonts" / "NotoSansTC-Regular-static.ttf"   # 內文/一般(wght=400 靜態檔);2026-10-22 起取代微軟正黑體
ANIM_TPL = REPO / "pipeline" / "templates" / "anim"           # 網頁動畫模板(anim_web.py;tokens.css 與 <type>.html)
VENDOR = REPO / "pipeline" / "static" / "vendor"              # 本機 JS 套件(gsap.min.js;不走網路)
ANIM_WEB_CACHE = BUILD / "_anim_web"                          # anim_web 逐格 PNG 快取

_DOWNLOADS_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"
_downloads = None


def _known_folder(guid):
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid), ctypes.byref(g))
    out = ctypes.c_wchar_p()
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out))
    try:
        if hr != 0 or not out.value:
            raise OSError(f"SHGetKnownFolderPath hr={hr:#x}")
        return Path(out.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


def downloads():
    """使用者的「下載」資料夾;取不到時退回 OUTPUT\\final 並警告。"""
    global _downloads
    if _downloads is None:
        try:
            _downloads = _known_folder(_DOWNLOADS_GUID)
        except Exception as e:  # noqa: BLE001
            _downloads = OUTPUT / "final"
            print(f"警告: 取不到「下載」資料夾({e}),改用 {_downloads}", file=sys.stderr)
    return _downloads


def yt_inbox():
    """Youtube AD 的影片資料夾(= 下載資料夾\\V);正式成片與 .claude.json sidecar 交付到這裡。
    環境變數 UPLOAD_V_DIR 優先(與 Youtube AD 後端 config.py 同名同義,兩邊要設成同一個)。"""
    env = os.environ.get("UPLOAD_V_DIR")
    if env:
        return Path(env)
    return downloads() / "V"


YT_AD_DEFAULT = Path(r"<EXTERNAL_BACKEND>\Youtube AD")
YT_AD_SIBLING = REPO.parent / "EXTERNAL_BACKEND"   # 副本專案:與 a mirror checkout 同層


def yt_ad_root():
    r"""Youtube AD 專案根(讀 data\channels.json 用)。
    順序:環境變數 YOUTUBE_AD_ROOT → <EXTERNAL_BACKEND>\Youtube AD 存在 → 同層 EXTERNAL_BACKEND 存在 → 回 YT_AD_DEFAULT;
    副本專案(repo 根有 .video_root)改為同層 EXTERNAL_BACKEND 優先,免得在頻道主機器上讀到主的 Youtube AD
    (都不存在時仍回路徑而非 None,讓呼叫端照舊以「檔案讀不到」處理)。"""
    env = os.environ.get("YOUTUBE_AD_ROOT")
    if env:
        return Path(env)
    order = (YT_AD_SIBLING, YT_AD_DEFAULT) if (REPO / ROOT_MARKER).is_file() else (YT_AD_DEFAULT, YT_AD_SIBLING)
    for p in order:
        if p.is_dir():
            return p
    return YT_AD_DEFAULT


TREND_SLOT = {"ChannelA": "", "ChannelB": "c", "ChannelC": "d", "ChannelC": "d"}  # Youtube AD data\trend[_c|_d] 資料夾後綴


def trend_db(channel):
    """Youtube AD 的趨勢資料庫(競品、新聞;唯讀使用:topic_score.py 以 mode=ro 開);依頻道選資料夾。"""
    slot = TREND_SLOT[channel]
    return yt_ad_root() / "data" / (f"trend_{slot}" if slot else "trend") / "trend.db"


def ytad_root():
    """Youtube AD repo 根(context_pack 跑 tools/intel_query.py、讀 data/own 用);環境變數 YTAD_ROOT 優先,
    否則與 trend_db() 同一個根(yt_ad_root())。"""
    env = os.environ.get("YTAD_ROOT")
    return Path(env) if env else yt_ad_root()


def ytad_export_latest():
    """Youtube AD 自有頻道匯出(data/own/export/latest.json;唯讀)。"""
    return ytad_root() / "data" / "own" / "export" / "latest.json"


def ytad_export_dir():
    """Youtube AD 匯出檔資料夾(data/own/export/:latest.json、YYYY-MM-DD.json、channel_latest.json、channel_YYYY-MM-DD.json;唯讀)。"""
    return ytad_export_latest().parent


def ytad_channel_export_latest():
    """Youtube AD 頻道匯出(data/own/export/channel_latest.json;唯讀)。"""
    return ytad_export_dir() / "channel_latest.json"


def ytad_comments_dir():
    """Youtube AD 抓的留言檔目錄(data/own/comments/<video_id>.json;唯讀)。"""
    return ytad_root() / "data" / "own" / "comments"


def topics_file():
    """選題清單與評分結果(topic_score.py 讀寫)。"""
    return ROOT / "channel" / "topics.json"


def topic_cache_dir():
    """搜尋建議詞快取(24 小時內不重查)。"""
    return BUILD / "topic_cache"


def __getattr__(name):
    if name == "DOWNLOADS":
        return downloads()
    raise AttributeError(name)


def build_dir(tag):
    return BUILD / tag


TTS_SUBDIR = {"cosy3": "tts_cosy3"}  # 配音快取子目錄依引擎分開(換引擎不覆寫另一個引擎的快取);其餘引擎 = tts


def tts_dir(tag, engine=None):
    """配音快取目錄:build/<tag>/tts(chattts 等)或 build/<tag>/tts_cosy3。engine=None 時依 build/<tag>/tts_qc.json
    最後一次配音的紀錄判斷(紀錄的 engine 欄位;舊紀錄沒有此欄 = chattts)。"""
    if engine is None:
        import json
        qf = build_dir(tag) / "tts_qc.json"
        try:
            recs = json.loads(qf.read_text(encoding="utf-8")).get("records") or []
        except (OSError, ValueError):
            recs = []
        engine = next((r.get("engine") for r in recs if r.get("engine")), None)
    return build_dir(tag) / TTS_SUBDIR.get(engine, "tts")


def output_dir(tag):
    return OUTPUT / tag


def project_file(tag, name):
    """專案檔:ROOT\\projects\\<tag>\\<name>;那裡沒有而 repo 內有(repo 還沒搬進素材根、或剛 clone)就用 repo 的。"""
    p = PROJECTS / tag / name
    q = REPO / "projects" / tag / name
    return q if q.exists() and not p.exists() else p


def clips_file(tag):
    return project_file(tag, f"clips_{tag}.json")


def speaker(name):
    """音色檔:只給檔名就到 SPEAKERS 找。"""
    p = Path(name)
    return p if p.is_absolute() else SPEAKERS / p.name


def find(path, *bases):
    """輸入檔的相對路徑:依序在 bases(預設 ROOT、REPO)找第一個存在的;都沒有則回傳第一個基準下的路徑。"""
    p = Path(path)
    if p.is_absolute():
        return p
    bases = bases or (ROOT, REPO)
    for b in bases:
        if (b / p).exists():
            return b / p
    return bases[0] / p


def out_file(path, tag=None):
    """輸出檔的相對路徑一律以 ROOT 為基準;只有檔名且給了 tag -> OUTPUT\\<tag>\\<檔名>。"""
    p = Path(path)
    if p.is_absolute():
        return p
    if tag and len(p.parts) == 1:
        return OUTPUT / tag / p
    return ROOT / p


def rel(path):
    """快取簽章用:ROOT / REPO 底下的路徑換成 <ROOT>/... 或 <REPO>/...(正斜線),其餘字串原樣回傳。
    簽章因此不含絕對路徑,素材根或 repo 搬家後快取仍命中。"""
    s = str(path)
    for name, base in (("<ROOT>", ROOT), ("<REPO>", REPO)):
        b = str(base)
        if s[:len(b)].lower() == b.lower() and s[len(b):len(b) + 1] in ("", "\\", "/"):
            return name + s[len(b):].replace("\\", "/")
    return s


TABLE = ("REPO", "ROOT", "RAW", "IMAGES", "ANIM", "BGM", "SPEAKERS", "COSY_REF", "TTS_ENV", "TTS_MODELS", "PROJECTS", "BUILD",
         "OUTPUT", "TMP", "DOWNLOADS")


def _emit(text):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def main(argv):
    def val(n):
        return downloads() if n == "DOWNLOADS" else globals()[n]

    if not argv:
        for n in TABLE:
            _emit(f"{n:<11}{val(n).as_posix()}")
    elif argv[0] == "clips" and len(argv) == 2:
        _emit(clips_file(argv[1]).as_posix())
    elif all(n in TABLE for n in argv):
        for n in argv:
            _emit(val(n).as_posix())
    else:
        sys.exit(f"用法: paths.py [{' | '.join(TABLE)}] 或 paths.py clips <tag>")


if __name__ == "__main__":
    main(sys.argv[1:])
