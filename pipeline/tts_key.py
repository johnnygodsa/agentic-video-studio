"""TTS 快取鍵:不含任何絕對路徑,素材根或 repo 搬家後快取照樣命中(只用標準函式庫)。

.key 檔內容 = "<音檔鍵>|<品管版本>"(edge 沒有品管,只有音檔鍵)
  音檔鍵 = sha1("tts2|引擎|引擎參數簽章|voice|rate|朗讀文字(say 或 text)")
  引擎參數簽章 = 外部合成指令去掉直譯器與 .py 腳本後的其餘參數,其中的路徑只留檔名
               (例:"--spk-pt F_seed_2456.pt";音色檔以檔名識別,換音色請換檔名)
音檔鍵相同 = 同一段文字、同一組合成參數錄的音檔:品管版本變了只需重新檢驗,不必重錄;句編號位移時也靠它搬移。
舊格式(legacy_key)= sha1("引擎|--tts-cmd 全文|voice|rate|文字"),含絕對路徑,只給 migrate_tts_keys.py 對照用。
"""
import hashlib
import re

import tts_pron

KEY_VER = "tts2"
_PATHLIKE = re.compile(r"[\\/]|^[A-Za-z]:")


def _sha1(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def cmd_sig(tts_cmd):
    """外部合成指令(字串清單)-> 引擎參數簽章。"""
    out = []
    for tok in [str(t).strip('"') for t in (tts_cmd or [])][1:]:
        if tok.lower().endswith(".py"):
            continue
        out.append(re.split(r"[\\/]", tok)[-1] if _PATHLIKE.search(tok) else tok)
    return " ".join(out)


def audio_key(engine, sig, voice, rate, say):
    if engine == "chattts":  # 發音修正(tts_pron):含被替換字(助詞「著」等)的句子用替換後文字計鍵,其餘句子的鍵與修正機制出現前相同
        say = tts_pron.key_text(say)
    return _sha1(f"{KEY_VER}|{engine}|{sig}|{voice}|{rate}|{say}")


def full_key(audio, qc_ver=None):
    return f"{audio}|{qc_ver}" if qc_ver else audio


def audio_part(key_text):
    """.key 檔內容 -> 音檔鍵(去掉品管版本)。"""
    return key_text.split("|", 1)[0]


def trim_key(key_text, wav_sha1, trim_ver, final, comma_profile="std"):
    """裁切後音檔(.trim.wav)的鍵:只看音檔鍵與音檔內容,品管版本變動不重轉。
    comma_profile 非 std 時加 |comma=<profile> 後綴(std 時鍵與舊版完全相同)。"""
    return _sha1(audio_part(key_text) + wav_sha1 + trim_ver + ("|final" if final else "")
                 + (f"|comma={comma_profile}" if comma_profile and comma_profile != "std" else ""))


def legacy_key(engine, tts_cmd_text, voice, rate, say, suffix=""):
    return _sha1(f"{engine}|{tts_cmd_text or ''}|{voice}|{rate}|{say}{suffix}")


def legacy_trim_key(key_text, wav_sha1, trim_ver, final):
    return _sha1(key_text + wav_sha1 + trim_ver + ("|final" if final else ""))
