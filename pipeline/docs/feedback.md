# 回饋閉環:feedback.py、outcomes.jsonl、feedback_report.py

(契約:channel\_archive\plans\PLAN_文案資料驅動_2026-10-26.md §3.8;測試:`pipeline\tests\test_feedback_outcomes.py`)

## 指令
- `python -X utf8 pipeline\feedback.py --due [--export <latest.json>] [--min-age-h 72] [--dry-run]`
  讀 Youtube AD 匯出 `data\own\export\latest.json`(路徑:`paths.ytad_export_latest()` 若有,否則由 `paths.trend_db` 推導;`--export` 覆寫)。
  處理 `is_self`、`deleted_at` 為空且 `age_hours >= min-age-h` 的片(沒有 `projects\<tag>\` 的舊片也入庫,特徵欄 null;匯出已刪除的片從 outcomes 清掉,清前備份到 `tmp\outcomes_backup_*.jsonl`);每支一行寫 `channel\outcomes.jsonl`(鍵 video_id,重跑覆蓋該行,整檔依 published_at 排序重寫),再由 outcomes 重寫 `channel\scorecard.md`。`--dry-run` 只印不寫。
- `python -X utf8 pipeline\feedback.py --video <id> [--tag <tag>] [--angle A1] [--plan 1]`
  單片(走同一條路徑,不看 min-age,未到期窗口為 null);`--angle`/`--plan` 手動補,不給就沿用 outcomes 該行原值;有 `--tag` 且有 spec.json 時把成效寫回 spec 的 `result`。`--angle/--plan` 不再必填。
- `python -X utf8 pipeline\feedback_report.py [--outcomes channel\outcomes.jsonl] [--out channel\成效分析.md] [--channel-export <channel_latest.json>]`

## outcomes.jsonl 欄位(缺資料一律 null,不估算)
| 欄位 | 來源 |
|---|---|
| channel、slot、tag、video_id、title、published_at、is_self、age_hours | latest.json |
| publish_mode | latest.json,缺 -> `unknown` |
| duration_s、duration_bucket(<5分/5-8分/8-12分/>12分) | latest.json |
| weekday(0=週一)、hour | published_at 轉台北時間 |
| subject、title_angle | spec.json `package.subject[0]`、`package.titles[0].angle` |
| event_id | spec.json `event_id`,缺則 context.json |
| competitor_videos_7d、same_event_seq | `projects\<tag>\context.json`(遞迴找同名鍵) |
| hook_type、judge_sec、blocks、chars_per_min、facts_per_min | `build\<tag>\structure.json`(別名:opening_type、first_judgment_s;blocks 為 list 取長度) |
| facts_link_pct | `build\<tag>\facts_check.json`(link_pct/facts_link_pct;0–1 會 ×100) |
| thumb_plan、angle、note | `--due` 自動帶入:spec.json package 第 1 標題切角 / 第 1 封面方案,沒有再從 handoff.md 撈「切角 X」「方案 N」;note = handoff.md / brief.md 的「預失敗:…」那行。手動 `--plan`、`--angle` 覆蓋;已有舊值重跑沿用 |
| perf.{48h,72h,7d,latest}.{views,impressions,ctr_pct,avg_view_pct,subs_net,browse_pct,basis,age_hours} | windows / latest;browse_pct 缺就是 null(SUBSCRIBER 是首頁動態不是訂閱者,不代填);匯出沒有 72h 窗口則 `perf.72h` 為 null |
| primary_window | 72h -> 7d -> 48h,第一個有數據者 |
| retention_30s_pct、retention_curve_n | 留存曲線 [[位置%,留存%]] 在 30/duration_s×100 線性內插;超出曲線範圍或無 duration -> null |
| comments_flags | comments.flags |
| ab_mode、ab_status、ab_winner_idx | latest.json 每片 `ab`(Youtube AD PLAN_AB測試 §2.2;mode=title/thumb/both、status=running/winner/same/inconclusive/stopped/not_set/unknown;stopped=使用者手動停止、winner_idx 為 null、占比可能有);**缺 `ab` 鍵一律 null** |
| ab_versions | `ab.versions` 每版本保留 idx/title/thumb/share_pct/label/is_current,加 `title_angle`(spec `package.titles[idx-1].angle`)、`thumb_plan`(= idx;title 模式為 1)、`name_start`(標題以 spec subject 之一開頭)、`cover_angle`(spec `package.covers[idx-1].angle`,無則同序標題切角)、`cover_kind/gesture/color`(`channel\cover_persona_log.jsonl` 該 tag+plan 最後一筆)、`cover_layout`(spec covers 有 layout/版型才有);查不到為 null |
| fetched_at | 本機時間 |

## scorecard.md
表頭單一版本:發布、頻道、tag、video_id、標題、切角、封面、鉤子、判斷秒、標題切角、A/B,接 48h/7d 各 7 欄(匯出沒有 72h,不顯示)(觀看、曝光、CTR%、均看%、瀏覽%、非訂閱%、訂閱)。「未到期」/「無快照」/「無資料」意義同舊版。A/B 欄值:`封面#2 勝 41%` / `標題#1 勝 38%` / `合測#N 勝 x%` / `相同` / `無法判定` / `進行中` / `未設定` / `—`(無 ab 或 unknown)。改版前寫入、video_id 不在 outcomes 的舊列,原樣放在檔尾「舊格式列」節(連同其原表頭),不丟。

## 報告規則(feedback_report.py)
- 只用 is_self、不含已交出的ChannelC;每一節 = 同頻道 × 同片長帶(≤10 分 / >10 分);指標固定取 7d 窗口的曝光、CTR、均看%,加 30 秒留存、訂閱/千次觀看(沒有 7d 數據的片不進分層表)。
- 因子表:hook_type、judge_sec 帶(≤15/15–30/>30)、title_angle、thumb_plan、subject、same_event_seq(1/2/≥3)、competitor_videos_7d 帶(0/1–3/≥4)。每格 n、中位、IQR(線性內插四分位距)。
- **n<8 的格只印「資料不足(n=…)」**;Spearman(自實作,平均秩)只在 n≥10 才算,數值因子:judge_sec、competitor_videos_7d、same_event_seq、chars_per_min、facts_per_min、blocks。
- 教訓:同因子兩組都 n≥8 且中位差 > 兩組 IQR 均值/2 才寫一句事實句(不寫因果);兩組 n≥3 但未達 8 且差距過同門檻 -> 「候選假設(待 n≥8)」(最多 20 條)。「未知」值不參與。
- scorecard 欄名為「Nh(公開起算)」;窗口以匯出的 published_at 起算(Youtube AD 2026-10-26 起為實際公開時間;更早登記的片為上傳時間,後端 `own_register.py repair-published --apply` 可修)。
- 檔頭固定列「已知偏差」:排程片 published_at 歷史偏差、CTR 為 A/B 混合值、typical 對短片不公平、均看分母為互動觀看。
- 本輪沒有成效證據:不得宣稱點閱率或留存已提高;要等 outcomes ≥20 支才有意義(PLAN §4-4)。

## A/B 教訓節(feedback_report.py 末節,測試:`pipeline\tests\test_feedback_ab.py`)
- 只用 `ab_status` ∈ {winner, same, inconclusive}(stopped 不算完成,不參賽、不算勝);同頻道各一節;沒有任何 A/B 資料印「尚無 A/B 資料」。
- 每個版本算一次「參賽」,label=winner(或 idx=ab_winner_idx)算「勝」;每格 參賽 n、勝 n、勝率,**n<8 只印「資料不足(n=…)」**。
- title 模式改「同場觀看占比差」(同下節算法,`share_tests/share_contrast`,可比較場數 <8 印「樣本不足」);thumb 模式因子:封面切角、cover_kind、cover_gesture、cover_color、cover_layout(勝率表,有才分組,無為「未知」)。
- both 模式(合測)不能歸因,只列勝出組合表(標題#切角+封面方案)。
- 寫標題與封面前讀,只採 n≥8 的格(`channel\規則_交付發片.md` §3.4、§4)。

## 全頻道標題測試節(feedback_report.py 最末節,AB-6b;測試同 test_feedback_ab.py)
- 資料來源:Youtube AD `data\own\export\channel_latest.json`(`paths.ytad_channel_export_latest()`,與 spec_check 同法讀,唯讀;`--channel-export` 覆寫),`channels[].videos[]` 每片 `ab`(格式同 PLAN_AB測試 §2.2)。涵蓋頻道全部影片(含搬運),不經 outcomes.jsonl、不查 spec,因子只從標題文字算。讀不到檔印「讀不到…略過本節」;`build_report(rows)` 不傳 `channel_data` 時同。
- 只用 `ab.status` ∈ {winner, same, inconclusive};`ab.mode`=title 納入比較,both 只列場數、不納入;stopped、running、缺 `ab`/`versions` 略過。每頻道一小節。
- (a) 先印勝出 / 相同 / 無法判定各幾場;特徵表(去掉【…】):每場各版本超額 = share_pct − 該場平均,特徵在同場有差時取「有的 − 沒有的」平均超額,跨場平均,自助抽樣 2000 次(seed 1)取 95% 區間;場數 <8 不印;區間不跨 0 判加分 / 扣分,否則沒差;特徵含經驗框(我看/玩/跑/打/等/查)、三段 vs 兩段(只看全版本都有空格的場);表下印場內最高−最低占比差中位 / P75。
- (b) 勝出對照:該頻道 status=winner 的測試依 published_at 由新到舊取前 20 場,每場一行 `日期 勝 「標題」(占比%) / 敗 「標題」(占比%)、…`(share_pct 缺印 —)。給寫標題的人直接看,不是統計。
- (c) 自製 / 搬運分開統計一行:用每片 `is_self`;頻道內沒有任何片帶 `is_self` 就印「沒有 is_self 欄,全部合計」;部分缺則另列「未標示 N 場」。
