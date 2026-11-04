# 留存曲線對句(retention_align.py)

## 用途
把觀眾留存曲線的大跌點對回 `timeline.json` 的句子,看「哪幾句害觀眾離開」。是 `channel/research_文案優化_2026-10-20/70_留存對句.md` 人工做法的程式版,可重跑。

## 資料來源
- 曲線(三選一,`--curve`):
  - `70_留存曲線.json` 格式:`{tag: {video_id, points: [[pos%, 留存%], …]}}`(取 tag 鍵,或 `--video-id` 比對)。
  - Youtube AD `latest.json`:`videos[]` 以 `--video-id` 或 `tag` 比對,讀 `retention`(`[[pos, val]]`)與 `retention_typical`(`[[pos, low, high]]`,新版才有)。
  - 沒給 `--curve`:試 `paths.ytad_export_latest()`,不存在就回結束碼 3。
- timeline:`--timeline`,否則 `keep/<tag>/timeline.json`,再 `build/<tag>/timeline.json`(找不到結束碼 2)。用 `total`(秒)與 `lines[{idx,start,end,text}]`。
- 開場型態:`build/<tag>/structure.json` 有 `hook_type` 就直接用,否則由 `script_structure.classify_hook` 判斷(見下)。

## 算法
1. 每點秒數 = pos/100 × timeline total。
2. 相鄰兩點留存跌幅;位置 >95% 不算(結尾自然流失)。
3. 由大到小取前 N(`--top`,預設 5),入選點彼此相隔 >2 點;輸出依時間排序。
4. 每個跌點的秒區間與 `lines` 的 start/end 有交集的句子,最多 3 句。
5. `retention_30s_pct`(30 秒處內插)、`retention_50_pct`(位置 50% 內插)、`intro_drop`(第 0→1 點跌幅)。
6. 有 typical:跌點終點留存低於典型下緣 = 「低於」,高於上緣 = 「高於」,其餘「範圍內」。
7. 開場型態:`build/<tag>/structure.json` 有 `hook_type` 就直接用;沒有就呼叫 `script_structure.classify_hook`(單一來源,規則見 `docs/structure.md` HOOK_TYPE:反差 > 觀眾利害 > 事件宣告 > 背景交代),對 timeline 前 3 句(行內再依句號切句)判斷。

## 用法
- `python -X utf8 pipeline/retention_align.py --tag gow_sales --curve <70_留存曲線.json> [--top 5] [--json]`
- `python -X utf8 pipeline/retention_align.py --all --curve <70_留存曲線.json>`:對 `keep/` 下有 timeline 且曲線有鍵的 tag 印總表(開場型態、0→1% 跌幅、30 秒留存、最大跌點秒數與句號)。

## 輸出
stdout Markdown(格式同 70_留存對句.md),`--json` 印 JSON;同時寫 `build/<tag>/retention_align.json`:
`{tag, video_id, total_s, retention_30s_pct, retention_50_pct, intro_drop, hook_type, drops:[{pos_from, pos_to, sec_from, sec_to, ret_from, ret_to, drop, typical_low?, typical_high?, vs_typical?, lines:[{idx,start,end,text}]}]}`

## 注意
timeline 是製作版,與已發布版有改版時秒數會偏;單步跌幅雜訊大,只當候選。測試:`pipeline/tests/test_retention_align.py`。
