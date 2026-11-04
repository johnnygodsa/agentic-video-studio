r"""配音引擎比武 IndexTTS2 vs CosyVoice3(channel/_archive/plans/PLAN_工具升級_2026-10-26.md T1)、BreezyVoice vs CosyVoice3(2026-11-04,docs/tts.md §4.2)。只比武、出報告,不接進出片流程。

入口:python pipeline\run.py tts_bakeoff/cli [--suite breezy] <probe|corpus|smoke|synth|judge|report> [--dry-run] ...(用法見 cli.py 檔頭)
  metrics.py           指標純函式(CER、拼音 CER、多音字讀對率、時長誤差、成對 bootstrap 區間、證據強度)
  corpus.py            語料抽樣(最近 5 支片 build\<tag>\tts_qc.json 各 60 句)
  engines.py           跨環境合成:常駐子行程客戶端(cosy3_worker / indextts2_worker 同一套 @@READY/@@RES 協定)、顯存取樣
  report.py            tmp\tts_bakeoff\report.md 與 listen.md
  indextts2_worker.py  IndexTTS2 常駐子行程(tts_env_indextts2 執行)
  breezy_worker.py     BreezyVoice 常駐子行程(tts_env_breezy 執行;breezy / breezy_ann 兩變體共用)
工作檔一律在 tmp\tts_bakeoff\,不寫 build\ 快取;不動快取鍵、QC_VER、KEY_VER。
"""
