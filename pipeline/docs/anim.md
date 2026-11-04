# 動畫

(原 README 章節 §5;文中 §n 沿用原編號,對照見 README.md §2。行號不寫在文件裡:`python -X utf8 pipeline/tools/funcmap.py --grep <函式名>`)

## 5. 動畫(anim_lib.py;build 的 parse_anim 為欄位權威)
設計規格(挑哪種類型、版面、顏色、動作、禁用樣式、未實作清單)在 `pipeline\ANIM_DESIGN.md`;改動畫外觀前先讀。
anim 欄位 `type`:
- `timeline`:節點組有兩種來源(2026-10-16):**anim 自帶 `points`**(`{type:"timeline", points:[[日期,說明],…], question_between?, src?, step:n|"q"}`,一支片可有多組,用 `@def anim:名稱=` 各定義一組;`build.tl_meta(a, tlmeta)` 決定該用哪組,自帶 `points` 時 `question_between` 也只看 anim 自己的,step 範圍依該組)或退回頂層 `timeline.points`(舊片相容)。連續句合鏡以「同一組 points(含 question_between)」為準:`visual_key` 對自帶 points 的鍵為 `timeline:<points json>`,不同組相鄰不合鏡,頂層組與自帶組也不合鏡;`parse_anim`、`_check_src`、`_anim_layers`(橫直式共用,快取簽章含各句 anim 故自帶 points 已入鍵)、`anim_preview` 都經 `tl_meta`。測試 `tests\test_timeline_points.py`。基本用法:各句 `{type:"timeline", step:n|"q"}`(q = 問號 `PAL_NEG`,需 timeline.question_between);`make_timeline`、版面 `timeline_layout`(2026-10-13 重做:points 第三欄顏色**已忽略**;已出現的節點與年份 `PAL_TEXT`,剛出現的一個 `PAL_ACCENT`,下一步出現時 0.3 秒退回 `PAL_TEXT`;說明字 56px 起、行距 1.32 倍,`_wrap_even` 平衡換行(每行 >= 2 字、不拆英數詞、避頭尾;英文詞組中間 +300、數字與單位間 +80、含英文時中文詞中間 +120 的斷行扣分,所以優先在中英交界或空白斷行),超過 3 行或相鄰說明相距 < 24px 才逐級降到 50,`degraded` 為真時要在回報列出;說明寬 <= 408 讓第一/末節點離邊 >= 96)
- `list`:`{title, items:[字串…], step:"all"|0..n-1, note?}`;step=k 該句開頭彈出第 k 項;`make_list`、版面 `list_layout`(編號圓點 `PAL_ACCENT` 底加深色字 (27,20,20);圓點加最寬項目整塊水平置中於 x=960、塊內文字墨跡靠左;項目 > 5 個 `parse_anim` 給警告(`build.ANIM_WARNS`,不是錯誤);note 墨跡下緣 790,有 src 時 768)
- `bars`:`{title, items:[[標籤,正數,單位,{color?,icon?,hi?}?],…]}` 或 `groups:[{title,bars:[…]}]`;`step` 省略=整組一次播,`"title"` 或 0..n-1 逐條顯示(顯示第 0..k 條)。**規格(2026-10-11 重做,常數都在 `anim_lib.py` `BARS_*` 起;2026-10-13 改共用色票與數值排版)**:靠左,標籤右對齊 x=420、基線 x=460、最長條終點 1500、數值在條尾右 24px;條厚 56/間隔 44,放不下先縮條厚到 40 再縮間隔到 36,仍放不下 `raise ValueError("長條圖項目過多,請拆成兩張")`(未分組最多 7 條;幾何 `bars_geometry(sizes, grouped, gh, bottom_max)`);條尾圓角 10、基線端直角;基線 2px 40% 淺灰,無格線無外框;最後一條下緣 <= 800(有 `src` 時 <= 752,`BARS_BOTTOM_SRC`);分組:組間 96、組標題在組上方 16 左對齊基線;非強調條 `PAL_NEUTRAL` #6F7E9E(對底色 4.8:1),強調條 `PAL_ACCENT` #FFB000(10.7:1)(item 第 4 欄 `{"hi":true}` 指定強調哪幾條,任一條帶 `hi` 鍵即不自動挑最大值,`{"hi":false}`=全不強調;有 `color` 的類別色 alliance 藍/horde 紅 `BAR_COLORS` 維持,且不自動強調);文字固定 #E7E9EA(標籤 56px)/白(數值 64px,強調條 72px,無假粗體),不用資料色;數值 `_val_sprite`:數字與單位分開畫,單位 0.75 倍字級(不小於 44px)、共用基線、間隔 8px(單位 `%` 不留間隔),整數 >= 1000 加千分位;`place()` 的 val 墨跡框 = 數字加單位;每條由左長出,長到 80% 數值淡入;`_BarsLayout`、`make_bars`、`make_bars_step`;`python -X utf8 pipeline\anim_preview.py --bars-demo <資料夾>` 出兩案例圖並印量測;測試 `pipeline\tests\test_bars_layout.py`
- `span`:`{from,to,big,ticks?:8,caption?}` 時間跨度;`make_span`(亮起的線、節點、刻度 `PAL_ACCENT`,未亮灰;`span_layout` 讓兩端標籤與大字、說明離邊 >= 96:標籤太長先把中心往內夾、仍互碰才縮字;caption 在有 src 時上移到 y=700)
- `stamp`:`{text}` 印章;`make_stamp`(`make_stamp` 的 hold/angle 為函式參數)
- `versus`:`{title,left:{head,lines[1..2],mark?:"yes"|"no"},right:{…},step:0|1|2}`(0 標題與欄標題/1 左欄/2 右欄);`make_versus_step`、版面 `versus_layout`(面板 x 96..912 填色 (28,31,42) 約 92% 不描框;欄標題下短橫條 `PAL_TEXT2`;沒有 VS 圓標;內文字級 72 起由 `_fit_rows` 縮到 56,再不行整體往下降;面板下緣 800,有 src 時 752)
- `flow`:`{title,nodes:[2..4 字串],step:0..n-1}`(step n=顯示到第 n 個節點);`make_flow_step`(節點填色 (28,31,42,235) 不描框,最後一個節點 `PAL_ACCENT` 3px 外框,箭頭 `PAL_TEXT2`;節點區左右離邊 >= 96 `FLOW_EDGE`;`flow_bounds` 取墨跡框)
- `cols`(2026-10-13,時間資料直條):`{title, items:[[標籤, 正數, 單位?, {hi?}?],…2–7 根], step?, src?}`;時間由左到右不排序。`_ColsLayout`、`make_cols_step`、`cols_step_seconds`(= `bars_step_seconds`)。基線 y=700(2px `PAL_LINE`,依內容寬置中)、最高柱頂 y=330,槽寬 min(280, 1500/n)、柱寬 min(150, 槽寬*0.6),整組置中;柱頂圓角 10、基線端直角;`PAL_NEUTRAL`,`hi:true` 或(沒有任何 hi 鍵時)最大值 `PAL_ACCENT`;數值在柱頂上 16px(64、強調 72,單位 0.75 倍且 >= 44),標籤 56px 在基線下、上緣距基線 18px,標籤寬 > 槽寬 `raise ValueError("直條圖標籤過長…")`;step 省略 = 一次播,"title" 或 0..n-1 = 顯示第 0..k 根(每根 0.5 秒 ease-out,80% 時數值淡入,比例尺固定用全部最大值)
- `share`(100% 堆疊條):`{title, rows:[{label, parts:[[名稱, 數值, 顏色?],…2–4 段]},…1–4 列], unit?:"%", step?, src?}`;每列數值總和須 99–101(parse_anim 報錯)。`_ShareLayout`、`make_share_step`、`share_step_seconds`。條左端 x=460、寬 1280,列標籤右對齊 x=420(56px),條厚 96/列距 72(4 列或有 src 放不下時兩者等比縮小,下限 0.55 倍再報錯),整組在圖例下方到 800(有 src 752)垂直置中;段間 4px 空隙不描邊,最左段左端直角、最右段右端圓角 10;顏色第三欄可給 `BAR_COLORS` 名稱或色碼,沒給依色序 `SHARE_SEQ`,**同名稱全部列同色(以第一次出現為準)**;段內數值(60px,單位 0.75 倍)放不下(寬 + 32)就不畫;圖例在標題下 y=275(色塊 28、名稱 48px、項距 56);step 省略 = 一次播,"title"(標題加圖例)或 0..列數-1 = 顯示到第 k 列,每列由左至右展開 0.6 秒
- `num`(獨立深色底數字卡):`{label, big, compare?, tone?:"up"|"down"|"none", step?:0|1, src?}`;`_NumLayout`、`make_num_step`、`num_step_seconds(prev, shown, big)`、`num_is_count`。label 72px `PAL_TEXT2` 中心 y=230;big 的數字與 → 為 300px 白字、其餘單位 0.45 倍共用基線,整行置中於 y=450,寬 > 1728 等比縮小;compare 64px `PAL_TEXT` 中心 y=660,tone up/down 在文字左側畫 `PAL_ACCENT`/`PAL_NEG` 三角(none 或省略不畫)。big 開頭為單一數字且沒有「→」時 0.8 秒由 0 數到目標(右緣對齊終值、基線不變),否則 0.35 秒淡入;step 省略 = label、big 依序出現後 compare 在 big 到位 0.4 秒後淡入;0 = 只有 label 與 big;1 = compare 出現(須有 compare)
- 新三類的版面檢查:`AL.new_layout(a)` 回傳 `.boxes`(命名文字框)與 `.bounds`;`anim_problems` 檢查內容下緣(<= 800,有 src <= 768)、左右離邊 >= 96、文字框(含 src 框)重疊,版面例外(標籤過長、排不下)直接回傳錯誤訊息;`python -X utf8 pipeline\anim_preview.py --new-demo <資料夾>` 出 cols_demo / share_demo / num_demo 並印量測;測試 `pipeline\tests\test_new_anim_layout.py`
- 直式(F3-4):`set_profile("portrait"|"landscape")` 改寫 `PORTRAIT_SET` 列的模組常數(W/H 1080、CX 510、SRC_*、BARS_*、LIST_*;橫式值 import 時記下原樣還原,非執行緒安全)、常數(改直式版面要把 `P_LAYOUT_VER` +1;`P_NATIVE`、`P_LAYOUT_VER`、`P_X0..P_Y1`、`P_FS_MIN` 48、`P_SIZES` 直式期間 text_sprite 字級紀錄);`_list_layout_p`(圓點靠左、換行右界 `LISTP_X1` 1020、字級 72->48、項目少時標題 + 項目整組垂直置中(layout 回傳 `title_cy`))、`_wrap_p`(換行點只落在詞與詞之間:`WORD_TOKS`,token 比行寬還寬時退回預設)、`timeline_layout_p` / `_make_timeline_p`(縱向:年份在上、說明在下;說明字級 72->48、年份 = min(說明+12, 72),節點少時列間距放大到 `TLP_GAP_MAX` 160;整組以文字墨跡外框在窗內水平、垂直置中(依全部節點的最終版面,過程不跳動;垂直範圍 70-1010,有 src 時到 960),縱線在文字左 `TLP_LINE_DX` 60 隨文字;軸線從第一個節點開始,無線頭;layout 另回傳 tx/lx/ink);bars 只換常數。星座背景固定 `STAR_W/STAR_H` 1920x1080,`over_star` 遇較小前景時裁中段
- `emoji`:`{name}`(名稱見 `EMOJI`,下載 Noto webp 快取);`puzzle`:無必要欄位
- `src`(2026-10-13,任何 anim 類型都可帶):`"src": "字串"` = 右下角出處小字(44px、`PAL_TEXT2`、描邊 2px,墨跡右緣 x=1824、下緣 y=824,隨標題淡入後常駐);共用 `src_place`/`_src_note`,各 `make_*` 的 `src=` 參數;`parse_anim` 檢查為非空字串。**版面檢查 `build._check_src`**:bars 檢查 src 框與標籤/數值/組標題重疊或排不下;timeline/span/list/versus/flow 用 `AL.anim_problems`(`anim_bounds` 取內容墨跡框):內容下緣 <= 800(有 src 時 <= 768)、左右離邊 >= 96、timeline 說明放不下、list note 貼到最後一項、versus 內文超出面板,任一項成立就報錯。
- 顯示文字正規化 `norm_text`:動畫內所有顯示文字(標題、項目、節點、說明、欄標題、caption、src、單位)畫字前套用,半形 `, ( ) : ; ? !` 在前後任一側是 CJK 時換全形(1,000、Take-Two (2K) 這類純英數不動)。
- 共用色票 `PAL_TEXT/TEXT2/NEUTRAL/ACCENT/NEG/LINE` 起;所有動畫文字描邊 2px;`_title_block` 底下短橫條為 `PAL_TEXT2` 60% 不透明
- 逐步類型(list/bars/versus/flow/cols/share/num)連續句要合成同一個鏡頭:每句 anim 除 step 外必須完全相同(含 `src`);timeline 連續 step 且同一組 points 才同為一鏡
- 時長規則:每步在該句開頭出現;最後一步完全顯示後再停 ANIM_HOLD=1.5 秒(emoji 為 ANIM_PAD=0.5),不足由 build_timeline 補靜音
- 星座背景:`make_star_bg(t)` / `over_star`(--anim-bg star;`_StarBG` 在 `anim_lib.py` 檔尾)。整數格取 `格索引 mod STAR_N(150)` 的快取:磁碟 `build\_anim\star_v{STAR_VER}\NNN.png`(無損 RGB,共約 31MB)+ 行程內 LRU(60 張);改星座外觀必須升 `STAR_VER`。`_star_compute` / `_over_star_ref` 是原本的即時算法,供逐像素比對。`build_anim_shot` 簽章用 `f0 % AL.STAR_N`。
- `anim_preview.py <script.json> <資料夾> --sheet`:全片動畫鏡頭最後一格拼成 `sheet_NN.jpg`(960x540 三欄、每張 9 格)並印 `anim_problems` 異常與總數;`share` 段內數值依段底亮度選白字或深字(`_rel_lum`、`SHARE_LUM_DARK`)
- `anim_make.py`(263 行):`build` 產 anim/ 素材庫(manifest 雜湊,參數 --root --force --only --title --test);`anim_preview.py` 看版型(`--types`,`--bars-demo`,`--new-demo`)


## 6. 網頁渲染(anim_web,2026-10-22 起預設)
anim 預設 `engine: web`(`pipeline\anim_web.py` + `templates\anim\<type>.html` + `tokens.css`,GSAP 逐格 seek 截圖);網頁模板狀態(2026-10-22,計畫 #2 第一部分):`bars`(含多系列 `series`)、`list`、`num`、`versus`、`span`、`stamp`、`flow` 已有;`timeline` 也已接上(2026-10-22 計畫 #3a:`anim_web.timeline_data` + `build.tl_web_spec` / `_web_layers`;自帶 points 與頂層共用 timeline 都走 web,連續 step 同一鏡頭,同 step 的後續句凍結終態,`engine: pillow` 走舊路);`cols`、`share` 也已有(2026-10-22 計畫 #3c,見本節末「cols / share / bars 升級」);bars / cols 的 `shock` 軸暴衝選項(2026-11-05,見「bars·cols 軸暴衝」);只有 `puzzle`、`emoji` 仍走 pillow。欄位與舊 anim_lib 完全相容(`@def anim` JSON 不改),文字照舊走 `norm_text`;標題左對齊(同 bars:`--pad-x` / `--title-top`),版面常數在 tokens.css,節奏常數取自 anim_lib。
- `list`:`title`、`items`、`note?`、`src?`、`step?`("all" 或第 k 項彈出;step 的 prev/shown 由 `build.list_plan` 給,build.py `_web_layers` 為此多一個分支)。字級 72 先縮到 52 再換行,列距 ≤170。
- `num`:`big`、`label?`、`compare?`、`tone?`(up/down 加三角)、`step?`(0 = label+big、1 = compare)、`src?`。開頭單一數字 count-up 0.8 秒。
- `versus`:`title`、`left` / `right` = `{head, lines(1..2), mark?(yes/no)}`、`step`(0 標題欄 / 1 左 / 2 右,必填)、`src?`。內文字級 72 → 56。
- `flow`:`title`、`nodes`(2..4,可含換行)、`step`(必填,step n = 顯示到第 n 個節點)、`src?`。節點字級固定 70,換行段各自平衡斷行。
- `span`:`from`、`to`、`big`(含數字則 count-up)、`caption?`、`ticks?`(預設 8)、`src?`。無標題。
- `stamp`:`text`;0.6 秒落下 + 衰減震動後定格,斑駁用 SVG feTurbulence(seed = 文字雜湊,可重現),中心 (960, 430)。
- timeline(templates/anim/timeline.html):舊 points/step/question_between 原樣可跑;新增 scale:"time"(依 YYYY、YYYY/M、YYYY/M/D、M/D 比例排列,間隔過大自動斷軸 //,斷軸 ≤2,超過改均分;無法解析退回均分)、tracks:[{name,color?}]≤3(點第 3 欄 {"track":索引或名稱};每軌一條基線,底部共用軸刻度對齊事件點)。
- 版面自動:單排 → 上下交錯(>8 點直接交錯)→ 縮字到 44;邊緣標籤往內平移不限寬;「?」與標籤重疊時自動上下移或縮小;問題寫入 problems。
- 資料契約:points, scale, tracks, question_between, src, W, H, prev, shown, q, gap=1.2, lead, dur。step k -> prev=k, shown=k+1, dur=1.2;"q" -> prev=shown=n, q=true, dur=2.0。
- 動態:軸線由左至右畫出 → 節點 back.out 彈入 → 新節點金色,下一步 0.3 秒退回原色;「?」彈入後上浮 3px 回位,不循環。
- 接線:自帶 points 的 anim 只用自己的 points / question_between / scale / tracks;沒有 points 退回 script 頂層 `timeline`(含其 scale / tracks;anim 自己寫的 scale / tracks 優先)。無 step 的 `timeline_data` = 全播(prev 省略,段長 1.2 × 節點數)。
- 共用斷詞(`pipeline	ext_wrap.py`,jieba + `sub_words.txt`,閱讀卡 `news_lib` 與 anim_web 共用):anim_web 對所有顯示的中文字串(title、items、note、flow 節點、versus、num label/compare、span caption、timeline 說明、bars 標籤)在詞與詞之間插 U+200B(`zwsp`),`tokens.css` 設 `word-break: keep-all; line-break: strict`,中文只在詞邊界換行;timeline 的 wrap 優先用注入斷點(沒有才退回 `Intl.Segmenter`)。斷錯的詞(如「貝爾蒙特」)加進 `pipeline\sub_words.txt`;該檔內容在 `anim_web.sig` 內,改了鏡頭快取自動失效。

### 新圖表 line / table / kpi(2026-10-22,計畫 #3b;只有網頁版,寫 `engine: pillow` 或直式會被 parse_anim 擋下)
共通:`title`(必填)、`src?`、`unit?`、`hi?`、`step?`(省略 = 一次播;`"title"` 或 0..n-1 逐步,連續句合成同一鏡頭,規則同 bars:step k = 顯示到第 k 項,level = k+1;`build.LEVEL_TYPES`、`AW.new_step_seconds` 是段長權威)。字級 ≥44;放不下先縮字(table 52→44)、換行(只在詞邊界),再不行寫 `problems`(渲染時印「警告」)。容量上限由 `build._parse_web_only` 擋(超過請拆成兩張,**不做自動分頁**:逐列 / 逐格 step 已是分段呈現)。動態:ease-back 彈入、count-up、無光暈。測試 `tests\test_anim_web.py`(三型 seek 末格無 JS 錯 + 確定性)。
- `line`:`x`(2–24 個類別或日期標籤)、`lines`(1–3 條 `{name?, data}`,`data` 與 x 等長數字;多條必須有 name,出圖例)、`scale?:"time"`(x 按日期比例;YYYY、YYYY/M、YYYY/M/D、M/D,須遞增)、`area?`(面積)、`unit?`(圖例列右側「單位:xx」+ 末點數字單位)、`points?`(≤5 個 `[x, 短標籤≤10字]`:垂直金色虛線 + 圓點落在第一條線 + 標籤,隨最後一條線畫到該 x 時彈入;類別軸 x 須是 x 裡的標籤,時間軸可是範圍內任意日期)、`hi?`(線序號或名稱:加粗 + 末點數字金色;同一張圖所有末點數字用同一個小數位數:資料中最多的,上限 1)、`ymin?`/`ymax?`。y 刻度自動取 1/2/5×10^n;預設從 0 起(面積,或最小值 ≤ 最大值 60%),否則從資料最小值起。`step` = 畫出第 k 條線(標註點在最後一條畫完時彈入)。線由左至右畫出(clipPath 線性),末點數字 count-up。id:`#line-k`、`#end-k`、`#note-j`。
```json
{"type":"line","title":"三款遊戲同時在線人數","unit":"萬","scale":"time","hi":"乙","src":"SteamDB","x":["2021/1","2021/9","2022/4","2022/12","2023/8","2024/3","2024/11"],"lines":[{"name":"甲","data":[52.5,61,74,70.2,88,96,120]},{"name":"乙","data":[30,38,35,60,82,91,98.5]},{"name":"丙","data":[80,72,66,51,40,35,28]}],"points":[["2021/9","改版"],["2022/12","漲價"],["2024/3","停服"]]}
```
- `table`:`cols`(1–4 個表頭,不含首欄)、`rows`(1–5 列 `[項目, 格…]`,格數 = cols 數)、`corner?`(首欄表頭)、`hi?`(`{"row":k}` 或 `{"col":j}`,0 起算二選一,金色外框不改填色)。格子:`true`/`"✓"` = 綠勾、`false`/`"✗"` = 紅叉(SVG 筆畫畫出)、數字(整數 ≥1000 加千分位)、短字白字。`step` = 顯示到第 k 列(表頭隨標題出現;hi 外框在其列或最後一列出現後彈入)。字級 52,列多或換行時縮到 44;列數少時列高拉到最多 1.9 倍字高。id:`#row-k`、`#hi`。
```json
{"type":"table","title":"五款主機規格比較","corner":"主機","cols":["記憶體","儲存","支援四K","上市價"],"src":"官方規格頁","rows":[["PlayStation 5","16 GB","825 GB",true,"$499"],["Xbox Series X","16 GB","1,000 GB",true,"$499"],["Xbox Series S","10 GB","512 GB",false,"$299"],["Switch 2","12 GB","256 GB",false,"$449"],["Steam Deck","16 GB","512 GB","✗",649]],"hi":{"row":3}}
```
- `kpi`:`cells`(2–4 格 `{label, value, unit?, delta?, note?}`,頂層 `unit` 為各格預設單位)、`hi?`(格序號,金色外框)。`value` 為數字或字串:字串取第一段數字做 count-up,前後文字當前 / 後綴(「約 18%」→ 約 + 18 + %;無數字則直接顯示);`delta` 以開頭 `+` / `-` 判定,預設正 = 綠上箭頭、負 = 紅下箭頭、其他灰,文字照寫;每格可選 `better:"up"|"down"`(預設 up;down = 數字越低越好,例「負評比例 ▲+6%」上升顯示紅、下降顯示綠,箭頭仍照實際漲跌);數字字級全格共同(2 格 160 / 3 格 150 / 4 格 120,放不下往下縮到 72,仍不行報 problems);標籤 / 數字 / 變化 / 註四條水平帶全格對齊。`step` = 顯示到第 k 格。**數字字級不可 >160px**(Skia GPU 的 >162px 文字走 SDF 路徑,count-up 時同格兩次渲染有數個像素的隨機差,確定性測試會抓到)。id:`#cell-k`、`#val-k`。
```json
{"type":"kpi","title":"上市第一週成績","unit":"萬","src":"官方公告","cells":[{"label":"銷量","value":320,"note":"含數位版"},{"label":"同時在線","value":185.5,"delta":"+12%"},{"label":"退款率","value":"4.2%","unit":"","delta":"-0.8%","note":"歷史新低"}],"hi":1}
```

### bars·cols 軸暴衝(2026-11-05;外部設計參考 video-shotcraft 的 axis-rescale-shock,只參考畫面設計,程式自寫)
- **軸暴衝**(`bars` / `cols` 的 `shock` 選項;不開 = 省略或 `false`,模板資料與輸出和舊版逐像素相同):某一項(`true` = 數值最大的一項〔並列取第一個,不一定是最後一項〕,整數 = 指定項序號,0 起算、groups 跨組依序)的數值遠大於其他項時,先照舊比例尺(其他項最大值只佔繪圖區 55%)長出,暴衝項長到天花板線後加速衝出框(天花板線變金),接著座標軸重縮放(暴衝項 = 滿格、其他條等比縮短 0.7 秒),暴衝項定格金色並在此時才出數字(count-up)。重縮放完的畫面 = 一般排法 + 暴衝項金色。
  - 限制(parse_anim 擋):單系列(不可搭 `series` / `stack` / `ref`)、數值非負、暴衝項須 >= 其他項最大值的 2 倍(`AW.SHOCK_RATIO`,差距不夠大就不要開)、只有網頁渲染。
  - 段長 + 1.4 秒(`AW.SHOCK_EXTRA_S`;`build.anim_seconds` / `level_seconds` 自動加)。逐步模式只在暴衝項長出的那一步(`prev <= shock < shown`)播暴衝;之前的步驟停在舊比例尺、之後停在新比例尺。
  - 橫條衝向右、直條衝向上;衝出量受右邊安全邊 / 標題限制(最多約 200px / 80px)。直式同樣支援。
```json
{"type":"bars","title":"各平台月活躍","shock":true,"src":"公開財報","items":[["甲平台",12,"萬"],["乙平台",18,"萬"],["丁平台",150,"萬"]]}
{"type":"cols","title":"每月新增玩家","shock":3,"items":[["8 月",12,"萬"],["9 月",18,"萬"],["10 月",15,"萬"],["11 月",160,"萬"]]}
```
測試 `tests\test_anim_web.py`:軸暴衝(衝出 / 重縮放途中)的確定性 + `test_shock_off_same_data`(不開時資料與舊版相同)+ `test_shock_true_targets_max`(最大項不在最後時 `true` 指向最大項)。寫稿提示:`script_lint` 對單系列 bars / cols 沒寫 shock、最大值 >= 次大值 3 倍時提示「可加 "shock":true」(警告級,不擋)。

### cols / share / bars 升級(2026-10-22,計畫 #3c;網頁版;`engine: pillow` 只認舊欄位,用新欄位 parse_anim 報錯)
系列色改成藍 #4f9dff / 青綠 #2fd1b4 / 珊瑚 #ff8a6b(`--series-1..3`,share 第 4 段紫 `--series-4`),負值紅 `--neg-fill` #ff5a5f,系列色上的字 `--on-series`;bars / cols / line / share 共用,單系列用 series-1,hi 仍是金色(多系列 hi = 金色外框 + 數值金色)。
- `bars` 新增:`stack:true`(需 `series`,各系列疊成一條,段內放得下就標數字,總和標在末端;堆疊不可有負值)、`ref:{value,label}`(垂直虛線 + 上方標籤,例 `{"value":80,"label":"80% 門檻"}`;value 納入比例尺)、負值(以 0 為中線,負值向左、單系列紅色、多系列保留系列色 + 數值紅字;`ref.value` 可為 0)、網頁版最多 10 條(pillow 仍 7)、標籤過長先縮字再換行(詞邊界)。`items` / `groups` / `step` / `series` / `hi` 行為不變。
- `cols`:舊欄位 `items:[[標籤,數值,單位?,{hi?}?]]`(單系列沒有 hi 鍵時自動強調最大值)原樣可跑;新增 `series`(2–3,每項數值改為 `[v1,v2,…]`,缺值 null,圖例 + 「單位:」靠右)、`stack`、`ref`(水平虛線,標籤在線的右端外側)、負值(基線以下、紅色,類別標籤固定在圖底)、x 軸為年份 / 時間序列(類別等距)、網頁版 2–12 組(pillow 2–7)。`step k` = 顯示到第 k 組(該組各系列一起長出)。id:`#col-k-s`、`#val-k-s`、`#lbl-k`、`#ref`。
- `share`:舊欄位 `rows:[{label, parts:[[名稱,數值,顏色?]…2–4 段]}]`(1–4 列,每列總和 99–101)、`unit`(預設 `%`)原樣可跑;新增 `style:"bar"|"donut"`(預設 bar = 100% 堆疊條;donut 只限單列,多列 parse_anim 報錯)。段內數值放不下 → 移到條下方 / 環外並加引線(`problems` 檢查互碰);同名稱同色;未指定色依序取 series 1..4;亮底段用深字。bar 的圖例在標題下,donut 的名稱清單在環右側、列標籤在洞中。`step`:"title" = 標題 + 圖例,k = 顯示到第 k 列。id:`#seg-i-j`、`#row-i`。
- 段長沿用 `AL.cols_step_seconds` / `share_step_seconds`;cols / share 的網頁版不跑 pillow 版面檢查(`_check_src` 略過),版面問題由模板寫入 `problems`(渲染時印「警告」)。
```json
{"type":"cols","title":"各平台遊戲營收","series":["PC","主機","手機"],"stack":true,"ref":{"value":250,"label":"目標"},"src":"自編","items":[["2021",[38,52,90],"億"],["2022",[41,55,96],"億"],["2023",[48,58,101],"億",{"hi":true}]]}
{"type":"share","title":"營收來源占比","style":"donut","rows":[{"label":"2025 年","parts":[["遊戲銷售",62],["內購",24],["訂閱",11],["其他",3]]}]}
{"type":"bars","title":"三平台每月用量","series":["Steam","PS5","Xbox"],"stack":true,"ref":{"value":300,"label":"300 萬門檻"},"items":[["一月",[120,90,40],"萬"],["二月",[130,95,45],"萬"]]}
{"type":"bars","title":"各遊戲評價變化","ref":{"value":0,"label":"零成長"},"items":[["遊戲甲",24.5,"%"],["遊戲丙",-8.5,"%"]]}
```
樣本與驗收腳本:`tmp\aw3c\run.py`(渲染到 `tmp\aw3c\<名>_last.png`;含 bars / cols 舊定義 parse_anim 回歸)。測試 `tests	est_anim_web.py` 含 cols / share / donut / 堆疊 / ref 的確定性。

### 直式網頁圖表(2026-10-22,計畫 #5b)
- **畫布**:直式動畫沿用既有 `--portrait` 原生畫面窗 **1080x1080**(成片 y 260–1340,字幕在窗外),不是 1080x1920 全幅。文字安全框 x 80–940、y 40–1040(同 `build.P_SAFE`),所以窗內下方不留字幕帶。
- **切換方式**:`anim_web.open_job` 依 job size 在 `<html>` 設 `--W/--H` 並在 `W <= H` 時加 class `portrait`;`tokens.css` 的 `:root.portrait` 覆寫 `--pad-x 80 / --pad-r 140 / --title-top 48 / --fs-title 64 / --content-top 250 / --content-bottom 1000(有出處 960)/ --plot-bottom* / --src-right 140 / --src-bottom 1030`,標題寬 860 允許換行。模板內以 `const P = d.W <= d.H` 分支,右緣一律用 `--pad-r`,內容頂端 = max(`--content-top`, 短橫條下緣 + 28)。橫式值不變(list / flow / num / versus / span 重渲像素差 0)。
- **支援清單**:`anim_web.PORTRAIT_OK` = **全部 13 型**(bars cols line share table kpi + list num versus span stamp flow timeline;寫在一處,`AW.has_template(t, portrait=True)`)。直式 `build.anim_engine` 全走 web(`engine: pillow` 仍可強制 pillow);`AL.P_NATIVE` 的 timeline / list / bars 在未寫 engine 時也改走 web;`portrait_window` 視為原生鏡頭。`check_web_capacity(portrait=True)` 對全部型別以 1080x1080 量(安全區左 80 / 右 140 / 上下 40)。
- **各型規則**:bars <= 12 條、標籤欄 <= 300 寬(換行,行高 1.1)、條厚上限 72(多系列 56)、列距上限 40、下限 40 / 12;cols <= 6 組(超過報錯「請改寫成 bars 或拆成兩張」)、圖高上限 640、字級 44–56;line x 軸標籤最小間距 28 -> 72(刻度約減半)、繪圖區寬下限 400;share 條形:列標籤在條上方、條滿寬 860,甜甜圈置中、圖例在圖下方;table <= 3 欄(超過報錯)、首欄寬 <= 300;kpi 2 格上下疊、3–4 格 2x2(數字字級 120 / 92,標籤 48、變化 52)。文字下限仍 44(註記 30)。
- **橫式繪圖區拉高**:bars 條厚 / 列距從上限(96 / 64,多系列 72 / 56)開始,放不下才等比縮到 36 / 20,條少時維持上限並讓內容靠下(剩餘空間 80% 留在上方);bars / cols / line 的繪圖區下緣改用 `--plot-bottom`(800)/ `--plot-bottom-src`(780),line x 軸標籤下緣離字幕安全線 72(有出處)/ 52px。
- **bars 長標籤**:標籤超過欄寬先縮字到 44,再換行;換行後高度超過列距寫 `problems`(「標籤…換行後高度 N px 超過列距(縮短標籤)」),渲染前檢查列為錯誤。實測 30+ 字單一標籤橫式 5 行 202px、直式 339px 都會被擋。
- **確定性測試**(`tests	est_anim_web.py`):同一格「連續播過來」與「獨立 seek」偶爾差 1 個字形邊緣像素(alpha <= 10,Chromium 層光柵的歷史相依;DOM style 兩邊逐字相同,換軟體光柵 / force3D / 整頁重繪都無法消除),比對改為預乘 alpha 後容許 <= 8 個像素、每通道差 <= 40。

### 直式七型與 kit(2026-10-22,計畫 #5c;模板內以 `const P = d.W <= d.H` 分支,橫式像素差 0)
- **list**:單欄,字級 60 -> 44 自適應(項目一律換行,寬 = 940 - 文字起點);全部放不下一頁就依序切頁(各頁高度二分搜尋平均,最多 3 頁,超過寫 `problems`),上一頁在新頁第一項彈出前淡出(逐步模式 0.1 秒、全播用間隔內 0.3 秒);note 只在最後一頁。
- **num**:置中於安全框(cx = 510),大字寬上限 860(字級 300 起縮到 60)、label / compare 可換行(64px),label / 大字 / compare 中心 y = 250 / 520 / 790。
- **versus**:左右兩格改上下兩格(寬 860、高 = (內容區 - 24) / 2);欄標題在上、✓ / ✗ 在左(88px)、內容在右,字級 64 -> 44。
- **span**:**維持橫向軸但縮短**(x 130–890;大字在上 cy 230、軸 y 560、兩端標籤 64 -> 44、說明換行置中),理由:大字是主角,縱向軸要另建一整套版面且與刻度逐一亮起的節奏衝突。
- **stamp**:置中於 (510, 520),寬上限 724(傾斜 8 度後仍在 x 80–940),字級 170 起縮到 60;不分兩行(旋轉後文字外框互相重疊,容量量測會誤報)。
- **flow**:節點由上而下(寬 860、高 <= 220,字級 56 -> 44)、箭頭向下(軸由上往下長、箭頭尖前進);2 個節點間距 100、3–4 個 80。
- **timeline**(`buildPortrait`):單軌 = 縱向軸在左、年份靠軸左側右對齊、說明在軸右側(字級 56 -> 44;「?」放在 `question_between` 兩點之間預留的 150px 空白);**多軌 = 軌道並排成直欄**(欄名在上,節點在各欄縱線上,年份在上說明在下,字級 48 -> 44,同欄不重疊往下排);放不下依序切頁(各頁平均,最多 3 頁)。直式一律均分順序,**不做 `scale: time` 的時間比例與斷軸**(靜默改均分)。
- **kit 直式**:`kit.layout / job(portrait=True)`,`KIT.PORTRAIT_VIS = (80, 40, 940, 1040)` = 窗內文字安全框(字幕在窗外,下方不留字幕帶),可放區 = vis(不再內縮 40)、箭頭不出框、`lower` 無目標時貼安全框左下(x 80)。直式動畫鏡頭由 `build.plan_kit_portrait` 產 1080x1080 圖層(`at.el` 以直式圖表頁量外框,`at.box` = 窗內百分比,`at.text` 與 timeline 的 el 略過並警告),`portrait_cmd` 把圖層疊在動畫上、卡片之下(`s["pwin"]["kit"]`);其他直式鏡頭(影片取景 / 引言卡 / 對比)的 kit 仍是橫式成品鏡頭上的圖層(只進模糊底圖),窄版截圖的 `at.text` 直式未做。
- **open_job 預播**(`anim_web.VERSION` 5):build 完先播到底再回 0,讓位置 0 的 `tl.set` 生效。之前逐步模式的第 0 格、以及「同 step 後續句只取第 0 格」的凍結段,終態項目整張空白(橫式也有;直式端到端時發現)。

## 7. 動態小件 kit(2026-10-22,計畫 #4a;`pipeline\kit.py` + `templates\kit\kit.html`)
句子行尾 json 加 `kit:[{type, at?, t0?, …}]`(單一物件也收;`script_txt2json` 擋欄位錯,數量上限由 `script_lint` 報超標、build 渲染前檢查列錯誤)。`t0` = 相對該句配音起點秒數,預設 0.3;同一鏡頭跨多句時各句小件依時間疊在同一鏡頭(小件歸屬「出現時刻所在的鏡頭」)。
- **目標 `at`(三選一)**:`{"text":"一團亂"}` 截圖 / 閱讀卡的字(`.boxes.json`,同 hl:忽略空白大小寫、可跨行,取第一個命中的外框);`{"box":[x,y,w,h]}` 畫面百分比(影片片段、實機畫面;圖片鏡頭上視為畫布座標,跟著漂移);`{"el":"#bar-2-0"}` 網頁圖表元素(只限網頁圖表鏡頭,timeline 除外;build 開圖表頁播到底量外框)。
- **小件與欄位**(顏色只用 tokens:金 `--accent`、綠 `--pos`、紅 `--neg`、`--panel`;線條下墊 55% 深色描邊,不模糊、不是光暈):
  - `callout`:`at`、`pad?`12、`width?`3 —— 圓角框從左上順時針畫出 0.5 秒。
  - `arrow`:`at`、`from?`(auto / tl / tr / bl / br / l / r / t / b;auto = 從目標朝可見區中心那一側出發)、`len?`200、`gap?`18 —— 線伸長 0.4 秒後箭頭出現(尾端浮動 ±3px、週期 2.4 秒,圖層渲到鏡頭結束;位置見「擺放規則」))。
  - `zoom`:`at`、`scale?`1.6、`r?`170 —— 圓形放大鏡從目標滑出 0.45 秒;來源是該鏡頭底圖(text 組 = 補邊 2x 合成圖、tilt = 前景畫布、引言 / 對比 = 整張);影片與動畫鏡頭不支援(模板 problems 警告)。
  - `spotlight`:`at`、`dim?`0.6、`pad?`16 —— 目標外變暗 0.3 秒淡入;**不可用在 tilt 鏡頭**(lint / build 擋)。
  - `pop`:`text`、`at?`、`size?`120 —— 金字深描邊,ease-back 彈入;沒給 at 放可見區中上。
  - `badge`:`text`(含數字就 count-up 0.8 秒,保留前後綴與千分位)、`at?`、`dir?`up / down(▲▼,綠 / 紅底)、`tone?`(accent / pos / neg)、`size?` —— 目標右上外側彈入。
  - `lower`:`text`、`sub?`、`at?` —— 下標籤(深藍底板、白字 48 / 次字 36、金色底線展開),左側滑入;預設左下(x=96、下緣在字幕帶上 40px)。
  - `tick` / `cross`:`at`、`side?`right / left / center、`size?` —— 筆畫畫出 0.3 秒(綠勾 / 紅叉)。
  - `progress`:`value`(0–1 或 "3/5")、`label?`、`at?` —— 進度條 0.8 秒填滿;預設在字幕帶上方整寬。
  - `punch`:無欄位 —— 整個鏡頭畫面 1.0→1.06→1.0(0.25 秒),不產圖層。
- **節制規則**:同一句 ≤2 個(punch 也算)、punch 每句 ≤1、同一鏡頭 ≤4、spotlight 不配 tilt。
- **擺放規則(2026-10-22;`kit.layout`,自由擺放的小件不蓋文字與圖表元素)**:障礙物 = 該鏡頭全部文字框(`.boxes.json` 全部行 + 出處標籤框,換算成畫布 / 成片座標;fx 動態以 u=0 / 0.5 / 1 掃過的外接框)+ 圖表模板所有文字與色塊外框(anim_web 播到底後量 DOM,`probe.all`)+ 字幕安全區(`IMG_BOTTOM_KEEP` 帶,框不進 `vis` 下緣以下)+ 其他已放小件框(callout / tick / cross / zoom 圈 / progress / 箭身)。排序:固定框的 -> arrow -> lower -> badge -> pop。
  - `arrow`:目標周圍找「箭尾離目標框 120–260px、箭身(線寬 10 外各留 7px)與箭頭(3px)不碰任何障礙物」的方向,優先右上、左上、右下、左下,再試其他角度;尖端停在目標框外 8px(同目標有 callout 時停在 callout 框外);目標所在的文字框先扣掉目標本身。全不行 = 選侵入最少者並警告。擺放後 `from` / `len` / `gap` 不再生效。
  - `pop`:目標附近最近的空白處(離任何障礙物 ≥24px);字級最多縮 3 級(×0.85 / 0.72 / 0.6);仍放不下 = 畫面中上方重疊最少處並警告。
  - `lower`:左下字幕線上方(x = 可見區左 +96、下緣離字幕線 16px),與文字框重疊先往上找空白帶(≥16px),再縮小一級(×0.8),仍重疊才警告。
  - `badge`:目標外側 右 > 上 > 左 > 下(離目標 12→20→32px、沿邊滑動),離障礙物 ≥8px;四側都不行就取全畫面最近的空白。el 目標一樣。
  - callout / tick / cross 本來就框目標,不動。放不下列「警告」(不是錯誤):圖片 / 影片鏡頭在 `--check-only` 就算得出來(`小件擺放: …`);圖表 el 鏡頭在渲染時由 anim_web 印 `[anim_web] kit 警告:…`。每個圖層的最終框與障礙物存 `build\_anim_web\kit_<key>\kit_layout.json`(含每件離最近障礙物的距離)。字寬以 Pillow 估(誤差小於邊距)。
- **`el` id 清單**(都是播完的終態外框):bars `#title`、`#lbl-k`、`#bar-k-s`、`#val-k-s`、`#ref`(堆疊時整條 `#bar-k-0`、總和 `#val-k-0`);cols `#title`、`#lbl-k`、`#col-k-s`、`#val-k-s`、`#ref`、`#base`;line `#title`、`#line-k`、`#end-k`、`#note-j`;table `#title`、`#head`、`#row-k`、`#hi`;kpi `#title`、`#cell-k`、`#val-k`;share `#seg-i-j`、`#row-i`(k / i = 項序、s = 系列序、j = 段序,從 0 起)。
- 範例行:
```
img:hcg|可是同樣這些評論一面倒說它一團亂 ;; {"hl":["一團亂"],"kit":[{"type":"callout","at":{"text":"一團亂"}},{"type":"arrow","at":{"text":"一團亂"},"t0":0.8}]}
img:khan|預告一出來韓國的體育京鄉就整理了玩家的反應 ;; {"kit":[{"type":"lower","text":"體育京鄉","sub":"2026/05/29"},{"type":"spotlight","at":{"text":"遊戲就只是遊戲"},"t0":0.6}]}
anim|三月是唯一破門檻的月份 ;; {"anim":"usage","kit":[{"type":"callout","at":{"el":"#bar-2-0"}},{"type":"badge","text":"302萬","at":{"el":"#val-2-0"}}]}
```
- **自動 lower(截圖出處,2026-10-22)**:page 模式截圖的出處角標改成鏡頭起點自動加的 `lower`(主字「原文:站名」、副字「中文翻譯 · 日期」,資料來自 `.layout.json` `tag_text`),不寫在 script、不算同鏡頭 <= 4 上限;同鏡頭已有自己寫的 lower 就不加(保留舊角標)。退回舊角標:`label_style: "corner"`(單句 / 頂層)或 `--label-style corner`。細節見 build.md「截圖出處標籤 = lower」。
- 測試 `pipeline\tests\test_kit.py`(定位換算、fx 跟隨、節制規則;`python -X utf8 pipeline\tests\test_kit.py`)。
