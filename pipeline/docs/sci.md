# 動畫科普片

(原 README 章節 §10;文中 §n 沿用原編號,對照見 README.md §2。行號不寫在文件裡:`python -X utf8 pipeline/tools/funcmap.py --grep <函式名>`)

## 10. 動畫科普片(pipeline\sci\)
- `render_clip.py` 單一場景算圖:`<scene> --dur --hue --params "{json}" --out <name> [--frames-only]`;每 0.1 秒 seek 一張 PNG 到 `tmp\<name>\`,並做外框檢查(出界、邊距、字幕帶、淨空區、字牌壓鴿子、純函式)。
- `stage.html` 通用舞台(場景只需提供 `Scene.render(t,PARAMS)`);`pigeon.js` 認真鴿骨架;`kit.js` 共用元件;`scenes\<名>.js` 一個場景一個檔。
- `make_film.py` 合成整支片(一個指令只印 ≤30 行摘要):`python -X utf8 pipeline\sci\make_film.py --tag <tag> --ver v1 [--only N] [--strict]`
  - `--only N` 只重算第 N 個場景(1 起),其餘沿用 `tmp\film_<tag>_NN\`;`--strict` 場景檢查未過就中止。
  - 場景檔不存在時用佔位場景(底色加場景名),摘要標「佔位」。
  - 輸出:`build\<tag>\film_timeline.json`(場景 t0/t1、每句成片 start/end)、`output\<tag>\<tag>_<ver>.mp4`、`qa_<ver>.png`(每 1 秒一格、8 欄、寬 384)。
- `<tag>\film.json`:`{"hue":46,"bgm":null|"檔名(bgm\ 內)","scenes":[…]}`;場景 `{"scene":名,"lines":[a,b]}`(含 a、b 的句編號)或 `{"scene":名,"dur":秒}`(插入的無旁白段,其後句子順延)。
  - `lines` 場景從第一句開頭起,到下一場景開始;`tail` 秒 = 最後一句後多停(之後所有句子順延);場景邊界對齊 0.1 秒(向下取整)。
  - 傳給場景的 params:`hue`、`dur`、`lines=[{idx,text,start,end}]`(秒,相對場景起點)。
- 輸入:`build\<tag>\timeline_tts.json`(只有配音的時間)與 `build\<tag>\tts\NNN.trim.wav`。聲音先用 numpy 拼成 `film_voice.wav`;BGM 音量 0.25、循環、片尾淡出 1.5 秒(無側鏈壓低)。
- 科普片配音(沒有片段標籤檔,**不可帶 `--clips auto`**):`python -X utf8 pipeline/run.py build --script <tag>/script.json --voice seed402 --rate +18% --gap 0.12 --section-gap 0.30 --tts-engine chattts --spk M_seed_402.pt --tag <tag> --tts-only --out <tag>_v1.mp4`(128 句約 17 分鐘);之後 `run.py listen_page --tag <tag> --ver v1`。
- 音效:`make_sfx.py` 合成 `channel\sfx\intro.wav`、`outro.wav`(木琴上行加叮;2026-10-11 使用者選定 A);make_film 在 intro 場景開頭與 outro 最後一句開頭混入配音軌(`SFX_VOL` 0.6),檔案不存在就略過。
- 字幕:libass(`film_subs.ass`),沿用 build 的 SUB_* 與斷句;科普樣式 = 白字、墨色 #1B1414 描邊 6px、陰影 5px、無底框;標點一律換半形空格。
- 舞台載入順序:`pigeon.js` → `kit.js` → `charts.js` → 全部 `props_*.js` → `tpl_*.js`(§10.5)→ 場景(`render_clip.py` 的 `build_html`;新片的圖解庫命名 `props_<片名>.js` 即自動載入)。

### 10.0 直式(F2-4,數值待 Shorts 實測修正)
- `kit.js` 的 `LAYOUT.landscape/portrait`(W,H,SAFE,margin[左上右下],SUB_BAND,sub,title,pigeon);`Kit.L` 為目前使用那組,`Kit.portrait` 由 `window.__PARAMS.portrait` 決定。
- 場景要支援直式,座標必須讀 `K.L`;現有場景都寫死橫式座標,不能直接加 portrait(F4-0 模板化後才支援)。示範:`scenes\layout_demo.js`。
- `make_film.py --portrait` 或 film.json 頂層 `"portrait": true` → 1080x1920;直式字幕 Fontsize 106、描邊 7、陰影 6、中心 (535,1400)、每段 ≤11 字(執行時暫改 `B.SUB_MAX_W`,不動 build.py)。`render_clip.py --portrait` 算單格,邊距四邊各自下限(左 80 上 120 右 140 下 320)。
- 已知:同一場景同一 t 連算兩次偶有微小像素差(intro 47px、最大 2 階),疑似抗鋸齒;平行算圖若有接縫閃動從這裡查。

### 10.1 `charts.js`(`window.Charts`;圖表與標記,每支片重用)
座標一律 px;回傳紙片字串(已含 data-k/data-id)。共用:`u`(紙片倍率,預設 1.4)、`pal`、`id`、`k`(出現後第幾格;<0 不畫、省略 = 已出現;進場 `K.pop(k)`)。字級低於下限會被拉回(數字 150、標籤 56、來源 40)。
- `hbars({x,y,w,rowH,gap,fs,numFs,labelW,max,bars:[{label,value,text,icon,color,grey,hi,k}]})`:橫向排行長條;x,y 為左上;每列 = 標籤牌(可含 icon)+ 長條 + 數值牌;`hi` 黃底標籤與墨底黃字數值,`grey` 灰條灰字。
- `ratioBar({x,y,w,h,fs,segs:[{value,label,text,color,side,k}]})`:一條分段比例條;x,y 為中心;字牌上下交錯,左側色條同該段顏色。
- `bigNum({x,y,num,unit,note,fs,unitFs,noteFs,fill,ink,rot,k,kNote})`:大數字卡(黃底墨字)加下方說明牌。
- `checklist({x,y,w,rowH,gap,fs,items:[{label,state:'empty'|'check'|'q',k,kState}]})`:勾選清單;`kState` = 記號出現後第幾格。
- `iconRow({x,y,pitch|w,size,fs,items:[{icon,label,dim,k}]})`:一排 icon 逐一彈入加短標籤(間距 220 時標籤最多 2 字)。
- `podium({x,y,w,h,fs,places:[第一,第二,第三] 各 {label,color,lift,k}})`:頒獎台(x,y 為台底中心);`podiumPos(o)` 回傳三階 `{x,top,w,h}` 供圖解站上去。
- `twoCol({x,y,w,h,gap,fs,left:{title,color,titleFill,titleInk,k},right})`:兩欄板;`twoColPos(o)` 回傳兩欄可用範圍 `{x,y0,y1,w}`。
- `dotGrid({x,y,size,n,color,k,kFill,per})`:10×10 方格佔比;`kFill` 起每格多上 `per` 個。
- `route({r,th,fs,stops:[{x,y,label,labelSide,k,kOn}]})`:路線站點;`kOn` 省略 = 已亮、<0 = 灰;線段兩端都亮才上主色。
- `srcTag(字, {x,y,anchor:'left'|'right'|'center',fs,pal,rot,k})`:來源小牌(40px)。
- `triviaMark({x,y,size,rot,k,kOut})`:無用知識「?」牌(預設右上角、邊長 120);`kOut` 退場 2 格。
- `bubble(字|[多行], {x,y,fs,dashed,tail:'bl'|'br'|'tl'|'tr'|null,fill,rot,k})`:對話泡;實線 = 說出口,`dashed` 虛線 = 傳言。
- `dateTag({x,y,top,main,size,color,rot,k})`:日曆牌(上緣色帶小字、下方大字)。
- `priceFlip({x,y,from,to,unit,fs,k,kFlip,rot})`:價牌(吊牌,x,y 為中心,fs 預設 110);`kFlip` 省略或 <0 只顯示 `from`;≥0 舊價縮小變灰加紅刪除線上移,新價 `to` 以黃牌在下半彈出;`from`/`to` 可為數字或字串;外框寬度翻牌前後相同(高度 1.7→2.9 倍 fs)。
- `lineChart({x,y,w,h,pts:[{label,value,text,k}],min,max,fs,hi,title,k})`:折線逐點出現;x,y 為繪圖區左上(主題襯底色 `pal.pad` + 墨色基線,`label` 在基線下方 16px 起,留 ≥107px);兩端都出現才畫線段;`hi` = 索引或陣列(黃牌);`min`/`max` 省略時資料留 10% 邊;`title` 黃牌在繪圖區上方外側靠左(底緣在繪圖區上緣上 0.3×fs),有 title 時資料上緣多留一個數值牌高度;數值牌在點正上方(牌底距圓點上緣 ≥ 0.25×fs),value 比前一點小時改放右上避開進來的線;牌互相重疊時往上讓開。
- `decileRow({x,y,w,h,vals,texts,labels,hiIdx,max,fs,title,k,kStep,marker:{value,label,k,side:'left'|'right'}})`:十等份薪資階梯(n 根由矮到高的柱,n = `vals` 長度,不限十根);x,y 為繪圖區左上,數值牌在柱頂、`labels`(預設 D1…Dn)在基線下方(留 ≥107px);`hiIdx` 黃柱加墨底黃字數值;`marker` = 橫線(蓋在柱上、被數值牌蓋住)加墨底黃字牌(預設左端線上方),標某值落在哪兩根之間;`kStep` = 每根柱晚幾格出現;數值牌寬超過柱距時奇數根自動抬高。
- 輔助:`icon(ic,cx,cy,box,dim)`(`ic={svg,w,h}`,即 `PropsTurtle.LIST[名]` 的內容與寬高)、`plate(字,fs,o)`、`sheet(內容px,o)`、`tw(字,fs)` 估字寬。

### 10.2 `props_turtle.js`(`window.PropsTurtle`;turtle 片圖解)
`fn(pal, o)` 回傳以單位繪製、中心在原點的紙片內容,呼叫端包:`K.paper(PT.boar(pal,{bald:true}), {x,y,scale:u,k:'prop',id,wide:PT.LIST.boar.wide})`。`LIST[名] = {fn,w,h,zh,wide}`(w/h 單位)。
- 動物:`turtle {expr:'normal'|'speechless', headUp:true|角度}`(側面朝右、褐殼)、`hatchling {ang}`(俯視)、`boar {bald}`(脖子缺毛)、`jellyfish {col}`。
- 建築:`hotel {lit:20 格陣列或單一亮度;≥0.67 亮、≥0.34 半亮}`、`incinerator {tall:0–1, rot:餐廳旋轉格數, restaurant:false}`(底邊固定 y=+200)、`house {lit}`、`counter`、`notice`。
- 垃圾處理:`bin`、`truck {spin}`、`ashPile`、`tallySheet {hi:索引或陣列, tally:各格正字筆畫數(≤10), n:出現幾格}`(19 格、4 欄)。
- 海洋垃圾:`straw {col}`、`bottle {cap:false}`、`cap {col}`、`syringe`、`net`、`hook`、`fishline`、`bag {col:素面單色}`、`fragments {n}`、`cup`、`cutlery`。
- 備品:`toothbrush {col}`、`toothpaste`、`comb {col}`、`razor`、`foam`、`showerCap`、`slipper`、`miniBottle {col}`、`pumpBottle {col}`。
- 其他:`fan {ang}`、`phone {screen}`、`coin`、`bulb {on:false, rays}`、`moon`、`taiwan {fill}`(28 點;`twXY(lon,lat)` 換算圖上座標)、`car {col}`、`computer`、`microwave`。
- 圖解總表:`python -X utf8 pipeline\sci\render_clip.py t_props_sheet --dur 6 --hue 170 --out turtle_props --frames-only`(每頁 1 秒:前 4 頁圖解、後 2 頁圖表示範;字幕帶與邊距兩項檢查對總表不適用)。

### 10.3 `props_pearl.js`(`window.PropsPearl`;pearl 片圖解,用法同 §10.2;LIST 的 w/h 單位)
- 飲料與點心:`cup {ice}`(116×242)、`pearl {hard}`(126)、`vinegar`(128×230)、`wifecake`(182)。
- 澱粉:`chain {tags:0–8, bend:0..1}`(420×180,wide;tags 掛主色方塊零件)、`lock`(96×140)、`bag {text}`(166×198,`labelBox`)。
- 烹煮保存:`pot {steam:false}`(284×292)、`rice {hard}`(204×176)、`clock {h}`(176;h=小時,小數=分,6.5=6:30)、`thermo`(110×246;7 與 60 間警示色)。
- 人與場所:`germ {full}`(200×190)、`factory {water:false}`(284×306)、`phone`(200×130)、`tongue {ang}`(110×140)、`lens`(190)。
- 食物各一:`noodle`(196×209)、`frozen`(164×138)、`sausage`(188×50)、`fishball`(70×232)、`dumpling`(190×90)。
- 總表:`python -X utf8 pipeline\sci\render_clip.py p_props_sheet --dur 5 --hue 265 --out pearl_props --frames-only`(5 頁、每頁 ≤8 個,含各參數變化)。

### 10.4 `props_salary.js`(`window.PropsSalary`;salary 片圖解,用法同 §10.2;LIST 的 w/h 單位)
- 錢與人生:`bill {n}`(千元鈔 320×140 = 長寬比 160:70,抽象徽記不畫人像)、`payslip`(170×196)、`gradcap`(226×140)、`gate`(280×236,橫牌空白無校名)、`briefcase`(210×176)、`bank`(290×236)、`survey`(170×222)。
- 天秤與世界:`scale {tilt:-1..1,正 = 右盤下沉}`(350×240)、`globe {sign:牌子字, v:1|2}`(210×306;v1 藍海綠陸、v2 橘海紅褐陸,供「世界一/二」)、`meter {v:0–1}`(262×248;指針與下方笑臉由哭到笑)。
- 鹽與羅馬:`helmet`(210×220)、`saltbag`(170×196)、`shaker`(110×220)、`dict {text:書背字 ≤5 字}`(130×250)、`stele {lines}`(176×240)。
- 量長度:`tape {out:0..1}`(340×146)、`field {u, bills:0–1000}`(112×72,俯視,**1 單位 = 1 公尺**:105×68)。`PS.FIELD` = `{len:105, wid:68, billMM:160, pitch:0.16, perRow:656.25}`;`field` 描邊以 px 為準,呼叫端須把縮放倍率以 `u` 傳進來,`K.paper` 的 scale 用 `ps`(預設 = `u`;總表 u=10.5、ps=1.8,陰影才是約 9×11px 的小偏移,否則被 u 放大成一大塊);`bills` 沿長邊排千元鈔(第一排 656 張放滿,其餘排第二排;鈔票長度照真實比例,寬度放大成 9px 才看得見)。重用:turtle 的 `phone`、`coin`;pearl 的 `clock`。
- 總表:`python -X utf8 pipeline\sci
ender_clip.py salary_props_sheet --dur 5 --hue 135 --out salary_props --frames-only`(5 頁:前 3 頁圖解每頁 8 個含參數變化,第 4 頁 decileRow 示範(數值牌與 marker 線垂直距離 < 22px 時線在牌處斷開),第 5 頁千元鈔排足球場比例驗證);格在 `tmp\salary_props\`,每頁第 3 格(f_002、f_012…)複製到 `output\salary\props\salary_props_p1–p5.png`。圖解三頁的邊距與字幕帶檢查不適用。

### 10.5 場景模板(F4-0;規格 `projects\framework\sci_tpl_spec.md`)
- 接法:`tpl_common.js`(`window.Tpl.common`:觸發格、依序分配、停留檢查、標題牌、鴿子)+ `tpl_<名>.js`(`Tpl.<名> = {LAYOUT:{landscape,portrait}, render, check}`);`render_clip.build_html` 在 props 之後載入(common 先)。通用場景 `scenes\tpl.js` 依 `params.tpl` 轉呼叫。
- film.json:`{"tpl":"list","lines":[a,b],"data":{…}}`(`scene` 與 `tpl` 擇一,違反就中止);摘要名 `tpl_<名>`。
- check 在 render_clip 內、算圖前跑(`Scene.check`):錯誤印「模板錯誤:…」並 exit 2,make_film 標「模板錯誤」、該場景放佔位畫面(不論 `--strict`);「警告」只印(停留 < 1.5 秒)。沒有 DEF 備援,lines 缺就是錯誤。
- 共通 data:元素 `at`(場景內句索引)+ `word`(觸發格 = 字索引 ÷ 句長 × 句長秒數;找不到 → 錯誤);省略 `at` = 第 i 個掛第 min(i,句數-1) 句開頭(撞格順延 3 格);`out:{at,word}` 0.3 秒縮掉;`pigeon:{expr:名|[每句],clip,hide}`(橫式 `K.L.pigeon`,直式 (510,1290) u 2.0,內容區下緣讓到鴿子頂上 24px;橫式畫鴿子時內容區右界 = 鴿子實際外框左緣 1368 − 40 = 1328,`tpl_common.PG_LEFT`〔實測 idle 全表情含嘴 1368.9〕,不畫鴿子仍 1440)。
- 共用:`common.fitBlock(A, {fsMax, fsMin, hOf(fs), wOf(fs)})` 回傳 `{fs,h,w,top,cx,cy}`(最大字級、群組置中;上下各留 12px),後續模板一律用;`titleBox(s, pos?)` 標題字級上限 橫 84/直 88,太寬自動縮。
- `number`:`num, unit?, note?(≤16 字,太寬自動拆兩行), src?, at?, word?, flip?:{from,to,at,word}`(有 flip 畫 `Charts.priceFlip`,預設第 1 句翻)。字級自動放大:數字上限 橫 300/直 260、價牌 220/180、說明 64,數字加說明整組置中(有來源牌時扣掉來源牌那一帶)。
- `list`:`title?, style:'check'|'num'|'dot', items:[{text,at?,word?,state?,icon?}], hi:[i]`;橫 6 項 ≤14 字、直 5 項 ≤9 字;字級由 `common.fitBlock` 取放得進內容區的最大值(上限 橫 84/直 80、下限 56/60),標題加清單整組在內容區垂直、水平置中;三種樣式都自繪前綴(文字起點留 0.3 倍字級;check 的 hi = 文字區貼黃紙,不支援 icon;num/dot 的 hi 整列黃底,icon 寫 `turtle.coin`)。
- `bars`(`Charts.hbars`):`title?, unit?, src?, bars:[{label,value,text?,icon?,at?,word?,grey?}], hi:[i], max?`;橫 6 條、直 5 條;數值牌字 = `text`,省略 = value+unit;字級 fitBlock(橫 96–56、直 88–60),群組高不足內容區 45% 時加高列高(上限 1.6 × 字級);群組寬撐滿內容區(最長條 ≥ 橫 300/直 200px,否則錯誤);`src` 有標題且放得下時在標題列右端,否則在最後一條下方 24px、靠左對齊長條群組(算進群組高)。
- `compare`(`Charts.twoCol`,一次畫一欄):`left/right:{title,items:[字],icon?,at?,word?}, hi:'left'|'right'|null`;每邊 ≤4 項、每項 ≤10 字;橫式左右、直式上下排(直式一律不畫鴿子,寫了 pigeon 只警告);hi 邊襯底 + 黃標題,另一邊灰底 + 墨標題;條目在該欄出現後第 2 格起每 2 格一條;字級 72–56(直 72–60)。
- `timeline`(自繪):`title?, nodes:[{year,label,at?,word?}], hi:[i]`;2–6 個(直 ≤5);橫式水平軸(年份上、標籤下,相鄰標籤放不下自動兩層交錯、第二層加柄;年份單列,太寬 → 錯誤,年份寫 4 位數),直式垂直軸(年份左、標籤右;節點少時拉長列距到內容區 45%);牌高 1.3 × 字級;hi 黃圓 + 墨底黃字年份 + 黃標籤。
- `pigeon_talk`(F4-0c):`expr:名|[每句], clip, bubbles:[{text,at?,word?,dashed?}], props:[{lib,name,params,at?,word?,x?,y?,u?}], out?`;鴿子放大、面向右(flip)當主角:橫 (700,812) u 3.1、直 (655,1286) u 2.2〔規格 橫 u3.2 頭頂進上邊距、直 u3/y1150 泡泡區放不下兩個兩行泡,實測改小〕;泡泡在鴿子前方(橫式右側、直式上方),`text` 字串用 `\n` 換行或陣列、≤2 行,同時 ≤2 個(槽 i%2;第 i+2 個出現前 3 格第 i 個縮掉,被擠掉前須完整停 ≥1 秒),字級 fit(橫 80–56、直 80–60,放不下 → 錯誤);`props` 取 `window[lib].LIST[name]`(lib 寫 `PropsSalary` 或簡寫 `salary`;找不到 → 錯誤),≤3 個,未給 x,y 時直排在鴿子另一側(左側)、縮放取放得下的最大值(上限 1.6);clip 只用 `BOX` 有的(turn 會改 flip 不列入;shock/hop/walk 外框超出上邊距或進字幕帶 → 錯誤);check 另以算出的外框查邊距、彈入過衝 1.15 時的字幕帶、與鴿子間距(橫 40/直 24)。
- `thumb`(F4-1,封面,靜態單格橫式;依 `channel\規則\頻道_ChannelC.md` §4):`lines:[主,副,補](合計 ≤13 字), hi?:0–2(黃底墨字色帶,預設 2), expr:表情名, prop?:{lib,name,params?}, side?:'left'|'right'(鴿子側,預設 left), hue?`;字級目標 236/130/108、依字區寬自動縮(下限 200/110/90,不足 → 錯誤);鴿子 u3.0 朝向字,右側時整體上抬 70px 避開右下淨空;check 擋字數、表情名、prop、字級下限。
  一個指令出圖:`python -X utf8 pipeline\sci\make_thumb.py --tag <tag> [--data <json>]`(預設讀 `<tag>\thumb.json`)→ `output\<tag>\<tag>_thumb.png`(deliver.py 認這個檔名),算圖後量外框查安全區、右下淨空、字與鴿子/prop 重疊、鴿子佔高 55–72%,再縮成 320 寬印每行字高(主 ≥33、副 ≥18、補 ≥15 px);小圖 320/246/168 存 `tmp\thumb_<tag>\`。exit 0 通過、1 幾何或縮小未過、2 資料錯誤。範例:`examples\thumb_salary.json`(`--tag tpl_thumb_demo`)。
- 鴿子間距(F4-0c,`render_clip.check(..., tpl=True)`,只對 `tpl` 場景):每格每片內容紙片(鴿子、襯底以外,已進場)與鴿子外框水平距 ≥ 40(直式 24)或垂直距 ≥ 24,否則「未過 鴿子間距」;摘要印「內容與鴿子最小間距 橫/直」。
- 整片實跑:`tpl_demo\film.json`(六個模板各一段,借 salary 1–17 句配音;`build\tpl_demo\` 放複製來的 timeline_tts.json 與 tts wav)→ `python -X utf8 pipeline\sci\make_film.py --tag tpl_demo --ver v1`。
- 範例與測試:`pipeline\sci\examples\tpl_<名>.json`(`sets:[{name,dur,orient?,lines,data}]`)。單組:`python -X utf8 pipeline\sci\render_clip.py tpl --dur 7.5 --params @tmp\x.json --out x [--portrait]`(`--params @檔` 從檔讀 json,檔內 `{tpl,lines,data}`)。


## ChannelC片頭片尾(2026-10-16,給 build.py 評論片管線當鏡頭用;不用鴿子)
- 場景:`pipeline\sci\scenes\lab_intro.js`(3 秒:0.0–0.8 五字每 0.2 秒彈出、1.0 印章 1.6 倍砸下、1.2 落地震動 4 格)、`lab_outro.js`(4.5 秒:五字每 0.1 秒、同樣 1.0 砸 1.2 落地、1.6–1.9 副標「認真研究那些有趣的事」淡入)。Logo 寬約 1300px(x 301–1604)、垂直中心 Y≈470,字幕帶 Y≈924 淨空;墨底 #1B1414、方格紙紋、「C」品牌黃印章、其餘紙白、字型 GenSen。時間先取整格(10 格/秒),純函式。
- 出檔:`python -X utf8 pipeline\sci\make_lab.py [intro|outro]` -> `anim\lab\lab_intro.mp4`、`lab_outro.mp4`(1920x1080、30fps、無聲)與 `_sfx.mp4`(混入 `channel\sfx\intro.wav` / `outro.wav`,檔不存在就略過;音效是舊鴿子片頭的時間表,**未對齊新動畫**);檢查格在 `tmp\lab_frames\`。`anim\` 被 .gitignore,mp4 不進 git,要重跑指令產生。
- script.txt 寫法(build.py 的手動 `shots`,`src` = raw\ 下不含 .mp4 的檔名,用相對路徑指到 anim):
  `標籤|字幕 ;; {"shots":[{"src":"../anim/lab/lab_intro","start":0}]}`(片尾 `lab_outro`)。要帶音效就改 `lab_intro_sfx`(影片原聲會被當 bed,響度被壓在 BGM 與配音之下,聲音會很小)。該句(或合併後的句群)鏡頭長度不要超過 3 / 4.5 秒,超過會超出片長。
- 已知限制:鏡頭平均亮度約 33–40 < `LIFT_Y` 40,build 會自動提亮底色;計入「同來源 120 秒」與影片鏡頭最短 2.5 秒規則;未實跑 build 驗證。
