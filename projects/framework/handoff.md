# 框架實作交接(PLAN_FRAMEWORK §7)— 2026-10-14

## 已完成(每項一個 commit)
- F1-0 spec.json + spec_check(8e586cf)/F1-1 檢查接進 make_version(2dda6ee)/F1-2 聽審門檻改相對值(c48ccca)/F1-3 封面標題自檢(f1bf29c)/F1-4 feedback.py(66b1a56)/F1-5 不需改碼(slot d 已接)/F1-6 規則收斂(835bb4d)
- F2-0 topic_score(1615072)/F2-1 topic_scan(1ba602b)/F2-2 visual_suggest(c5d587b,日期排除 4051101)/F2-4 sci 直式(7a2431a)/F2-5 封面 A/B(Youtube AD 161b11d)

## 使用者指示
- 製作中的兩支片(onimusha、re9 相關)先不動:不改文案、不改 spec。onimusha 只當唯讀測試資料。

## 已知未決
- topic_score demand:query 要寫一兩個詞,否則都走主詞 5 折。ChannelC peer 無資料(trend_d 無 my_daily)。
- visual_suggest 泛用比例只認 generic 類標籤;舊文案都沒用,所以舊片都是 0%。
- sci 現有場景座標寫死橫式,直式要等 F4-0 模板化。同一 t 連算偶有微小像素差。
- ChannelC新片(2jaWyvoTds4)Studio 抓取「時段不符」,等排程補抓後確認。
- F2-5 A/B 選擇器未實測,下一次結案確認(見記憶 yt-pipeline-2026-10-14)。

## F2-3 已完成
- 版面規格 5a937b7(`projects\framework\shorts_spec.md`)/build.py 直式模式 f355aa2/shorts_build + deliver --shorts + 字幕書名最後才放寬 952799f。
- 測試 Shorts:`output\dei_gamersdead\dei_gamersdead_s1_v1.mp4`(母片 32-38 句,36.8 秒,不交付)。
- 橫式回歸:影像 framemd5 全同;音訊最後約 1.3 秒每次執行本來就不同(混音不確定性,同版本重跑也不同)。
- 已知限制:動畫、引言卡、截圖在直式整張縮成 1080x608,字太小 → 已列 F3-4。在那之前 Shorts 挑句以影片與卡片為主。
- 直式另把 VIDEO_SPLIT 調成 4.5 秒(VIDEO_MAX 5);動畫/引言鏡頭 > 5 秒只印警告。
- deliver `--shorts --enqueue` 會中止:Youtube AD 後端尚未支援 Shorts 佇列(要另開後端任務)。
- 第一支正式 Shorts 交付後,使用者看過再修 shorts_spec 的【判】數值。

## F3 已完成(2026-10-14)
- F3-0/F3-2 news_lib + news_specs(98064b9):gd 5 張重截 boxes/layout 全同。新片 news 檔範例 `pipeline\assets_gd2_news.py`(33 行)。
- F3-1 clips_lib + clips.json(939a52e):gd 58 段逐欄位同原程式。格式範例 `pipeline\examples\clips_gd.json`。
- F3-4 直式原生畫面(a895879、84c62ad、ba8635d、fb6eb8f、ce82337):timeline/bars/list、引言、對比、窄版截圖(`news_lib --narrow`,檔名 `_p.png`)以 1080 寬直接繪製;截圖上下緣落在行間、文字與標籤右緣 ≤ 940;check_portrait 查切半行、保留區、標籤漏畫。橫式 13 項逐格比對全同。
- F3-3 README 程式地圖行號重對、舊 assets_* 標 legacy(f8c4f2f)。

## F3 已知限制
- 直式對比若兩邊是截圖,只能縮小上下排、字遠小於 48px → Shorts 的對比只用文字。
- 直式時間軸 6 節點時說明字級降到 48(墨跡行帶 43)。直式 list 字級上限 72、時間軸列距上限 160 是主對話/代理自定,第一支 Shorts 給使用者看後再調。
- 其他動畫型別(num 等)直式仍退回整張縮放並印警告。
- 疊在原生鏡頭上的卡片只做單元測試。
- 橫式整片 framemd5 沒重跑(動畫快取鍵沒變);下次正式橫式出片時順便確認。
- 其他 6 份舊 news 檔、re9/re9o 的 clips 參數只從 diff 判斷等價,沒實跑。
- `images\gd_*_p.*` 窄版測試圖未 commit(素材,依清理規則處理)。

## F4 已完成(2026-10-14)
- F4-0 規格 `projects\framework\sci_tpl_spec.md`(a9b88c4、e23936b)。7 模板中 6 個:number/list(ae26f65、7289845、6d88d69)、bars/compare/timeline(e43b8db…4994377)、避開鴿子(488066c)、pigeon_talk + 間距檢查 + tpl_demo 整片實跑(6b7998b…fb0a613)。範例 `pipeline\sci\examples	pl_*.json`;用法 README §10.5。s_cash framemd5 回歸不變。
- F4-1 tpl_thumb + `make_thumb.py`(dd25d43):範例 `output	pl_thumb_demo\`。

## F4 已知限制【判】
- 字級上限、鴿子位置(pigeon_talk 橫 (700,812) u3.1、直 (655,1286) u2.2)、縮圖字高下限(§4.1 ÷6:主 33/副 18/補 15 px @320 寬)皆主對話/代理自定,第一支用模板的片給使用者看後修。
- compare 直式不畫鴿子;timeline 6 節點年份需 4 位數;bars 橫式 6 條列距約 11px 偏擠。
- tpl_thumb 沒程式化:冷色底改暖橘字未實測、表情可讀性、不複讀標題。`channel\發片資料_規則.md` §4.1 範例三行是 14 字,超過自己訂的 13 字上限,待修文件。
- 總覽圖腳本(代理臨時寫)直式格被裁切,只當代理自查用。
- 測試產物:`tmp	pl_*`、`build	pl_demo`、`output	pl_demo`、`output	pl_thumb_demo`、`output\channel	pl_*` 可依清理規則刪。

## 下一步:F4-2 第一次檢討
- 要 10 支以上數據;未滿就等。下一支ChannelC新片直接用模板(目標新 JS ≤ 5 檔)。
