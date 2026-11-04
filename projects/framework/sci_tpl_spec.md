# 科普場景模板規格(F4-0,PLAN_FRAMEWORK §4.3)— 2026-10-14 主對話

【判】= 主對話自定,第一支用模板的片給使用者看後修正。

## 1. 接法
- 模板檔 `pipeline\sci\tpl_<名>.js`,各自掛 `window.Tpl.<名> = { render(t, params), check(params) }`;`render_clip.build_html` 在 props 之後、場景之前把 `tpl_*.js` 全部載入。
- 通用場景 `scenes\tpl.js`:`render` 依 `params.tpl` 轉呼叫 `Tpl[params.tpl].render`;`Scene.name='tpl'`。
- film.json 場景寫 `{"tpl":"list","lines":[a,b],"data":{…}}`(不寫 `scene`;`scene` 與 `tpl` 擇一)。make_film:有 `tpl` 就算 `tpl.js`,params 多帶 `tpl`、`data`;tmp 目錄名、摘要用 `tpl_<名>`。
- 模板**不准有 DEF 備援**:`lines` 缺、句數與 data 引用不合 → `check` 回錯誤字串,make_film 標「模板錯誤」並中止該場景(不論 `--strict`)。舊場景檔不改(§4.2 不回溯)。
- 版面一律讀 `K.L`(橫/直兩組),每個模板的版面常數寫成 `{landscape:{…}, portrait:{…}}` 一個物件,不散在程式裡。
- 圖表元件沿用 `Charts.*`、圖解沿用 `Props*.LIST`,模板只負責排版與時間;不重寫元件。

## 2. 時間觸發(全部模板共用,放 `tpl_common.js` 或 kit 內 `K.tplAt`)
- 任何會出現的元素寫 `at`(場景內句索引,0 起)與選填 `word`(該句裡的字串;觸發格 = 字索引 ÷ 句長 × 句長秒數,同 s_rank_a 的 `wordK`;找不到 word → check 錯誤)。省略 `at` = 依序分配:第 i 個元素掛第 min(i, 句數-1) 句開頭。
- 元素在觸發格以 `K.pop` 彈入,不補間。
- **最後一個元素完全出現後到場景結束 ≥ 1.5 秒**(CLAUDE.md 動畫停留規則);不足 → check 警告(不中止),摘要列出。
- 退場只用 0.3 秒(3 格)縮掉,且只在 data 寫 `out:{at,word}` 時才做。

## 3. 共通版面數值【判】
| 項目 | 橫式 1920×1080 | 直式 1080×1920 |
|---|---|---|
| 內容區 | x 80–1440(鴿子佔右側 1440–1840)| x 80–940,y 120–1280(1320–1480 字幕帶,鴿子在下方或省略)|
| 標題牌 | 左上 (100,110),fs 72,黃底 | 上方置中 y 200,fs 80 |
| 字級下限 | 數字 150、標籤 56、來源 40(Charts 已拉回)| 標籤 60、其餘同 |
| 來源牌 | 內容區左下、字幕帶上緣以上 ≥ 20px | 同 |
| 同時運動的非文字元素組 | ≤ 2(含鴿子)| 同 |
| 每鏡焦點 | 1 個:`hi` 指定的項黃底,其餘主色或灰 | 同 |
- **填滿與置中**(F4-0a 看圖後補):內容群組在內容區(直式:120 到鴿子頂上 24px)**垂直置中**、橫式水平靠內容區中線;項目少時字級放大到上限,不可縮在一角。字級上限【判】:list 列字 橫 84/直 80、標題 橫 84/直 88;number 數字 橫 300/直 260、note 橫 64/直 64。直式內容群組高度目標 ≥ 內容區 45%。共用函式放 `tpl_common`(`fitBlock`:給項目數、內容區 → 回傳字級、起點),後續模板一律用。
- 鴿子:每個模板都接受 `data.pigeon = {expr|[每句表情], clip:'idle'|…, hide:false}`;橫式在 `K.L.pigeon`,直式在內容區下方中央、縮 0.8;`hide:true` 不畫。表情名只用 pigeon.js 現有 9 種。
- 所有字不得進字幕帶、不得超出 margin;沿用 render_clip 的外框檢查。

## 4. 各模板 data
| 模板 | data | 上限 | 用到的元件 |
|---|---|---|---|
| `list` | `title?`, `style:'check'|'num'|'dot'`, `items:[{text,at?,word?,state?,icon?}]`, `hi:[i]` | 橫 6 項、直 5 項;每項 ≤ 14 字(直 9) | `Charts.checklist`(num/dot 自繪前綴)|
| `bars` | `title?`, `unit`, `src?`, `bars:[{label,value,text?,icon?,at?,word?,grey?}]`, `hi:[i]`, `max?` | 橫 6 條、直 5 條 | `Charts.hbars` |
| `compare` | `left/right:{title,items:[文字],icon?,at?,word?}`, `hi:'left'|'right'|null` | 每邊 4 項、每項 ≤ 10 字;直式改上下排 | `Charts.twoCol` |
| `timeline` | `nodes:[{year,label,at?,word?}]`, `hi:[i]` | 橫 6、直 5 個節點 | `Charts.route` 或自繪橫軸(直式改直軸)|
| `number` | `num`, `unit?`, `note?`, `src?`, `at?`, `word?`, 選填 `flip:{from,to,at,word}` | note ≤ 16 字 | `Charts.bigNum`、`priceFlip` |
| `pigeon_talk` | `expr:[每句]`, `clip`, `bubbles:[{text,at?,word?,dashed?}]`, `props:[{lib,name,params,at?,word?,x?,y?}]` | 泡泡同時 ≤ 2、每泡 ≤ 2 行 | `K.pigeon`、`Charts.bubble`、`Props*.LIST` |
- 超過上限 → check 錯誤(不自動縮字)。字寬用 `Charts.tw` 估,溢出內容區 → check 錯誤。
- `pigeon_talk` 鴿子放大當主角(橫式 u 3.2、置中偏左 x 700;直式 u 3、y 1150)【判】。

## 5. 驗收(主對話看圖)
- 每個模板 2 組 data(一組最少、一組到上限)× 橫直 = 4 組,`render_clip.py tpl --params …` 出格;外框檢查全過;`seek(t)` 同 t 兩次結果相同(允許既有抗鋸齒微差)。
- 測試 data 放 `pipeline\sci\examples\tpl_<名>.json`(含假 lines),之後當寫 film.json 的範例。
- 一張總覽 PNG 每組取最後一格,路徑回報給主對話;代理不看圖。
- README §10 加 §10.5 模板用法(data 欄位表、指令)。
- 現有 5 支片的 film.json 重跑 `make_film --only` 任一場景結果不變(只抽 1 場景比對 framemd5)。
- `tpl_thumb` 是 F4-1,不在本批。
