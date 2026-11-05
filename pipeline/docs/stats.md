# stats.py:自製片數據(D3,取代直接開 own.db)

(契約:Youtube AD `PLAN_OWN_DAILY.md` §5 latest.json schema、§6 channel_latest.json schema、D2-7 freshness/refresh API;測試:`pipeline\tests\test_stats.py`)

只讀 Youtube AD 的匯出檔,不開任何 DB、不自己算窗口。匯出資料夾 `paths.ytad_export_dir()`(`<EXTERNAL_BACKEND>\Youtube AD\data\own\export\`):`latest.json`(自製片)、`YYYY-MM-DD.json`(日期副本)、`channel_latest.json`(三頻道:自製/非自製片、基準、競品)、`channel_YYYY-MM-DD.json`。`--export-dir` 可覆寫。

## 指令(`python -X utf8 pipeline\stats.py ...`)
| 指令 | 內容 |
|---|---|
| (無參數) | 總覽 ≤60 行:資料時間、發布 ≤28 天自製片的觀看/48h/7d/CTR/均看%(`~` = 近似窗口) |
| `--tag <tag\|video_id>` | 單片:最新快照、48h/7d/28d 窗口與 basis、頻道常見範圍、流量來源、抓取健康 |
| `--stale` | 只印異常:非當天、缺當天快照、alerts、連續失敗、窗口無快照 |
| `--channel <名>` | 該頻道自製/非自製基準(中位[Q1~Q3])+ 近期自製與非自製片 |
| `--channel <名> --compare` | 規劃新片用:自製近期片對同片長自製基準位置(年齡 <7 天標「未滿7天」)+ 非自製近期片 + 競品熱門 |
| `--channel <名> --rivals [N]` | 競品熱門前 N(預設 10);ChannelC選題關閉,固定無資料 |
| `--review <tag>` | 逐日曲線(各日期副本的最新快照)、窗口值、對同片長自製基準的位置(首7天觀看/均看/CTR)、當初計畫(spec.json package)vs spec.result |
| `--review --channel <名> --days N` | 頻道期間內自製片檢討表(預設 28 天) |
| `--ensure-fresh` | 加在任一查詢前:先確保當天數據(見下);失敗只在第一行標警示 |
| `--hook` | SessionStart 用,見下 |

訂/千(每千觀看淨訂閱 = subs_net ÷ views × 1000,2 位小數;views<1000 或 subs_net 為 None 印 `-`):`--channel` 基準段後印「訂閱/千(合計|中位|n)」三行,自製/非自製 × ≤90 天/>90 天歷史(只算可算的片;合計 = Σsubs÷Σviews×1000);`--tag`/`--review <tag>` 訂閱後加 `(x/千)`、review 多一行對同期自製/非自製合計;`--compare` 自製行、`video_lines`、`--review --channel` 表各加「訂/千」欄。單片 |淨增|<5 值後加 `*`,輸出末附一次「* 淨增<5 人,樣本小不下結論」;跟同期基準比,單片不下結論。

頻道名認得:ChannelA/ChannelA、ChannelB/ChannelB、ChannelC=ChannelC(以 slot `''`/`c`/`d` 對應,不比對顯示名)。

## 輸出第一行
一律印資料時間。當天(generated_at 為今天且 `summary.missing_today_snapshot` 為空)→ `資料時間 X(快照最舊 Y) | 當天數據,無缺快照`;否則 `⚠ 數據非當天:資料時間 X、缺 N 支(tag…)`。計畫文件開頭要抄這個資料時間;標「非當天」時註明哪些判斷依據舊數據。

## --ensure-fresh 流程(不擋規劃)
1. `GET /api/own/freshness`(後端網址同 `yt_queue.base_url()`,`YT_QUEUE_URL` 可改)。連不上 → 背景 `run.bat autostart`(Youtube AD 根;8000 已有人會自己結束),每 5 秒查,最多等 2 分鐘。
2. `fresh` 為真 → 結束。否則 `POST /api/own/refresh`(`blocked` 且沒有 Job = Chrome 拉不起來 → 放棄),每 30 秒查 freshness,最多 20 分鐘。
3. 任何失敗:照用現有匯出檔,第一行標非當天並附原因。

## --hook(`.claude\settings.json` SessionStart)
freshness 1 秒逾時;後端沒開 → 背景 `run.bat autostart`;非當天 → 背景行程 `stats.py --bg-refresh` 送 POST refresh,不等待。輸出 4 行(`HOOK_CAP`):資料時間 / 當天與否與缺幾支 / 刷新或啟動狀態 / `[回溫] ChannelA N 支(片名前 12 字 ×倍數…) ChannelB M 支`(無命中印 `[回溫] 無`,同時覆寫 `channel
ebound.json`,失敗只警告)。任何例外只印一行警告,結束碼 0。

## 與 feedback.py 的關係
`feedback.py --due`(寫 `channel\outcomes.jsonl` 特徵+成效、`feedback_report.py` 出 `成效分析.md`)已改讀 latest.json(2026-10-26),與本檔同源,仍保留(docs/feedback.md);`paths.own_db()` 已刪,`spec_check` 的判語 14 天檢查改讀 `channel_latest.json`。

## topic_scout(選題會議資料收集;`pipeline	opic_scout.py`,測試 `tests	est_topic_scout.py`)
`python -X utf8 pipeline	opic_scout.py --channel <頻道> [--date YYYY-MM-DD] [--out 路徑]` → `tmp\scout_<頻道>_<日期>.md`(頻道名統一成 ChannelA/ChannelB/ChannelC),印路徑與各節筆數。0 token、唯讀;每節首行寫資料 as_of,缺資料寫明原因、不中止(例外也轉成該節「不可用:…」)。規格 channel\_archive\plans\PLAN_流程嚴謹化_2026-10-29.md §1.1。
- a 自製近 14 天:直接呼叫 `stats.cmd_channel(compare=True)`,與 `--compare` 輸出同源。
- b 回推偵測:用 `channel_YYYY-MM-DD.json` 日期副本 + `channel_latest.json` 每支影片的 `views_total`(以 `my_daily_last` 去重)相鄰差分成逐日觀看(間隔多日按天平均補值,列尾註「含補值」)。涵蓋自製與非自製片(舊搬運片也會被推)。**年齡 > 7 天,兩條觸發任一成立即列「回推」**:①單日爆量 = 最新日 ≥ 3× 前 7 日逐日中位且 ≥ 100(前段 ≥ 4 天才判);②緩升 = 近 7 日合計 ≥ 1.5× 前 7 日合計且近 7 日日均 ≥ 100(前 7 日合計:逐日滿 7 天用逐日,不足時用匯出檔 `views_7d` 在 7 天前那份的值,標 `[逐日]`/`[views_7d]`)。每列寫觸發類型、發布日、最新日/中位/倍數、近 7 日/前 7 日合計;自製片附 latest.json `traffic_source` 前 3,非自製寫「無來源資料」。另列「未達門檻、近 7 日合計升幅前 5」只排名、不算回推。最新日是 `my_daily_last`(比匯出日晚約 3 天)。2026-10-29 實測 9W0UMS-8878 緩升 1.53×(41,762 / 27,256),緊貼門檻。
  - **2026-11-03 起**:逐日序列優先讀 `channel_latest.json` 每支影片的 `views_daily`(近 35 天 `[[日期,views]]`,Y 的 XREQ R1;沒有該欄位時退回上述日期副本差分,缺的日子補 0),門檻不變;另讀 Y 的 `data\own\latest_activity_<a ChannelA|b ChannelB>.json`(匯出資料夾上一層,不存在就略過):片齡 > 7 天且 `views_48h` ≥ max(500, 前 7 日日均×2×3) 也算命中(來源標「最新活動」)。
  - 核心 `topic_scout.detect_rebound(channel, activity, fallback)`,hook 與選題會議共用;命中覆寫 `channel
ebound.json`(`generated_at` + `hits`:video_id/title/kind 自製|搬運/age_days/week_ratio/max_day_ratio/source/channel…;不寫 board.json)。測試 `tests	est_rebound.py`。
  - **流量來源占比(Y 的 XREQ R8,2026-11-05)**:latest.json 每片若有 `traffic_7d`(發布後 7 天內各來源觀看數 dict:BROWSE/SUGGESTED/SEARCH/EXTERNAL/NOTIFICATION/OTHER + `captured_at`)或 `traffic_recent`(回溫偵測時補的近 7 天同欄),`stats.py --tag` 在「流量來源」後多印「7d 來源:瀏覽 x% 推薦 y% 搜尋 z% …(擷取日)」/「近7日來源:…」(占比、0 不列);`topic_scout` b 節命中列同樣附這行;`rebound.json` 每筆有才帶 `traffic_recent`/`traffic_7d`(原 dict,取自 latest.json 同 video_id)。沒有欄位一律照舊、不印。函式 `stats.traffic_mix/traffic_lines`;測試各在 `test_stats.py`/`test_rebound.py`/`test_topic_scout.py`。
- c 留言訊號:該頻道最近 5 支有留言檔的自製片(`data\own\comments\<id>.json`):`summary.by_flag`(缺則用 `comment_lexicon.json` 詞表)、讚前 5 原句(≤80 字)、旁白/配音抱怨 = AI 旗標數;沒留言檔的 tag 列在首行。
- d 競品與新聞:子行程 `intel_query.py opportunities --slot main|c --limit 10`(前 10 行)與 `trend_emerging.py --slot <slot> --top 10`(含表頭 12 行);失敗或逾時(120s)該節寫「不可用:<錯誤一行>」。ChannelC無 intel_query slot,固定不可用。
- e Studio:`tmp\studio_<日期>.txt` 存在則附原文 ≤80 行,否則寫「未讀 Studio(手動:Chrome 讀 tab-research 與即時 48h)」。
- 常數(檔頭):`BACK_RATIO=3`、`BACK_MIN_VIEWS=100`、`BACK_MIN_AGE_DAYS=7`、`BASE_DAYS=7`、`MIN_BASE_DAYS=4`、`SLOW_RATIO=1.5`、`SLOW_MIN_DAILY=100`。

## audience_model(觀眾模型統計,channel\_archive\plans\PLAN_流程嚴謹化_2026-10-29.md §3;測試 `pipeline	ests	est_audience_model.py`)
`python -X utf8 pipelineudience_model.py --channel <ChannelA|ChannelB> [--update]`,0 token,來源全唯讀 → `channeludience\<頻道>_comments.jsonl` 與 `<頻道>_stats.md`(personas.md 由主對話從 stats 寫,程式不產)。
- 來源(固定順序,去重時先到先留):`ytad` Youtube AD `data\own\comments\*.json`(own_comments dict)→ `ref_own` comments_ref 內 own 格式 → `ref_info` `*.info.json`(yt-dlp,競品)→ `ref_list` `*.comments.json` 純陣列(yt-dlp,競品;標題取同名 info.json)。`comments_all.md` 是摘要表(讚數混在敘述儲存格),不穩定,略過並在 stats 註明。
- 頻道歸屬:自製片取檔內 channel;競品取專案 tag 的頻道(`outcomes.jsonl` > `projects\<tag>\spec.json` > `board.json`;「ChannelA/ChannelB」併為「ChannelA/ChannelB」)。歸不到的略過並計數。
- 去重鍵 video_id + 作者 + 前 40 字(同鍵讚數取大)。jsonl 欄位:video_id、tag、is_own、like、text、flags、axis、captured_at、author、title、src。
- 旗標/軸向:`comment_lexicon.json`(flags + flag_order/video_axis/game_axis/video_implied_flags,後四項抄自 Youtube AD 詞表;演算法等同 `backend\comment_flags.classify`,不 import 那邊)。啟發式,精度未驗證。
- stats.md:首行 as_of(來源最大 captured_at,不用當下時間,所以重跑同結果)與 n;來源筆數;by_flag(全部/自製/競品,可複選);讚前 50(自製、競品分列);bigram 前 50(中文 2 連字、簡繁併為繁體、去停用字);按切角(outcomes 的 angle,空退 title_angle)讚數加權正負比(詞表啟發式,僅自製片);旁白/配音相關原句與「資訊錯誤」原句(自製片全部)。
- `--update`:另外保留既有 jsonl 中來源檔已消失的列;不加則由來源完整重建。兩者重跑皆冪等。
- `--hook`(SessionStart,`.claude\settings.json` 第三條):兩頻道各 `--update`(執行緒並行,總時限 10 秒,超時印「略過」不擋開工;檔案先寫 `.tmp` 再換名),只印 1 行 `[觀眾] ChannelA n=5653(+0) ChannelB n=5614(+0);人設 ChannelA OK/過期 ChannelB OK/過期`;任何錯誤只警告,結束碼 0。
- `persona_status(channel) -> dict(status, n_now, n_persona, reason)`(hook 與 `topic_scout.py` 開頭「人設狀態」節共用)。人設檔 `channel\audience\<頻道>_personas.md` **第 1 行**固定:`<!-- persona_meta: {"as_of":"2026-10-29","n_own":479,"n_all":5653,"angles":["判"]} -->`(n 取 stats 檔頭;`angles` = 人設寫時已涵蓋的切角代號,重寫人設時一併更新)。過期條件任一:檔不存在、無/讀不懂 persona_meta、as_of 超過 90 天、自製 n ≥ 人設 n_own×1.3(n_own=0 時改為 n ≥ 200;未達 200 則標樣本不足、仍過期)、`outcomes.jsonl` 該頻道近 30 天的 `angle`/`title_angle` 代號不在 `meta.angles` 裡(meta 沒有 angles 鍵才退回比對人設正文)**且該代號的片留言已在 `<頻道>_comments.jsonl`** → reason 寫「新切角:<代號>」;片留言還沒抓則不算過期,reason 附「切角 X 的片尚無留言檔:結案 24h 抓後再更新」。n_own=0 且自製 n<200 一律過期,reason 附「樣本不足」。
