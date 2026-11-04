# pipeline 程式地圖(入口)

給代理用:這份只說「哪個檔做什麼、做哪件事讀哪份文件」。行號不寫在文件裡,找函式用 `python -X utf8 pipeline/tools/funcmap.py --grep <函式名>` 或 Grep `^def <名>`(全表在 `docs/funcmap.md`,自動產生)。
路徑一律由 `paths.py` 取得(`python pipeline/paths.py ROOT` 可印素材根)。啟動:`python pipeline/run.py <腳本名不含.py> [參數]` = 用配音環境 python(`-X utf8`)在 repo 根執行。

## 1. 各檔用途
共用:
- `director.py` 每支片的 production.json(init/status/log/intervene/feedback/brief)與 `run`(A→E 串接、每段評 gate、卡點記 blocks);`director_ab.py` A→B4 步驟與 C 段改句(B 段 `brief.flow:"v3"` 走寫稿員自檢 + 合併審稿 review 步,見 `docs\director_ab.md` §5「flow v3」);`llm.py` `claude -p` 函式層(call/call_escalating);`gates\` 各段 gate 與 `specs.py` 片型規格、SPEECH_CPM;規格 `docs\director.md`、`docs\director_ab.md`
- `video_cost.py <tag> [--json]` / `--all [--since YYYY-MM-DD]` 每支片 token 與占上限 %(director llm_calls + Claude Code 主對話/子代理逐則歸屬,依 `director.MODEL_W` 加權;有快照時以「占週上限 %」為主、顯示「中文短名(tag)」);`--snap --h5 N --h5-reset ISO --week N --week-reset ISO [--fable N]` 由主對話把 get_usage 讀到的官方百分比寫進 `channel\usage_snapshots.jsonl`(校準:每 1% = 多少 w);`--now` 一行印最新快照與自快照後估計用量;`--all` 寫 `channel\token_ledger.md/.json`;中文名 `channel\tag_names.json`(director brief 有 topic 且無此 tag 時自動補);規格 docs\director.md「session」列、video_cost.py 檔頭
- `paths.py` 所有路徑(ROOT/RAW/IMAGES/ANIM/BGM/BUILD/OUTPUT/TMP/TTS_ENV…)、`build_dir(tag)`、`output_dir(tag)`、`clips_file(tag)`、`speaker(name)`、`find()`、`downloads()`
- `senses\` 感官層(耳朵 E1/E2/E3 等;E3 = `ear_e3_gemini.py` Gemini 逐句審聽):做法、指令、官方文件查證見 `docs\senses.md`
- `run.py` 啟動器;`build.py` 主程式(配音→鏡頭→渲染→合成);`script_txt2json.py` script.txt→script.json
- `tts_chattts.py` ChatTTS 合成+全套品管(由 build 以子行程呼叫);`tts_pron.py` 發音修正表;`tts_split.py` 一行多句拆子句;`tts_pause.py` 句中停頓量測/修整、辨識字詞時間對回原文(字幕分段時間用);`tts_tail.py` 溫和裁靜音與句尾硬切偵測;`tts_key.py` 快取鍵(不含路徑);`tts_report.py` 句間停頓診斷;`listen_page.py` 配音聽審頁(docs/build.md §9.1);`tts_polyphone.py` 破音字誤讀偵測(docs/tts.md §4);`tts_cosy3.py` + `cosy3_worker.py` + `tts_cosy_text.py` + `cosy_pron.json` / `cosy_terms.json` CosyVoice3 引擎(make_version `--engine cosy3`,docs/tts.md §4.1);`tts_bakeoff/` 配音引擎比武 IndexTTS2 vs CosyVoice3(只比武不接入,docs/tts.md §4.2)
- `senses/` 感官層(PLAN_工作室v2 §6.3):`senses/ear_e1_pilot.py` E1 全標注 pilot(table vs all 送引擎文字與多音字來源統計,不合成);開關 `COSY_ANNOTATE=all` / `make_version --annotate all` / `tts_dispatch --annotate all`(預設 table = 現行),docs/tts.md §4.7
- `script_lint.py <tag>` 文案 AI 感檢查(報幕句、不是A是B、書面轉接、排比對仗、語助詞密度與唸不出的語助詞、第一人稱、句長變異;2026-10-26 加旁白連貫五組警告 SOURCE_LEAD/REPORT_RATIO/CLAUSES/NUMS/CHAIN_BREAK,docs/build.md §3.1;2026-10-28 加判決腔硬擋 VERDICT;規則與常數在檔頭);寫完文案、進配音前跑,超標 0 才過(v2 2026-10-20:新增重講/代稱/暖場等 7 組警告,不中止,`--strict` 才算超標;門檻在檔頭 `T`;細節 docs/build.md §3.1);`style_metrics.py --tags|--all` 文體指標
- `taste_run.py [--case T02] [--json] [--audio] [--scan N]` 口味回歸(channel	aste 46 案:壞例抓得到、好例不誤報;結果 pass/fail/llm/audio/gap,gap 不算 pass,有 fail 結束碼 1;假片只在 tmp	aste\;2026-10-31 補的檢查:script_lint OPEN_LOAD/PRONOUN_FIRST/PRICE_TWD/PLAYED_CLAIM、freeze.py `--alias-ok` 別名閘門、deliver.py 改版封面標題警告與使用者自排時間擋下;docs/build.md §3.1)
- `speakable.py <tag> [--json] [--explain]` 可唸性預檢(未登錄英文、記憶 bad、backlog、易錯字未覆蓋、英文/數字密度、句長;門檻依實測,docs/speakable.md);`line_fix.py <tag> --lines 12,15 --reason "…" [--mode lint|qc|speak] [--dry-run]` 一批句子一次 LLM 改寫、機器硬驗(數字/hl/標籤與行尾 json 不動、lint 與可唸性 err 0)才原子寫回,已凍結拒絕;`script_lint.check_sentences(tag, line_nos)` 句級 lint 子集(規格 docs/director_ab.md §5/§7/§8)
- `anim_lib.py` 動畫繪製函式庫(emoji/轉場/timeline/puzzle/stamp/span/bars/list/versus/flow/星座背景);`anim_make.py` 一次產生 anim/ 素材庫(emoji、轉場 .mov;與新類型無關);`anim_preview.py` 預覽 versus/flow/list/timeline/bars
- `assets_lib.py` 截圖/圖片共用(字型、換行、`Page`、OCR、`save_boxes`、`add_label`)
- `gpu_lock.py` 全機 GPU 鎖(依 publish 排隊、共用 `gpu_used_mib`);`freeze.py` 文案凍結(2026-10-26 起只鎖配音文本 narration_sha,畫面欄位可改;`make_version --tts-review --freeze` 自動凍結);`board.py` 共用進度板 `channel/board.json`/`board.md`(階段 A資料→B文案→C配音→已凍結→D畫面→E自審→已排程→改版→結案;docs/build.md §9.3)
- 資料驅動寫稿(2026-10-26,channel\_archive\plans\PLAN_文案資料驅動_2026-10-26.md §2–§3):`context_pack.py --tag --channel [--event|--query]` 寫稿上下文 → `projects/<tag>/context.md|json`(呼叫 Youtube AD `intel_query.py brief`;留言分群用 `comment_lexicon.json`;docs/context_pack.md);`pace.py` 語速常數(330 字/分、5.5 字/秒,lint 共用);`script_structure.py <tag>` 結構檢查(開場型態、判斷秒、塊與梯子、最強證據位置、CTA、結尾、字/分與事實/分 → `build/<tag>/structure.json`;docs/structure.md);`facts_lib.py`/`facts_check.py <tag>` 事實核對表解析與逐句連結(行尾 json `f`;docs/facts.md);`retention_align.py --tag` 留存曲線對句(docs/retention.md);`feedback.py --due` + `feedback_report.py` 成效回填與分析(`channel/outcomes.jsonl`、`scorecard.md`、`成效分析.md`;docs/feedback.md)
- `stats.py` 自製片數據(讀 Youtube AD 匯出檔 latest.json / channel_latest.json / 日期副本,不開 DB):總覽、`--tag`、`--stale`、`--channel [--compare|--rivals]`、`--review`、`--ensure-fresh`、`--hook`(SessionStart);規格 docs/stats.md
- `topic_scout.py --channel <頻道> [--date]` 選題會議資料收集(0 token、唯讀):自製近 14 天、回推偵測(舊片被演算法推)、留言訊號、競品與新聞、Studio → `tmp\scout_<頻道>_<日期>.md`;規格 docs/stats.md「topic_scout」
- `audience_model.py --channel <頻道> [--update]` 留言彙整成觀眾模型(0 token,來源唯讀:comments_ref、Youtube AD data/own/comments)→ `channel/audience/<頻道>_comments.jsonl` + `_stats.md`(旗標、讚前 50、bigram、切角正負比、旁白/資訊錯誤原句;docs/stats.md「audience_model」)
- `qa_sheet.py` 成片總覽圖(每 N 秒一格);`yt_queue.py` 後端佇列客戶端;`deliver.py` 複製完整版到 `paths.yt_inbox()`(下載\V,Youtube AD 的影片資料夾)並寫同主檔名 `.claude.json` sidecar;`deliver_preview.sh` 任何片的 720p 預覽(< 29 MB 兩段式);`re9_deliver.sh` re9 專用版(含 bgm 對照)
- `shorts_build.py` Shorts 一個指令出片(F2-3b,母片句子 -> 工作 tag `<tag>_<id>` 直式成片 + QA + 說明檔骨架,docs/build.md §9.2);`deliver.py --shorts` 交付直式成片(sidecar 加 `"shorts": true`,不可搭 `--enqueue`)
- `re9_notes.py` 產交付說明 v*_notes.md(`--specs` `--img-prefix` 可換片,實際為共用);`ocr_win.ps1` Windows OCR(Windows 預設引擎;`OCR_ENGINE=rapid` 改用 RapidOCR,見 docs/assets.md);`migrate_tts_cache.py` / `migrate_tts_keys.py` 一次性快取搬移(舊片用)
舊片專用(新片不要改,複製其做法):
- **新片截圖用 `news_lib.py` + `news_specs.py`(見 docs/assets.md「新片截圖」)**;以下 `assets_*_news/specs/clips` 與 `assets_*_crop` 一律標 **legacy**(新片改用 news_lib / news_specs / clips_lib,舊檔不刪不改,僅供舊片重跑與參考)。`assets_re9_clips.py` / `assets_re9_news.py` / `assets_re9_specs.py`(RE9)。注意 `assets_re9_news.py` 含共用的截圖引擎(JS_PREP/JS_DARK/compose/capture),其他截圖程式 import 它
- `assets_wow_clips.py`(含共用的片段建檔/檢查邏輯)/ `assets_wow_news.py` / `assets_wow_specs.py`(《永恆》第一支;`disc` 為暴雪論壇 Discourse 規格工廠)
- `assets_wowi_clips.py` / `assets_wowi_news.py` / `assets_wowi_specs.py` / `assets_wowi_crop.py`(G 團訪談片,最新範例)
- `assets_dei_clips.py`(dei 片段,另有 `--overview` 每來源總覽圖)/ `clip_scan.py`(OCR 走 `assets_lib.ocr_batch`;`ocr_batch.ps1` 只在引擎為 win〔Windows 預設〕時用;`ocr_compare.py` 比兩引擎;程式篩片段:每秒一格,亮度+OCR 剔除黑/字卡/字幕,輸出乾淨區段;`--dark` 調暗門檻;`scene_cuts(src)` 用 ffmpeg scene 分數 > `SCENE_THR` 0.3 偵測整支來源的硬切,快取 raw/<src>.cuts.json,`assets_wow_clips.build()` 把片段內的硬切存進各片段的 `cuts`)
- B4 讀音確定性化(flow v3,docs/director_ab.md「B4 v3」):`pron_pre.py <tag> [--json]` 由 tts_script.json + sub_scan.json 算確定性候選(接縫/多音/英文/backlog,附 lookup 與該字規則,接縫單一 token 自動寫詞表);`pron_apply.py` 把 pron-review 回的結構化決定只新增地寫進 pron_rules/cosy_pron/cosy_terms/sub_words(驗 token、原子寫、自驗還原)
- 配音稿與讀音審(2026-10-29,docs/tts.md §4.5):`tts_script.py <tag> [--verify] [--no-words]` 配音稿 `build/<tag>/tts_script.md` 與每片詞表 `words.txt`(`seg.set_tag` 載入);`pron_backlog.py` + `pron_backlog.md` 常讀錯字累積表;`tts_moe.py lookup|--polyphones` 教育部讀音(`moe/`);`pron_memory.py` + `pron_memory.json` 語境讀音記憶、`tts_c0.py <tag>` C0 風險句試配(docs/tts.md §4.6)
- 感官層 `senses/`(PLAN_工作室v2 §6.3):`ear_e2.py` 聲調偵測(每字估聲調、多音字期望比對;`ear_e2_align.py` 對齊、`ear_e2_tone.py` 特徵與訓練、`ear_e2_eval.py` 評估;docs/senses.md「E2」)
- `sub_scan.py`(字幕檢查,不渲染:`run.py sub_scan --tag <tag>` 列出把詞切開的接縫;加 `--sync` 列出字幕段起點與語音相差 > 0.15 秒的段,需要配音快取)/ `sub_words.txt`(字幕拆段不可切開的自訂詞,一行一詞;jieba 詞典沒有的詞加在這裡;`--seg jieba|ckip` 與 `sub_seg_compare.py` 見 docs/build.md 可切換斷詞器)

## 2. 做哪件事讀哪份
| 任務 | 讀 | 常用指令 |
|---|---|---|
| 改 build / 渲染 / 鏡頭排程 | docs/build.md §2(build.py 各子節) | `python pipeline/run.py build --tag <tag> ...`;常用序列見 §7 |
| 文案轉檔(script.txt -> json) | docs/build.md §3 | `python -X utf8 pipeline/script_txt2json.py <tag>`;`python -X utf8 pipeline/script_lint.py <tag>`;句畫檢查與逐句畫面表 `python -X utf8 pipeline/visual_check.py --tag <tag> --table`(docs/build.md §3.2) |
| 配音與品管 | docs/tts.md §4 | 由 build 以子行程呼叫 `tts_chattts.py`;`tts_report.py`、`tts_polyphone.py` 診斷 |
| 遠端配音調度(C 段;不帶 --prefer 只印三後端狀態,使用者選後再跑) | docs/tts.md §4.3–§4.4;規則 0_流程 §6 | `python -X utf8 pipeline/tts_dispatch.py <tag> --prefer colab\|kaggle\|local [--dry-run]`;`--status`;Kaggle `pipeline/remote/kaggle_run.py`;Colab `pipeline/colab/pack_for_colab.py`、`colab_tts.ipynb` |
| 語境讀音記憶、C0 風險句試配(全片配音前) | docs/tts.md §4.6 | `tts_env_chattts\Scripts\python.exe -X utf8 pipeline/tts_c0.py <tag> [--dry-run]`;`python -X utf8 pipeline/pron_memory.py lookup\|add\|list\|check` |
| 自製動畫(清單/長條圖/時間軸等) | docs/anim.md §5;設計規格 ANIM_DESIGN.md | `python -X utf8 pipeline/anim_preview.py ...` |
| 新片網頁截圖 | docs/assets.md「新片截圖」(news_lib / news_specs) | 複製 `assets_TEMPLATE_news.py` 為 `assets_<簡稱>_news.py`,填 SPECS 與 HL;`--check` 通過才用 |
| 新片影片片段 | docs/assets.md「clips_lib.py」節 | `clips_lib.py`、`clip_scan.py`、`clips_screen.py`;片段標籤檔 `projects/<tag>/clips_<tag>.json` |
| 動畫科普片(ChannelC) | docs/sci.md §10 | `python -X utf8 pipeline/sci/make_film.py --tag <tag> --ver <ver>`;`sci/make_thumb.py` 做封面 |
| spec(標題封面規格) | docs/spec_topic.md §11 | `spec_check.py --tag <tag>`;選題改走 Youtube AD `intel_query.py opportunities/brief`(topic_score/topic_scan 已於 2026-10-26 刪除) |
| 寫稿上下文 / 結構與事實檢查 / 留存對句 | docs/context_pack.md、docs/structure.md、docs/facts.md、docs/retention.md | `python -X utf8 pipeline/context_pack.py --tag <tag> --channel <頻道> [--event <id>]`;`script_structure.py <tag>`;`facts_check.py <tag> [--write-spec]`;`retention_align.py --tag <tag>` |
| 看數據 / 規劃前比較 / 檢討 | docs/stats.md | `python -X utf8 pipeline/stats.py`;`--ensure-fresh --compare --channel ChannelA`;`--review <tag>` |
| 發片回饋 | docs/feedback.md | `python -X utf8 pipeline/feedback.py --due`;`feedback_report.py` |
| 一個指令出一版 | docs/build.md §9(make_version、shorts_build、listen_page) | `python -X utf8 pipeline/make_version.py ...`;`shorts_build.py` 出直式 |
| 多 session 排 GPU、文案凍結、進度板 | docs/build.md §9.3(gpu_lock、freeze、board) | `python -X utf8 pipeline/gpu_lock.py status`;`freeze.py <tag>`;`board.py show` |
| 交付 | docs/build.md §9;CLAUDE.md「路徑與檔案」 | `python -X utf8 pipeline/deliver.py --tag <tag> --ver <ver> --title ...` |

## 3. 代理守則
- 只讀任務需要的那一節(docs/ 下對應檔的對應章節),不整份讀。
- 大檔(build.py 約 4 千行)先用 funcmap `--grep` 或 Grep `^def <名>` 定位,再用 Read 的 offset/limit 讀行範圍。
- 產物 json(timeline.json、tts_qc.json、clips_*.json)不整檔 cat,只印筆數與異常項。
- 能平行的工具呼叫一次發。
- 改了程式不必更新行號(`docs/funcmap.md` 重跑 funcmap.py 即可),但要更新對應 docs 章節的欄位與指令說明。
