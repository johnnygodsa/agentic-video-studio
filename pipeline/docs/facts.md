# 事實核對表機器版(facts_lib / facts_check)

規則來源:`channel\規則\2_文案.md` §5 閘門 2「文案每個數字、日期、引言都對回表上一列」。計畫:`channel\_archive\plans\PLAN_文案資料驅動_2026-10-26.md` §3.7。
目標:每個數字、日期、引言都能對回 facts.md 的某一列;狀態弱(推算/單一/未證實/轉述)的句子畫面必須有小字。

## 1. facts*.md 格式(`facts_lib.parse`)
- 讀 `projects\<tag>\facts*.md`(facts.md 排最前)所有 Markdown 表;表頭第一格 `#` 且有一格含「主張」才算,其餘表/說明忽略。
- 欄位用關鍵字對應(每欄取第一個符合的標題,所以欄位順序、有無都可以):

| 欄位 | 標題關鍵字 |
|---|---|
| claim | 主張 |
| status | 狀態、核對 |
| quote | 原句、依據 |
| magnitude | 絕對值、幅度(「幅度/反面」同欄算這個) |
| source | 來源、網址 |
| counter | 反面、限制、注意 |

- id:第一欄 `F\d+` 或純數字(`F12a` 也收)。儲存格內有未跳脫的 `|`(例 `Xbox Series X|S`)會依狀態欄自動併回;要保險就寫 `\|`。
- `Fact`:id、claim、source、quote、status_raw、status、magnitude、counter、file、line。

## 2. 狀態正規化
同一格含多個關鍵字時取較弱者(未證實 > 推算 > 單一 > 轉述 > 玩家 > 一手)。

| status | 原文關鍵字 | spec.json 的 status(--write-spec) |
|---|---|---|
| confirmed | 一手、官方、資料庫、逐字、已核、確認 | confirmed |
| secondary | 轉述、媒體、二手、報導、多家 | partial |
| player_quote | 玩家原話、玩家、留言、網友 | single |
| derived | 推算、推論、自算 | partial |
| single | 單一、單方 | single |
| unverified | 查無、未經證實、未證實 | unverified |
| unknown | 其他 | partial |

弱狀態 = derived / single / unverified / secondary。

## 3. 文案怎麼寫:行尾 json 的 `f`
`標籤|字幕 ;; {"f": ["F12","F13"], "note": "推算"}`。`script_txt2json` 原樣帶到 script.json。沒寫 f 時工具會嘗試自動配對。

## 4. 檢查規則(`facts_check.py <tag> [--strict] [--write-spec] [--json]`)
- 需核對句 = 含數字(阿拉伯數字、年月日、有單位的中文數字如七十美金)、「」引言、或 spec.json `names[]` 人名。
- 有 f:句內每個數字必須在所引 F 的 主張/原句/絕對值/來源(去網址)數字集合內(年份、日期也比);不符 = 狀態不符;引了不存在的 F = 錯誤。
- 無 f:所有數字交集剛好一條 F(多條時再用「」引言/人名縮小)就自動配對(auto);否則未連結(摘要會列出原因,請補 f)。
- 弱狀態句要有 `note`,或 anim/quote 的 src 含「未證實|推算|轉述|媒體|報價|估」,否則警告「弱狀態無小字」(只警告)。
- 數字正規化:`二十三萬`、`23 萬`、`230,000` 都是 230000;`3,077 萬` = 30770000 = `$30.77M`;`6.39%` 保持百分比(事實端同時收裸數字);時間與日期先抽出再算(其數字不另算):`八點四十`、`8:40`、`08:40` = `08:40`;`五點`、`5點`、`05:00` = `05:00`;`六點到九點` = 兩個時間;
  `十一月五號`、`11/5`、`11-05`、`11 月 5 日` = `11-05`;`2026-10-26` = `2026` 與 `10-26`;`二零一九年` = `2019`;`一千多`、`兩百多` 取下限 `1000`、`200`(近似值,事實端有 1000 才對得上);`兩天` = 2。
  `有一點、差一點` 不是時間,「一點」只在時段詞(清晨、下午…)後才算 01:00;`3-5 人` 這類範圍可能被誤判成日期(代理指標)。
  句子端的中文數字只收「接年月日號點歲倍人場次美金元…」或以萬/億結尾者,「一個、一直、第一場」不算。
- 出處檢查(2026-11-03,`facts_lib.source_gaps`):句子連到(含 auto)的 F 要有出處,否則該句記「無出處」:來源沒有 http(s) 網址、也沒引用其他 F 編號或本機檔(`comments_ref\`、`.md`、`.json`),或原句空/「查無」(開頭是查無)。狀態 derived(推算)的列原句可空(依據是算式),來源仍要有網址或 F 參照。裸網域(`gnn.gamer.com.tw/...`、`ginx.tv`)不算網址。
- 引矛盾:所連 F 的狀態原文含「矛盾」(兩邊都列、不裁定的列)→ 該句記「引矛盾」。(狀態正規化仍把它歸 unknown,直接看 status_raw。)
- 表內缺出處(只警告,不進摘要數字、不影響 exit):facts.md 狀態不含「查無」、卻缺網址/原句的列,報告印清單。
- 輸出最後一行固定:`[facts_check] 連結 N/M 句 (xx%)、未連結 K、狀態不符 J、錯誤 E、無出處 X、引矛盾 Y`(X、Y 在尾端追加;`gate_b.facts_stat`、`review_md.facts_warnings` 用正規式抓前段/各鍵,不受影響;gate_b 目前不把 X、Y 算進放行條件);exit 0,`--strict` 時 J+E+X+Y>0 → exit 1。`--json` 在摘要前另印 JSON(多 `no_source`、`contra`、`table_gaps`)。
- `--write-spec`:把連結結果寫進 `projects\<tag>\spec.json` 的 `facts[]`(每條有連到句的 F 一筆:id、claim、lines、status、src=facts 檔路徑);
  其他鍵保留;spec.json 不存在就建最小檔。會整個取代原本的 facts[]。狀態不符的句不寫入。

## 5. 與其他工具
- `spec_check.py`:spec.json 的 `facts` 缺或空、且 facts*.md 存在 → 略過「句子沒有 fact 涵蓋」並印「事實覆蓋改由 facts_check 檢查」,不報錯(不必為了躲檢查把檔名改成 spec_pkg.json)。
  `facts` 有內容時照舊檢查;沒有 facts*.md 也照舊。
- `make_version.py`:script_lint 之後呼叫 `facts_check <tag>`(facts*.md 存在才跑,預設不加 --strict,連結率進摘要)。
- 素材根:腳本讀 `paths.ROOT`;非 Windows 或測試時用環境變數 `CLAUDE_VIDEO_ROOT`。

## 6. 測試
`PYTHONPATH=<repo> python3 -X utf8 -m pytest pipeline/tests/test_facts_check.py -q -p no:cacheprovider -s`
fixture 在 `pipeline/tests/fixtures/facts/`(三種表頭、`proj/` 的小 script.txt);最後一個測試會對 wow_stress、cp2077_25、sf_movie 印連結率。
