# 素材程式(截圖與片段)

(原 README 章節 §6;文中 §n 沿用原編號,對照見 README.md §2。行號不寫在文件裡:`python -X utf8 pipeline/tools/funcmap.py --grep <函式名>`)

## 6. 素材程式
**flow v3:代理程式主導**(B10,`director_ab._asset_call`):素材員 effort low、只准跑本節的 assets/clips/news_lib 指令,不得 Read 圖片/影片檔,靠 `--check` 文字結果判斷。
代理回報後 director 對每個 ok=true 的截圖項自己再跑 `assets_<簡稱>_news.py --check <name>`(`verify_screens`;news 檔的 `main(SPECS, "<tag>", …, prefix=…)` 的 tag 必須是片名,否則視為找不到而 ok=false)。
manifest 項可有 `why`(ok=false 的原因);v2 不變。
### 新片截圖:news_lib.py + news_specs.py(F3-0/F3-2,2026-10-14 起新片一律用這個)
- **新片 news 檔 ≤ 40 行**:`SPECS = {...}`(呼叫 news_specs 工廠)+ `HL = {...}` + `main(SPECS, "<tag>", HL)`。範本與回歸樣板 `assets_gd2_news.py`(33 行)。舊的 `assets_*_news.py` / `assets_*_specs.py` 全部 legacy,不刪不改。
- `news_lib.py`(截圖引擎,合併 assets_re9_news 引擎 + assets_gd_news 檢查;其餘 6 份 news 檔與 gd 版只差輸出前綴/specs 模組名):`main(SPECS, tag, HL=None, prefix=None, argv=None)` 入口,輸出 `<prefix><name>.png/.boxes.json/.layout.json`,`prefix` 預設 `<tag>_`(沿用舊前綴時覆寫)。指令:`[name…]` 截圖、`--only a,b`、`--check`(HL + 版面 + 墨跡)、`--dump`(列原文供寫 rules)、`--relabel a,b`(只換標籤,重截被擋的圖)、`--overview [檔]`、**`--out 資料夾`(預設 images/;回歸/試截用 tmp\…,避免覆寫定稿圖)**。
- 窄版(F3-4,Shorts 直式用):`--narrow`(常數:輸出 `NARROW_W` 1000 寬、視窗 <= 680、spec css 的 width/max-width 壓到 `NARROW_CSS_W` 620、頁內字 >= `NARROW_MIN_PX` 36、全部改可換行、padx 10 / `NARROW_EDGE_PX` 24、`JS_HIDE_FLOAT` 隱藏固定/黏住的元素與無文字的絕對定位小圖示、標籤字 54)-> `<prefix><name>_p.png/.boxes.json/.layout.json`;`compose_narrow`。舊片 spec 用 runner(例 `from assets_gd_specs import SPECS, HL; main(SPECS, tag, HL, prefix="gd_")`)加 `--narrow`
- 函式:`build(SPECS, names, prefix, out_dir, dump)`、`check(SPECS, HL, names, prefix, out_dir)`(`_check_layout`/`_check_ink`)、`relabel`、`overview`、`compose`(單頁/`parts` 合成)、`capture`(兩段式,補邊)、`_open`、`_save_layout`、`JS_PREP/JS_TRANSLATE/JS_DARK/JS_LAYOUT/JS_RUNS`。SPECS 可為 dict 或含 `name` 的 list;規格欄位說明在檔頭;`hl` 欄位可取代 HL 字典。
- **暗色三層(news_lib `_open`,2026-10-22,PLAN_閱讀卡 §2B;只管 mode=page)**:spec `dark` = `auto`(沒寫就是 `DARK_DEFAULT`)| `native` | `force` | `js` | `off`。auto = ①`color_scheme=dark` 開頁(網站原生深色)→ 探測 `JS_BASELUM`(保留區塊祖先的底色亮度),仍亮 → ②改在**另開的強制深色瀏覽器**重開(`FORCE_ARGS` = `--enable-features=WebContentsForceDark:inversion_method/cielab_based/image_behavior/none`,圖片不反相;功能旗標是啟動參數,不能只對單一 context 開,所以 `build()` 註冊 playwright、用到才開第二支、結束關掉;沒註冊 playwright 的呼叫端退回 js)→ ③`JS_CAL` 校色(只把保留區塊與祖先的不透明底色統一 `#15202b`、近黑/近白中性字統一 `#e7e9ea`,灰字/有色字/圖片/邊框不動)。探測時先切回 light 量一次,仍暗 = 原本就是深色(層=dark0)三層全略過。`native` = ①+③、`force` = ①+②+③、`js` = 舊版 `JS_DARK` 整套變色、`off`/`False` = 不處理。各頁實際用了哪層記在 `news_lib._DARK_LAYER`。DARKFIX/`js` 欄位先跑,探測看的是跑完後的底色。
- 規格新增欄位(原本只有 gd 版有):`ua`(該頁 User-Agent,SEC 用)、`noscroll`(True=不捲動 lazy-load、不點 No thanks 類按鈕)。與 legacy 差別:引擎內不再 monkey-patch、狀態不放全域(版面資料由 `capture` 回傳)。
- `news_specs.py`(規格工廠,與舊版輸出逐欄位相同,`tmp\f30\eq_test.py` 46 項 dict 相等測試驗過):CSS/JS 片段 `FONT NOBORDER NOCASE FLAT DARKFIX unclip cut_js block_css inl title_css body_css`、`flat_all(SPECS)`(每張預設 js=FLAT,gd 用);通用 `art`(文章頁)`para`(單段)`gnn`;依網站 `kotaku`(標題+署名+日期+一段)`kotaku_head`(標題+副標)`kotaku_art` `kotaku_para`、`gs_para`(GameSpot)`gd_para`(Game Developer)`gb_para`(GamesBeat)`ign_p` `press_start` `ps_art` `gf`(Game File)`am`(Aftermath)`sec`(SEC 10-K,自帶 ua)`steam`(Steam 鑑賞家)`disc`/`meta`(暴雪論壇)。新站點:先用 `art`/`para` 湊,常用就加工廠到這個檔。
- **紅線序列**(計畫 §2C,2026-10-22;`hl` 欄位或 HL 字典有詞就出,`--narrow`/`--dump` 不出):主圖與 .boxes/.layout 截完後,同一頁 `JS_HL_WRAP` 把命中詞包成 `span.hl`(比對規則同 build.py `find_hl_boxes`,同詞最多 `HL_MAX` 處,跨行拆成每行一個 span;包完 span 位置變了就不出序列)→ `JS_HL_LAYER` 切成**底線圖層頁**(文字/底色/陰影透明、圖片 visibility:hidden、`omit_background`;`span.hl::after` 紅 #ff2d2d、粗 0.12em、左右延伸 0.15em,`--p` 0..1 用 clip-path 由左至右露出)→ 比對切換前後每個 span 的 getBoundingClientRect,任一邊位移 > `HL_SHIFT_MAX` 1px 就不出序列(印 `[紅線] 切成底線圖層後 span 位置改變`)→ 在圖層頁上 `JS_HL_BASE` 量基線寫 `--uy`(底線上緣 = 基線下 `HL_UL_BASE` 0.2em,超出截圖區往上收)→ 每條 p = 0.1…1 各截一張,裁切/補邊/縮放同主圖。
  - 檔案:`<prefix><name>_hl/b<j>_p00..p10.png`(只裁該條底線的小塊,p00 為空圖;j 依詞序再依文件序,同 find_hl_boxes 順序)+ `<prefix><name>.hl.json` = `{ver:1, size:[W,H], p:[0,0.1,…,1], bars:[{kw, x, y, w, h, files:[11 個相對 images/ 的路徑]}]}`,x/y 為原圖(畫布)像素。重截會先清掉舊序列;沒有任何底線就不寫 .hl.json(build 走舊畫法)。`.boxes.json`/`.layout.json` 格式不變。
  - 站方樣式的坑:Press Start 這類 WordPress 站 ① `*::after{display:none}` → `HL_LAYER_CSS` 用 `display:block !important` 蓋;② 區塊樣式 `html :where([style*="; border-color"]) {border-style:solid}`,行內寫 border-color 會讓每層祖先多出 3px 框線、內文下移(ps 圖 33px,底線落到截圖區外)→ 圖層頁只對本來就有框線的元素寫 border-color。新站出現 `[紅線]` 訊息就照這兩類查。
  - 驗證(2026-10-22):cod26 hcg 1 條、ps 1 條、khan 2 條;`tmp
c1\check_<圖>.png` 為 p=1.0 疊原圖。
- **閱讀卡(`mode: card`,計畫 PLAN_閱讀卡 §2A,2026-10-22)**:spec 明寫 `mode="card"` 才走卡片,**沒寫的舊 spec 一律 page、行為完全不變**(計畫原寫預設 card,為不動舊片改成明寫)。
  - 流程(`news_lib.card_prepare`,由 `capture` 入口呼叫):開原頁 → `JS_PREP`/`js`/`hook` 抓 meta(og:image、標題/署名等欄位原文)→ `JS_TRANSLATE`(rules 照舊)→ `JS_CARD_PARAS` 取譯文段落(targets 內非標題的文字,`<br>` 當分段)→ og:image 用同一個 context 下載到 `tmp\cards\<name>_hero.jpg`(失敗印 `[卡]` 警告、退回純文字)→ 寫 `tmp\cards\<name>.json`(抽取結果+字級結果)與 `.html`(單檔,CSS/JS 內嵌)→ 回傳指向本機 HTML 的 spec(targets=[".card"]、padx/pady=60,輸出剛好 1920x1080)→ 之後 `_open`/`JS_MEASURE`/`JS_LAYOUT`/`JS_RUNS`/紅線序列/`.boxes`/`.layout` 全部沿用。不加角落標籤(出處在卡內底列)。`--dump` 與 `--narrow` 不走卡片。
  - 模板 `pipeline\templates\readercard\`:`article.html`(頂列 [站名膠囊 · 日期]、標題 56px、英文原題 32px、署名、摘錄、右側 38% hero)、`para.html`(只有摘錄)、`post.html`(頭像/帳號/時間/內文/讚數)、`card.css`、`card.js`。粗體字型 `fonts\NotoSansTC-SubBold.ttf` 經 `paths.ROOT` 取路徑;內文 Regular 用系統 Noto Sans TC(`fonts\` 沒有 Regular 靜態檔)。`.hl` 不在 card.css 設樣式(紅線截圖時才包 span,頁面上必須純行內,否則版面位移)。
  - 字級自適應(`card.js`,PLAN §5.3):摘錄 ≤2 行 64px、3–4 行 56px、5–6 行 48px;主欄上下留白 > 卡高 25%(240px)就再放大一級(含 72px,最多 6 行);48px 仍 >6 行且有 hero → 把 hero 拿掉(主欄變寬)重量;標題 >2 行縮字 56→50→46。結果在 json 的 `fit`,`card_prepare` 印 `[卡]` 一行,超標印 `[卡·警告]`。
  - 留白放大級(2026-10-22):`card.js` 的 `LV` 在 64px 之上加 72、80 兩級,只給「主欄留白 > 卡高 25%」規則逐級放大用;80px 只限 para 版型,放大後行數不能比原本多,否則退回上一級。內容太少(2 行)時留白仍可能 >25%,只印 `[卡·警告]`。
  - 斷行與欄寬(2026-10-22):譯文裡單個 `<br>`(page 模式逐行用)在 card 模式合併成一段,前片段以「…」結尾才另起一段,連續兩個 `<br>` 才是明確分段;段落與標題由 `_wbr_html` 用 jieba(繁轉簡斷詞、同 build.py 作法,吃 `sub_words.txt`)在詞與詞之間插 `<wbr>`,CSS `word-break:keep-all; line-break:strict`,切點只落在詞邊界、行首不是標點;不用 `text-wrap:balance`(會壓窄行寬)。摘錄欄寬沒有 hero 時用滿卡片內寬;最後一行 ≤2 字(不計標點)時 `card.js` 逐步縮窄該段。內文字型 `fonts\NotoSansTC-Regular-static.ttf`(wght=400 靜態檔,`CARD_FONT_REG`),不用系統字型。hero 放不下(>6 行或內容高過主欄)就拿掉。
  - `card` 欄位:`layout`(article|para|post;預設有標題=article、否則 para)、`title`(中文標題,rules 沒翻譯標題時用;英文原題從 `title_sel`(預設 h1)抽並顯示在標題下,>110 字截短加「……」)、`byline_sel`、`date_sel`、`name_sel/time_sel/likes_sel`(post)、`hero`(False=不放圖)、`lang`("zh"=原文是中文,底列只寫「原文:網站名」)。網站名/日期取自 `site`(「網站名 2026/10」格式)。卡上字都來自原頁或 rules 譯文,不自己加字。
  - 驗證(2026-10-22):`tmp\rc2\run_cards.py`(複製 cod2026 的 hcg/kotaku_pcg/khan 加 mode: card,輸出 `tmp\rc2\`)`--check` 錯誤 0、紅線序列皆出;舊路徑 `assets_gd2_news.py --out tmp/f30` 與 `--check` rc=0。
- 回歸結果(2026-10-14,`assets_gd2_news.py --out tmp/f30`):5 張 gd_ 圖尺寸 1920x1080 相同、.boxes.json 與 .layout.json 完全相同;像素 4 張 0 差,k14_two 僅第 702 列 1589 px 不同(網頁內容,非引擎)。

### 檢查項(`news_lib.check`,`assets_*_news.py --check` 跑;PLAN_閱讀卡 §3 + PLAN_畫面優化六項 C,2026-10-22)
錯誤算進回傳值(rc=1),警告只印。常數都在 `news_lib.py` 的「渲染前檢查常數」。
- **閱讀卡**(`_check_card`,mode: card 才跑):所有 run 的框離卡邊(`CARD_RECT`=60,60,1860,1020)≥ `CARD_MARGIN` 40px,且文字框底緣 ≤ `CARD_SUB_TOP` 840(=1080−`build.IMG_BOTTOM_KEEP`,字幕帶;`card.css` .card 底部內距 180px 把出處列 `.foot` 抬進 840 以上,2026-10-22);標題 ≤ 2 行、摘錄 ≤ 6 行(讀 `tmp\cards\<名>.json` 的 `fit`);hero 抓失敗由 `card_prepare` 印 `[卡] hero 圖抓失敗…退回純文字版` 並把 `hero` 設 None,check 印「純文字版」。
- **紅線**(`_check_hl`,有 `.hl.json` 才跑):每條底線取 p=1.0 那張的紅色像素(alpha>128、R>200、G/B<110)。x 範圍 ⊆ 該行命中詞範圍 ± `HL_X_TOL` 0.2 字寬(「字寬」取字級與平均字寬較大者:CJK 等寬,英文字母窄但底線兩端固定外延 0.15em);上緣在該行 box 下緣 -0.15~+0.25 行高內(box 是字形墨跡框,實測上緣約在下緣 -0.07 行高);每個命中的每一行至少要有一條底線。命中比對同 `JS_HL_WRAP`(忽略空白大小寫、最多 4 處、不重疊)。**跨行本身不再是錯**:有 `.hl.json` 時每行一條、逐條驗;沒序列(舊畫法)才維持「不可跨行」。另外 runs 是逐文字節點切的(card 模式因 `<wbr>` 切很碎),同一行的詞會落在多個 run,比對是用字元序列不是單一 run。
- **暗色**(`_check_dark`,`dark` 不是 off 的 spec 都跑):全圖亮度中位數(Rec.601,0–1)> `DARK_LUM_MAX` 0.5 = 暗色沒生效,報錯。
- **純色塊**(`_check_flat`,C,只警告):重點區 = 文字框與圖形框(`layout.json` gfx)外包矩形外擴 0.5 倍行高(沒有任何框 = 整個截取區,抓空白頁);閱讀卡 = 卡面。取重點區最常見的 6 個顏色,各通道 ±6 內的像素做開運算(20x20 @ 1/4 解析度 = 去掉窄於 80px 的色帶,行距欄距不算)後取最大連通區域,佔重點區 > 35% 警告。有內容時排除頁面底色(閱讀卡:卡面 `#1c2a38`/卡外 `#15202b`;截圖:畫布左上角色與 `#15202b`),不然任何文字頁的留白都會報;沒有任何文字框/圖形框時底色也算,所以故意截空白頁會警告。驗證:blank(data: URL 空 div)99% 警告;hcg/kotaku/khan 0%;gd_ 五張 0%;Press Start 0%。
- **遺留修正(2026-10-22)**:`JS_CAL` 不再改淺底元素內的字(Bluesky「追蹤」鈕白底白字);`_open1` 的 `bypass_csp` + `ctx.route` 讓 https 頁載入本機 Noto 字型,Press Start 實測 `document.fonts` 載入 `Noto Sans TC Static` 400/700,譯文 `font-family` 第一順位為它。

### 截圖(assets_lib.py + assets_wowi_news.py + assets_wowi_specs.py;assets_*_news/specs 為 legacy,新片用 news_lib)
- `assets_lib.py`:字型/`wrap`、`Page`、`ocr`(T4:`OCR_ENGINE=win|rapid`,預設 Windows=win、其他=rapid〔`rapidocr-onnxruntime`,詞框為依字元寬度等分的估算,輸出預設 OpenCC 簡轉繁 `OCR_S2T`,`OCR_RAPID_REC` 可換繁體模型〕,rapidocr 沒裝時退回 Windows OCR;`ocr_batch(資料夾)` 給 clip_scan / gd_crowd_scan;`ocr_compare.py` 比兩引擎)、`save_boxes`(.boxes.json:每行文字框 {text, box, chars})、`add_label`(回傳標籤外框)、`ink_check`(墨跡檢查,見下)
- **標籤規定**:翻譯過的網頁截圖一律標「中文翻譯 · 原文:網站名」。規格的 `site` 只寫網站名(例:`Game File`、`SEC 10-K 年報(Take-Two)`),**不可以 `=` 開頭**(`=` 會原樣顯示、跳過這個格式)
- 引擎在 `assets_re9_news.py`:`JS_DARK`(白底頁改暗色 #15202b/#e7e9ea;spec `dark:False` 關閉)、`compose`、`capture`(截取區超出文件範圍時自己裁再補邊:Playwright 會把 clip 默默裁進文件內,區塊貼著頁面左/上緣或撐出右緣時圖會變窄、被拉寬、與框錯位;`JS_DOCSIZE`/`_frame_color`。選用欄位 `edge_px`/`top_px` = 成片上左右/上方至少留幾 px);SPECS 欄位說明在該檔檔頭:`url` `vw` `targets`([css]或[(css,內含文字)]) `rules`([(英文全文,中文)],`…`結尾=前綴比對,`re:`=正規式) `site`(標籤網站名) `css` `js` `dark` `cookies` `parts`(合成圖)
- `assets_wowi_specs.py`:`SPECS[name]=dict(url,vw,site,targets,css,rules,…)`、`HL[name]=[建議底線詞]`;`gnn()`、`block_css()` 為中文頁工廠;網頁截圖加 `padx=34`
- `assets_wowi_news.py [name…]` 產 images/wowi_<name>.png + .boxes.json;`--dump` 列原文區塊供寫 rules、`--check` 驗 HL 詞都在 boxes.json、`--overview` 總覽圖、`--reuse` 沿用上一支的圖(REUSE 表)。新片:複製這兩檔改 `OUT_PREFIX`/`TAG`/SPECS,不為每支重寫引擎
- `assets_dei_news.py`(dei 專用,規格在 `assets_dei_specs.py`)另有**版面檢查**:截圖時以 `JS_LAYOUT` 量每個文字框,存 `images/dei_<name>.layout.json`(與 .boxes.json 的 runs 一一對應);`--check` 驗:框完整在截取區內且左右離邊 >= 40px、中心點 `elementFromPoint` 沒被別的元素蓋住、沒被 overflow 非 visible 的祖先裁掉(以上為錯誤);字高 < 20px 列警告。舊圖沒有 layout.json 會略過並提示重截。
- **墨跡檢查**(`assets_dei_news.py --check`,`assets_lib.ink_check`;看 PNG 像素,不是只信框):文字墨跡離左右 >= 40px、離上 >= 24px;每個文字框內有墨跡且首尾字都在;框外同一列左右 40px 內沒有像文字的墨跡(框漏字/錯位);框與墨跡系統偏移 <= 8px。背景取每個框所在列帶的局部中位數色(Steam 這類非純色底可用),圖片與圖示的位置在截圖時由 `JS_LAYOUT` 量好存進 layout.json 的 `gfx`(檢查時略過),另以像素特徵排除色塊/項目符號/邊線;有底色的按鈕/膠囊(button/[role=button]/圓角>=6px、底色與頁面底色亮度差 >0.15、高 <=120 寬 <=600,如 Bluesky 的 Follow)也併入 `gfx`,但框內文字框會從排除區挖出來,字仍照常驗墨跡(`_carve_gfx`);標籤區與沒有 .boxes.json 的純圖片略過。最後印一行 `[墨跡總結]`(合格數、最小離邊、最大誤差、未合格名單)。截圖留邊目標 `EDGE_PX=64`/`TOP_PX=44`。重截被擋(403/驗證,不可繞過)的圖用 `--relabel a,b` 只換現有 PNG 的標籤。新片的截圖程式沿用這一項
- `assets_sv3_news.py` / `assets_sv3_specs.py`(survive3 專用,前綴 `sv3_`,引擎與檢查同 dei 版;規格 `fax`=evilresource 傳真內文、`alyssa`=英文維基 Outbreak 的 Alyssa 條目)。規格技巧:內文是 div 直屬文字節點時用 `js` 先包成 span 再套 rules;譯文含 `<br>` 可強制換行(讓 hl 不跨行、重點句離底 >= 240px);用「…」前綴比對加「……」截短
- `assets_gows_news.py` / `assets_gows_specs.py`(gow_sales 專用,前綴 `gows_`,複製 sv3 版;規格 `kotaku_230k`/`kotaku_vaca`=Kotaku 標題區、`ch_neg`=Critical Hits(葡文)標題+導言、`steam_store`=Steam 商店頁評論摘要(`dark:False`、`site` 以 `=` 開頭不加「中文翻譯」);`unclip(sel)` 把祖先 overflow 改可見,避免原頁固定高度裁字)
- `assets_gta5_news.py` / `assets_gta5_specs.py`(dei_gta5 專用,前綴 `gta5_`,複製 gows 版;規格 `gamespot_bad`=GameSpot 評測評分與優缺點(缺點排前、兩欄)、`gamespot_body`/`gamespot_praise`=評測內文段落(`gs_para`)、`gamesbeat_target`/`petition`=GamesBeat 2014 Target 下架報導兩段(`gb_para`)、`kotaku_leak`/`kotaku_npc`=Kotaku GTA 6 洩漏者報導(`kotaku_art`);內文段落用「前綴…」比對整段後以「……」截短)
### 影片片段(assets_wowi_clips.py -> assets_wow_clips.py;legacy,新片用 clips_lib)
- `SEG = {來源id: [(起秒, 止秒, [標籤…], "備註", {可選覆寫 crop/top/bottom})…]}`(秒 = raw/<id>.mp4 檔內秒數);`CROP` 手動黑邊 `"w:h:x:y"`;`TAGS` 需要的標籤;`MAX_PER_SRC` 120;`SEC_PER_LINE` 4
- `build()` 重建 projects/<tag>/clips_<tag>.json(欄位 src/start/end/tags/note/crop/dark/top/bottom;自動修黑場頭尾、標 dark、偵測黑邊);`C.OUT`/`C.SCRIPT`/`C.TAGS`/`C.SEG` 由 wowi 版覆寫
- `--check`(`check()`):每標籤片段數 ≥3 且總秒數 ≥ 該標籤句數×4;每支來源 ≤120 秒;片段起點非黑畫面;片段內部連續黑畫面 <0.5 秒。其他:`--preview`/`--preview3`(每片段 1/3 格總覽)、`--sheet SRC START END STEP [OUT]`
- 新片素材片段流程(survive3 範例 `assets_sv3_clips.py`):`yt-dlp` 下載 -> `clip_scan.py <src>... [--dark 10]` 篩乾淨區段 -> 依來源粗分標籤、切 <=8 秒寫進 SEG -> `--check` -> `--overview`(總覽圖在 `output/<tag>/clips/`);script.txt 用 `@fallback 標籤=備援` 補缺。
- 年齡限制(Capcom/PlayStation/Dead Space 等官方頻道常見)不可繞過:下載前用 `yt-dlp --skip-download --print "%(id)s|%(channel)s|%(age_limit)s|%(height)s" <id>` 預檢,被擋就找 IGN/GameSpot 的轉載。批次下載請在前景跑(背景子殼會與後續指令搶同一檔)。`assets_sv3_clips.py` 檔頭有 survive3 兩輪來源與被擋清單;偏暗預告 `clip_scan --dark 10`,亮度 >110 的區段(白色結尾卡)不收。
- `assets_gta5_clips.py`(dei_gta5 專用,來源前綴 `g5_`,標籤 gta6/gta5/trevor/gta5ee;Rockstar 的 Gameplay、Michael.Franklin.Trevor.、Trevor、Franklin 皆被年齡限制擋,改用 IGN/GameSpot 轉載,清單見檔頭;SEG 已用 `scene_cuts` 排成頭尾 2.5 秒內無硬切)

### clips_lib.py(F3-1,新片一律用這個;`assets_*_clips.py` 全部 legacy,不刪不改)
- 引擎 = `assets_wow_clips.py` 的 probe_dur/detect_crop/luma/refine/build/check/contact_sheet/sheet/preview,另含 `overview`(每來源一張總覽);各片 `assets_<tag>_clips.py` 的差異全部參數化進 clips.json,不再寫 Python。
- 指令:`python -X utf8 pipeline/clips_lib.py --tag <tag>`(重建 `paths.clips_file(tag)`,build.py `--clips auto` 讀它)/ `--check` / `--overview` / `--preview [--nf 3]` / `--sheet SRC START END STEP [OUT]`;共用選項 `--spec <clips.json>`(預設 `projects/<tag>/clips.json`)、`--out <片段檔>`、`--outdir <圖片夾,預設 output/<tag>>`。`--check` 退出碼 0=全部達標。
- `projects/<tag>/clips.json`:
  ```
  {"script": "<tag>/script.txt",            // 可省,預設 <tag>/script.txt;check 用它算各標籤句數(行首 `標籤|`)
   "tags": ["gears","expo"],                 // check/preview 的標籤清單;省略則取 sources 內出現過的全部
   "params": {"max_per_src":120, "sec_per_line":4, "black":6, "dark":40, "fps":4, "scene_cuts":true},   // 皆可省(此為預設)
   "min": {"proto":[1,5.0]},                 // 可省:{標籤:[最少段數,最少總秒]},有列者不套「>=3 段且 >= 句數x4 秒」(re9_online 式)
   "crop": {"<src>":"1920:800:0:140"},       // 可省:整支來源手動黑邊 w:h:x:y(沒給才 cropdetect)
   "safe": {"<src>":{"top":0.1,"bottom":0.8}},   // 可省:整支來源可見垂直範圍 0~1
   "section": {"<src>":780},                 // 可省:section_offset
   "sources": {"<src>": [ {"start":3.2,"end":8.9,"tags":["gears"],"note":"備註","bottom":0.8,"crop":"w:h:x:y"} , [3.2,8.9,["gears"],"備註",{"bottom":0.8}] ]}}
  ```
  選用鍵:`"disable":[src…]` 整支來源停用;`"exclude":{src:[[起,止],…]}` 手動挖掉區間;`"auto_exclude"` 由 `clips_screen.py` 產生(每 0.5 秒量亮度/對比/下方字幕帶 OCR:`scan` 掃描快取 tmp/clips_screen、`stats SRC T1 T2` 校準、`apply --dark-src tag:ow3=34 --flat-src tag:ow3=15 --white 215 --flat 10 --letters 5`)。改完重跑 `clips_lib.py --tag` 重建。
  `<src>` = `raw/<src>.mp4` 去副檔名(含 gd_ 這類前綴);片段物件除 start/end/tags/note 外的欄位視為覆寫(crop/top/bottom),也可寫成陣列簡式。輸出片段欄位 src/start/end/tags/note/cuts/dark/crop/top/bottom/section_offset;`cuts` = 片段內硬切(`clip_scan.scene_cuts`,快取 `raw/<src>.cuts.json`,`scene_cuts:false` 則不寫)。
- 回歸(2026-10-14):`pipeline/examples/clips_gd.json` 是 `assets_gd_clips.py` SEG 的轉檔;用 `--spec pipeline/examples/clips_gd.json --tag gd_regress --out tmp/x.json` 跑出 58 段,與原程式 `build()` 輸出逐欄位完全相同(含 cuts),`--check` 輸出與原程式一致。注意:`projects/dei_gamersdead/clips_dei_gamersdead.json` 是手動剔除/追加後的版本(33 段),與 SEG 不同,不要拿該範例覆寫它。

