# spec / feedback / 選題

(原 README 章節 §11、§12、§13、§14;文中 §n 沿用原編號,對照見 README.md §2。行號不寫在文件裡:`python -X utf8 pipeline/tools/funcmap.py --grep <函式名>`)

## 11. spec.json 與 spec_check.py(F1-0,規格見 channel\_archive\plans\PLAN_FRAMEWORK.md §0.2)
- 檔案:`projects\<tag>\spec.json`(主對話寫,程式讀)。欄位依 §0.2,另加三個選填欄位:
  - `names`:真人姓名清單(字串陣列);旁白句含其中任一個就必須有 fact 涵蓋。**譯名表(R5)**:另有獨立鍵 `tw_names`(與 `names` 無關)為物件 `{"Phantom Liberty": {"tw": "自由幻局", "avoid": ["往日之影"]}}`(值可簡寫成純字串譯名),查證階段 researcher 填;字幕/`@say` 出現 avoid 他譯、或含原文卻同句沒有譯名 → 錯誤(`check_names`)。
  - `judgment_line`:「判斷句」的句號;用累積字數 ÷ 6.5 估它結束的秒數,對 `targets.judgment_by_s`。
  - `sections[].bridge: true`:該段講惡靈古堡以外的遊戲;橋接比例 = bridge 段字數 ÷ 全片字數,對 `targets.bridge_min`。
- **句號 `lines`**:script.txt 旁白句依出現順序 1-based 編號(不含 `#` 說明行與 `@` 指令),與 `script_txt2json` 輸出的 `sections[].lines` 攤平後的順序一致。fact、section、`judgment_line`、`visual_plan`、`shorts` 都用這個編號。程式直接呼叫 `script_txt2json.parse/build_lines`,不另寫 parser。
- 指令:`python -X utf8 pipeline\spec_check.py --tag <tag> [--spec <路徑>]`(`--spec` 預設 `projects\<tag>\spec.json`)。印一張達成表加錯誤清單(30 行內);有錯誤 exit 1,只有警告 exit 0。
- **錯誤**:fact 缺 `lines` 或句號越界、status 不是 confirmed/partial/single/unverified;旁白含數字(阿拉伯數字,或中文數字+年月日歲倍套萬億公尺公里成人名位場次集天週分秒小時;純「一」與「第一」不算,「二代、三個」不算)、含 `「」『』`、含 `names` 人名,卻沒有任何 fact 的 lines 涵蓋該句;標題 `facts` 引用不存在的 id;`unverified` fact 所在句的 anim/quote `src` 沒有「未證實」;section 範圍越界。
- **警告(達成表,不中止)**:估計片長(字數 ÷ 6.5)vs `len_s`、判斷句秒數、話題數(`role=topic` 段數)、橋接比例、自製畫面比例(F2-2 起用實際指定算:script 欄位 anim/quote 的句數 ÷ 總句數,`visual_plan` 的指定補在沒有指定畫面的句子上;不再有「未計算」)。
- **畫面檢查(F2-2,`spec_check.check_visuals`,畫面由 `visual_suggest.line_visual` 判定)**:
  - 警告「數字句沒數字畫面」:沿用 `has_number` 的句子,畫面不是 `anim:num/bars/cols/share/timeline/span`、不是 card、quote、compare、截圖加 hl,且(list/versus/flow 這類文字型 anim)句中阿拉伯數字沒有全部出現在該 anim 欄位文字裡 → 警告。已知偏嚴:「九月」「二十年」「2001 年」這類日期與年份也算數字,純敘事句會被警告,可改掛 card 或接受。
  - 錯誤「素材畫面疊動畫」:同句 anim 又帶 `v`/`img`/`shots`/`quote`/`compare`(build 的 `visual_key` 以 anim 優先、悄悄忽略素材,不會報錯,所以這裡擋)。
  - `visual_plan` 值開頭:`anim:<type>`、`quote`、`compare`、`screenshot`/`img`/`shot`、`clip`、`card`;鍵可為句號 `"3"` 或範圍 `"3-5"`。script 欄位優先於 `visual_plan`;`visual_plan` 只補沒有指定畫面(只有 v 標籤)的句子。
- **visual_suggest.py(F2-2)**:`python -X utf8 pipeline\visual_suggest.py --tag <tag> [--spec <路徑>]`(spec 選填,預設 `projects\<tag>\spec.json`,沒有就略過;只讀)。每句印「實際」(已定 = script 欄位或 visual_plan;只有 v 標籤 = 未定 clip)與「建議」(PLAN §3.1:「」→quote;數字→num / bars〔多個數字或有比較詞〕/ timeline〔≥2 個年份或「從…到」〕/ span〔期間〕/ card〔只有年份〕;新舊對照→compare;清單→list;因果→flow;對立→versus;結尾段→list;fact 有非百科網頁 src→screenshot;其餘 clip)。泛用句 = 建議 clip、未指定、v 標籤屬 `GENERIC_TAGS`(games/generic/misc/filler…,或 `spec.generic_tags`)。比例 = 泛用句 ÷ 總句數,目標 ≤10%。輸出 40 行內,句數多時只列「未定且建議特殊畫面」與泛用句。寫文案時給泛用畫面的句子請用 `generic` 這類標籤,才算得進比例。
- **package 檢查(F1-3,`spec_check.check_package`;依據 `channel\規則\4_交付發片.md` §3–§5,常數上方註明章節)**:`package.titles` 與 `thumbs` 都空 → 印「無 package,略過」;有任一項才檢查,有錯 exit 1(`make_version` 的 spec_check 會因此中止,所以 package 草稿未完成前先不要填半套)。
  - 標題錯誤:不是 5 個、>28 字(全形 1、半形 0.5)、含禁用寫法(`【】()[]`、`,，、;；|`、emoji、`…`、「以為X其實Y」、「一次看懂」等農場詞,常數 `TITLE_BAN_*`)、前 3 個 `angle` 有重複;警告:不在 14–24 字、切角代號不在「判數引損問反身矛」、第 1 名是問句、問句超過 1 個、含數字的標題少於 2 個。標題 `facts` 引用不存在的 id 仍由 `check()` 報錯。
  - 封面錯誤:方案數不是 3(`channel=ChannelC` 或 `form=sci` 為 1)、`lines` 不是三行、三行合計 >13 字、主/副文字空、含問號、`composition` 不在 `face|object|versus` 或三方案重複(科普 1 張不查)、`colors` 不在色票;警告:主文字不是 2–4 字、`angle` 重複、三行同色。另警告(2026-11-03,`COVER_TITLE_DUP_MIN`):方案 N 的主/副/補充字各自去掉主體名後,與第 N 個標題的最長共同字句 ≥4 全形字(`longest_common`,依標點/空白切段)→「與標題N重複字句」(4_交付發片 §4.2:封面三行不與同號標題同組字句)。DEI 系列等頻道特例、兌現檢查不查。
  - **新增選填欄位**:`thumbs[].composition`(`face` 人物表情特寫 / `object` 物件或數字特寫 / `versus` 對比並置;ChannelA/ChannelB必填)、`thumbs[].angle`(切角代號)、`thumbs[].colors`(三行 `"色名 #色碼"`,預設亮黃/純白/亮橘)、`thumbs[].hook`、`thumbs[].side`(字所在側,預設右)、`package.chapters`(`[{"line":句號,"title":"…"}]`,時間取 timeline)。
- **負面判語 14 天重複(`spec_check.check_neg_repeat`,發片資料_規則 §3.1,2026-10-20)**:跑 `--tag` 一般檢查且有 package 時,本片 5 標題與封面三行字若含 `NEG_PHRASES`(吃相難看/盤子/雙標/翻車/割韭菜/背刺/打臉/破防/自殺式/下架…,可擴充)且 Youtube AD 頻道匯出 `channel_latest.json`(`paths.ytad_channel_export_latest()`,唯讀,2026-10-27 D3 起不再開 own.db)同 slot(spec `channel` ChannelA→`''`、ChannelB→`'c'`,其他頻道略過)近 14 天、`tag` 不是本片的標題含同一判語 → **錯誤**,訊息列出撞到的舊片日期與標題。own.db 讀不到 → 警告「無法讀 own.db,略過判語檢查」,不中斷。
- **封面人像跨片重複(`spec_check.check_persona`,SOP §4,2026-10-19)**:`spec_check.py --tag <tag> --notes <說明檔.md>`(給 `--notes` 只跑這項,不需 spec.json;`--tag` 用來排除 log 中自己)。讀「發片資料」方案1/2/3 段的 主體/場景/視覺構圖,關鍵字詞典(`HAIR_PAT` 等)抽 kind 與六格+色彩,抽不到記 null;對 `channel\cover_persona_log.jsonl` 其他 tag 最近 10 筆原創玩家:六格相同 ≥3、手勢同最近 3 筆、場景同最近 2 筆、方案1 與 3 都是原創玩家且不同格 <4 → 錯誤(exit 1);原創玩家缺格、最近 5 筆方案1 已 ≥2 筆原創玩家 → 警告。`--record`(需 --tag 與 --notes)把方案1、3 寫進 log(同 tag+plan 覆寫);`--recent-sheet <新圖>` 拼最近 8 張 Youtube AD `data\covers\*\plan1_doubao.png`(唯讀)加新圖到 `tmp\cover_recent_sheet.jpg`。`make_version` 交付前跑檢查(有錯誤「未交付」)、交付成功後 `--record`。
- **說明檔骨架帶入**:`re9_notes.py --spec <spec.json>`,package 有標題或封面時在說明檔尾加 `## 發片資料` ```text 區塊(函式 `package_block`:章節/業配/5 標題/3 方案五段,格式照發片資料_規則 §9);核心鉤子、章節等沒填的欄位寫「(待填)」,交付前要人工補完。沒給 `--spec` 或 package 空則不產生此區塊。

## 12. feedback.py(回饋閉環,2026-10-26 改版)
- 已改為讀 Youtube AD `latest.json`、寫 `channel\outcomes.jsonl` 與 scorecard,另有 `feedback_report.py`;指令、欄位與門檻見 `pipeline\docs\feedback.md`。舊的 own.db 直讀(48h/72h/7d 窗口挑快照邏輯)已移除,窗口改取匯出的 windows。

## 13. 選題(原 topic_score.py / topic_scan.py,2026-10-26 已刪)
- 選題改用 Youtube AD 的 `intel_query.py opportunities` / `brief` 加 `context_pack.py`(見 `channel\規則\1_選題.md` 與 channel\_archive\plans\PLAN_文案資料驅動_2026-10-26.md §3.1–§3.5);原評分表(demand/peer/fresh/assets 分級)與每週掃描流程停用。`channel\topics.json` 保留為歷史,`paths.topics_file()` 等常數暫留。
