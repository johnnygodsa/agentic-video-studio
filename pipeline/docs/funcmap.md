# 函式地圖(funcmap.py 自動產生,勿手改)

重產:`python -X utf8 pipeline/tools/funcmap.py`;只找某個:`--grep <關鍵字>`。

## pipeline/anim_lib.py
clamp(x, a=0.0, b=1.0)  L42  
lerp(a, b, t)  L45  
ease_out_quad(t)  L48  
ease_in_quad(t)  L51  
ease_out_cubic(t)  L54  
ease_in_cubic(t)  L57  
ease_in_out_cubic(t)  L60  
ease_out_back(t, s=1.70158)  L63  
font(size)  L67  
parse_color(c)  L72  
to_np(img)  L77  
resize_rgba(img, size, resample=Image.LANCZOS)  L80  預乘 alpha 縮放,避免透明邊緣的白邊/黑邊。
scale_alpha(img, a)  L85  
paste_center(canvas, sprite, cx, cy)  L92  straight-alpha 疊合;sprite 可超出畫布。
text_sprite(text, size, fill=WHITE, stroke=0, stroke_fill=BLACK, shadow=False)  L99  
wrap_text(text, f, max_w)  L118  
norm_text(s)  L135  動畫內顯示文字的標點正規化:半形 , ( ) : ; ? ! 在前後任一側是 CJK 字(含全形標點)時換成全形;
wrap_kinsoku(text, f, max_w)  L151  逐字換行 + 避頭尾:收括號 / 頓號 / 標點不放行首(寧可略超寬),開括號不放行尾。
save_png_seq(frames, outdir)  L169  
save_mov(frames, path, fps=FPS, alpha=True)  L177  alpha=True:qtrle(argb)mov;alpha=False:h264 mp4(不透明)。
read_frames(path, w, h, want=None)  L196  用 ffmpeg 解 mov/mp4 為 RGBA ndarray 的 generator;want=index 集合時
fetch_noto_webp(cp, cache_dir)  L230  
_webp_durations_ms(path)  L239  
decode_webp_30fps(path)  L249  動態 webp -> 30fps 等間隔的 RGBA(512) 序列(依各格 duration 展開;Pillow 已處
make_emoji(name, seconds, cache_dir, base=EMOJI_BASE, fade_out=True)  L262  彈入 0.25s(0→1.1→1 ease-out)+ 主體循環 + 0.2s 縮小淡出;最後一格全透明。
_band_mask(cx, width, ss=2)  L307  
_wipe_c(tau, tA, tB, D)  L315  斜帶中心 x 隨時間:快速掃入 -> 中段全遮(微漂移)-> 掃出。
_wipe_frames(D, tA, tB, text=None)  L327  
_pos_layer(sprite, cx, cy)  L361  
_fit_title_size(text)  L366  
make_wipe()  L372  trans_wipe:0.5s,深紅+黑雙層斜帶掃過;約第 0.2~0.3s 全遮(3 格)供換場。1920x1080 
make_title_wipe(text)  L376  帶段落標題版:1.3s,全遮約 0.25~1.05s;中央白色大字可見約 0.9s(淡入淡出各 0.1s)。
make_glitch(seconds=0.35, seed=7)  L380  trans_glitch 疊加版:黑/白/深紅的橫向切片條 + 細掃描線,中段最強。
glitch_vf(t0, seconds=0.35, in_label='in', out_label='out', w=W, h=H, seed=7, prefix='g')  L404  回傳 filter_complex 片段:對 [in_label] 在 [t0, t0+seconds] 做真正的 RG
_circle_sprite(r, fill, ring=WHITE, ring_w=5, ss=4)  L429  
_dark_bg()  L439  
_wrap_even(text, f, max_w, min_chars=2, toks=None)  L454  平衡換行:先用貪心算出最少行數 n,再在 n(不行就 n+1、n+2)行裡找「最長行最短」的切法;
timeline_layout(points)  L509  timeline 版面(純幾何,可單獨測試)。points = [(年份, 說明, 色)…](色欄位已不用)。
_mix(c0, c1, u)  L551  
make_timeline(points, question_between=None, bg='alpha', seg_seconds=1.2, q_seconds=2.0, sr...)  L556  points=[(年份字串, 說明字串, 顏色(已不用,欄位保留)), ...];question_between=(i
_knob(d, edge, cell, pad, r, fill)  L654  在 piece 局部座標(0,0 為 cell 左上,已含 pad 偏移)畫一個邊上的 knob(向外凸)或 notch
_puzzle_piece_mask(rr, cc, cell, ss=2)  L672  
_puzzle_sprites(cell)  L698  
make_puzzle(seconds=2.5, center=(960, 400), cell=190)  L721  3x3 拼圖依序拼上,最後中央一片缺著並閃紅框(結尾停在紅框亮)。1920x1080 RGBA。
make_stamp(text, center=(960, 420), hold=1.0, angle=-8, color=STAMP_RED)  L758  紅色印章:放大落下 -> 輕微震動 -> 定住,動畫 0.6s;之後凍結最後一格 hold 秒。1920x1080 RG
_blit(img, sp, cx, cy)  L811  就地疊合(中心座標;自動裁切超出畫布的部分)。
_blit_xy(img, sp, x, y)  L816  
_base(bg)  L826  
_title_block(img, title, cy, p, size=84)  L830  標題 + 其下的中性色短橫條(PAL_TEXT2,60% 不透明);p=0..1 淡入並由下方滑入。
src_place(text)  L845  src 出處小字的 (貼圖, 左上 xy, 墨跡 bbox):墨跡右緣 x=SRC_RIGHT、下緣 y=SRC_BOT
_src_note(img, text, p=1.0)  L853  右下角出處小字(任何動畫類型共用;p=0..1 淡入,隨標題一起出現後常駐)。text 為空就不畫。
_split_num(s)  L861  '7 個月' -> ('', 7, ' 個月');沒有數字回傳 None。
_fit_size(text, size, max_w, min_size)  L870  字級由 size 往下縮到墨跡寬度 <= max_w(不小於 min_size)。
span_layout(frm, to, big, caption='')  L877  span 文字版面:兩端標籤(字級 80 起,太長先把中心往內夾到離邊 96px,兩標籤互碰再縮字)、大字(210 起縮
span_bounds(frm, to, big, caption='', src=None)  L891  span 全部內容的墨跡 (l, t, r, b)(最終狀態;大字以目標數字計)。
make_span(frm, to, ticks, big, caption='', bg='alpha', seconds=SPAN_S, src=None)  L908  橫軸 from -> to,中間 ticks 個刻度由左至右逐格亮起(約 1.6s),大字 big 的數字同步由 0 數
_fmt_num(v, shown)  L965  
bars_step_seconds(prev, shown)  L976  bars 逐步模式一段動畫的長度(秒):由顯示 prev 條變成 shown 條(shown=0:只有標題)。shown
_bar_color(spec, default)  L1010  
_bar_opt(it)  L1018  
_ink(sp)  L1022  sprite 的不透明區域 bbox (l, t, r, b)。
bars_title_bottom()  L1030  標題(含其下紅線)下緣 y;以 CJK 參考字串量,版面不隨標題字串變動。
_thousands(num)  L1037  整數部分 >= 1000 加千分位逗號('12345.5' -> '12,345.5')。
_baseline(txt, size, stroke=2)  L1043  text_sprite(txt, size, stroke) 貼圖內的字型基線 y。
_rel_lum(rgb)  L1049  sRGB 色的相對亮度 0..1(WCAG)。
_val_sprite(num, unit, size, rgb=None)  L1056  bars 數值貼圖:數字 size px、單位 size*0.75 px(不小於 44),共用基線(底緣對齊),間隔 8
bars_geometry(sizes, grouped=False, gh=0, bottom_max=BARS_BOTTOM_MAX)  L1076  純幾何(可單獨測試)。sizes = 每組條數(未分組 = [n]);gh = 組標題字高(分組時)。
class _BarsLayout  L1099  bars 的版面(make_bars / make_bars_step 共用)。items = [[標籤, 數值, 單位
_BarsLayout.__init__(self, items, groups=None, icon_root=None, src=None)  L1104  
_BarsLayout.color(self, k)  L1143  
_BarsLayout.first_of(self, g)  L1148  
_BarsLayout.place(self, k, e=1.0)  L1151  第 k 條在長度進度 e(0..1)時的位置:dict(bar=條矩形, L=條長, label/icon/val=(貼
_BarsLayout.group_place(self, g)  L1169  
_BarsLayout.axes(self, img, shown, prev, t, full)  L1175  基線:未分組一條;分組時每組一條(只畫到該組已出現的最後一條)。full=True:整組一次播(舊 make_bars,
_BarsLayout.group_title(self, img, d, g, q)  L1189  
_BarsLayout.bar(self, img, d, k, e, lt)  L1196  
make_bars(title, items, bg='alpha', seconds=BARS_S, groups=None, icon_root=None, src=None)  L1214  標題先出,各條橫向長條依序由左長出(長度依數值比例),條尾顯示 數值+單位(數字同步遞增)。
make_bars_step(title, items, shown, prev=0, title_in=False, bg='alpha', groups=None, icon_ro...)  L1238  bars 逐步顯示(時間的純函式):前 prev 條已在畫面上,第 prev..shown-1 條依序長出。長度比例以全
list_seconds(n, has_note, step='all')  L1269  list 動畫本身的長度(秒):"all" = 全部依序彈出 + 備註;整數 step = 該項彈出(第 0 項含標題)
list_layout(items, note=None, src=None)  L1285  list 版面(純幾何)。整個清單區塊(圓點加最寬項目)水平置中於 x=960,區塊內文字靠左(對齊墨跡左緣)。
make_list(title, items, step='all', note=None, bg='alpha', src=None)  L1325  標題下方項目逐一彈出(PAL_ACCENT 圓點+序號)。回傳 list[dict(name, frames)]:
versus_step_seconds(prev, shown)  L1394  
flow_step_seconds(prev, shown)  L1402  
_mark_sprite(kind, r=52, ss=4)  L1411  綠色圓底白勾("yes")/ 紅色圓底白叉("no")。
_wrap_balanced(text, f, max_w)  L1439  換行不拆英數字詞(如 4,000 / G);只需兩行時選「最長行最短」的切點,且偏好在空白處切。
_fit_rows(text, size, max_w, min_size)  L1471  一行文字:先縮字級(不小於 min_size),還放不下就換行。回傳 (字級, [列])。
versus_layout(left, right, src=None)  L1478  versus 版面(純幾何)。回傳 dict:panel (x0,y0,x1,y1)、cols(每欄 head / ro
make_versus_step(title, left, right, shown, prev=0, title_in=False, bg='alpha', src=None)  L1518  versus 逐步顯示(時間的純函式)。left / right = {"head", "lines"[1..2], "
_flow_geom(n)  L1567  
flow_bounds(nodes)  L1575  flow 全部節點的墨跡 (l,t,r,b)(面板外框;節點內文字必在面板內)。
make_flow_step(title, nodes, shown, prev=0, title_in=False, bg='alpha', src=None)  L1581  flow 逐步顯示:節點 prev..shown-1 依序出現(第 2 個起,箭頭先畫出再彈出節點);前 prev 個已
_hit(a, b)  L1661  
_union(boxes)  L1665  
_title_box(title, cy=BARS_TITLE_CY, size=BARS_TITLE_FS)  L1669  標題(含底下短橫條)的墨跡框(最終狀態)。
_put_ink(sp, x_ink, y_ink, anchor='l')  L1677  貼圖左上 xy 與墨跡框:anchor l = 墨跡左緣在 x_ink、r = 右緣、c = 水平中心;y_ink = 
class _ColsLayout  L1686  cols 直條圖版面。items = [[標籤, 正數, 單位?, {"hi"?}?], ...]。基線 y=700,最
_ColsLayout.__init__(self, title, items, src=None)  L1690  
_ColsLayout.color(self, k)  L1721  
_ColsLayout.place(self, k, e=1.0)  L1724  
_ColsLayout.axis(self, img)  L1736  
_ColsLayout.col(self, img, d, k, e, lt)  L1739  
cols_step_seconds(prev, shown)  L1754  
make_cols_step(title, items, shown, prev=0, title_in=False, bg='alpha', src=None)  L1758  cols 逐步顯示(時間的純函式):前 prev 根已在畫面上,第 prev..shown-1 根依序長出(每根 0.5
share_step_seconds(prev, shown)  L1785  
class _ShareLayout  L1793  share 佔比堆疊條版面。rows = [{label, parts:[[名稱, 數值, 顏色?], ...]}, .
_ShareLayout.__init__(self, title, rows, unit='%', src=None)  L1797  
_ShareLayout.row_layer(self, i, e)  L1866  第 i 列在展開進度 e(0..1)的貼圖(左上 = (SHARE_X0, tops[i]));由左至右展開並裁切;展不
make_share_step(title, rows, shown, prev=0, title_in=False, bg='alpha', unit='%', src=None)  L1887  share 逐步顯示:前 prev 列已在畫面上,第 prev..shown-1 列依序由左至右展開(每列 0.6 秒)
_num_runs(big)  L1924  big 拆成 [dict(text, kind=num|unit, gap=與前一段的間距)]:數字與 → 為 num(
num_is_count(big)  L1938  big 開頭是單一數字(可含千分位與小數)且沒有「→」:數字由 0 數到目標。
num_step_seconds(prev, shown, big='')  L1944  num 逐步:level 1 = label + big、level 2 = compare。shown <= prev
_tri_sprite(up, color, ss=4)  L1957  
class _NumLayout  L1965  num 數字卡版面:label(可省略)72px 中心 y=230、big 數字 300px(單位 0.45 倍,共用基
_NumLayout.__init__(self, label, big, compare=None, tone=None, src=None)  L1968  
_NumLayout._layout(self, S)  L2003  依字級 S 排 big 各段:self.items(貼圖、左上 xy、基線列 bl)、total = 墨跡總寬、big_
_NumLayout.count_sprite(self, e)  L2027  count-up 中第一段數字的貼圖與左上 xy(墨跡右緣對齊終值右緣、基線不變)。e = 0..1(已 ease)。
make_num_step(label, big, compare=None, tone=None, shown=None, prev=0, title_in=False, bg='...)  L2038  num 逐步顯示(時間的純函式):level 1 = label + big(數字由 0 數到目標,或淡入);level
new_layout(a)  L2077  cols / share / num 的版面物件(含 .boxes / .bounds);規格不合會 raise Val
anim_bounds(a, points=None)  L2091  timeline / span / list / versus / flow 的內容墨跡框 (l,t,r,b)(最終狀態
anim_problems(a, points=None)  L2109  版面問題清單(字串;空 = 合格):下緣超過 800(有 src 時 768)、左右離畫面邊 < 96,以及各類型專屬項
_smooth(e0, e1, x)  L2148  
class _StarBG  L2156  
_StarBG.__init__(self)  L2157  
_StarBG.intensity(self, t)  L2189  0..1 強度圖(已含壓暗權重與不透明度)。
_StarBG.frame(self, t)  L2221  
_star_compute(t)  L2233  原本的逐格即時計算(不經快取);快取內容與逐像素比對的基準。
_star_dir()  L2241  
_star_cached(k)  L2246  第 k(0..STAR_N-1)格的背景:記憶體 -> 磁碟 PNG(無損)-> 重算並寫入。寫檔先寫暫存檔再改名(平行
make_star_bg(t)  L2276  時間 t(秒,成片絕對時間)的星座背景,回傳 HxWx3 uint8(深色底 + 光點星座;唯讀,勿就地修改)。同一個 
over_star(fg, t)  L2286  straight-alpha RGBA ndarray(整張 HxWx4,bg='alpha' 產的動畫格)疊到 t 時
_over_star_ref(fg, t)  L2303  原本的全圖公式(供逐像素比對)。
set_profile(name)  L2338  切換版面常數組:"landscape"(預設,1920x1080)/ "portrait"(直式畫面窗 1080x108
_stack_lines(lines, size, fill=WHITE, pitch=None)  L2345  多行左對齊貼圖(各行 text_sprite 疊起來,行距 pitch)。
_list_layout_p(items, note=None, src=None)  L2355  直式 list 版面:圓點靠左 x=80,文字自動換行(寬 <= 940 - 文字左緣),字級 64 起逐級降到 48;
_wrap_p(text, f, max_w)  L2402  直式換行:換行點只落在詞與詞之間(WORD_TOKS:jieba 詞、英數詞與括號整段);有 token 比行寬還寬時退
timeline_layout_p(points, src=None)  L2410  直式 timeline 版面(縱向):縱線在文字左 60px,每個節點一列,年份在上、說明在下(皆靠左,說明自動換行)。
_left_at(img, sp, x_ink, cy, a)  L2448  墨跡左緣對齊 x_ink、垂直置中 cy 貼上(a = 不透明度)。
_make_timeline_p(points, question_between=None, bg='alpha', seg_seconds=1.2, q_seconds=2.0, sr...)  L2453  直式 timeline(make_timeline 在 PORTRAIT 時轉呼叫;回傳格式與動畫時序同橫式:線長到節點

## pipeline/anim_make.py
_hash(obj)  L35  
_dir_bytes(p)  L39  
_item(anim, rel, frames, fps=A.FPS, alpha=True, png_dir=None, tp=None, **extra)  L43  寫出 mov(或 mp4)與選用 PNG 序列,回傳 manifest item。rel 不含副檔名。
build_units(anim, titles)  L58  每個 unit = (unit_name, params, builder)。builder() 回傳 manifest
build(root, force=False, only=None, titles=())  L95  
_pick_dark_screenshot(root)  L117  
_cover(im, w=A.W, h=A.H)  L132  
_checker(w, h, t=32)  L139  
_over(bg, fr, x=0, y=0)  L145  straight-alpha ndarray 疊到 bg(PIL RGBA)。
overview(root, man, shot, out)  L151  
demo(root, man, shot, out)  L193  
main()  L245  

## pipeline/anim_preview.py
render_run(run, tlmeta, media, out_dir, tag)  L25  
bars_report(lay)  L48  量測 bars 最終版面:條 y 範圍 / 間隔、最長條終點、最後一條下緣、強調條、文字框重疊與出界(用繪字墨跡 bbo
bars_demo(out_dir, media, names=('bars_sbi.png', 'bars_grouped.png'))  L74  
new_report(a)  L96  cols / share / num 最終版面量測:內容邊界、文字框重疊與出界、版面問題(anim_problems)。
new_demo(out_dir)  L120  
_last_frame(run, tlmeta, media)  L140  該 run 所有動畫格(走 build 實際算圖路徑,每句 STEP_FRAMES 格)的最後一格疊星座背景;串流處理不
sheet(script_arg, out_dir, media)  L150  全片動畫總覽:每個動畫鏡頭取最後一格,縮成 960x540,三欄拼 sheet_01.jpg…(每張最多 9 格);並對
main()  L192  

## pipeline/anim_web.py
has_template(t, portrait=False)  L47  有網頁模板;portrait=True 時還要在 PORTRAIT_OK 內。
sig(t)  L52  模板版本簽章:模板 + tokens + gsap 內容雜湊 + VERSION(build 的鏡頭快取簽章也用它)。
_hex(c)  L67  
_color(c)  L71  
_dec(v)  L77  數值的小數位數(照文案寫法:499.99 -> 2、30 -> 0),最多 3 位。
bars_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L83  bars 定義 -> 模板資料。items / groups 舊欄位原樣;series=[名稱…](≤3)時每條數值為 
_ref(a)  L113  目標線 ref={value, label} -> 模板資料(label 走半形標點正規化 + 斷詞)。
_nt(s)  L119  
_wt(s)  L123  顯示文字:半形標點正規化 + 共用斷詞(詞與詞之間插 U+200B,模板 CSS word-break:keep-all
_head_data(a, title_in, size)  L128  
list_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L133  list:prev is None = 一次全播("all");逐步模式 step k = 第 k 項彈出(prev=k
num_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L146  num:level 1 = label + big、level 2 = compare;prev is None = 一
versus_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L160  versus:level 0 = 標題 + 欄標題、1 = 左欄、2 = 右欄;prev is None = 一次全播(
flow_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L171  flow:prev / shown = 已顯示的節點數;prev is None = 一次全播。
span_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L180  
stamp_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L188  
timeline_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L195  timeline:a 須已帶 points(自帶或 build 併入頂層共用 timeline);scale / tra
new_levels(a)  L222  line = 線數、table = 列數、kpi = 格數(step k = 顯示到第 k 項,level = k + 
new_step_seconds(a, prev, shown)  L227  line / table / kpi 一段動畫(prev -> shown)的長度(秒);shown == prev =
_span(a, prev, shown)  L246  
line_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L251  line:x = 類別或日期標籤、lines = [{name, data}]、scale "time" 時按日期比例;
_tbl_cell(v)  L271  表格格子 -> {k: yes|no|text, t}:True / ✓ 系 = yes、False / ✗ 系 = n
table_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L282  table:cols = 表頭(≤4 欄,不含首欄)、rows = [[項目, 格…]](≤5 列);hi = {"ro
_kpi_value(v)  L292  kpi 數字 -> {num, dec, comma, pre, suf}(可 count-up)或 {text}(無數
kpi_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L303  kpi:cells = [{label, value, unit?, delta?, note?}](2–4 格);頂層
_step_range(n, prev, shown)  L314  逐步類型的 (prev, shown, 起點延遲, 間隔, 長出秒數, 段長):prev is None = 一次全播(
cols_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L321  cols:items=[[標籤, 數值或[各系列數值], 單位?, {hi?}?]];series(≤3)/ stack
share_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None)  L343  share:rows=[{label, parts:[[名稱, 數值, 顏色?]…]}];style "bar"(100
segment(a, prev=None, shown=None, title_in=True, n=1, icon_root=None, fps=AL.FPS, siz...)  L367  一段動畫的渲染工作:格數 = min(n, 段長 × fps 無條件進位 + 1),之後由呼叫端停在最後一格。
_frames(job)  L379  
_done(job)  L384  
render(jobs, inproc=False)  L389  渲染(或取快取)多段,回傳每段的 PNG 路徑清單。未命中的段落預設交給子行程一次渲完。
load(path)  L409  PNG -> HxWx4 uint8(straight alpha)。
_font_css()  L415  
open_job(browser, job)  L421  開一頁、注入字型 / tokens / gsap、build(data)。回傳 (context, page, buil
probe_rects(browser, pr)  L468  圖表頁(pr = {type, data, size, ids, all?})播到底後:各 id 的外框 {id: [x
seek_shot(page, t, path=None)  L480  
render_job(browser, job, out_dir)  L485  逐格截圖到 out_dir/NNNN.png;回傳 (每格毫秒, build 結果)。
launch(pw)  L503  
run_jobs(jobs)  L507  
analyze(m, w, h, bottom_keep=SAFE_BOTTOM_KEEP)  L561  量測結果 -> 錯誤訊息:文字 < FS_MIN、元素出安全區(左右 SAFE_X、上 SAFE_TOP、下進字幕安全帶
measure_jobs(jobs)  L590  
measure(jobs)  L608  對 segment() 產的工作播到底量版面:回傳每項 {errors, problems, bottom}(同 key
main()  L637  

## pipeline/asr_worker.py
build(backend, models, device, threads)  L22  
build_aligner(models, device)  L52  Qwen3-ForcedAligner-0.6B -> f(x, text) = [[字, 起, 迄], ...]:一個
main()  L72  

## pipeline/assets_ain_news.py
tp(sel, key)  L12  

## pipeline/assets_ally_news.py
card(url, targets, rules, site, js=FLAT)  L7  

## pipeline/assets_bw_news.py
card(url, key, rules, site, ptag='p', layout='para', **cd)  L7  閱讀卡:key = 目標段落內含文字;rules = [(段首前綴…, 譯文)];layout=article 時 cd
steam_sum(app, date='2026/10/29')  L72  Steam 商店頁評論摘要(繁中原生、原本深色),同 pbz_day1 的 steam_sum

## pipeline/assets_cod26_news.py
hcg(key, zh, w=1100, fs=40)  L7  

## pipeline/assets_cod_news.py
tgb(texts, rules, js=None, w=1500, fs=38, vw=1600)  L11  
cut_all(*cuts)  L17  cuts=[(目標索引, 起, 止)…]:先攤平,再把長段縮成原文片段
anc_js(*sels)  L62  目標的祖先全部解除固定寬高與裁切(Steam 頁的容器有固定寬度 + overflow:hidden)
rev(url, rules)  L69  Steam 評論頁(單則):標題列(推薦與否、時數、日期)+ 內文

## pipeline/assets_cp25_news.py
card(url, ptag, targets, rules, site, layout='para', title_sel=None, **cd)  L16  閱讀卡:譯文都寫在 rules,卡上的標題/摘錄/出處列由 url+targets+rules 抽出
patch(li, key, zh, *more)  L24  
rv(sid, cut, rules, fs=38, full=True, w=900, oy_max=200)  L28  Steam 社群的單篇評論頁(UI 用繁中,評論本文 cut 取首段原文再由 rules 譯);full=False 只

## pipeline/assets_dei_clips.py
overview()  L191  每支來源一張總覽(每個片段取中間一格,寬 240):output/dei/clips_<src>.jpg

## pipeline/assets_dei_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
class _UABrowser  L120  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L123  
_UABrowser.new_context(self, **kw)  L126  
_save_layout(out, sp, canvas, runs)  L130  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L153  
check(only=None)  L182  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L212  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L227  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L241  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L274  

## pipeline/assets_dei_specs.py
gf(url, targets, rules, w=1000, fs=34)  L26  
sec(url, key, zh, w=800, fs=32)  L73  
art(url, ptag, targets, rules, site, w=1000, fs=34, vw=1100, title_sel=None, titl...)  L103  通用文章頁:ptag 為內文段落選擇器;title_sel 為標題(加大、加寬)
am(url, key, rules, **kw)  L179  
cut_js(idx, start, end)  L246  把第 idx 個目標區塊(一整大段)縮成「start 起到 end 止」的原文片段(只取原文,不改字)
steam(url, targets, rules, css='', js=None)  L402  

## pipeline/assets_el_news.py
js(*fns)  L23  
spec(url, site, targets, rules, css, cuts=(), vw=1350)  L27  cuts=[(目標序號, 起, 迄)]:把該目標縮成原文片段(只取原文)
gi_one(url, hdr, key, zh, cut=None, w=1250, fs=42)  L33  

## pipeline/assets_em_news.py
card(url, key, rules, site, ptag='p', layout='para', **cd)  L7  
steam_sum(app, date='2026/10/31')  L59  Steam 商店頁評論摘要(同 assets_bw_news.steam_sum)

## pipeline/assets_evc_news.py
both(*fns)  L6  把多個 `() => {...}` 合成一個(evaluate 只會執行最後一個表達式)
steam_syn(url, start, end, key, zh, w=1000, fs=42)  L11  Steam 商店簡介:目標為整個說明區,cut_js 取其中一段原文(Steam 頁本身已是暗色,dark=False)

## pipeline/assets_fs_news.py
card(url, ptag, targets, rules, site, js=FLAT, ts='h1')  L7  

## pipeline/assets_gd_clips.py
overview()  L134  每支來源一張總覽(每個片段取中間一格,寬 240,標出起訖秒):output/dei_gamersdead/gd_cli

## pipeline/assets_gd_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
_wait_chk(pg, ms=4000)  L125  
class _UABrowser  L135  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L138  
_UABrowser.new_context(self, **kw)  L141  
_save_layout(out, sp, canvas, runs)  L145  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L168  
check(only=None)  L199  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L229  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L244  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L258  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L291  

## pipeline/assets_gd_specs.py
inl(sel, fs, extra='')  L37  一行內的小字(署名、日期):行內區塊、寬度自動
title_css(sel, w, fs, extra='')  L44  
body_css(sel, w, fs, extra='')  L48  
kotaku(url, date_en, date_zh, by_en, p_key, p_zh, h1_rule=None, w=1200, fs=44, vw=13...)  L56  
gs_para(key_start, prefix, zh, w=1300, fs=42)  L129  

## pipeline/assets_gows_clips.py
overview()  L100  每支來源一張總覽(每個片段取中間一格,寬 240):output/gow_sales/clips/clips_<src>

## pipeline/assets_gows_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
class _UABrowser  L120  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L123  
_UABrowser.new_context(self, **kw)  L126  
_save_layout(out, sp, canvas, runs)  L130  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L153  
check(only=None)  L182  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L212  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L227  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L241  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L274  

## pipeline/assets_gows_specs.py
unclip(sel)  L14  把目標的祖先全部改成 overflow 可見、不限高(原頁用固定高度+overflow 裁字,版面檢查會報被裁)
kotaku(url, rules, w=1000)  L21  Kotaku 文章標題區:h1 + 副標(.post-excerpt)

## pipeline/assets_gta5_clips.py
_seg(src, rows, tag, note, extra=None)  L38  
overview()  L58  每支來源一張總覽(每個片段取中間一格,寬 240):output/dei_gta5/clips/clips_<src>.

## pipeline/assets_gta5_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
class _UABrowser  L120  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L123  
_UABrowser.new_context(self, **kw)  L126  
_save_layout(out, sp, canvas, runs)  L130  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L153  
check(only=None)  L182  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L212  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L227  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L241  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L274  

## pipeline/assets_gta5_specs.py
gs_para(prefix, zh, w=1000, fs=44, vw=1100)  L48  GameSpot 評測內文的一段(wp-block-paragraph),prefix 為該段開頭的英文前綴(以…結尾)
gb_para(prefix, zh)  L73  
kotaku_art(rules, targets, w=1200, fs=36)  L96  

## pipeline/assets_hs_news.py
big(fs, w)  L18  

## pipeline/assets_hsnd_news.py
card(url, targets, rules, site, js=FLAT)  L7  

## pipeline/assets_lib.py
font(size, bold=False, legacy=False)  L26  
wrap(draw, text, fnt, width)  L39  
class Page  L60  
Page.__init__(self, src, x0, x1, bg, name, pad=0, s_max=1.6)  L61  
Page.strip(self, y0, y1, gap=0, x0=None, x1=None)  L77  
Page._build(self)  L83  
Page.cb(self, x0, y0, x1, y1)  L90  顯示座標 -> 畫布像素框
Page.cbs(self, x0, y0, x1, y1)  L99  同 cb,但框跨多個 strip 時逐段回傳(落在 strip 外的部分略過)
Page.fill(self, x0, y0, x1, y1, color)  L107  
Page.smear(self, x0, y0, x1, y1)  L113  以框左右兩側像素橫向漸層填滿(適合平滑底色)
Page.fitfill(self, box, refs)  L124  以 refs(顯示座標框,需為乾淨背景)的像素擬合二次曲面,填滿 box(適合斜向漸層底色)
Page.shade(self, x0, y0, x1, y1, color=(14, 14, 14), solid_from=0.3)  L148  框內由上往下漸暗至 color(蓋在圖片上方放標題用)
Page.text(self, box, txt, size, color, bold=False, line=1.5, align='l', pad=0)  L157  box: 顯示座標 (x0,y0,x1,y1);size: 畫布像素(渲染時乘縮放)
Page.mark(self, txt, box)  L161  登記一個 hl 可定位的區塊(顯示座標框),例如保留原樣的英文名稱
Page._rec(self, d, ln, f, x, y)  L165  記錄一行文字的逐字水平範圍與墨水垂直範圍
Page.px(self, x, y)  L172  
Page.flow(self, box, items, gap=14)  L175  box 內由上往下依序排版多段文字;items=[(txt,size,color,bold,line)]
Page.render(self, label, out=None)  L179  
_warn_once(key, msg)  L226  
_default_engine()  L232  預設引擎:Windows 用 win(Windows OCR 有 zh-Hant-TW 語言包,繁中字形正確);其他平台
ocr_engine()  L238  目前使用的 OCR 引擎:環境變數 OCR_ENGINE=win|rapid 可覆蓋,沒設用 _default_engi
_rapid_engine()  L253  RapidOCR 單例。OCR_RAPID_REC=<繁體(或其他)辨識模型 .onnx> 可換掉內建的簡體為主辨識模型
_s2t_convert(text)  L290  簡體 -> 繁體(OpenCC s2tw,只轉字形,用語不轉)。OCR_S2T=0 關閉;opencc 沒裝時警告一次並
_split_words(text, x, y, w, h)  L312  把一行的框 (x,y,w,h) 依字元寬度估算切成詞框 [{t,x,y,w,h}]。
_rapid_to_lines(result)  L332  RapidOCR 輸出 [[四角點, 文字, 信心], …](或 None)-> [{"text","words":[{
ocr(path, lang='en-US')  L346  OCR,回傳 [{"text","words":[{t,x,y,w,h}]}]。引擎由 OCR_ENGINE=win|r
ocr_batch(folder)  L365  資料夾內所有 *.jpg 做 OCR,回傳 {檔名: 全文(行以換行相接)}(clip_scan / gd_crowd_
save_boxes(png, runs)  L383  文字區塊座標 sidecar(images/<name>.boxes.json),build.py 的 hl 紅框用
add_label(img, site, size=22)  L388  右下角來源標籤「中文翻譯 · 原文:site」(site 以 = 開頭才原樣顯示,翻譯過的網頁截圖不可用);回傳標籤外框
ink_check(img, runs, skip=(), edge=40, top=24, tol=8, thr=45)  L400  看 PNG 像素驗文字框(不是只信 .boxes.json)。背景 = 每個框所在列的局部中位數色,非純色底、含圖片的頁
page(fn)  L503  
entry(name, site, title_en, title_zh, notes='')  L508  

## pipeline/assets_oni_clips.py
scan_all(rescan)  L52  
pieces(src, runs)  L68  乾淨區段依來源硬切切開,每段 2.5~8 秒(過長均分),內部不含硬切。
build_spec(res)  L84  
lib(*args)  L110  

## pipeline/assets_pbz2_news.py
card(url, ptag, texts, rules, site, **kw)  L9  閱讀卡(para 版型):texts 為各段開頭英文(找目標用),rules 為 [(前綴…, 譯文)]

## pipeline/assets_pbz_news.py
card(url, texts, rules, site='Eurogamer 2026/10', ptag=P)  L11  閱讀卡(para 版型):texts 為各段內含文字(找目標用),rules 為 [(段首前綴…, 譯文)]
head(url, en_title, zh_title, en_sub, zh_sub, author, job, site='Eurogamer 2026/10')  L16  標題區真實頁:標題+副標+署名+星等圖形(署名列的 Review/by/職稱逐字翻,人名不動)

## pipeline/assets_pbzd_news.py
cut(idx, *segs)  L30  
review(path, keep_en=(), rules=(), site=SITE_ZH, js=None, bar=False)  L37  
letter(targets, rules)  L47  官方公告頁(SPA,class 是雜湊,真實頁版面抓不到穩定區塊):用文字找段落,走閱讀卡(para 版型);信尾「又收

## pipeline/assets_pbzx_news.py
zh_para(url, site, key, w=1200, fs=46, vw=1300)  L13  
en(url, site, targets, rules, css='', vw=1300, **kw)  L18  

## pipeline/assets_ps5_news.py
k(url, paras, title=None, **kw)  L13  Kotaku 新版型:paras=[(段首英文, 中文)...],title=(英文標題, 中文) 可省

## pipeline/assets_ps5b_news.py
a(url, site, h1, ps, **kw)  L22  h1(可 None)+ 若干段 (開頭英文, 中文)

## pipeline/assets_re9_clips.py
probe_dur(src)  L256  
detect_crop(src, a, b)  L262  在片段內取 3 個時間點 cropdetect,只接受純黑邊(pillarbox 或 letterbox)且 >=3%;
luma(src, a, b, crop=None)  L285  a~b 秒每 1/FPS 秒一個平均亮度(crop 內)
refine(src, a, b, crop)  L294  切掉黑場:在 a~b 內找出連續「不黑」區段(容許 1 格=0.25 秒的黑閃),兩端各內縮 0.25 秒,留 >=2.
build()  L319  
tag_lines()  L349  
union_len(spans)  L359  
check()  L375  

## pipeline/assets_re9_news.py
_wait_load(pg, ms=4000)  L227  
fw(s)  L238  中文旁的半形標點改全形(規格裡可直接打半形)
_open(browser, sp, dsf)  L244  開頁 -> 保留區塊 -> 翻譯;回傳 (ctx, page, 量測框)
_frame_color(img)  L284  圖片最外圈最常見的顏色(補邊用)
capture(browser, sp, width=FW)  L293  回傳 (PIL.Image 寬 width, runs[像素,相對該圖左上])。兩段式:先 DSF=1 量測,再以 DS
_bg(img)  L343  
_tag(canvas, text, x=18, y=14)  L347  子塊左上角網站名標籤(僅合成圖用)
compose(browser, sp)  L356  單頁 -> 1920x1080 畫布;parts -> 直向堆疊
build(names)  L393  
_flat(runs)  L415  
check()  L419  驗證 HL 建議詞都能在 .boxes.json 中找到(比對方式同 build.py find_hl_boxes:忽略
overview(out=None)  L439  總覽圖:各圖縮圖並排、標圖名(寬 <= 2400)

## pipeline/assets_re9l_clips.py
_seg(rows, note)  L37  
overview()  L95  每支來源一張總覽(每個片段取中間一格,寬 240):output/re9_leon/clips/clips_<src>.

## pipeline/assets_re9l_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
class _UABrowser  L120  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L123  
_UABrowser.new_context(self, **kw)  L126  
_save_layout(out, sp, canvas, runs)  L130  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L153  
check(only=None)  L182  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L212  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L227  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L241  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L274  

## pipeline/assets_re9l_specs.py
ps_art(rules, targets, w=1150, fs=38)  L14  

## pipeline/assets_re9o_clips.py
check()  L130  

## pipeline/assets_re9o_news.py
build(names)  L23  
check()  L48  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
overview(out=None)  L68  

## pipeline/assets_re9o_specs.py
ign_p(url, txt, rules, w=1000, fs=40, **kw)  L38  
ps(qtxt, atxts, rules, w=1000, qfs=30, afs=42, oy_max=200, **kw)  L101  qtxt=None 表示不放問題;atxts 內 "H:" 開頭者為 h3(問題),其餘為 p(回答)

## pipeline/assets_recv_news.py
card(url, rules, site, layout='article', **c)  L44  

## pipeline/assets_rs2_news.py
tp(sel, key)  L17  
df_post(txt, zh, tm)  L21  DF 影片字幕段 -> post 引言卡:data: 頁放英文原句(autosub 清稿),rules 譯成繁中;出處列
steam_price(appid, block, rules)  L30  Steam 商店頁購買區(?cc=us,美金);價格改成「xx 美金」寫法,折扣整句與按鈕走 rules

## pipeline/assets_sbi_news.py
site(url, label, targets, rules, css='', js=None, vw=1300, oy=200)  L19  

## pipeline/assets_sfm_news.py
ptt_js(metas, excerpts, pushes)  L19  metas=要留的 metaline 關鍵字(作者/標題/時間);excerpts=[(起,迄)] 原文整段;pushe
ptt(aid, metas, excerpts, pushes, keep=())  L41  
yt(vid, lc, key, site, user, cut=None, ago=None)  L80  cut=(起,迄):長留言只留原文的這一段,兩端加「……」

## pipeline/assets_sg2_news.py
ka(targets, rules, **kw)  L11  

## pipeline/assets_sr_news.py
card(url, ptag, targets, rules, site, js=FLAT)  L9  

## pipeline/assets_sv3_clips.py
overview()  L277  每支來源一張總覽(每個片段取中間一格,寬 240):output/survive3/clips/clips_<src>.

## pipeline/assets_sv3_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
class _UABrowser  L120  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L123  
_UABrowser.new_context(self, **kw)  L126  
_save_layout(out, sp, canvas, runs)  L130  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L153  
check(only=None)  L182  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L212  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L227  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L241  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L274  

## pipeline/assets_sv3_specs.py
art(url, ptag, targets, rules, site, w=1000, fs=34, vw=1100, title_sel=None, titl...)  L14  

## pipeline/assets_tg_news.py
tg(url, site, targets, rules, ptag=P, w=1100, fs=42, **kw)  L12  
head(url, zh_title, zh_date, en_title, en_date)  L16  
body(url, key, prefix, zh, site='TheGamer')  L22  

## pipeline/assets_tracer_clips.py
overview()  L93  每支來源一張總覽(每個片段取中間一格,寬 240):output/dei_tracer/clips/clips_<src

## pipeline/assets_tracer_news.py
_open_chk(browser, sp, dsf)  L95  
_capture_chk(browser, sp, width=R.FW)  L110  
_wait_chk(pg, ms=4000)  L125  
class _UABrowser  L135  new_context 時帶入該頁指定的 User-Agent(由 build 在每頁開始前設定 ua)
_UABrowser.__init__(self, b)  L138  
_UABrowser.new_context(self, **kw)  L141  
_save_layout(out, sp, canvas, runs)  L145  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
build(names)  L168  
check(only=None)  L199  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
_check_ink(n, runs, site, stat)  L229  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
relabel(names, old_prefix='=來源:')  L244  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動
_check_layout(n, runs)  L258  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
_names(args)  L291  

## pipeline/assets_tracer_specs.py
k16(css_sel, prefix, zh, w=1200, fs=40, vw=1300, rule_key=None)  L17  Kotaku 2016 的一段(css_sel 為段落選擇器,prefix 為該段開頭英文,以…結尾做前綴比對)

## pipeline/assets_wep_news.py
hide_js(*starts)  L15  隱藏開頭是指定文字的 li(含其子清單);樓層小標是 li 內裸文字節點,先包成 span 才能被規則比對
forum(pn, items, rules, date, hide=(), tid=TID, vw=1500, css=BIG)  L21  items = [(p|li, 段落內含文字)];日期為頁面顯示時間(台灣)換算成美西日期
zh(url, targets, site, hide='')  L39  官網繁中文章:閱讀卡(para),只摘要用的段落;hide 為先隱藏的行

## pipeline/assets_wow_clips.py
probe_dur(src)  L166  
detect_crop(src, a, b)  L172  在片段內取 3 個時間點 cropdetect,只接受純黑邊(pillarbox 或 letterbox)且 >=3%;
luma(src, a, b, crop=None)  L195  a~b 秒每 1/FPS 秒一個平均亮度(crop 內)
refine(src, a, b, crop)  L204  切掉黑場:在 a~b 內找出連續「不黑」區段(容許 1 格=0.25 秒的黑閃),兩端各內縮 0.25 秒,留 >=2.
build()  L229  
tag_lines()  L263  
union_len(spans)  L273  
check()  L289  
grab(src, t, crop=None, w=320)  L332  來源在 t 秒的一格(PIL Image,去黑邊後縮成寬 w);失敗回 None
contact_sheet(items, out, cols=6, w=320)  L341  items = [(src, t, crop, label, safe_dict)];每格畫標籤,有 top/botto
sheet(argv)  L366  
preview(nf=1)  L374  每標籤一張:每個片段取中間一格(nf=1;用 clips json 的最終起訖,含自動修過的黑場與 crop);nf>1

## pipeline/assets_wow_news.py
class _TZBrowser  L22  new_context 時固定美西時區:Discourse 的貼文日期用瀏覽器時區顯示
_TZBrowser.__init__(self, b)  L25  
_TZBrowser.new_context(self, **kw)  L28  
_wait_load(pg, ms=4000)  L35  Discourse 是 Ember 單頁應用:捲動會把貼文從 DOM 拿掉、改 DOM 又會被它重繪蓋掉。
build(names)  L56  
check()  L81  驗證 HL 建議詞都能在 .boxes.json 中找到(比對方式同 build.py find_hl_boxes:忽略
overview(out=None)  L101  總覽圖:各圖縮圖並排、標圖名

## pipeline/assets_wow_races_news.py
blue(hdr, rules, hide=(), vw=1500)  L13  藍帖 post_6 的某個種族小節(巢狀 li);hide=要略去的其他行開頭

## pipeline/assets_wow_specs.py
disc(tid, pn, paras, rules, title=False, lis=False, vw=1100, keep=(), extra_css=''...)  L39  Discourse 單樓貼文:作者列 + 指定段落(p 或 li,以內含文字找)+ 讚數;title=True 另留標題
meta(user_zh, date_en, date_zh, title_en=None, title_zh=None)  L48  作者列的共通規則:貼文數、日期(只留日期,不留時分)
D(d)  L91  

## pipeline/assets_wowban_news.py
web(url, site, prefix, zh, hdr=None, cut=None, w=1150, fs=40)  L12  單段文章:cut=(起, 止) 把長段縮成原文片段(只取原文)
bn(tid, pn, date, zh_date, prefix, zh, **kw)  L20  

## pipeline/assets_wowi_clips.py
tag_more(src, idxs, tag)  L27  

## pipeline/assets_wowi_crop.py
blank_row(m, y, span=30)  L30  y 附近最近的空白列(整列無字)。
main()  L39  

## pipeline/assets_wowi_news.py
build(names)  L26  
reuse()  L54  
check()  L61  HL 建議詞都要在 .boxes.json 找到(比對方式同 build.py find_hl_boxes:忽略空白與大
overview(out=None)  L81  

## pipeline/assets_wowi_specs.py
block_css(sel, w, fs, lh=1.6, extra='')  L16  
gnn(targets, css='', rules=(), w=1000, fs=32, **kw)  L32  
en_css(sel_p, sel_h, w, fs, hs=None)  L82  
baha_floor(pid)  L165  
baha(targets, edits, w=1000, fs=34, css='')  L182  edits = [(樓層 post id, [行...])]:行內的「……」是截掉的部分;其餘片段必須逐字出現在原文(J

## pipeline/assets_wpd_news.py
card(url, ptag, texts, rules, site, **kw)  L11  閱讀卡(para 版型):texts 為各段開頭英文(找目標用),rules 為 [(前綴…, 譯文)]

## pipeline/assets_wret_news.py
shop(url, targets, rules, css, vw=1300, js=None, site=SRC_SHOP)  L19  
card(sp, **c)  L59  
cardart(url, targets, rules, site, **c)  L63  

## pipeline/assets_ws_news.py
_js(segs=None, brk=None)  L38  
spec(url, targets, rules, site, layout='article', segs=None, brk=None, **card)  L44  閱讀卡:targets 為 [css | (css, 內含文字)];rules 為 [(前綴…, 譯文)];segs 為
zh_art(url, title, p, site, segs=None, **kw)  L50  中文文章頁:h1 + 一段
baha(snA, target, site, segs=None, post=None, who=None, ncls='username', brk=None,...)  L55  巴哈貼文/留言:post=該樓 section id(post layout,抓暱稱時間);沒給就 para。ncls=
_yt_comment_html(vid, cid)  L75  從本機 yt-dlp 留言資料取一則,寫成最小 HTML(tmp/ws_shots/yt_<id>.html),回傳 f
disc(tid, n, targets, rules, site, **kw)  L91  

## pipeline/audience_model.py
_compile(words)  L70  
_hit(compiled, low)  L80  
load_lexicon(path: Path=LEXICON)  L85  
classify(text: str, lex: dict)  L96  
norm_channel(name)  L112  
_iso(ts)  L117  字串或 epoch 秒 → +08:00 ISO(秒)。無法解析回傳空字串。
_like(c)  L132  
_read_json(p: Path)  L139  
parse_file(path: Path)  L146  回傳 dict(kind, video_id, title, channel, captured_at, comment
_jsonl(p: Path)  L177  
build_maps(root: Path)  L188  tag→頻道、video_id→(tag, 頻道, 切角)。來源優先序:outcomes > spec.json > b
gather_sources(root: Path, ytad_dir: Path)  L214  列出 (src, tag_or_None, 路徑),順序固定(ytad → ref_own → ref_info → r
collect(root: Path, ytad_dir: Path, lex: dict, channel: str)  L231  掃全部來源 → (rows, stats_meta)。rows 已依 (video_id,作者,前40字) 去重、只留該
row_key(r)  L286  
merge_existing(new_rows, old_rows)  L290  --update:保留來源已消失的舊列;同鍵以新抓為準、讚數取大。
sort_rows(rows)  L301  
tnorm(s: str)  L306  
bigrams(text: str)  L310  
polarity(text: str)  L321  
_one_line(s: str, n: int)  L334  
_vtitle(r)  L339  
render_stats(channel: str, rows: list, meta: dict, lex_flags: list)  L343  
run(channel: str, update: bool=False, root: Path=None, ytad_dir: Path=None, out_d...)  L441  主流程;回傳 (rows, meta, jsonl 路徑, stats 路徑)。
_own_n_now(channel: str, out_dir: Path)  L479  現在自製片留言數:優先 stats.md 檔頭「自製片 N」,退而數 jsonl 的 is_own。
persona_status(channel: str, root: Path=None, out_dir: Path=None, now: datetime=None)  L492  人設是否過期。回傳 dict(status 'OK'|'過期', n_now, n_persona, reason)。
_hook_update(channel: str, res: dict)  L559  
hook_main(timeout: float=HOOK_TIMEOUT)  L569  SessionStart:兩頻道 --update(總時限 timeout 秒,超時略過)+ 人設狀態,只印 1 行,結
main()  L595  

## pipeline/audio_consts.py
channel_kind(channel)  L24  頻道名(--channel 或 spec.json 的 channel:ChannelA/ChannelA、ChannelB/ChannelB、ChannelC/不科
bgm_for_channel(channel, tag)  L36  頻道名 -> 定案 BGM 檔名;不認得頻道 = None。第三頻道三首以 tag 的 crc32 取餘輪用(穩定,同一
bgm_gain_db(voice_db, win, extra_db=0.0)  L45  預設 BGM 增益 dB:回傳 (增益 dB, 套用條款 'p90'|'peak')。win = (p10, p50, 
bgm_gain_auto(voice_db, win, extra_db=0.0)  L54  預設 BGM 增益:回傳 (線性增益, 增益 dB, 套用條款 'p90'|'peak')。win = track_wi
bgm_norm(db)  L60  BGM 響度對齊倍率:把量到的 db 拉到 BGM_REF_DB,再乘 --bgm-vol 才是實際音量。
bgm_sidecar(path)  L68  曲子的同名 .json 側檔(AI 生成曲:使用者定案的 bgm_db 偏移與出處);沒有或讀不了回 {}。
sidecar_db(side)  L76  側檔 dict 的 bgm_db(相對預設算法的偏移 dB;與命令列 --bgm-db 疊加);沒有回 0.0。
bgm_sidecar_db(path)  L84  
sidecar_duck(side)  L88  有側檔(含 bgm_db)的曲子才閃避(配音時壓低 BGM);側檔 duck:false 可關。

## pipeline/board.py
board_dir()  L35  
json_path()  L39  
md_path()  L43  
now_iso()  L47  
norm_stage(v)  L51  舊階段名換成新名;其他原樣。
_norm_data(data)  L56  
load()  L63  
get(tag)  L75  
_atomic_write(path, text)  L79  
class _Mutex  L91  board.lock 互斥(超過 LOCK_STALE_S 秒視為殘留)。
_Mutex.__init__(self)  L94  
_Mutex.__enter__(self)  L97  
_Mutex.__exit__(self, *exc)  L112  
sort_key(item)  L119  
ordered(data)  L124  
_cell(v)  L128  
render_md(data)  L138  
_save(data)  L147  
_clean(kw)  L153  
latest_ver(tag)  L176  該片 output 最新版的版本號字串(v3 之類):從 {tag}_v*.mp4、listen_v*.txt、v*_說
stage_problems(tag, stage)  L189  設 stage 的前置條件:回傳 [未過項的說明](空 = 可設)。非受控階段、找不到版本號 = 空(後者印警告)。
update(tag, force=False, **kw)  L206  只更新給的欄(None 不動);tag 不存在就新增。回傳更新後該筆。
set_stage(tag, stage, force=False, **kw)  L231  
remove(tag)  L235  
show_text(data=None)  L243  
main()  L251  

## pipeline/build.py
log(*a)  L79  
run(cmd, cwd=None)  L84  
probe_duration(path)  L92  
probe_has_audio(path)  L97  
sha1(s)  L103  
file_sig(path)  L107  快取簽章用的檔案指紋:相對於素材根的路徑 + 大小 + 修改時間(不含絕對路徑,素材根搬家後仍相同)。
load_lines(script_path)  L114  
load_meta(script_path)  L124  script 頂層資料:sections 的 title/trans/name,以及 timeline(動畫用的時間軸節
load_fallback(script_path)  L131  script 頂層 fallback:{標籤: [備援標籤, …]}。挑片段時該標籤的未用片段不夠,就依序改用備援標籤的
parse_range(spec, n)  L139  
file_sha1(path)  L156  
_synth_edge(todo, voice, rate)  L160  
_run_engine(cmd)  L187  跑外部 TTS 引擎,把它 stderr 裡的摘要/進度行(以 [ 或兩個空白開頭;進度條不算)即時轉到 log,品管結
_synth_external(todo, tts_cmd, voice, rate, tts_dir)  L200  子行程批次合成:cmd <jobs.json> --voice V --rate R;jobs = [{"idx","t
_qc_json(raw)  L223  音檔旁的 .qc.json 原始內容(不檢查版本);沒有或壞掉回傳 None。
_qc_record(raw, key)  L234  音檔旁的品管紀錄;必須是目前的 QC 版本、同一把快取鍵、且音檔內容沒被換過才算數,否則回傳 None(要重新檢驗)。
_pron_changed(engine, u, rec)  L243  cosy3:音檔錄音時的讀音標注(cosy_pron.json / pron_rules.json)或英文寫法(cosy
_trim_one(u)  L252  u = 配音單位(一個子句或一整行):u["raw"] 原始音檔,u["qc"] 品管紀錄;產生 <raw>.trim.
write_qc_report(units, redone, path)  L274  合併每個配音單位的品管紀錄成一份涵蓋全部單位的報告;回傳未通過的 (單位標籤, 原因)。標籤:單句行 = 句編號,多句行
tts_silent(lines, tts_dir)  L292  測試用靜音引擎(--tts-engine silent):每句一段靜音,長度取 script 的 silent_dur,
relocate_tts_cache(want, tts_dir, ext)  L303  快取以「文字」為鍵:文案插句/刪句後句編號會位移,先依 .key 內容把既有音檔搬到新的句編號。
_read_pcm(path)  L332  
assemble_line(ln, tts_dir)  L337  一行的音檔:單一單位直接用其 trim.wav;多個子句 = 各子句 trim.wav + 句後停頓(ln["claus
frozen_abort(frozen, reasons)  L358  凍結後禁新合成(PLAN_TTS_FLOW R3/T4):reasons = [(單位標籤, 原因)](快取未命中的單位
tts_all(lines, voice, rate, tts_dir, engine='edge', tts_cmd=None, no_synth=False, fro...)  L370  tts_cmd:外部引擎的合成指令(字串清單)。no_synth:有任何一句需要合成/重新檢驗就中止,不動任何音檔。
anim_hold_pads(lines, durs, gap, section_gap, tlmeta=None, card_min=0.0, img_min=0.0)  L484  動畫鏡頭「最後一步完全顯示後至少停留 ANIM_HOLD 秒」:鏡頭(連續句)太短時,在該鏡頭最後一句之後補靜音,
pause_padded(ln, pad, gap)  L555  這句的補靜音是否由 pause 決定(log 標記用)。
build_timeline(lines, gap, section_gap, tlmeta=None, card_min=0.0, img_min=0.0)  L561  
lift_gamma(y)  L596  影片鏡頭的提亮 gamma;不需要提亮(或亮度未知)回傳 None。
load_luma_cache(path)  L604  亮度探測結果存檔(--check-only 與正式渲染共用同一份,重跑不必再探測)。
save_luma_cache()  L615  
luma_at(media, src, t, crop=None)  L620  
brightness(media, src, start, length, crop=None)  L633  
probe_dims(path)  L638  
find_clip(clips, src, t)  L647  手動指定的鏡頭:找出涵蓋該時間點的 clips 條目(取其 crop / top / bottom)。
frame_spec(media, src, clip)  L655  影片鏡頭取景:clip["crop"] 去黑邊 -> cover 到 WxH -> 依 top/bottom(去黑邊後畫
cut_violations(clip, start, length)  L686  影片鏡頭用到的素材區段 [start, start+length] 內,離頭或尾不到 VIDEO_MIN 秒的來源硬切(
class ClipPicker  L695  
ClipPicker.__init__(self, clips, max_per_src, media, seed=20240607)  L696  
ClipPicker.snapshot(self)  L709  
ClipPicker.restore(self, st)  L713  
ClipPicker.mark(self, src, a, b)  L720  
ClipPicker._free(self, clip)  L726  
ClipPicker._rand_start(self, clip, a, b, length)  L741  在可用區間 [a, b-length] 內隨機取起點;相鄰鏡頭取自同一段素材時避開 +-self.gap(預設 SAME
ClipPicker._cut_fix(self, clip, a, b, start, length)  L763  start 起的 length 秒若有離頭尾太近的硬切:改成從某個硬切之後起、或收在某個硬切之前(離 start 最近的
ClipPicker.note_manual(self, idx, src, start, length, crop=None)  L775  手動指定的鏡頭:檢查亮度,只警告。
ClipPicker.pick(self, tag, length)  L782  回傳 (clip, start, 亮度);挑不到回傳 None。
ClipPicker.pick_reuse(self, tag, length)  L827  最後手段:重用同標籤已用過的畫面。條件:與重疊到的每一次使用在成片上相隔 >= REUSE_GAP 秒、同來源累計秒數(
special_imgs(ln)  L881  quote / compare 句用到的圖片名(用來檢查存在與同圖連續)。
_jkey(x)  L890  
visual_key(ln)  L894  這一句的畫面規格;相鄰句子規格相同就共用鏡頭。
group_runs(lines)  L919  
video_groups(ls)  L930  同標籤的連續句:依句界切段,短於 VIDEO_MIN 的句子併入下一句(最後一句太短就併入前一段)。回傳 [[f0, f
quote_chars(q)  L950  
shot_min_frames(s, img_min)  L954  
kind_name(s)  L967  
img_kind(media, img)  L972  圖的動態分組:"text"(極慢 zoom + 漂移)| "photo"(tilt/zoom 輪替)。
layout_shots(lines, kind_of=None)  L988  第一階段:只排鏡頭的時間(尚未挑影片片段)。kind_of(img) -> "text"|"photo" 決定圖片鏡頭預
stitch_min(shots, img_min)  L1037  鏡頭不足最短時長時,向相鄰的影片鏡頭借時間(先借後面、再借前面;借完對方仍須 >= VIDEO_MIN,且有上限)。
pick_videos(shots, media, clips, max_per_src, fallback=None)  L1063  第二階段:替影片鏡頭挑片段。素材少的標籤(指名特定畫面的子標籤)先挑,免得被通用標籤用掉;
_fit_font(text, size, max_w, stroke)  L1203  
make_card(card, path)  L1213  
make_spoiler(text, path)  L1256  畫劇透警告牌(只含牌子本身,透明底 RGBA)。回傳 (x, y, w, h):牌子在 1920x1080 畫面上的位置
spoiler_filters(sp_cfg, png, in_idx, in_label, out_label)  L1282  劇透牌:靜態、只在最後 SPOILER_FADE 秒淡出。回傳 (額外輸入參數, filter 字串)。
_tw(tok)  L1301  
_is_punct(tok)  L1307  
_strip(toks)  L1311  
_clean_sub(toks)  L1320  字幕顯示文字:單獨的標點字元換成一個半形空格(數字內的小數點等包在英數字詞裡,不動),連續空格併一個、頭尾去空格。
_dw(toks)  L1327  
_sub_words()  L1339  
_simp(text)  L1343  jieba 內建詞典是簡體,繁體直接丟進去會斷錯(人事部/門):斷詞與查詞典前先逐字轉簡體;長度變了或 opencc 不
_jieba()  L1348  jieba 模組(跨界字串檢查查它的詞典詞頻;斷詞器選擇見 seg.py / --seg)。不可用回傳 False。
_wrap_toks(text)  L1353  直式動畫換行用 token(join = text):括號整段、英數詞(含詞間空白)整段、其餘用斷詞器(預設 jieba
_is_cjk(c)  L1377  
_cross_word(text, simp, off)  L1381  切在 text[off] 前:左右各取 1-2 個字的跨界字串若是詞典裡的詞(jieba 詞典詞頻 > 0,含自訂詞表)
_cut_reasons(toks, cross=True, seg=None)  L1396  每個 token 位置 i(切在 toks[i-1] 與 toks[i] 之間)不可切的原因,可切為 None。斷詞器不
_legal_cuts(toks, cross=True)  L1445  回傳可切的 token 位置集合(切在 toks[i-1] 與 toks[i] 之間)。None 表示斷詞器不可用。
_is_en(t)  L1462  
_is_cjk_tok(t)  L1466  
_pos_words(text)  L1470  [(起, 訖, 詞, 詞性)](jieba.posseg,繁轉簡斷、切回原字);不可用回傳 None。
_phrase_score(toks)  L1485  每個切點 i(切在 toks[i-1] 與 toks[i] 之間)-> (分數, 原因);分數越大越不該切(負數 = 偏
_phrase_cost(toks)  L1555  _split_dp 用的切點成本 i -> 分數(phrase_mode 才用);不可用回傳 None。
_split_dp(toks, legal, n, score=None)  L1561  在合法切點中選 n-1 個,使各段寬度與平均的平方差最小,每段在 [SPLIT_MIN_W, SUB_MAX_W]。無解
_relax_rank(why)  L1611  放寬順序(F2-3b):0 = 本來就可切、1 = 數字與量詞/中文數字串、2 = 其他(詞中間、段首黏前字)、3 = 
_split_long(toks)  L1623  
_split_long_greedy(toks)  L1650  
_title_colon_spans(toks)  L1669  《…》(有成對、不巢狀)內含冒號(: 或 :)的書名,回傳 [(《的位置, 》的位置)](token 索引)。
_sub_pieces(text)  L1683  依標點切出的各段 token(含段尾標點);「、」連接的短詞併成一段。書名號內的冒號不斷句。
split_phrases(text)  L1704  回傳 [(顯示文字, 權重)]。依標點切段,數字/英文單字不拆,顯示去頭尾標點。
sub_seams(text, judge=None)  L1723  字幕拆段的接縫檢查:回傳 [(左段, 右段, 原因)]。只看超過上限、在沒有標點處切開的接縫(_split_long);
sub_phrase_seams(text)  L1740  字幕拆段的片語接縫(2026-10-29):只看超寬段在沒有標點處的接縫,詞沒切開(sub_seams 沒列)但落在 _
check_sub_seams(lines)  L1758  渲染前檢查:全片字幕拆段不可把詞切開。
_ass_t(x)  L1764  
set_sub_profile(name)  L1772  切換字幕組(landscape / portrait):改寫 SUB_* 全域並重算 SUB_EM、SUB_PAD_X、
sub_text_width(text)  L1782  字幕文字在 libass 的前進寬度(px):以同字型、換算後的字級用 Pillow 量。
_spread(ph, s0, e0, end)  L1790  把字幕段依權重分配在 [s0, e0];最後一段延到 end(接上句後靜音)。回傳 [(文字, 起, 迄)]。
_say_units(s)  L1806  送配音文字的音節數估計(字幕時間等比例分配的權重):中文字與數字每字 1,英文單字依母音群。
_phrase_spans(text, ph)  L1812  split_phrases 的各字幕段在 text 中的 (起, 迄) 字元位置:以非標點字元依序對位;對不上回傳 No
_phrase_times(text, say, say_t, s0, e0, end, legacy=False)  L1825  一個配音單位(整行或一個子句)的字幕段起訖 [(文字, 起, 迄)]。[s0, e0] = 該單位語音在片中的起訖,最後
_line_units(ln)  L1847  一行的配音單位 [(送配音文字, 語音起, 語音迄, say_t)](成片秒,時間軸上的實際起訖);沒拆子句的行是一個單
_unit_refs(text, units, ph)  L1855  各字幕段起點的參考時間 [(秒, 種類)];字幕段對不回 text 時回傳 None。每段依它第一個字在送配音文字中的位
hl_word_time(ln, kws)  L1880  這行 kws 中最早被唸到的詞的片中秒數(hl 底線卡詞用);詞不在旁白、所屬配音單位沒有品管對齊時間一律回傳 None
line_phrase_times(ln, legacy=False)  L1907  一行的字幕段與起訖秒。拆成子句的行(ln["clauses"])逐子句處理;每個配音單位內的分段時間見 _phrase_
sub_sync(lines, timed_fn=None)  L1936  全片每個字幕段的起點與語音的時間差 [dict(idx, text, start, ref, diff)](diff 正
audio_gaps(path)  L1951  成片音軌的時間戳缺口 [(缺口前秒, 缺口後秒)]。有缺口 = 混音中途掉了聲音(播放器會把之後的聲音提早播,字幕與畫面
note_text_width(text)  L1970  
note_wrap(text)  L1977  note 超過 NOTE_MAX_PX 時斷成兩行(\N);優先在最接近中點的空白斷,沒空白就字數中點。
note_events(lines, shots)  L1987  每句 note 要畫的時段:該句畫面區間 [f0, f1) 與「影片片段鏡頭」(kind=video 且非 specia
write_ass(lines, path, shots=None)  L2008  
_cover(im, w, h)  L2095  
_cover_at(im, w, h, ax=0.5, ay=0.0)  L2102  cover 裁切,可指定裁切位置(ax/ay: 0=靠左/上, 1=靠右/下)。
_blit(canvas, sprite, x, y)  L2110  把 RGBA 小圖 alpha 合成到 canvas(可超出邊界,自動裁掉)。
split_label(im, fs=22)  L2120  圖右下角烤進去的「中文翻譯 · 原文:…」標籤(assets_lib.add_label:黑底圓角、白字)。
_paste_label(canvas, label, right, bottom, scale)  L2151  
_load_boxes(media, img)  L2175  
find_hl_boxes(entries, kw)  L2182  在 sidecar 文字區塊中找關鍵字(忽略空白與大小寫,可跨行),回傳原圖像素框清單。
_ul_span(box, entries, imw)  L2205  底線的橫向範圍(原圖像素):文字左右各延伸 HL_UL_EXT 倍行高,最短 HL_UL_MINLEN 倍行高;
_ink_bottom(media, img, box)  L2232  命中框內文字墨跡的下緣(原圖 y);框內找不到與底色差異明顯的像素就回傳 None。
_hl_hits(s, media, imw)  L2248  s["hls"] 各段的命中框(原圖像素,含底線範圍);回傳 (與 hls 同序的清單, 找不到的 [(句, 關鍵字)]
_tilt_quad(fx, u)  L2268  _tilt_filter 在進度 u(0 = 第一格,1 = 最後一格)的目的四角:左上、右上、左下、右下(成片像素)。
_zoomish(fx)  L2279  zoom 類 fx(zoom、text 組的 drift_l / drift_r):用 2x 畫布 + _zoom_fi
_zoom_params(fx)  L2284  (終點倍率上限, 水平漂移 px:鏡頭期間由 -dx 移到 +dx)。非 zoom 類回傳 (1.0, 0)。
fx_map(fx, u, zoom=None)  L2295  fx 動態在進度 u 時「畫布座標 -> 成片座標」的函式;與 shot_cmd 的 _zoom_filter、_til
_zoom_pad(s)  L2318  zoom 類(含 drift)鏡頭動態全程,成片左右邊會取樣到畫布外多少 px(1x,含 4px 餘裕);0 = 不會露
_extend_sides(comp, dx0, dx1, dy0, dy1, pad)  L2333  text 組畫布左右補邊(A 法):圖(畫布內 dx0-dx1 x dy0-dy1)沒蓋到的左右兩側,用圖最外 4 欄每
_extend_vert(comp, dy0, dy1)  L2351  text 組畫布上下補邊(2026-10-22):圖(畫布內 dy0-dy1 列)沒蓋到畫布底/頂時(字幕帶下方露出模糊
_fx_maps(fx, zoom=None)  L2371  
_zoom_fit(c0, c1, zmax=ZOOM_END, drift=0)  L2375  zoom 鏡頭的 (終點倍率, 錨點 ax, ay):錨點放在文字內容寬(畫布 x 範圍 c0-c1)的中心,
_side_margin(c0, c1, maps)  L2388  畫布 x 範圍 c0-c1 在 fx 動態全程離成片左右邊的最小距離。
_top_limits(x0, x1, maps, edge)  L2393  文字框(畫布 x 範圍 x0-x1)對畫面上緣的兩個門檻(畫布 y):框頂 >= vis 時整行在畫面內且留足 TEXT
text_clip(ents, sc, pos, fx, zoom=None)  L2407  每個文字框(.boxes.json)在 fx 動態全程(FX_U)的成片位置,驗「畫面邊緣不裁字」:
layout_image(s, media, im_size)  L2438  圖片鏡頭版面:決定縮放 sc 與圖片左上角 pos(輸出像素)。
_load_hlseq(media, img)  L2601  截圖時一起產出的底線序列索引 images/<img>.hl.json(news_lib 計畫 §2C);沒有、或尺寸與
_hl_seq_bars(media, seq, kws, sc, px, py, k)  L2615  瀏覽器出的底線序列 -> [(各 p 的 sprite 清單, x, y)](畫布座標);任一詞在序列裡找不到就回傳 N
hl_starts(hs, shot_f0, shot_frames)  L2630  各段 hl 離鏡頭開頭的起點秒數;hs = 依序的 {"f0", "tw"}(tw = hl_word_time 的結果
prep_hl(s, stem, bw, bh, k, lay, media=None)  L2643  依 s["hls"] 的命中框畫紅色底線,每段 hl 輸出一組逐格 PNG(與前景同畫布座標):
_label_info(media, img)  L2724  ((圖寬, 圖高), 重貼前的標籤 (w, h) 或 None),依 split_label 的偵測結果;每張圖只開一次
_place_label(s, media, im_size, label_wh, lay)  L2734  烤在圖上的「中文翻譯 · 原文」標籤重貼的位置(成片像素、k=1):回傳 (右緣, 下緣, 外框 (x0, y0, x1
split_tag_text(t)  L2765  .layout.json 的 tag_text(例「中文翻譯 · 原文:Press Start 2026/05/29」)
_tag_text(media, img)  L2778  news_lib 在 .layout.json 寫的出處標籤字串;舊圖沒有回傳 None。
decide_labels(shots, lines, media, cli_style='lower', top_style=None)  L2787  截圖鏡頭的出處標籤要用哪一種(2026-10-22):預設 lower = 抹掉烤在圖上的右下角標、改自動加一個 kit
_label_ent(s, media, lay)  L2819  標籤當成一個不可裁的「文字框」(原圖像素座標,格式同 .boxes.json)供 text_clip 驗證;沒有標籤或非
prep_image(s, media, outdir)  L2833  圖片鏡頭素材:依 layout_image 的縮放/平移放圖(其餘以同圖模糊壓暗填滿),烤在圖裡的「中文翻譯」標籤改貼在
_wrap_text(text, font, max_w)  L2895  引言卡/對比卡斷行(2026-10-22):只在詞與詞之間換行(text_wrap.break_groups,jieba
_blur_bg(media, img, dim)  L2922  
make_quote(q, img, media, path, portrait=False)  L2930  引言卡:模糊壓暗的同圖(沒有圖就純深色)+ 深色半透明底板 + 上方說話者身分(q["who"],選填)+ 大字引文 +
make_compare(cmp_, media, path, portrait=False)  L2995  左右並排:各半滿版 cover 裁切(靠上),中間 COMPARE_GAP px 分隔線,上方各一個標籤條;圖上烤的翻譯
_make_compare_p(cmp_, media, path)  L3022  
prep_special(s, media, outdir)  L3045  quote / compare 鏡頭:各自產一張完整畫面 PNG,走 fx=none 的靜態路徑。
_tilt_filter(fx, N)  L3057  3D 透視傾斜(約 8-12 度,隨影格極慢漂移)。fg 為透明畫布,用 perspective 的 destinati
_zoom_filter(s, N, pad_in=False)  L3070  zoom 鏡頭:perspective 把畫布四角送到 fx_map 的位置(次像素內插,不會像 zoompan 逐格取
attach_kits(shots, lines)  L3092  把各句 kit 分到「小件出現時刻」所在的鏡頭:s["kits"] 每項加 t(相對鏡頭起點秒)與 line,s["pu
attach_label_lowers(shots)  L3121  decide_labels 決定改用 lower 的鏡頭:在鏡頭起點(t=0,滑入 0.4 秒、整個鏡頭不淡出)加一個自
_kit_base(s, ox)  L3129  zoom 小件的來源畫面(頁面座標):text 組 = 補邊後的 2x 合成圖、tilt = 透明前景畫布、其餘圖片鏡頭
_kit_obstacles(s, media, entries, ox, follow)  L3138  該鏡頭文字框(.boxes.json 全部行 + 出處標籤)的小件障礙物外框 [x, y, w, h]。
plan_kits(shots, media)  L3160  每個有小件的鏡頭產 1-2 個圖層(跟隨 / 固定),擺放避開障礙物;回傳 (渲染工作清單, 警告)。存入 s["kit
cap_push_for_kits(shots)  L3219  kit 離邊(2026-10-22 計畫 #5):小件圖層框(plan_kits 擺好的 boxes)在 push 推移
check_web_capacity(shots, tlmeta, media, portrait=False)  L3248  動畫容量(2026-10-22 計畫 #5):網頁渲染的動畫鏡頭以模板實際排版量測(anim_web.measure:播
plan_kit_portrait(s, media)  L3281  直式原生動畫鏡頭(s["pwin"]["native"] == "anim")的小件圖層(計畫 #5c):1080x10
prep_kits(shots, media)  L3322  plan_kits 後把圖層交 anim_web 一次渲完。
_punch_filter(times, push=0.0)  L3332  punch:整個鏡頭畫面以中心 1.0 -> PUNCH_SCALE -> 1.0(半個 sin,PUNCH_S 秒),
shot_cmd(s, media, out_mp4, out_pcm)  L3351  
render_shot(s, media)  L3444  
write_wav(path, chunks)  L3474  
build_voice(lines, total_frames, path)  L3483  
voice_eq_filter(spec)  L3502  --voice-eq 的值 -> ffmpeg 濾鏡字串(空字串=不處理)。
rms_db(pcm)  L3513  s16le 雙聲道 PCM 的有聲部分 RMS(dBFS);量不到聲音回傳 None。
track_db(path, seconds=None)  L3524  音檔(前 seconds 秒)的有聲部分 RMS(dBFS)。
track_win_db(path, w=3.0)  L3531  音檔的 w 秒窗(不重疊)RMS(dBFS)分布:(p10, p50, p90, max);略過 < -60 dB 的靜
bed_target(voice_db, bgm_db)  L3546  原聲的目標響度(dBFS RMS):BED_TARGET_DB、配音 - BED_BELOW_VOICE_DB、BGM 
bed_gain(db, target, cap)  L3552  一個鏡頭的原聲增益:把量到的響度 db 壓到 target;不超過 cap(--bed,舊的固定增益),所以小聲的來源不
build_bed(shots, path, target, cap)  L3558  各鏡頭的原聲接成 bed.wav。固定增益會讓大聲的預告(Diablo IV)蓋過 BGM,所以每個影片鏡頭先量響度再各
make_qa(shots, bdir)  L3579  
clauses_abs(ln)  L3615  子句在成片時間軸上的起訖秒與句後停頓(單句的行為 None);--tts-only 與 timeline.json 用。
load_timeline(lines, path)  L3623  --check-only:用既有 timeline.json 補上每句的時間(vstart/vend/dur/f0/f1
_line_span(s)  L3638  
precheck_images(shots, media)  L3643  每個圖片鏡頭算一次版面(存進 s["layout"]);回傳錯誤清單(hl 找不到、重點區過大)。
check_text_clip(shots, media)  L3662  截圖鏡頭的文字不可被畫面邊緣切到:用實際的版面(precheck_images 算好的 s["layout"])與 fx
_is_static(s)  L3681  底圖靜態的鏡頭(截圖、閱讀卡、引言卡、對比):圖片鏡頭且不是動畫鏡頭。
_push_cap(s, media)  L3686  該鏡頭在輕推移放大後,所有畫面內的文字框(含出處標籤)仍離左右邊 >= TEXT_EDGE_X、離上緣 >= TEXT_
plan_push(shots, lines, media, enabled=True)  L3712  鏡頭間 0.2 秒輕推移(2026-10-22 六項 D):只在「靜態 → 靜態」交界(前一個鏡頭與本鏡頭都是 _is_
check_text_pad(shots)  L3742  text 組(drift/zoom)截圖鏡頭動態全程會取樣到畫布外時,prep_image 自動把畫布左右補邊(A 法:
check_image_runs(lines, img_min)  L3756  同一張圖(quote 的底圖、compare 的左右圖也算)連續出現:句數 <= IMG_MAX_UNITS、總長 <=
timing_only_check(lines, secs, tlmeta, args, media)  L3790  --check-only --timing-only:配音後的時長預檢,不需任何素材(圖、片段、clips 都可以不存在
check_cuts(shots)  L3822  影片鏡頭內不可有離頭尾不到 VIDEO_MIN 秒的來源硬切(會變成一閃而過的畫面)。回傳 (錯誤, 有硬切資料的鏡頭數
check_durations(shots, img_min)  L3836  每個鏡頭的時長:低於最短時長、影片片段超過 VIDEO_MAX 都是錯誤;並印出時長分佈。
plan_cards(lines, shots, card_min, total_frames)  L3860  卡片顯示區間:連續句子的卡片內容相同就是同一張(不重複淡入淡出);至少 card_min 秒,不足時延續到後面的鏡頭,
anim_engine(a)  L3922  這個 anim 實際用的渲染器:engine 省略 = web;web 但該類型還沒有網頁模板(或直式)時退回 pill
tl_meta(a, tlmeta)  L3935  這個 timeline anim 用的節點組:anim 自帶 points 就用它(question_between 也
_is_num(v)  L3945  
_parse_web_only(a, i, errs)  L3949  line / table / kpi(只有網頁版)的欄位檢查;通過回傳 a,否則記錯誤回傳 None。step:省略 =
_ref_ok(r)  L4030  
_chart_ext(a, i, errs, t, its)  L4034  bars / cols 共用的新欄位檢查(計畫 #3c):stack 需要 series 且不可有負值、ref = {v
parse_anim(ln, tlmeta, errs)  L4057  檢查一句的 anim 欄位;有錯就記進 errs 並回傳 None。
_list_stepped(a)  L4256  
bars_flat(a)  L4260  bars 的所有條(跨組依序,step 的編號就是這個順序)。有 groups 時由 groups 展開;格式不對回傳 
_level_stepped(a)  L4271  逐步顯示的類型(bars 逐步模式 / versus / flow):各句的 step 對應一個「已顯示到第幾步」(le
anim_level(a)  L4276  這一句結束時的 level:bars = 條數("title" = 0)、versus = step(0 標題 / 1 
level_seconds(a, prev, shown)  L4284  逐步類型一段動畫(prev -> shown)的長度(秒)。
level_plan(parts)  L4294  逐步各句的 (prev, shown, first):shown = 這句結束時的 level,prev = 動畫起點已
anim_finish(items)  L4307  一個動畫鏡頭(連續句合併後)「最後一步完全顯示」的時間(秒,從鏡頭開頭算)。
list_firsts(parts)  L4331  stepped list 的各句:是否為該 step 的第一句(第一句播出現動畫,同 step 的後續句凍結)。
list_plan(parts)  L4336  stepped list 的各句 (prev, shown, first)(網頁渲染用,同 level_plan 的形狀
anim_seconds(a)  L4346  這段動畫本身的長度(秒)。
_check_src(a, s, tlmeta=None)  L4364  動畫版面檢查:bars 的 src 出處小字與各文字墨跡框重疊、排不下(有 src 時最後一條下緣上限 AL.BARS_
check_anim(lines, shots, secs, tlmeta)  L4389  動畫與轉場的檢查,回傳錯誤清單:emo 欄位已停用;anim 規格;動畫鏡頭(連續句合併後)的最後一步完全顯示後至少停留
_over(bg, fr, x=0, y=0)  L4438  straight-alpha RGBA(ndarray)疊到 RGB 底圖的 (x, y),回傳新的 RGB ndarr
_anim_frames(s, tlmeta, media)  L4448  動畫鏡頭逐格(HxWx3 uint8),剛好 s["frames"] 格:動畫播完後停在最後一格(emoji / 問號是
tl_web_spec(a, tlmeta, step=None)  L4459  timeline 的網頁資料來源:自帶 points -> 只用 anim 自己的 points / question_
_web_layers(s, media, bgm, tlmeta=None)  L4468  網頁渲染(anim_web)的逐格:逐步模式每句一段(prev -> shown;同 step 的後續句只取終態一格),
_anim_layers(s, tlmeta, media, bgm)  L4504  逐格 ndarray:bgm == "dark" 時為 HxWx3(含深色底);"alpha" 時為 HxWx4 str
build_anim_shot(s, tlmeta, media)  L4607  動畫鏡頭 -> 不透明 mp4(快取在 ANIM_CACHE),格數 = 鏡頭格數。
_cached_asset(stem, frames_fn, alpha=True)  L4633  素材快取:ANIM_CACHE/<stem>_v<LIB_VERSION>.mov|mp4,旁邊的 .n 記錄格數。回傳
plan_trans(lines, secs)  L4647  段落轉場清單(作用在「進入這一段」的交界);段落沒寫 trans 就是 none。回傳 (items, warnings
materialize_trans(items)  L4668  
trans_filters(items, first_in, in_label)  L4677  把轉場接在 [in_label] 之後:先 glitch(真的位移畫面),再疊 wipe/title。
parse_len(spec)  L4724  
make_hook(text, path)  L4729  標題帶鉤子字 PNG(1080x1920 透明):白字、黑描邊 4px、右下陰影 5px(62% 黑),墨跡中心 (51
_img_text_span(s, media)  L4746  圖片鏡頭的文字框聯集(含「中文翻譯·原文」標籤)在橫式成片的 x 範圍;fx 動態全程取聯集,只算落在畫面內的框。
_card_span(png)  L4772  
_p_native_png(s, ln, media)  L4777  直式原生畫面(引言卡 / 對比 / 窄版截圖)-> (畫面檔, 最小字級, 說明);引言、對比是 png,窄版截圖是 m
_img_p_geom(img, groups, media)  L4791  窄版截圖在直式畫面窗(1080x1080)的幾何。文字欄(全部行框的 x 聯集)縮放到 P_TXT_X0-P_TXT_X
_img_p_cut(g)  L4823  窄版截圖幾何中被窗上緣或下切點切到半行的行(文字)清單;渲染前檢查用。
_img_p_zone(g)  L4831  窄版截圖進入 Shorts 右側按鈕區的文字框清單(畫布座標;窗內可見的行框與標籤);渲染前檢查用。
_img_p_base(g)  L4845  窄版截圖直式窗底圖(RGBA 1080x1080):縮放後的截圖、下切點以下蓋底色、標籤貼在窗右下(右緣 P_TXT_X
_img_p_label_box(g)  L4857  標籤在窗內的外框 (x0, y0, x1, y1);沒有標籤 None。
_img_p_label_errs(g, base)  L4865  標籤檢查(渲染前):有標籤必須畫出來(框內要有白字墨跡)、右緣 <= P_BTN_X、在窗內且 y 不進字幕帶(畫布 y
_ul_sprite(w, th, e)  L4889  紅色底線貼圖(圓頭、深色外緣;樣式同 prep_hl)。
make_img_p(s, media, path)  L4900  窄版截圖 -> 直式畫面窗 1080x1080 的 mp4(長度 = 鏡頭格數):幾何見 _img_p_geom;翻譯標
_card_p(png)  L4964  卡片(1920x1080 透明 PNG)-> 直式原生窗 1080x1080:墨跡範圍左右各加 P_MARGIN 放得進
portrait_window(s, ln, media)  L4983  鏡頭的直式取景(spec §3):回傳 dict(x0, cw, wh, wy, why[, native, fs])。
check_portrait(lines, shots, total, len_rng, hook, media=None)  L5021  直式額外檢查(spec §5):回傳 (錯誤, 警告)。窄版截圖另查上緣是否切到半行字。
portrait_cmd(s, win, hook_png, out)  L5054  橫式成品鏡頭 -> 直式鏡頭:cover 底圖在 1/4 解析度 boxblur 後放大、亮度 x0.45;畫面窗靜態取
render_portrait_shot(s, hook_png, tlmeta=None, media=None)  L5097  呼叫前須 AL.set_profile("portrait")(原生動畫用直式常數組;main 在平行渲染前後切換)。
main()  L5116  

## pipeline/channel_sheet.py
_font(name)  L18  repo fonts\ 有就用(副本專案隨附字型),否則用使用者安裝的字型。
font_css()  L35  
main(names)  L45  

## pipeline/clip_scan.py
scene_cuts(src, thr=SCENE_THR)  L25  raw\<src>.mp4 整支的硬切時間(秒 = 新鏡頭第一格的時間)。縮到 320 寬跑 ffmpeg 的 scen
scan(src, min_run=3)  L46  

## pipeline/clips_lib.py
class Spec  L29  clips.json 載入後的設定;欄位見 README。
Spec.__init__(self, tag, path=None, out=None)  L32  
Spec.p(self, k)  L53  
norm_seg(s)  L57  片段可寫物件 {start,end,tags,note,+覆寫欄位} 或陣列 [起,止,[標籤],備註,{覆寫}];回傳
minus_ranges(a, b, excl)  L65  [a,b] 扣掉 excl 區間後剩下的片段(長度 < 1 秒者略)
raw(src)  L79  
probe_dur(src)  L83  
detect_crop(src, a, b)  L89  在片段內取 3 個時間點 cropdetect,只接受純黑邊(pillarbox 或 letterbox)且 >=3%;
luma(sp, src, a, b, crop=None)  L111  a~b 秒每 1/fps 秒一個平均亮度(crop 內)
refine(sp, src, a, b, crop)  L119  切掉黑場:在 a~b 內找出連續「不黑」區段(容許 1 格的黑閃),兩端各內縮 0.25 秒,留 >=2.5 秒者。
build(sp)  L145  
tag_lines(sp)  L185  
union_len(spans)  L196  
check(sp)  L211  
grab(src, t, crop=None, w=320)  L260  來源在 t 秒的一格(PIL Image,去黑邊後縮成寬 w);失敗回 None
contact_sheet(items, out, cols=6, w=320)  L269  items = [(src, t, crop, label, safe_dict)];每格畫標籤,有 top/botto
sheet(sp, argv)  L294  
_safe_of(c)  L302  
preview(sp, outdir, nf=1)  L306  每標籤一張:每個片段取中間一格(nf>1 取等分 nf 格,選片時查鏡頭內容);用片段檔的最終起訖(含自動修過的黑場與 
overview(sp, outdir)  L321  每支來源一張總覽(每個片段取中間一格,寬 240,標出起訖秒):<outdir>/clips_<src>.jpg
main(argv=None)  L332  

## pipeline/clips_screen.py
cache_file(src)  L28  
scan_src(src)  L32  
load_spec(tag)  L66  
srcs_of(spec)  L71  
merge(bad_ts, pad=0.5)  L76  不合格時間點(每格代表 1/FPS 秒)併成區間,前後各留 pad
main()  L88  

## pipeline/context_pack.py
_now()  L44  
_read_json(p)  L48  
_c(v, n=300)  L55  欄位值轉一行字串(dict/list 用緊湊 JSON),超過 n 字截斷。
_int(v)  L62  
_dt(s)  L69  
project_dir(tag)  L77  專案目錄:素材根的 projects\<tag>;那裡沒有而 repo 內有就用 repo 的(同 paths.proj
outcomes_file()  L83  
load_subject(pdir)  L87  spec.json(沒有則 spec_pkg.json)的 package.subject 與 topic_class;
_run_cli(cmd, timeout, cwd)  L100  
_parse_brief(stdout)  L105  
fetch_brief(event, slot, query, timeout)  L118  跑 intel_query.py brief … --json;回 (doc, None) 或 (None, 原因)。
brief_video_ids(doc)  L145  brief 裡出現的影片 id(可比片、最近自製片、競品片若有 video_id)。
_norm(text)  L155  
_comment(c, vid, ts=None)  L159  
lang_of(text)  L165  語言判定:漢字佔字母類字元 ≥ CJK_RATIO → zh;拉丁字母 ≥ 50% → en;其餘(含無字母)→ oth
_upload_date(d)  L177  
_source_row(d, vid, comments, origin)  L182  
collect_comments(pdir, extra_ids=())  L190  讀 comments_ref/*.info.json(yt-dlp)與 ytad_comments_dir()/*.js
dedupe(comments)  L227  先以 id、再以正規化文字合併(讚數取大、來源影片取聯集);去掉正規化後為空的(純表情)。
tokens(text)  L251  分群用詞集合:jieba 可用時取詞;否則中日韓連續字取字 bigram(單字取本身),英數取整個詞
token_method()  L265  
_jaccard(a, b)  L269  
_clip(text, n=REP_CHARS)  L273  
cluster(top)  L277  單鏈結(Jaccard ≥ JACCARD);回 (依合計讚數排序的前 MAX_GROUPS 群, 總群數)。
load_lexicon()  L304  
flag_text(text, lex)  L309  
sample_per_video(comments, k=PER_VIDEO)  L314  每支影片各自去重後取讚數前 k 則,再跨片合併去重。
_lang_part(full, sampled, cred, list_all_below=None)  L322  單一語言:全部則數與旗標計數、取樣後分群(或少量時全列)。
analyze_comments(raw)  L340  全部去重標旗標(計數用);每片取前 PER_VIDEO 則合併後依語言分 zh/en 各自分群;旗標範例只取中文。
load_outcomes(path)  L368  
match_outcomes(rows, tag, subject, topic_class, keywords)  L382  同 subject、同 topic_class 或標題/subject 含關鍵字的舊片(排除本片)。
_outcome_line(r)  L407  
_head(src, as_of, n)  L424  
_brief_missing(ctx)  L428  
sec_summary(ctx)  L432  
sec_event(ctx)  L453  
sec_demand(ctx)  L477  
sec_saturation(ctx)  L496  
_flag_str(flags)  L510  
_flag_counts(by_flag)  L516  
_lang_lines(part, label)  L520  
sec_comments(ctx)  L536  
sec_history(ctx)  L557  
sec_audience(ctx)  L592  
sec_gaps(ctx)  L604  
brief_fields(ctx)  L612  §8 四欄(給 brief 直接貼);沒有 brief 回 None。
sec_brief(ctx)  L628  
render(ctx)  L647  
_sum_int(*vals)  L659  
build(tag, channel, event=None, query=None, use_ytad=True, timeout=120)  L664  
main(argv=None)  L714  

## pipeline/cosy3_worker.py
reply(tag, obj)  L45  
tail_f0(path, win=0.3)  L50  句尾 F0 斜率:librosa.pyin -> 最後一個有聲音框往前 win 秒內的有聲音框 -> 半音(12*log

## pipeline/decide_list.py
_add(d, key, idx, text, **extra)  L30  
en_undecided(texts)  L36  ① 英文詞:{詞: {lines, sample, say}};say = cosy_terms 登錄的寫法(_dire
pron_undecided(texts)  L45  ② 讀音標注:{鍵: {lines, sample, src}};src = cosy_pron | pron_rule
polyphone(tag)  L61  ③ 跑 tts_polyphone.py:回傳 (前 TOP_N 筆 list, 一行說明);失敗回 ([], "未跑:
_ln(lines)  L79  
render(tag, ver, en, pron, poly, poly_note)  L83  
count_undecided(tag, ver)  L98  讀 output\<tag>\decide_<ver>.md 的摘要行(render 寫的「英文唸法 N 筆|讀音標注 
run(tag, ver, texts=None, with_polyphone=True)  L109  產生 decide_<ver>.md;回傳一行摘要「要你決定的唸法 N 筆(英文 a|讀音 b|疑似誤讀 c)→ 路徑」

## pipeline/deliver.py
mb(p)  L38  
sha1(p)  L42  
video_size(p)  L50  
_section_block(md, heading)  L57  取 `## heading` 之後第一個 ```text 區塊內容;沒有回傳 None。
parse_notes(md)  L67  回傳 (deepseek_text, desc_extra);發片資料缺或不完整 deepseek_text 為 Non
enqueue_missing(deepseek_text, desc_extra)  L78  --enqueue 前檢查說明檔,回傳缺漏說明清單(空 = 齊全):署名為空、發片資料缺/不完整、發片資料仍含(待填)。
_ver_no(ver)  L90  
prev_sidecar(tag, ver, inbox=None)  L95  同 tag 上一版(版號 < ver 的最大者)的 sidecar dict;沒有回 None。inbox 預設 pat
revision_issues(tag, ver, title, cover_arg, inbox=None)  L113  T41:改版(ver 非 v1)且同 tag 已有上一版 sidecar:沿用封面與標題(4_交付發片 §1)。回警告清
schedule_conflict(tag, publish_at)  L130  T44:handoff.md 寫了「使用者自己排時間」卻帶了 --publish-at -> 回錯誤訊息;否則 None
sidecar_path(video)  L143  
png_size(p)  L147  讀 PNG 檔頭回傳 (w, h);不是 PNG 回傳 None。
resolve_cover(arg, tag)  L156  回傳封面來源 Path 或 None;--cover 指定的不存在或規格不符直接中止,自動找到的規格不符也中止。
cover_name(title, ver)  L174  
copy_cover(cov, dst_dir, name)  L178  封面複製到 dst_dir/name(.part 再 replace);回傳檔名。
resolve_channel(arg)  L196  回傳 (頻道全名, token_slot);頻道不認得或 channels.json 讀不到/沒有該頻道就中止。
write_sidecar(dst, tag, ver, title, deepseek_text, desc_extra, cover=None, channel=None, to...)  L213  
gate_d_items(tag, ver, channel=None)  L231  --enqueue 前的 gate_d 硬擋:呼叫 gates.gate_d.run(tag, ver)(回 [item
gate_d_check(tag, ver, skip=False, channel=None)  L245  印各項;回傳是否可交付。skip(--skip-gate-d 緊急繞過)只印警告,一律放行。
main()  L256  
deliver(a)  L303  交付;回傳目的 mp4 Path(dry-run 回傳 None);失敗直接 sys.exit。

## pipeline/director.py
now_iso()  L39  
prod_path(tag)  L43  
_read_json(p)  L47  
_atomic_write(path, data)  L54  
board_rec(tag)  L62  
guess_channel(tag, given=None)  L70  
_rel(p)  L85  
_item(iid, ok, note='', path=None)  L95  
_glob(d, pat)  L99  
_first(paths)  L106  
count_pending_facts(p)  L110  facts 表格內狀態欄是「待查」的列數(圖例行不是表格列,不計)。
_ver_no(p)  L119  
mp4_list(tag)  L124  
_count(v)  L128  
find_video_id(tag, prod)  L132  
check_0(tag, ctx)  L146  
check_a(tag, ctx)  L155  
check_b(tag, ctx)  L160  
check_b4(tag, ctx)  L165  
check_c(tag, ctx)  L170  
check_d(tag, ctx)  L175  
check_e(tag, ctx)  L180  
seg_state(items)  L188  
infer_stage(states, board_stage)  L193  
collect(tag, channel=None)  L206  推斷結果 dict:tag/channel/stage/board_stage/gates/artifacts/vers
_blank(tag, channel)  L239  
load_prod(tag)  L244  
init(tag, channel=None)  L248  不存在才建;回傳 (資料, 是否新建)。
write_back(tag, res)  L258  
_append(tag, key, rec)  L276  
log_call(tag, fn, model, tin, tout, cache=0, cost=None, secs=None, ok=None, seg=None, ...)  L284  secs/ok/seg/agent 由 llm.py 帶,沒給就不寫(舊呼叫相容)。
intervene(tag, what)  L293  
feedback(tag, text, case=None)  L297  
_gate_mod(seg)  L308  
_py()  L313  
_sys()  L317  
_script(*parts)  L321  
_newer(a, b)  L325  a 存在且比 b 新(b 不存在也算)。
run_ctx(tag, a)  L331  
_refresh(tag, ctx)  L337  
_voice_frozen(tag)  L344  配音凍結步的跳過條件:freeze.json 存在且 tts_review.json 品管未過 0。
plan_steps(tag, seg, ctx, a)  L350  本段步驟:[{step, cmd, skip, block, status_only}];skip/block 是原因字
_block(tag, seg, step, reason, rc=None, log=None, count=True)  L397  
_warn(tag, seg, step, note)  L408  
_tail(text, n=3, cap=300)  L413  
eval_gate(tag, seg, ctx)  L418  評本段 gate、寫回 gates[seg];不過則記卡點。回傳 (passed, items)。
_exec(tag, ver, seg, step, cmd)  L434  跑一步:輸出追加到 output\<tag>\director_<ver>.log,runs 記 rc 與秒數。回傳 (
_precheck(tag, seg, ctx)  L458  前置 gate:A 無;C 看 B4 完成(寬鬆,舊片沒有新 gate 的產物);B/B4/D/E 看上一段 gate。
_skip(st)  L471  步驟略過原因;A/B 段依前一步產物,callable 在執行前才評。
print_plan(tag, segs, ctx, a)  L476  
_run_fn(tag, seg, st)  L487  跑 fn 步(LLM / 改句);回傳卡點原因或 None。
run(tag, a)  L501  回傳結束碼:0 全過、3 卡點、2 參數錯。
explain(seg)  L575  
write_brief(a)  L581  
render_table(res)  L596  
main(argv=None)  L607  

## pipeline/director_ab.py
class Block  L58  步驟卡點;reason 進 production.json.blocks。
Block.__init__(self, reason)  L61  
_llm(tag, fn, prompt, **kw)  L66  
_need(r, what)  L73  
_pd(tag)  L81  
_script(tag)  L85  
_brief(tag)  L89  
_plan(tag)  L93  
_write_json(path, data)  L97  
_newer_all(a, *inputs)  L101  a 存在且比每個存在的 input 新;回傳略過原因或 None。
write_brief(tag, fields)  L109  合併寫 projects\<tag>\brief.json;回傳完整內容。
_fix(tag, items, mode)  L120  line_fix.fix_lines;回傳其結果。模組未就緒或用量上限 → Block。
merge_warn_log(tag, recs)  L133  recs = {key: {action, reason}};補 at 後併進 warn_log.json。
_record_fix(tag, warns, res)  L143  把 line_fix 結果對到警告鍵:改到的句 = fixed,未解決 = kept(why 當理由);回報的 warn
_frozen(tag)  L159  
script_rows(tag)  L166  旁白句號 -> script.txt 行號(1 起算),與 script_txt2json 同源。
apply_lines(tag, items)  L177  套用 [{line:句號, new_line}]:換掉該行「標籤|」之後、「 ;; 」之前的字;回傳改到的句號。
revise(tag, issues, warns=(), seg='B', what='審稿條目')  L199  改內容(Opus medium,script-writer);line_fix 不得改意思,這裡可以。回傳改到的句號。
_context_cmd(tag, brief)  L220  
comment_urls(tag)  L229  brief.urls,否則 context.json 的 comment_sources 裡帶 url/video_id
step_comments(tag, ctx, a)  L242  
_validate_plan(r)  L255  
step_consensus(tag, ctx, a)  L265  
step_research(tag, ctx, a)  L276  
_validate_facts(tag)  L285  
step_facts(tag, ctx, a)  L295  
step_replan(tag, ctx, a)  L303  consensus 的論點在查證前寫的;facts 出來後依查到的東西重排 claims/blocks,不足片長照實寫(
_asset_call(tag, kind)  L318  
step_assets(tag, ctx, a)  L329  
_taste_b()  L340  channel\taste\README.md 裡段別 B 的案例列(摘要,≤20 行)。
_channel_file(tag)  L348  
step_write(tag, ctx, a)  L353  
_speak_errs(report)  L369  speakable.check_tag 的硬項 -> line_fix items。
step_speak(tag, ctx=None, a=None)  L379  speakable 硬項 → line_fix(mode=speak);≤3 輪,仍有 = 卡點。
_txt2json(tag)  L394  參數與 make_version 同:輸入 <tag>/script.txt、前綴讀說明行(沒寫就走預設,visual_
lint_round(tag)  L401  跑四個檢查(txt2json → structure → visual --table → lint);回 {sent,
_reasons(hits)  L424  
step_lint(tag, ctx=None, a=None)  L431  句級 → line_fix;結構級 → revise;≤3 輪。警告進 warn_log。
_recheck(tag)  L449  revise 後再過一次可唸性與 lint(沒命中就不花 LLM)。
_review_round(tag, kind)  L455  本輪輪次:最新報告比 script.txt 舊就開下一輪,否則 None(報告仍有效)。
_review(tag, kind, n, extra='')  L463  
step_editor(tag, ctx=None, a=None)  L477  一輪:連貫斷點 >0 → revise,報告記 revised(gate 不再算);不重審。
step_player(tag, ctx=None, a=None)  L488  ≤2 輪:r1 必處理條目 → revise → r2;r2 仍有 → ask_user.json,卡點 要問使用者(不
_only_added(old, new)  L513  new 是否只比 old 多東西(舊條目全在、值不變)。
_pron_path(name)  L522  
_validate_apply(tag, snap, pending)  L526  讀音檔還能解析、只新增;backlog 前 3 條都有紀錄。不符就還原並回失敗原因。
_pron_review(tag, n)  L547  
_pron_apply(tag, items, pending)  L559  
_tts_script_cmd(tag)  L574  
_sub_scan_cmd(tag)  L578  
step_b4_prep(tag, a)  L582  txt2json → tts_script → sub_scan(接縫 >0 結束碼 1,交給 pron 迴圈)。
step_pron(tag, ctx, a)  L595  tts_script/sub_scan → pron-review → pron-apply → 重跑到未決 0、接縫 
qc_issues(tag, ver, seen)  L612  回 (品管/時長 items, E4 items, 對不到句的時長錯誤);line = script.txt 行號(li
step_qc(tag, ctx, a)  L641  make_version --tts-review(不凍結)→ 品管/時長/E4 有句 → line_fix(qc)→ 
_git(*args)  L665  
commit_seg(tag, seg)  L669  段過 gate commit:只 add 明確路徑(comments_ref 不進 git);index.lock 重試
steps(tag, seg, ctx, a)  L694  本段步驟 [{step, cmd, skip, block, status_only, fn, desc}];skip 

## pipeline/facts_check.py
_f_ids(raw)  L35  行尾 f 欄位 -> (canon id 清單, 錯誤訊息或 None)。
_fact_blob(f)  L46  
_note_ok(ln)  L50  
analyze(lines, facts, names=())  L60  回傳 dict:sentences(逐句結果)與統計。lines 為 spec_check.load_lines 的句子
spec_facts(res, project_root=None)  L142  analyze 結果 -> spec.json 的 facts[]。
write_spec(tag, facts_list)  L162  
summary_line(res)  L175  
report(tag, res, fact_files)  L181  
main(argv=None)  L207  

## pipeline/facts_lib.py
class Fact  L53  
norm_status(raw)  L66  
canon_id(fid)  L74  F12 / f12 / 12 -> 'F12'(比對用)。
find_files(project_dir)  L80  projects\<tag>\facts*.md;facts.md 排最前,其餘依檔名。
_split_row(line)  L87  
_map_header(cells)  L96  回傳 {欄位名: 欄索引};不是 fact 表(缺 # 或 主張)回 None。
_fix_cells(cells, ncols, cols)  L109  欄數比表頭多(內文有未跳脫的 |)時,把多出的格子併回去:優先併進讓「狀態欄」仍像狀態的那一段。
parse_text(text, file='')  L126  
parse(paths)  L155  paths:檔案路徑或其清單(也接受目錄 -> 該目錄的 facts*.md)。回傳 Fact 清單(檔案順序、列順序)
_fmt(d)  L187  
cn_to_int(s)  L193  中文數字字串 -> int;無法解析回 None。支援 二十三、兩百一十二、一萬兩千、二零一九。
_hm(h, m)  L238  
_md(mo, d)  L242  
_dian_cn(m, text)  L246  「X點[Y分]」→ (HH:MM, 結束位置);小數點(三點五)與「一點點」回 None。
_dates_times(text)  L276  抽出日期/時間 → [(鍵, (起, 訖))];互不重疊,先抽日期再抽時間。
_arabic(text)  L314  回傳 [(正規化字串, 是否百分比, 起訖)]。
_chinese(text, strict)  L331  strict=True(句子端):只收接單位或以萬/億結尾的中文數字。回傳 (集合, 百分之N 集合)。
numbers_in(text, strict=False)  L358  文字中的數字(正規化字串集合)。strict=True 用於旁白句(中文數字只收有單位者)。
sentence_numbers(text)  L373  
fact_numbers(fact, with_source=True)  L380  事實表一列可對得上的數字集合:claim+quote+magnitude(+source 去網址)。百分比同時收裸數字。

## pipeline/feedback.py
outcomes_path()  L42  
scorecard_path()  L46  
export_path(override=None)  L50  
_read_json(path)  L60  
_dig(d, *keys, depth=3)  L67  在 d(dict)裡找第一個出現的 keys 之一(先本層,再往下找 depth 層的 dict);找不到回 None。
_num(x)  L83  
_fnum(x, nd=2)  L87  
duration_bucket(sec)  L93  
retention_at(curve, pos)  L102  留存曲線 [[位置%, 留存%], ...] 在 pos(%)處線性內插;pos 超出曲線範圍回 None。
_parse_utc(s)  L113  
_facts_link_pct(tag)  L117  
spec_features(tag)  L126  
build_features(v, tag)  L136  
cover_log_path()  L167  
_persona_entry(tag, plan)  L171  cover_persona_log.jsonl 中該 tag + plan 的最後一筆(沒有回 {})。
_at(lst, i)  L187  
_ab_version(ver, mode, tag, spec)  L191  單一版本:保留匯出欄位,補 title_angle、thumb_plan 與封面特徵(spec / persona lo
build_ab(v, tag)  L214  匯出每片的 ab -> outcomes 欄位;缺 ab 鍵(或不是 dict)一律 null。status 照錄(含 
ab_cell(row)  L228  scorecard 的 A/B 欄。
_perf_block(src, extra_basis=None)  L243  
build_perf(v)  L250  
has_data(blk)  L267  
primary_window(perf)  L271  
build_row(v, tag, now=None)  L275  
read_outcomes(path=None)  L295  
write_outcomes(rows, path=None)  L310  
merge_row(old, new, angle=None, plan=None)  L318  新算的 row 覆蓋舊的;手動欄位(angle、thumb_plan)新值沒給就沿用舊值。
_esc(s)  L331  
_fmt(v)  L335  
_cell(row, w, key)  L341  
sc_line(row)  L354  
_legacy_rows(path, known_ids)  L362  既有 scorecard 裡 video_id 不在 outcomes 的列(依所屬表頭分組),原樣保留。
write_scorecard(rows)  L377  
load_export(path)  L393  
collect_rows(videos, min_age_h=72, only_vid=None)  L400  回傳 (rows, skipped[(video_id/tag, 原因)])。
apply_rows(new_rows, angle=None, plan=None, dry_run=False)  L423  
write_spec_result(tag, row)  L434  
_summary(r)  L445  
main(argv)  L452  

## pipeline/feedback_report.py
_pv(r, key)  L48  
_subs_k(r)  L55  
quantile(vals, q)  L61  
median(vals)  L71  
iqr(vals)  L75  
_ranks(vals)  L79  
spearman(xs, ys)  L93  Spearman 等級相關(平均秩 + Pearson);其中一邊全部相同(無變異)回 None。
_band(v, edges, labels)  L105  
_seq(r)  L114  
_comp(r)  L119  
_hour(r)  L124  
_judge(r)  L129  
_txt(key)  L134  
_f(v, nd=1)  L152  
_med_cell(vals)  L158  
strata(rows)  L164  
factor_table(rows, name, fn)  L171  
lessons(rows, label)  L190  回傳 (教訓句 list, 候選假設句 list)。
spearman_table(rows)  L215  
_tlen(t)  L235  
_len_band(v)  L239  
_yn(v, yes, no)  L243  
_vtxt(key)  L247  
_is_win(r, v)  L266  
ab_factor_table(entries, name, fn)  L270  entries = [(row, version)];每格 參賽 n、勝 n、勝率;n<8 只印資料不足。
ab_section(rows)  L284  回傳 A/B 教訓節(list of lines);沒有任何 A/B 資料印「尚無 A/B 資料」。
_has_other_punct(t)  L323  含「？」以外的標點(含【】;半形 ? 視同 ？)。
load_channel_export(path=None)  L337  讀 channel_latest.json(同 spec_check:paths.ytad_channel_export
_ch_tests(ch)  L345  該頻道完成的標題測試 -> [(video, ab)];缺 ab / ab 為 null / versions 非 li
_ab_win(ab, ver)  L356  
_share(ver)  L360  
_ch_stat_line(tests)  L365  
channel_ab_section(data)  L370  全頻道標題測試節(list of lines);data = channel_latest.json 解析結果或 Non
build_report(all_rows, channel_data=None)  L421  
main(argv)  L454  

## pipeline/freeze.py
script_path(tag)  L28  
freeze_path(tag)  L32  
review_path(tag)  L36  
sha256(path)  L40  
narration_lines(tag)  L44  script.txt -> 每句送配音的文字清單(依句序)。與 script_txt2json.main + build
narration_sha(tag)  L62  配音文本 hash:每句送配音的文字依句序以
text_same(tag, rec, old_key='sha256')  L67  配音文本是否與紀錄(freeze.json / tts_review.json)相符的唯一判斷:rec 有 narrat
tts_keys_sha(tag, engine=None)  L78  tts_dir(tag, engine) 內全部 *.key 的內容排序後 sha256(沒有任何 key 檔 = 空字
class FreezeRefused  L85  凍結門檻未過;args[0] = 原因清單。
load_review(tag)  L89  
review_problems(tag)  L96  凍結門檻:回傳未過原因清單(空 = 可凍結)。
load(tag)  L121  
check(tag)  L126  已凍結且配音文本不符 -> 回傳中止訊息;未凍結或相符 -> None。
sp_same(tag, fz)  L142  
alias_table(path=TERMS_FILE)  L150  cosy_terms.json 的 _asr_alias -> {詞: [別名]};讀不了回 {}。
alias_base(tag)  L159  別名基準:上次凍結存的快照(freeze.json["asr_alias"]);沒有就取 git HEAD 版 cosy
alias_added(cur, base)  L171  目前的 _asr_alias 相對基準新增的 {詞: [新別名]}。
alias_problems(tag, cur=None, base=None, text=None)  L176  T27:新增別名且該詞出現在本片旁白 -> 原因清單(空 = 放行)。cur/base/text 可注入(測試用)。
freeze(tag, reason, force=False, alias_ok=None)  L194  凍結。門檻未過且非 force -> raise FreezeRefused(原因清單);force 時 reason 
main()  L225  

## pipeline/gd_crowd_scan.py
analyse(path)  L29  
persons(files)  L45  torchvision Faster R-CNN MobileNetV3(COCO,CPU)數人:score>=0.5 
extract(src, fps)  L66  
ocr_text(work, files)  L75  對 files 逐格做 OCR(縮成 960 寬放 work/ocr_in),回傳 {檔名: 英文字母數}
scan(src, fps, per_src, min_count)  L86  

## pipeline/gpu_lock.py
_load_shared(path)  L26  載入共用模組(以 yt_gpu_lock 為名,避免與本檔 gpu_lock 撞名;同行程只載一次)。
_publish_of(tag)  L58  
_report(info)  L66  
gpu_lock(tag, job, timeout=None)  L74  
main()  L78  

## pipeline/gpu_lock_local.py
lock_dir()  L26  
poll_s()  L30  
_nosmi()  L37  
max_used_mib()  L41  硬門檻(MiB);NOSMI=1 或 <=0 回 None = 關閉。
_smi(field)  L53  
gpu_used_mib()  L63  
pid_alive(pid, start=None)  L67  
_read(p)  L94  
holder()  L101  
queue()  L105  
describe(entry)  L109  
clean_stale(warn=True)  L115  持有者 pid 已不存在就清掉;回傳被清掉的持有者(或 None)。
class GpuLock  L137  with GpuLock(project, tag, job, ...):;acquire()/release() 亦可
GpuLock.__init__(self, project, tag, job, *, due=NO_DATE, timeout=None, cancelled=None, on_wai...)  L140  
GpuLock._entry(self)  L148  
GpuLock.acquire(self)  L152  
GpuLock._try_take(self, hp)  L187  
GpuLock.release(self)  L199  
GpuLock.__enter__(self)  L212  
GpuLock.__exit__(self, *exc)  L215  
gpu_lock(project, tag, job, **kw)  L219  
status_dict()  L223  
status_text(s=None)  L231  
release_tag(tag)  L251  
main(argv=None)  L263  

## pipeline/kit.py
item_errors(it)  L45  單一小件的欄位錯誤(中文)。
line_errors(items)  L66  同一句:每項欄位、同句 <= LINE_MAX 個、punch <= PUNCH_PER_LINE。
shot_errors(items, tilt)  L79  同一鏡頭(可跨句):<= SHOT_MAX 個、spotlight 不可用在 tilt 鏡頭(photo 組)。
find_text_rect(entries, kw)  L90  在 .boxes.json 文字區塊找 kw(同 hl:忽略空白大小寫、可跨行),取第一個命中;回傳原圖像素外框 (x0
to_canvas(box, sc, pos, ox=0.0)  L108  原圖像素框 -> 畫布(1x)[x, y, w, h];ox = 頁面左側補邊(text 組 zoom 類的 _zoom
pct_rect(box, size, ox=0.0)  L114  at.box(畫面百分比 [x, y, w, h])-> 像素 [x, y, w, h]。
map_rect(rect, f, ox=0.0)  L120  畫布矩形經 fx 映射函式 f(畫布 -> 成片,build.fx_map 回傳值)後的外接框 [x, y, w, h]
item_start(it)  L128  
gap(a, b)  L133  兩個 [x, y, w, h] 外框的最短距離(重疊或相貼 = 0)。
overlap_area(a, b)  L140  
nearest_gap(r, obs)  L144  r 離最近障礙物的距離(沒有障礙物 = 9999)。
pt_gap(p, r)  L149  點到 [x, y, w, h] 的距離。
subtract(r, hole)  L154  r 扣掉 hole 後剩下的矩形(最多 4 塊);不相交回傳 [r]。
_free_spots(w, h, dom, obs, margin, step=16)  L167  w x h 的框放在 dom=(x0,y0,x1,y1) 內、離每個障礙物 >= margin 的所有左上角(依序列掃描
_nearest_spot(w, h, dom, obs, margin, center, step=16)  L180  
_cost_spot(w, h, dom, obs, margin, center, step=16)  L189  沒有完全空白的位置時:重疊(含邊距)面積最小者,同分取離 center 近的。
text_width(txt, px, bold=True)  L208  Pillow 量字寬(與 kit.html 同字型);粗估即可,擺放另留邊距。
pop_size(it, scale=1.0)  L217  pop 外框(含 8px 描邊)寬高;字級 = (it.size 或 120) * scale。回傳 (字級, 寬, 高
badge_size(it)  L223  
lower_size(it, ls=1.0)  L230  
place_pop(it, rect, obs, dom)  L240  pop 放在離目標最近、不碰任何障礙物(邊距 MARGIN)的空白處;字級最多縮 3 級。回傳 (框, 字級, ok)。
place_badge(it, rect, obs, dom)  L254  badge 放目標外側:右 > 上 > 左 > 下,離障礙物 >= BADGE_MARGIN;四側都沒有就找全畫面最近的
place_lower(it, anchor, obs, dom)  L276  lower 固定在左下字幕安全線上方;與文字框重疊先往上找空白帶,再縮小一級,仍重疊才 ok=False。回傳 (框, 
arrow_geom(rect, u, dist, gap_tip=TIP_GAP, head=30)  L292  從目標中心往 u 方向:尖端停在目標框外 gap_tip,箭尾離目標框 >= dist。回傳 (tip, tail, 單
arrow_cost(tip, tail, u, obs, dom, head=30, hw=15)  L305  箭身(尖端到箭尾的線段 + 三角箭頭)侵入障礙物 / 超出範圍的程度;0 = 完全避開。回傳 (cost, 最近距離)。
place_arrow(rect, obs, dom, frames=())  L325  arrow:在目標周圍找「箭尾離目標 120-260px、整條箭身不穿過任何障礙物」的位置(右上 > 左上 > 右下 >
_fixed_box(it, vis)  L349  callout / tick / cross / zoom / progress 本來就框目標或固定位置,不移動;回傳它
layout(items, vis, obstacles, rects=None, portrait=False)  L377  自由擺放小件:依障礙物算出每件的最終位置。
_sig()  L449  
job(items, size, vis, base=None, probe=None, fps=30, obstacles=None, portrait=False)  L456  一個圖層的渲染工作(格式同 anim_web.segment,另帶 tpl / probe)。items 的 t 已是相

## pipeline/line_fix.py
script_path(tag)  L52  
_is_spoken(raw)  L56  
_split_raw(raw)  L61  一行(不含換行)-> (前綴含標籤與 |, 文字前空白, 字幕文字, 文字後空白, 行尾 ' ;; {json}' 原樣
load_script(tag)  L84  -> (全部元素 list[str](以 \n 切,保留行尾 \r), 旁白列 list[dict(no, text, 
write_atomic(path, text)  L103  
numbers(t)  L111  一句裡的數字集合:阿拉伯數字(去逗號)與 script_lint.num_groups 的數字群(去空白與逗號)。
_hl_list(extra)  L116  
_digits_left(text, says)  L121  
_hits(ln, text, nxt, says, pseg)  L125  -> (lint 命中 list, speakable 命中 list)。
_codes(lint_hits, sp_hits)  L130  
validate(new, ctx, says, pseg)  L134  新句硬驗;回 None = 過,否則一句失敗原因(帶回給模型重做)。ctx = 該句的原始資訊。
build_prompt(pending, mode, rejected)  L168  
_payload(res)  L193  call 的結果 -> (fixes list | None, 錯誤訊息)。接受 llm.Result(ok/data/
_now()  L209  
_refusal(tag)  L213  
fix_lines(tag, items, mode, *, call=None, dry_run=False)  L220  
_default_call()  L321  
main(argv=None)  L326  

## pipeline/listen_page.py
mmss(t)  L60  
trim_wav(tts_dir, rec)  L65  單位的 trim.wav:單句行在 tts/<句3位>.trim.wav,子句在 tts/sub/<音檔鍵>.trim.
unit_time(tl_lines, idx)  L73  成片時間點(秒):子句取子句起點,否則取該行起點。
g2p_text(d)  L86  g2p_disagree 一項(tts_g2p.compare 的 dict:ch/pos/rule/g2p)-> 「字
memory_pending(text)  L93  這句命中 undetermined 記憶的位置 -> ["穿著打", …](表空不載讀音表)。
e4_items(tag, ver)  L101  讀 projects/<tag>/ear_e4_<ver>.json -> {整句idx(int): [(kind, "
e4_flags(tag, ver)  L124  同 e4_items,但每句合成一段文字 {整句idx(int): "poly 為(wei4→bei4);runon 市
pick_reasons(recs, tag=None, ver=None)  L129  回傳 {單位idx: [(類別, 說明)…]};沒命中任何門檻或例外的單位不在結果裡。tag/ver 給了才併入 E4 
is_must(why)  L193  這句的原因清單 [(類別, 說明)…] 有沒有命中必聽類別(MUST_CATS)。
tier_split(items, reasons)  L198  items = [(秒, rec, …)](rec 有 idx)已依時間排好 -> (必聽 list, 其他待聽 lis
other_summary(rows, reasons)  L206  其他待聽句的類別彙整 -> [(類別標籤, [句號…])];一句多類別各算一次,依句數多到少。rows = [(秒, r
summarize(recs, reasons)  L215  各類別命中句數 {類別: n}(一句可命中多類)。
to_mp3(wav, mp3)  L224  
card(rec, tm, why, mp3rel)  L268  
make(tag, ver, prefer_tts=False)  L281  產生聽審頁;回傳一行摘要。prefer_tts:時間點取 timeline_tts.json(只配音未渲染時,timel
text_lines(tl_lines, recs, reasons)  L335  純文字清單內容(list of str):必聽節每行 `mm:ss|句號|原因|句子原文`(依時間);其他節只列「類別(
make_text(tag, ver, prefer_tts=False)  L348  只輸出「請優先聽」純文字清單 output/<tag>/listen_<ver>.txt(不出 HTML、不轉 mp3)
main()  L366  

## pipeline/llm.py
class Result  L33  
_exe()  L45  
build_cmd(model_id, *, agent=None, effort=None, tools=DEFAULT_TOOLS, schema=None)  L49  
_spawn(cmd, prompt, timeout, cwd)  L62  跑 claude,prompt 走 stdin。回傳 (rc, stdout, stderr);逾時 rc=None。
_envelope(out)  L73  --output-format json 的結果物件:dict,或事件陣列裡最後一個 type=result。解析不了回
parse_json_text(text)  L84  從回覆文字取 JSON 物件(可包在 ``` 內或前後有說明);取不到回 None。
schema_miss(schema, data, path='')  L98  驗 required 與欄位型別(含陣列元素);回第一個不符的欄位路徑或 None。
_is_limited(rc, env, out, err)  L116  
_interpret(rc, out, err, model_id, schema, secs)  L124  
_save_raw(tag, fn, rc, out, err)  L154  
_log(tag, fn, r, agent, seg)  L161  
call(tag, fn, prompt, *, agent=None, model='sonnet', effort=None, tools=DEFAULT_TO...)  L169  跑一次。validate(result) 回字串 = 失敗原因(call_escalating 下一次附進 prompt
call_escalating(tag, fn, prompt, **kw)  L188  同模型失敗 2 次 → Opus;Opus 再失敗回 ok=False;用量上限立刻回(不換模型硬跑)。

## pipeline/look_list.py
fmt_time(sec)  L31  
_lines_of(msg)  L36  訊息裡的『句N』或『句N-M』→ (a, b);沒有回 (None, None)。
raw_from_log(logp)  L45  log 文字 → [(a, b, kind, reason)];a/b 為句號(None = 訊息沒帶句號)。
raw_from_lint(tag)  L72  script_lint.visual_warnings(結構化)→ [(a, b, kind, reason)]。行號(
raw_from_assets(tag)  L91  截圖 / 閱讀卡的結構化警告(news_lib 存的 side 檔),只看這支片 script.json 用到的圖。
collect_raw(tag, ver)  L133  
build_rows(raw, tl)  L148  raw → 依時間排序、同一鏡頭合併的列。tl = timeline.json(dict)。
collect(tag, ver, tl=None, raw=None)  L182  
_cell(s)  L188  
render_md(rows, tag, ver)  L192  
write_md(rows, path, tag, ver)  L205  
run(tag, ver)  L212  make_version 用:寫 look_<ver>.md,回傳一行摘要。
main()  L219  

## pipeline/make_version.py
script_img_prefix(tag)  L73  script.txt 前 20 行說明(# 截圖(前綴 ain_…) / 圖檔前綴:xx_)裡的圖片前綴;沒有回 Non
pick_bgm(bgm, channel, tag, spec_channel=None)  L88  BGM 檔名與來源說明 -> (檔名, 來源)。優先序:使用者 --bgm > --channel > spec.jso
spec_channel_of(tag)  L100  projects/<tag>/spec.json 的 channel 欄位;檔案不存在或壞掉 = None。
precheck_cmds(tag)  L108  文案檢查各項(名稱, 指令);spec.json 不存在時 spec_check 為 None(略過)。
_warn_count(out, pattern, default='?')  L129  從檢查項 stdout 讀實際警告數;讀不到回 default(不再寫死 0)。
visual_error_lines(out, name='visual_check')  L138  visual_check stdout -> 「錯誤 Exx xN」區塊下的明細行(最多 5 行),供中止時印出。
run_prechecks(tag, log)  L152  依序跑三項;回傳 (是否全過, 摘要行 list, 錯誤項 list)。有錯誤仍把三項跑完,方便一次看全。
log_warn(tag, step, msg)  L205  非核心步驟失敗不中止整版:印一行並追加 {at, step, msg} 到 projects/<tag>/product
class Step  L217  
Step.__init__(self, name, cmds=None, fn=None, desc='')  L218  
freeze_check(tag, tts_review=False)  L225  文案凍結檢查:回傳中止訊息(None = 可繼續);--tts-review(聽審用)不受限。
timing_errors_of(rc, tail)  L230  時長預檢(build --check-only --timing-only)的輸出 -> 錯誤清單:取「錯誤:」行;結束
parse_new_synth(tail)  L239  配音步驟(build --tts-only)輸出 -> 本次新合成句數(int);解析不到 None。
write_tts_review(tag, engine, timing_errors=None, new_synth=None)  L253  --tts-review 配音後寫 build/<tag>/tts_review.json(freeze.py 的凍結門
qc_gate_problems(tag)  L271  C15:完整渲染前的品管硬擋。tts_qc.json 有品管未過單位且 freeze.json 不存在 -> 回中止訊息
board_after(tag, a, sample, delivered, frozen=False)  L289  make_version 完成後更新進度板;失敗只警告。frozen = --tts-review --freeze 已
probe_duration(p)  L311  
preview_cmds(src, dst, bdir, dur)  L317  同 deliver_preview.sh:目標 27.3 MiB,扣音訊 96k 與餘量 20k 後全給影像,兩段式。
terms_cmd(tag, engine='chattts')  L327  
c0_needed(tag)  L331  --tts-review 是否要先跑 C0 試配 -> (要跑?, 原因)。已凍結 = 否;c0_report.json
c0_cmd(tag)  L344  
notes_cmd(a, prefix, tl, bdir, video, prev, notes)  L348  re9_notes 指令;無 projects\<tag>\spec.json 回傳 None(略過)。
deliver_cmd(a)  L359  
persona_cmd(tag, notes, record=False)  L374  spec_check 封面人像跨片重複檢查(--notes);record=True 時把方案1、3 登錄到 cover
has_release_block(notes)  L380  說明檔存在且 deliver.py 能解析出「發片資料」區塊。
run_cmd(cmd, log)  L388  執行並把輸出附加到 log;回傳 (returncode, 輸出行 list)。
main()  L399  
summarize(st, tail, video, prev, tl)  L802  每步一行摘要(取輸出中有意義的最後一行或檔案大小)。

## pipeline/migrate_tts_cache.py
main()  L14  

## pipeline/migrate_tts_keys.py
file_sha1(p)  L25  
main()  L29  

## pipeline/news_lib.py
fw(s)  L510  中文旁的半形標點改全形(規格裡可直接打半形)
_frame_color(img)  L525  圖片最外圈最常見的顏色(補邊用)
_wait_load(pg, ms=4000, noscroll=False)  L539  
class _NeedForce  L557  
_dark_mode(sp)  L561  
_dark_key(sp)  L566  
_force_browser()  L570  第二層用:啟動參數層級的功能旗標無法對單一 context 開關,所以另開一支帶旗標的瀏覽器,只有真的需要的頁面才開(沒
_open(browser, sp, dsf, dump=False, layout=False, hook=None)  L578  開頁 -> 保留區塊 -> 翻譯;回傳 (ctx, page, 量測框, 版面資料或 None)。layout=True
_serve_noto(route)  L607  
_open1(browser, sp, dsf, dump, layout, hook, plan)  L612  plan: off | js(舊版整套變色) | native(emulate dark + 校色) | probe(e
_split_site(site)  L725  spec 的 site(「網站名 2026/10」或「=來源:xxx」)拆成 (網站名, 日期)
_cut(s, n)  L732  
card_render(layout, v)  L736  模板 + 變數 -> HTML(變數值已是 HTML;CSS/JS 內嵌,單檔可直接開)
card_prepare(browser, sp)  L745  mode: card -> 抽取原頁內容、寫 tmp/cards/<name>.json/.html,回傳指向本機 HT
_hl_layers(pg, kws, vclip, cbox, width)  L840  底線圖層序列(計畫 §2C):主圖截完後在同一頁包 span、只留底線,每條底線 p = 1/HL_STEPS … 1 
capture(browser, sp, width=FW, dump=False, hl=None, hl_out=None)  L898  回傳 (PIL.Image 寬 width, runs[像素,相對該圖左上], 版面資料)。兩段式:先 DSF=1 量測
_bg(img)  L953  
_tag(canvas, text, x=18, y=14)  L957  子塊左上角網站名標籤(僅合成圖用)
compose(browser, sp, dump=False, hl=None, hl_out=None)  L966  單頁 -> 1920x1080 畫布;parts -> 直向堆疊。回傳 (canvas, runs, info);inf
_narrow_sp(sp)  L1010  窄版 spec:視窗寬 <= NARROW_VW、css 寬度壓到 NARROW_CSS_W、頁內字至少 NARROW_
compose_narrow(browser, sp, dump=False)  L1018  窄版:單頁 / parts 直向堆疊成 NARROW_W 寬的圖(不放進 1920x1080 畫布),底下多留標籤列。回
_save_layout(out, sp, canvas, runs, info)  L1044  存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx
_save_tag_text(out, site)  L1066  出處標籤字串寫進 .layout.json 的 tag_text(2026-10-22;build.py 把標籤改成 k
_layout_kind(sp, canvas, runs, info)  L1080  .layout.json 的 kind:"text"(閱讀卡、以文字為主的頁)| "photo"(照片/實機截圖為主,b
_norm_specs(SPECS)  L1094  接受 {name: spec} 或 [spec(含 name)]
_save_hl(out, kws, bars, size)  L1099  底線序列:<圖>_hl/b<序>_p<00..10>.png + <圖>.hl.json(build.py prep_h
build(SPECS, names=None, prefix='', out_dir=IMG, dump=False, narrow=False, HL=None)  L1123  
_flat(runs)  L1165  
check(SPECS, HL=None, names=None, prefix='', out_dir=IMG)  L1182  HL 建議詞都要在 .boxes.json 找到(比對同 build.py find_hl_boxes:忽略空白與大小寫
_check_card(n, runs)  L1225  閱讀卡檢查(PLAN §3):文字離卡邊 >= CARD_MARGIN、文字框底緣 <= CARD_SUB_TOP(字幕
_hl_pieces(runs, kws, fs=None)  L1251  同 JS_HL_WRAP 的比對(忽略空白與大小寫、最多 HL_MAX 處、不重疊)-> [(kw, [x0, x1, 
_check_hl(out_dir, n, runs, kws, hlj)  L1282  紅線序列檢查(PLAN §3):每條底線(.hl.json;跨行命中本來就是每行一條)p=1.0 那張的紅色像素 x 範
_check_dark(out_dir, prefix, n, sp)  L1316  暗色檢查(PLAN §3):截完量全圖亮度中位數(0-1,Rec.601),> DARK_LUM_MAX = 暗色沒生效
_check_flat(out_dir, prefix, n, runs, card)  L1327  C:純色塊警告。重點區 = 文字框與圖形框的外包矩形外擴 FLAT_GROW 倍行高(沒有文字框 = 整個截取區,抓空白
_carve_gfx(gfx, runs, pad=3)  L1379  gfx 框(有底色的按鈕/膠囊)裡有文字框時,把文字框挖掉只留四周色塊,字本身仍要驗墨跡(ink_check 的 ski
_check_ink(out_dir, prefix, n, runs, site, stat)  L1397  墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat
_check_layout(out_dir, prefix, n, runs)  L1411  版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截
relabel(SPECS, names, prefix='', out_dir=IMG, old_prefix='=來源:')  L1444  只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動(重截被擋的圖用)
overview(SPECS, prefix='', out_dir=IMG, out=None)  L1457  總覽圖:各圖縮圖並排、標圖名(寬 <= 2400)
_opt(args, flag)  L1477  取出並移除 flag 與其後一個值(沒有 flag 回傳 None)
_names(args)  L1487  
main(SPECS, tag, HL=None, prefix=None, argv=None)  L1491  新片 news 檔的入口。tag 為片名(預設輸出前綴 <tag>_,舊片沿用短前綴時用 prefix 覆寫,例 gd_

## pipeline/news_specs.py
flat_all(SPECS)  L44  每張規格預設都先攤平段落(js 沒指定時用 FLAT);回傳同一個 SPECS
unclip(sel)  L51  把目標的祖先全部改成 overflow 可見、不限高(原頁用固定高度+overflow 裁字,版面檢查會報被裁)
cut_js(idx, start, end)  L58  把第 idx 個目標區塊(一整大段)縮成「start 起到 end 止」的原文片段(只取原文,不改字)
block_css(sel, w, fs, lh=1.6, extra='')  L66  中文頁:把保留區塊的寬度/字級固定下來(scale = 1920 / 區塊寬,所以寬度決定字有多大)
inl(sel, fs, extra='')  L73  一行內的小字(署名、日期):行內區塊、寬度自動
title_css(sel, w, fs, extra='')  L80  
body_css(sel, w, fs, extra='')  L84  
art(url, ptag, targets, rules, site, w=1000, fs=34, vw=1100, title_sel=None, titl...)  L89  通用文章頁:ptag 為內文段落選擇器;title_sel 為標題(加大、加寬)
para(url, site, sel, prefix, zh, w, fs, vw=1100, hdr=None, rule_key=None, lh=1.55,...)  L99  單一段落:prefix 為該段開頭英文(以…結尾做前綴比對);hdr 為找目標用的內含文字(預設 prefix 去掉…)
gi_para(url, date_zh, prefix, zh, hdr, cut=None, w=1250, fs=40, vw=1350)  L105  Game Informer 訪談(2026 版型,內文是 article 之後的裸 <p>):hdr 為找段落的內含文字
gnn(targets, css='', rules=(), w=1000, fs=32, **kw)  L118  巴哈姆特 GNN 訪談(中文原頁)
kotaku(url, date_en, date_zh, by_en, p_key, p_zh, h1_rule=None, w=1200, fs=44, vw=13...)  L128  Kotaku(2014 與 2026 同一版型):標題 + 署名 + 日期 + 一段內文
kotaku_head(url, rules, w=1000)  L136  Kotaku 新版型文章標題區:h1 + 副標(.post-excerpt)
kotaku_art(url, rules, targets, w=1200, fs=36)  L143  Kotaku 新版型:標題(header.mt-4 h1)+ 內文段落(div.entry-content p)
kotaku_para(url, css_sel, prefix, zh, w=1200, fs=40, vw=1300, rule_key=None)  L150  Kotaku 舊版型(2016)的一段:css_sel 為段落選擇器
gs_para(prefix, zh, w=1000, fs=44, vw=1100, url=GS_REVIEW)  L161  GameSpot 評測內文的一段(wp-block-paragraph)
gd_para(key_start, prefix, zh, w=1300, fs=42, url=GD_URL)  L166  Game Developer(原 Gamasutra)內文一段:key_start 找目標、prefix 做規則前綴
gb_para(prefix, zh, url='https://gamesbeat.com/target-pulls-grand-theft-auto-v/')  L172  GamesBeat 文章一段
ign_p(url, txt, rules, w=1000, fs=40, **kw)  L180  IGN 內文段落
press_start(qtxt, atxts, rules, w=1000, qfs=30, afs=42, oy_max=200, **kw)  L190  Press Start 專訪:qtxt=None 表示不放問題;atxts 內 "H:" 開頭者為 h3(問題),其餘為
ps_art(rules, targets, w=1150, fs=38)  L199  Press Start 專訪:h1 標題 + 一段內文
gf(url, targets, rules, w=1000, fs=34)  L211  Game File(Substack)文章
am(url, key, rules, **kw)  L217  Aftermath 文章一段
sec(url, key, zh, w=800, fs=32, company=None)  L226  SEC 10-K 年報一段(site 的公司名由網址判斷,可用 company 指定;預設 EA / Take-Two)
steam(url, targets, rules, css='', js=None)  L258  Steam 鑑賞家頁(dark=False;規則引擎要求每條都必須命中,所以各張只挑頁面上有的)
disc(tid, pn, paras, rules, title=False, lis=False, vw=1100, keep=(), extra_css=''...)  L298  Discourse 單樓貼文:作者列 + 指定段落(p 或 li,以內含文字找)+ 讚數;title=True 另留標題
meta(user_zh, date_en, date_zh, title_en=None, title_zh=None)  L307  作者列的共通規則:貼文數、日期(只留日期,不留時分)

## pipeline/ocr_compare.py
make_synth(n, out_dir)  L35  合成「遊戲畫面 + 下方中文字幕 + 上方英文字卡」圖,回傳路徑清單。
collect(args)  L62  
stats(lines)  L75  
check_engine(eng)  L82  回傳 None = 可用,否則原因字串
run_images(files, engines)  L98  
md_images(files, engines, res)  L123  
run_clip(srcs, engines)  L156  
main()  L179  

## pipeline/pace.py
count_chars(text)  L16  字數:不含標點與空白(同 script_lint.clen,另把底線也排除)。
est_seconds(text, pause=0.0)  L21  預估唸完這段文字的秒數 = 字數 ÷ CHARS_PER_SEC + pause。
minutes(chars)  L26  字數換算成分鐘(以 CHARS_PER_MIN)。

## pipeline/paths.py
_root()  L36  
venv_python(env_dir)  L53  venv 的 python:Windows = Scripts/python.exe,其他(Colab/Linux)= 
_known_folder(guid)  L76  
downloads()  L95  使用者的「下載」資料夾;取不到時退回 OUTPUT\final 並警告。
yt_inbox()  L107  Youtube AD 的影片資料夾(= 下載資料夾\V);正式成片與 .claude.json sidecar 交付到這
yt_ad_root()  L120  Youtube AD 專案根(讀 data\channels.json 用)。
trend_db(channel)  L138  Youtube AD 的趨勢資料庫(競品、新聞;唯讀使用:topic_score.py 以 mode=ro 開);依頻道
ytad_root()  L144  Youtube AD repo 根(context_pack 跑 tools/intel_query.py、讀 data
ytad_export_latest()  L151  Youtube AD 自有頻道匯出(data/own/export/latest.json;唯讀)。
ytad_export_dir()  L156  Youtube AD 匯出檔資料夾(data/own/export/:latest.json、YYYY-MM-DD.js
ytad_channel_export_latest()  L161  Youtube AD 頻道匯出(data/own/export/channel_latest.json;唯讀)。
ytad_comments_dir()  L166  Youtube AD 抓的留言檔目錄(data/own/comments/<video_id>.json;唯讀)。
topics_file()  L171  選題清單與評分結果(topic_score.py 讀寫)。
topic_cache_dir()  L176  搜尋建議詞快取(24 小時內不重查)。
__getattr__(name)  L181  
build_dir(tag)  L187  
tts_dir(tag, engine=None)  L194  配音快取目錄:build/<tag>/tts(chattts 等)或 build/<tag>/tts_cosy3。eng
output_dir(tag)  L208  
project_file(tag, name)  L212  專案檔:ROOT\projects\<tag>\<name>;那裡沒有而 repo 內有(repo 還沒搬進素材根、或剛
clips_file(tag)  L219  
speaker(name)  L223  音色檔:只給檔名就到 SPEAKERS 找。
find(path, *bases)  L229  輸入檔的相對路徑:依序在 bases(預設 ROOT、REPO)找第一個存在的;都沒有則回傳第一個基準下的路徑。
out_file(path, tag=None)  L241  輸出檔的相對路徑一律以 ROOT 為基準;只有檔名且給了 tag -> OUTPUT\<tag>\<檔名>。
rel(path)  L251  快取簽章用:ROOT / REPO 底下的路徑換成 <ROOT>/... 或 <REPO>/...(正斜線),其餘字串原
_emit(text)  L266  
main(argv)  L270  

## pipeline/pron_backlog.py
context(text, pos, w=1)  L27  語境詞:pos 前後各 w 字(去掉標點與空白)。
_esc(s)  L33  
load(path=FILE)  L37  
save(rows, path=FILE)  L53  
upsert(items, tag, path=FILE, today=None)  L63  items = [(字, 語境詞, 證據)](同一片一次跑的全部;同鍵出現幾次 = 本片次數)。回傳 (新增, 更新) 
_report_items(report)  L90  
polyphone_items(report)  L97  polyphone_report.json -> upsert items(只取 kind=alt 且 evidence
init(path=FILE)  L103  
top(n=3, path=FILE)  L114  

## pipeline/pron_memory.py
_sig(path)  L46  
load(path=None)  L54  -> {"_doc", "entries"};檔案不存在回空表。
save(doc, path=None)  L64  
_index(path=None)  L71  -> {(字, 左, 右): 條目}(略過 tombstone);依檔案 mtime/大小快取,檔案不存在回 {}。
has_entries(path=None)  L85  
_symbols(text)  L90  -> (語境符號 list, {漢字位置: 符號序})。英文、數字、拼音 token 連成一個 #;標點連成一個 |;空
_side(syms, i, n, step)  L107  
_keys(syms, i)  L118  [(左2, 右2), (左1, 右1), (*, *)],查詢由長到短。
context(text, pos)  L123  text[pos] 的語境鍵 -> dict(l2, r2, l1, r1);pos 不是漢字回 None。
scan(text, path=None)  L132  這句命中的記憶 -> [(位置, 條目)];每個位置取最長語境。表空回 [],不做任何字串處理。
mark_value(e)  L152  apply_pron 要在這個位置換上的值;不自動套用(undetermined、rewrite、沒有 fix)回 No
blocking(e)  L162  bad + rewrite:這個語境要改寫,配音稿算未決、C0 算唸錯。
ctx_label(e)  L167  
hit_key(e)  L171  pron_hits 的鍵(格式同規則的「詞→標注」)。
fix_of(ch, py)  L176  送引擎的值 -> fix(著換着 = zhe,其餘 mark);沒有標注回 None。
units(v)  L183  標注值 -> 每個字一單位的原字串(聲母 + 韻母 token 併一單位,一般字一單位)。
state_of(n_right, n_wrong, _n_undetermined=0)  L198  實測結果 -> state(唸對 >= 2 且唸錯 0 才 ok;無法判定不算通過)。
make_entry(ch, left, right, py='', state='ok', evidence='test', wrong_as=None, fix=None,...)  L205  
_find(rows, e)  L215  
_contradicts(a, b)  L219  
_merge_wrong(a, b)  L223  
_add_run(e, run)  L228  
_merge(old, e, run)  L233  
_rekey(e, ctx)  L246  
_split(doc, old, e, run)  L250  同鍵結果矛盾:兩邊各記自己的 2+2 並標 conflict;2+2 分不開就併在同一筆、改 undetermined。
upsert(doc, e, run=None)  L271  新增或併入一筆。-> added / merged / replaced / conflict / ear_kept /
seed_outcome(p)  L300  judge_record 的一個位置 -> right / wrong / undetermined。只有相似度過、沒有
wrong_entry(p, py, ph=None)  L308  唸錯的位置 -> wrong_as 一項 dict(heard, kind);聽成 None 回 None。
record_tests(rows, run, ph=None, day=None, path=None)  L319  實測結果寫進記憶表(tts_c0 與 tts_pron_verify 共用)。rows = [dict(text, po
check(doc, tokens=None)  L351  -> (錯誤 list, 衝突 list)。tokens = CosyVoice3 tokenizer 的 token 
_line(e)  L391  
_cmd_lookup(a)  L397  
_cmd_add(a)  L407  
_cmd_list(a)  L425  
_tokens()  L433  
_cmd_check(_a)  L438  
main(argv=None)  L449  

## pipeline/qa_sheet.py
grab(video, t)  L22  
main()  L28  

## pipeline/re9_notes.py
mmss(t)  L26  
size_mb(p)  L30  
duration(p)  L34  
package_block(pkg, L)  L46  spec.package -> 「發片資料」區塊文字(格式照 channel\規則\4_交付發片.md §5);標題、封
bgm_is_ai(name)  L76  --bgm 傳入的是檔名去副檔名、底線換空白;bgm\ 內同名 .json 側檔的 source 以「AI」開頭 = A
section_text(md, heading)  L87  取 `## heading` 整段(含標題行,到下一個 `## ` 或檔尾,去尾空白);沒有回傳 None。
prev_notes(out_path, ver)  L94  同資料夾最新的更早版本 v<N>_說明.md(N 小於本版;本版不是 v<N> 就取 N 最大且非自己者);沒有回傳 (
carry_sections(out_path, ver)  L111  有上一版說明檔就回傳 (署名段或 None, 發片資料段或 None, 上一版 N);發片資料段標題後、```text 
main()  L126  

## pipeline/retention_align.py
_load(path)  L25  
find_timeline(tag, explicit=None)  L29  --timeline 優先;否則 keep/<tag>/timeline.json,再 build/<tag>/time
_points(raw)  L38  [[pos, val], …] → [(float, float)],依位置排序。
_typical(raw)  L43  [[pos, low, high], …] → [(pos, low, high)]。
load_curve(tag, curve_path=None, video_id=None)  L48  回傳 {video_id, points, typical, source};找不到回 None。
interp(points, pos)  L77  在位置 pos(%)內插留存;超出範圍取端點。
interp_typical(typical, pos)  L89  回傳 (low, high) 或 None。
hook_type(tag, lines)  L98  
lines_in(lines, a, b)  L111  與 [a, b] 秒區間有交集的句子(最多 MAX_LINES 句)。
find_drops(points, typical, total, lines, top=5)  L123  
align(tag, timeline_path, curve, top=5)  L153  
write_result(tag, res)  L169  
_p(x)  L177  
to_markdown(res)  L181  
summary_table(results)  L194  
run_all(curve_path, top)  L204  
main(argv=None)  L224  

## pipeline/review_md.py
_read(p)  L23  
_load(p)  L30  
tts_warnings(report)  L37  tts_report.json(dict)-> 警告行 list;只列非空的警告欄位。
structure_warnings(st)  L49  structure.json(dict)-> 警告行 list(code / 句號 / 說明)。
facts_warnings(lines)  L54  facts_check stdout 行 -> 警告行 list:「警告 … N 句」N>0 的行、摘要行中 未連結/狀
run_facts_check(tag)  L69  有 facts*.md 才跑 facts_check.py(唯讀);回傳 stdout 行 list,跑不成回 []。
split_listen(text)  L82  listen_<ver>.txt 全文 -> (必聽行 list, 其他行 list);沒有「## 必聽」標題(舊版純清
listen_blocks(listen, ver)  L97  「聽」節的清單區塊 list:新格式 = 必聽(逐句,放最前)+ 其他(折疊,只有類別與句號);舊格式 = 整份原樣。
build(tag, ver, facts_lines=None)  L112  組出 review_<ver>.md 全文(字串)。facts_lines 給 None = 實際跑 facts_che
run(tag, ver)  L137  make_version 用:寫 review_<ver>.md,回傳一行摘要。
main()  L147  

## pipeline/run.py
main()  L16  

## pipeline/script_lint.py
spoken_lines(tag)  L90  
triple(text)  L99  同一句裡三段以上並列且開頭同字(有認,有改,有給時間)。
parallel(a, b)  L105  相鄰兩句對仗:開頭或結尾連續 3 字以上相同(一邊說/另一邊說、像不像那張照片)。
lead_subjects(pseg, sents)  L132  每句的句首主語:全片出現過的人名/機構/專名(nr/nt/nz/ns/eng,2-4 字)中,該句開頭吻合的最長者;沒有
subject_runs(pseg, sents)  L142  任一連續 subj_win 句內,同一句首主語出現 >= subj_run 次(R\92 原訂 3 句內 3 次只抓得到
number_runs(sents)  L156  
_pseg()  L168  jieba 詞性斷詞;沒裝就回 None(相關檢查退回字數規則)。
clen(t)  L181  
sentences(lines)  L185  
keywords(pseg, text)  L189  名詞/動詞/英文關鍵詞集合(2 字以上、排除弱詞)。
repeated_numbers(lines)  L194  
repeated_pairs(pseg, sents)  L205  
pronoun_hits(sents)  L222  
warmup_hits(pseg, sents)  L235  暖場與單句預告;同一句內後面已接上事實名詞者不算。
skeleton(sents)  L251  
first_judgment(sents)  L258  回傳 (第幾句, 換算秒數);全片沒有判斷詞回 (None, None)。
v2_warnings(lines)  L268  回傳 [(名稱, 命中 list[(行, 文字)], 是否超標)];命中為空的不回。
clause_cut(c)  L325  長子句的建議切點「前|後」:jieba 斷詞後最接近中點(以字元位置計)的詞邊界;沒有 jieba 或沒有內部詞邊界回 
report_sentence(t)  L366  
block_starts(tag)  L370  script.txt 裡「# 」段落標題的行號(升冪);旁白以此切塊。
source_lead(t)  L375  
num_groups(t)  L383  
_chain_words(pseg, t)  L394  一句的「承接用實詞」集合:有 jieba 取 n*/v*/eng 2 字以上;沒有就取 CJK 二字組與 >= 2 字母
_chain_caught(pseg, prev, t)  L404  
fluency_warnings(lines, starts=(), stats=None)  L409  旁白連貫四組警告(來源起句、子句過多、一句數字過多、沒接住上一句);格式同 v2_warnings。
pause_lines(tag)  L485  [(行號, 估計句末秒數, pause 或 None)];行尾 json 解析不了的當作沒有 pause(格式錯誤由 s
pause_warnings(tag)  L502  行尾 pause 的節奏警告(格式同 v2_warnings);全片沒用 pause 回 []。
visual_key(ln)  L528  script.json 一句的畫面 → (類別, 鏡頭鍵);鍵相同的相鄰句算同一個鏡頭(簡化自 build.visual
visual_warnings(vlines)  L546  畫面單調警告(不擋)。vlines = [(行號, script.json 句 dict)];格式同 v2_warnin
_may_tilt(d)  L575  這句的圖片鏡頭可能傾斜嗎:明寫 fx 照 fx;沒寫時 photo 組(layout.json kind=photo,或
kit_errors(vlines)  L589  動態小件(kit)檢查,一律算超標(PLAN_畫面優化六項 F):名稱存在、必要欄位、同句 <= 2、punch 每句 
visual_lines(tag, lines)  L611  讀 <tag>/script.json 的逐句畫面欄位,對上 script.txt 的行號;沒有 script.json
opening_load(lines, pseg=None)  L627  T01:開場前 T.open_sents 句裡出現一次、到後面塊才再出現的名詞(= 開場塞了留給後面塊解釋的論點);超過
pronoun_before_name(lines, names=())  L649  T04:第一個「她/他」之前(同句前段或前 3 句內)沒有人名或人物詞(英文專名、作者/總監…、spec names)-
price_twd_missing(lines, vlines=())  L666  T08:句子或畫面欄位有美金價格,同句與同句畫面都沒有台幣(NT$/台幣)-> 命中;財報營收類(PRICE_EXEMP
not_played(tag)  L681  T14:projects/<tag>/brief.json 的 played 為 false,或 handoff.md 
played_claims(lines, played=False)  L696  T14:使用者沒玩過(played=False 以外都不查)而旁白寫第一人稱遊玩經歷(我玩了/我通關/我打了 N 小時…
taste_warnings(lines, tag)  L703  T01/T04/T08 警告三項;格式同 v2_warnings。
spec_names(tag)  L714  projects/<tag>/spec.json 的 names(人名/專名清單);沒有回 ()。
sentence_hits(ln, text, nxt=None, pseg=None)  L725  一行旁白(text)的句級命中 -> [{line, code, block, why}];nxt = 下一行文字(對仗
check_sentences(tag, line_nos=None)  L769  script.txt 句級檢查子集 -> [{line, code, block, why}](依行號);line_no
main()  L781  

## pipeline/script_structure.py
_num_value(m)  L50  RE_NUM 命中 → (數值, 正規化字串);年份(1990–2035 且無單位)回 None。
_anim_type(extra, defs)  L65  
build_units(sections, defs, timeline_lines=None)  L72  展開成句子單位 [dict(line,row,sec,tag,extra,text,chars,start,end,an
is_new_fact(u)  L95  
classify_hook(sentences)  L99  前 3 句(字串清單)→ (主型態, 命中的所有型態)。單一來源:retention_align 也呼叫這裡。
entities(units)  L116  回扣開場用的實體:阿拉伯數字(含單位,排除無單位的 1–2 位數)、英數專名、「」《》內的名稱、不含虛字的 4 字連續中
numbers_of(units)  L136  
load_timeline(path, n_rows)  L146  回傳 lines list(長度須 = 資料行數);讀不到/長度不符回 (None, 原因)。
analyze(src, timeline_paths=())  L160  src = script.txt 全文;timeline_paths = 依序嘗試的 timeline.json 路徑。
summary(tag, r)  L292  
main(argv=None)  L314  

## pipeline/script_txt2json.py
_json_obj(s, no, what)  L50  
split_extra(s, no, strict)  L60  拆出行尾「 ;; {json}」。strict=False(段落行)時,解析不了就當作沒有額外欄位。
parse_spoiler(arg, no)  L76  @spoiler [秒數|]標題|說明 或 [秒數|]文字 -> {"text": "標題|說明", "dur": 秒}
expand_anim(ref, defs, no)  L88  anim 欄位為字串 '名稱#步驟' 時,展開成 @def anim:名稱 的內容加 step。
parse(src)  L100  
split_card(t)  L149  
build_lines(rows, defs)  L157  先處理一般標籤,再回頭補 card(需要鄰句的 v)。
main()  L219  

## pipeline/seg.py
_warn(key, msg)  L36  
set_seg(name)  L42  指定預設斷詞器(None = 看環境變數 / jieba)。
seg_name()  L50  要求的斷詞器名稱(未必可用;實際可用的看 segmenter().name)。
sub_words()  L59  
_read_words(path)  L68  
tag_words_file(tag)  L72  
phrase_mode()  L77  片語模式:字幕拆段在合法切點上加片語評分(build._phrase_score)。
set_phrase(on)  L82  
tw_name_words(tag)  L87  projects/<tag>/spec.json 的 tw_names:鍵與 tw 值(含冒號/空白的再拆片);中文 2
set_tag(tag, path=None)  L107  載入每片詞表(path 預設 build/<tag>/words.txt)+ spec.json tw_names,並開
simp(text)  L126  jieba 內建詞典是簡體,繁體直接丟進去會斷錯(人事部/門):斷詞與查詞典前先逐字轉簡體;長度變了或 opencc 不
jieba_module()  L140  jieba 模組(已加入 sub_words);不可用回傳 None。
class JiebaSeg  L160  
JiebaSeg.cut(self, text)  L163  
JiebaSeg.prefetch(self, texts)  L171  
merge_sub_words(text, words, sub_words_list)  L175  後處理併詞:移除落在 sub_words 詞內部的斷點(詞兩端不動)。words 的 join 必須等於 text。
align_words(text, words)  L192  把斷詞器回傳的詞對回原文(模型可能吃掉空白):回傳 join == text 的詞清單,對不上回傳 None。空白併入前
class CkipSeg  L216  ckip-transformers 斷詞器。`ws` 可注入(測試用假物件):ws(list[str]) -> list
CkipSeg.__init__(self, ws=None, sub_words_list=None, batch_size=64)  L220  
CkipSeg._words(self)  L228  
CkipSeg._run(self, texts)  L231  
CkipSeg.prefetch(self, texts)  L236  批次送模型(比逐句快很多);已有快取的略過。
CkipSeg._store(self, text, raw)  L244  
CkipSeg.cut(self, text)  L253  
_load_ckip()  L261  載入 ckip 斷詞器;失敗(沒裝、模型下不到)印警告回傳 None。
segmenter(name=None)  L275  回傳斷詞器;ckip 不可用退回 jieba;jieba 也不可用回傳 None。

## pipeline/shorts_build.py
parent_make(tag)  L41  最新一份 make_*.log(不含 Shorts 自己的 make_s*_*.log)-> (build 選項 dic
txt2json(src, dst, prefix, log)  L63  
flat(data)  L71  [(段名, 句)],依 spec 句號順序(sections[].lines 攤平)。
parse_range(s)  L76  
parse_cx(s)  L81  
say_of(l)  L89  
copy_tts(pairs, ptts, wtts)  L93  pairs = [(新句號, 母片句號)]:把母片 NNN.* 快取複製成新句號;sub\ 整個複製(檔名是音檔鍵,與句
check_counts(out)  L107  
probe_wh(p)  L116  
notes_skeleton(path, tag, sid, ver, rng_desc, hook, dur, warns, parent_notes)  L122  說明檔骨架(deliver 能解析的格式);署名區塊沿用母片說明檔的,第一行是長片連結。已存在不覆寫。
main()  L139  

## pipeline/speakable.py
say_text(text, says=None)  L43  字幕文字 -> 送配音的文字(@say 依序替換,同 freeze.narration_lines)。
_src(say)  L50  
_keep_positions(src)  L54  pron_rules 裡 keep 規則(確認模型預設讀音正確)占住的位置;rule_events 不回 keep,這裡
_covered(src, spans, ev)  L71  詞表區段、規則事件(含 keep)、記憶命中、著 已處理的位置集合。
known_chars()  L81  「已知易錯字」= pron_rules 有條目的字 ∪ 語境讀音記憶的字 ∪ pron_backlog 的字(pron_
_backlog_rows()  L87  [(字, 語境詞, 命中次數, 來源片)],只取狀態「待規則」。
_unregistered(say)  L100  未登錄英文詞 list;優先用 terms_check(單一來源),沒有就用 tts_cosy_text.analyze
features(say)  L110  一句送配音文字的數值特徵 dict:units、clause_max、en_n、en_ratio、digits、poly
_sev(v, warn, err)  L126  
check_line(text, says=None)  L130  一句的可唸性命中 -> [{code, severity:"err"|"warn", span, why}]。text 
script_rows(tag)  L166  script.txt -> [(行號, 字幕文字, 送配音文字)];@say 與行尾 say 欄位同 freeze.na
check_tag(tag)  L181  {lines:[{line, hits}](只列有命中的句), errors:n, warns:n, n_lines:n
explain()  L194  給寫稿 prompt 的短規則(<= 40 行);門檻取自 T,實測依據見 docs\speakable.md。
calibrate(build_dir=None)  L214  掃 build\*\tts_qc.json 的最終紀錄,回傳 {n, base:{目標:率}, rows:[(特徵, 區
_print_calibrate(res)  L255  
main(argv=None)  L262  

## pipeline/spec_check.py
has_number(text)  L52  
has_data_number(text)  L62  
load_lines(tag)  L66  
mark_ok(extra, key)  L75  
name_rules(spec)  L80  spec.tw_names 為 dict 時回傳 [(原文, 台灣譯名, [avoid...])];缺或非 dict →
_has_term(term, text)  L98  ASCII 原文不分大小寫且前後不可接英數(避免 AI 命中 FAIR);中文詞直接子字串。
check_names(spec, lines)  L105  譯名表(PLAN_TTS_FLOW R5):字幕/旁白(text 與 @say 後的 say)出現 avoid 他譯 →
facts_md_exists(tag)  L123  projects\<tag>\facts*.md 存在 -> True(spec.json 的 facts 空時,事實覆
check(spec, lines, skip_fact_cover=False)  L128  skip_fact_cover=True:略過「數字/引言/人名句要有 fact 涵蓋」(spec.facts 空且有 
text_width(s)  L211  全形(含中日韓)計 1、半形計 0.5。
package_empty(pkg)  L216  
check_package(spec)  L220  回傳 (errs, warns)。DEI 系列等頻道特例不檢查。
check_neg_repeat(spec, tag)  L350  回傳 (errs, warns)。本片標題/封面字含判語、且近 14 天同 slot 其他片標題含同一判語 → 錯誤。
anim_shows_numbers(ln)  L389  list/versus/flow 等文字型 anim:句中的阿拉伯數字全都出現在該 anim 的欄位文字裡 = 數字有秀
check_visuals(spec, lines)  L399  回傳 (errs, warns, custom_ratio)。畫面 = script 欄位 + spec.visual_
table(spec, lines, custom_ratio=None)  L418  
_first(pats, *texts)  L480  依序在各段文字找,取第一段有命中者中位置最前的正規值;都沒有 None。
_outfit(t)  L493  
_age(t)  L507  
_gender(t)  L515  
parse_notes_plans(text)  L520  回傳 {'1': {field: 行文字}, ...};只讀 方案N 單獨一行起到下一個方案/區塊結尾。
extract_persona(fields)  L539  從 主體/場景/視覺構圖 抽 kind 與六格、色彩方向;抽不到的格 None。
load_persona_log()  L553  
_same(a, b)  L565  
check_persona(tag, notes_path)  L569  回傳 (errs, warns, personas);personas = {plan: 抽取結果}。
record_persona(tag, notes_path, personas)  L611  方案1、3 各寫一筆;同 tag+plan 已存在就覆寫那一行(不重複)。
recent_sheet(new_img, n=8, cols=3, cell=(480, 270))  L640  最近 n 張 Youtube AD 方案1 底圖(只讀)加新圖拼成 contact sheet,新圖第一格紅框;回傳輸出
run_persona(a)  L659  
main()  L673  

## pipeline/stats.py
export_dir(override=None)  L47  
read_json(path)  L51  
load_latest(d)  L58  
load_channel(d)  L62  
resolve_slot(name)  L66  頻道名/簡稱 -> slot;不認得回 None。
base_url()  L74  
http(method, endpoint, timeout=3.0)  L79  回傳 (dict|None, 錯誤文字|None)。連不上/非 JSON/HTTP 錯誤 -> (None, 原因)。
freshness(timeout=3.0)  L91  
launch_backend()  L95  背景執行 Youtube AD 的 run.bat autostart(8000 已有人就自己結束)。不等待。回傳 (o
spawn_bg_refresh()  L111  背景行程 POST /api/own/refresh(同步重寫匯出檔可能數秒,hook 不等)。
ensure_fresh(log=print)  L124  回傳 (fresh:bool, note:str)。任何失敗都不擋:note 說明原因。
parse_ts(s)  L161  
freshness_info(latest, now=None)  L168  由 latest.json 算 (is_today, generated_at, data_as_of, missing
head_line(latest, now=None, note=None)  L181  輸出第一行:一律印資料時間;非當天加大字警示。
emit(lines, cap=LINE_CAP)  L196  
num(x)  L203  
fv(x, nd=0, suffix='')  L207  
fdur(sec)  L214  
age_str(hours)  L219  
win(v, name)  L226  
win_cell(w)  L230  
dur_group(sec)  L237  
find_baseline(ch, kind, sec)  L244  該頻道 kind(self/other)對片長分組的基準;分組沒有就退 all。
position(value, m)  L254  value 對 {median,q1,q3} 的位置字串。
channel_of(chdata, slot)  L266  
self_videos(latest, slot=None, days=None)  L274  
video_row(v)  L287  
cmd_summary(latest, now=None, note=None)  L300  
cmd_stale(latest, now=None, note=None)  L317  
find_video(latest, key)  L340  
cmd_tag(latest, key, chdata=None, now=None, note=None)  L347  
asof_line(ch, chdata)  L375  
baseline_lines(ch)  L380  
video_lines(ch, self_flag, limit)  L395  
rival_lines(ch, n)  L405  
cmd_channel(latest, chdata, slot, now=None, note=None, compare=False, rivals=None)  L413  
dated_files(d, regex)  L452  
history(d, video_id)  L461  逐日(以快照 captured_at 的日期去重,同日取較晚)的 latest 曲線。回傳 list[dict]。
plan_lines(tag)  L482  當初計畫(spec.json 的 package;handoff 只指出檔名)。
cmd_review_tag(d, latest, chdata, key, now=None, note=None)  L502  
cmd_review_channel(latest, chdata, slot, days, now=None, note=None)  L533  
cmd_hook(d, now=None)  L556  3 行內;錯誤只警告。回傳 lines。
build_parser()  L577  
run(args, now=None)  L593  
main(argv=None)  L621  

## pipeline/style_metrics.py
clen(s)  L22  
top(items, key=None, rev=True, n=3)  L83  
avg(g, k)  L99  

## pipeline/sub_scan.py
strict_stats(lines)  L24  超寬段中「嚴格合法切點(含跨界字串檢查)就能解」之外要放寬的個數,與可切點/候選切點總數(可切點越少 = 斷詞器把詞併得
main()  L45  

## pipeline/sub_seg_compare.py
pick_tags(n)  L24  
run_one(tag, seg, judge, tmpdir)  L29  
table(tags, segs, res)  L41  
main()  L57  

## pipeline/taste_run.py
case(tid, title, audio=None)  L35  
llm(note)  L43  
gap(note)  L47  
judge(*checks, note='')  L51  checks = [(說明, 是否成立)];全成立 pass,否則 fail 並列出哪幾條不成立。
_rm(d)  L57  只刪 tmp\taste 的直接子目錄(完整明確路徑,不比對名稱)。
workdir(tid)  L66  
cleanup()  L74  
numbered(texts)  L81  
fixture_lines(name)  L85  tests/fixtures/taste/<name>:script.txt 格式(標籤|字幕),略過 # 與空行 ->
names_of(warns)  L96  
patched(mod, **attrs)  L101  
run_pytest(*files)  L112  
t01()  L121  
t02()  L130  
t03()  L139  
t04()  L144  
t05()  L154  
t06()  L165  
t07()  L174  
t08()  L185  
t09()  L199  
t10()  L207  
t11()  L212  
t12()  L231  
t13()  L236  
t14()  L241  
t15()  L255  
t16()  L265  
t17()  L274  
t18()  L281  
t19()  L288  
t20()  L303  
t21()  L310  
t22()  L323  
t23()  L333  
t24()  L342  
t25()  L350  
t26()  L355  
t27()  L362  
t28()  L374  
t29()  L381  
t30()  L387  
_img_lines(specs, fps=None)  L406  
t31()  L421  
t32()  L431  
t33()  L466  
t34()  L472  
t35()  L477  
t36()  L486  
t37()  L494  
t38()  L499  
t39()  L505  
t40()  L514  
t41()  L529  
t42()  L540  
t43()  L553  
t44()  L563  
t45()  L573  
t46()  L578  
run_audio(c)  L583  --audio:另外跑案例的音檔層指令(CPU dry-run、不合成);回 (ok, 說明)。
run_case(tid, audio=False)  L590  
scan_recent(n=10)  L606  最近 n 支 script.txt 的新 lint 命中數(誤報率校準用)。
main(argv=None)  L619  

## pipeline/terms_check.py
_ct()  L22  
load_terms(path=TERMS_FILE)  L28  
is_latin(term)  L32  
_pat(term)  L36  拉丁詞要求前後不是英數(避免 CA 命中 CAD);非拉丁詞純子字串。
_mask(text, pat)  L43  
analyze(texts, terms=None)  L47  texts = 送配音的文字 list(第 i 個 = 第 i+1 句);terms 不給 = 讀 say_terms.
analyze_cosy(texts)  L76  同 analyze 的回傳格式,對照 cosy_terms.json(寫法由引擎自動套,unapplied 恆空)。
unregistered(texts)  L81  cosy 引擎:送配音文字(@say 後)裡沒登錄的英文詞,依首見順序。
unregistered_by_line(texts)  L86  同 unregistered,{行號(從 1): [詞]}。
registered_unverified(text)  L95  這句用到的、cosy_terms(含 _direct)有登錄但不在 _verified 的英文詞(順序 = TERMS 
still_en(w)  L102  送引擎仍是英文:_direct 的詞若 cosy_terms 另有寫法,以寫法為準(寫法沒有英文字母就不算)。
direct_open(texts)  L107  texts = 送配音文字 list(第 i 個 = 第 i+1 行)。回傳 {詞: [行號]}:在 _direct、不

## pipeline/text_wrap.py
card_cut(text)  L17  斷詞(同 build.py 作法,斷詞器共用 seg.py:預設 jieba〔詞典是簡體,先逐字轉簡體斷再切回原字〕,-
break_groups(text)  L41  在詞與詞之間可換行的切法:回傳不可再切開的字串清單(串起來 = 原文)。
_may_break(t, nx)  L54  
wbr_html(text)  L62  跳脫後在詞與詞之間插 <wbr>(搭 CSS word-break:keep-all,中文換行切點只落在詞邊界)
zwsp(text)  L68  詞與詞之間插 U+200B(給 textContent 用的換行點);已含 U+200B 的字串原樣回傳(避免重複注入)

## pipeline/topic_scout.py
_d(s)  L41  
daily_series(points)  L45  points: [(日期 str, 累計觀看)] -> [(日期, 當日觀看, 是否跨日平均)]。
detect_pullback(series, prior_week_api=None, ratio=BACK_RATIO, min_views=BACK_MIN_VIEWS, base...)  L64  兩條觸發任一成立即 hit:①單日爆量 = 最新日 ≥ ratio× 前 base_days 日逐日中位且 ≥ min_
load_series(export_dir, slot, upto=None)  L97  channel_YYYY-MM-DD.json 日期副本 + channel_latest.json -> {video
_top_sources(latest, vid, n=3)  L124  
section_b(export_dir, slot, latest, upto=None)  L133  回推偵測;回傳 (lines, n_hit)。
_lexicon_counts(texts)  L190  
comment_summary(doc)  L204  回傳 (by_flag dict, ai_n, 來源說明, top5 list[(讚, 原句)], n)。summary
section_c(latest, slot, comments_dir)  L217  近 5 支自製片留言訊號;回傳 (lines, 支數)。
run_cmd(cmd, cwd=None, timeout=SUBPROC_TIMEOUT)  L246  跑子行程;回傳 (ok, 輸出文字或一行錯誤)。
key_lines(text, n)  L260  
section_d(slot, runner=run_cmd)  L265  競品與新聞;回傳 (lines, 行數)。runner 可替換(測試)。
section_e(date_s, tmp_dir=None)  L289  
_safe(fn, *a)  L302  章節不得中止整份:例外 -> (['不可用:…'], 0)。
section_persona(name, status_fn=None)  L310  人設狀態(選題會議前置):過期時提醒先重寫人設再派 topic-critic。
_section_a(latest, chdata, slot, now)  L321  
build(slot, date_s, export_dir=None, comments_dir=None, tmp_dir=None, runner=run_cm...)  L326  回傳 (markdown 文字, {章節: 筆數})。
main(argv=None)  L354  

## pipeline/tts_asr.py
parse_spec(spec)  L41  'qwen06' / 'fun_nano' -> (後端, None);'whisper:medium' 或舊參數 'm
class Worker  L54  asr_worker.py 常駐子行程(協定見該檔)。submit 回 Future;同一個子行程的請求由單一執行緒依序
Worker.__init__(self, backend, device, aligner='none')  L58  
Worker._read(self, tag)  L77  
Worker._req(self, x, text=None)  L83  送一筆請求,回 @@RES 的 dict(text 給了才帶進請求,子行程有對齊器時回覆多 words)。
Worker._call(self, x)  L102  
Worker._call_align(self, x, text)  L105  
Worker.submit(self, x)  L109  
Worker.submit_align(self, x, text)  L112  辨識 + 對齊:Future -> (文字, [[字, 起, 迄], ...] 或 None = 對齊失敗/子行程沒有對
Worker.close(self)  L116  
class Whisper  L127  faster-whisper(本行程):主辨識器的字詞時間戳(small),或舊片重渲染的主辨識器(medium)。
Whisper.__init__(self, size, device='cuda')  L130  
Whisper.transcribe(self, x)  L139  
class ASR  L147  統一介面:transcribe(16 kHz float32) -> (文字, words)。ts=None 時不取時間
ASR.__init__(self, spec=PRIMARY, device='cuda', ts=TS_MODEL)  L150  
ASR.transcribe(self, x, text=None)  L167  text = 對齊用文字(簡體、無標點);有對齊器且給了 text 就用對齊器的逐字時間,否則(或對齊失敗)用 whis
ASR._ts_name(self)  L187  
ASR.submit(self, x)  L190  只要文字、在背景跑(副辨識器):回 Future。
ASR.close(self)  L197  
is_bad2(sim, pron_bad, sim_min)  L203  副辨識結果與文案不符:相似度低於主品管門檻,或多音字/換字位置聽成另一個讀音。
fields(m)  L208  qc 紀錄的副辨識欄位(沒跑副辨識 = 關掉 --asr2 或該句最終音檔沒有 wav:asr2 為 None)。
class Second  L213  副辨識器回查。judge(text, hyp2) -> (sim, pron_bad);結果寫回量測 dict m 的 
Second.__init__(self, judge, sim_min, asr=None, spec=SECONDARY, post=None)  L217  
Second.submit(self, m, text, x16)  L223  
Second.collect(self)  L228  
Second.close(self)  L238  
dual_phase(res, sec, retry, max_retry, text_of, wav16)  L243  雙辨識重錄(主品管重試之後呼叫):res 每筆 {w, m, ok, tries};通過主品管、副辨識不一致 -> 重錄
final_check(res, sec, text_of, wav16)  L273  最終音檔還沒跑過副辨識的(語速重錄換了一次嘗試)補跑一次;不一致只記 asr2_bad,不再重錄。
_one(c)  L283  
_key(c, py=None)  L288  對齊用的鍵:英數小寫;中文 = 不帶調拼音並模糊 zh/z、ch/c、sh/s、ng/n。py 給定時用它(多音字位置用
token_reading(py)  L296  標注 -> 帶調拼音 tone3:CosyVoice 拼音 token「[zh][ǎng]」-> zhang3;單一個字
_keys(c)  L305  字 c 所有讀音的對齊鍵(去調、模糊聲母韻尾;多音字取全部)。
pron_pos_bad(ref, hyp, targets)  L311  ref / hyp:已正規化(去標點、同一字形體系)的文案與辨識文字;targets {ref 位置: (原字, 應讀 
_fuzzy(s)  L351  
_syllables(s)  L355  文字 -> [(對齊鍵, 權重, 原文, 是否英文詞)]。拼音 token 組([zh][ǎng])與中文字 = 1 音
_inserts(ref, hyp)  L382  hyp 相對 ref 的插入事件 [(ref 詞元索引起, 迄, 多出的文字, 多出詞元的鍵集合)]:對齊後 hyp 區
common_inserts(ref, hyp1, hyp2)  L402  句中多唸字:ref = 實際送進引擎的文字(engine_text,含拼音 token);hyp1 / hyp2 = 兩

## pipeline/tts_c0.py
report_path(tag)  L40  
script_sha(tag)  L44  
units_of(says)  L50  配音單位(子句,與 build 送合成的文字相同)-> [dict(line, say, mtext, t)];相同文字
pos_map(a, b)  L61  a 的字位置 -> b 的同一字位置(只對到完全相同的區段)。
annotated(t)  L70  t 上會被標注的位置 {位置: dict(pos, ch, value, why)}(詞表逐字 + 規則事件)。
add_g2p(found, u, dis)  L85  g2p 不一致(位置在 mtext)併進 found;沒有標注的位置 value=None,應讀取規則表讀音。
backlog_table()  L98  
risk_of(u, dis, backlog)  L102  一個單位 -> (風險位置 list, 記憶已判要改寫的位置 list, 記憶命中數)。
english_of(says, units)  L124  未驗證的直送英文詞 {詞: 出現在哪些單位序}。
cover(cands, weight=None, limit=None)  L132  貪婪集合覆蓋。cands = {單位序: 元素集合};weight = {元素: 權重}(有給就先比權重總和)。-> 選
select(cands, weight, limit=MAX_SENT)  L148  全覆蓋不超過 limit 就用;超過時依 backlog 命中數優先,取滿 limit。
g2p_file(tag)  L155  
g2p_disagree(tag, units, compute=True)  L159  每單位的 g2p 不一致 list(位置在 mtext);-> (list, 來源說明)。結果依文字存檔,dry-run
build_plan(tag, compute_g2p=True, limit=MAX_SENT)  L178  -> dict(units, items, untested, known, english, note, n_mem)
work_dir(tag, items)  L218  工作資料夾依這批句子與送引擎文字分開,稿或標注變了不會讀到舊 qc 紀錄。
_default_reading(value)  L225  
judge_items(items, seeds, work, norm=None, ph=None, reading=None, simp=None)  L230  每句每 seed 判定;結果掛在 item["positions"][k]["results"] 與 item["en"
tally(x)  L263  
suggestion(x, c, wrongs)  L267  
build_report(tag, plan, seeds, ph=None, sha=None, missing=0, day=None)  L277  
write_report(rep)  L303  
memory_rows(tag, items)  L326  
print_wrong(rep)  L331  
status(tag)  L343  -> (通過, 說明)。
dry_run(tag, plan, seeds)  L359  
run(tag, seeds, plan=None, max_retry=0, norm=None, ph=None, reading=None, simp=None)  L374  真跑一次(不含 dry-run)。-> 結束碼。
main(argv=None)  L402  

## pipeline/tts_chattts.py
speed_prompt(rate)  L95  
load_chat()  L100  
load_spk_pt(chat, path)  L108  安全載入舊格式音色檔:只用 weights_only=True,失敗直接報錯,不退回 pickle。
synth(chat, text, seed, rate, spk)  L116  
_group4(n, lead_liang)  L132  0 < n < 10000 的中文讀法(含內部補零由呼叫端處理)。
int_to_cn(n)  L156  
num_to_cn(tok, year_ctx=False)  L177  
prep_text(text)  L187  發音修正(tts_pron:助詞「著」等多音字誤讀),繁->簡,數字轉中文讀法(本版 ChatTTS 沒有數字正規化器,
engine_text(text)  L200  實際送進 ChatTTS 的文字:prep_text 的結果,句中的逗號換成 COMMA_MARK。
n_syllables(text)  L207  估計音節數:中文一字一音節(數字先轉成中文讀法),英文單字以母音群數估計。
envelope_db(w, hop=0.01)  L215  
voiced_segments(w, rel_db=35.0, merge_gap=0.12, hop=0.01)  L224  
trim_tail_blip(w)  L248  句尾多出的短促聲音(像「嗯」)裁掉:最後一段 <0.4s 且與前段之間有 >= BLIP_GAP 秒靜音才裁
f0_median(w)  L257  
norm_text(s)  L270  
pinyin_seq(s)  L274  
_ratio(a, b)  L279  
similarity(ref, hyp)  L283  
tail_particle(ref, hyp)  L290  
_fuzzy(p)  L295  拼音模糊化:平翹舌、前後鼻音不分(ASR 常混)。
tail_units(s)  L300  比對句尾用的單位序列:中文字(數字、數字之間的「點」除外,ASR 會寫成阿拉伯數字)-> 該字所有讀音(模糊化)的集合;
_unit_match(a, b)  L317  
_weight(u)  L323  單位的份量:英文算字母數,中文字算 3(約一個音節的字母數)。
tail_ok(ref, hyp)  L328  原文最後 2 個單位必須正好是辨識結果的結尾(其後不得多字),防止漏唸句尾字或殘留犧牲段。
tokens(s)  L342  粗略的音節序列(切分原句/犧牲段用):中文字 -> 拼音,英文單字 -> 小寫原字;數字略過。
is_sacrifice(hyp)  L348  切下來的後段是否就是犧牲短句(開頭容許語助詞;短句本身常被截斷,認得出開頭即可),且沒有夾帶別的字(含英文、數字)。
class QC  L358  品管模型:語音辨識(tts_asr.ASR;預設 Qwen3-ASR-0.6B + faster-whisper sma
QC.__init__(self, asr_model, spk_min, pron_rules=False)  L362  
QC.to16(w)  L377  
QC.transcribe(self, w, text=None)  L380  text = 對齊用文字(fa_text);ts_engine = 這次字詞時間戳的來源("qwen3-fa" | "w
QC.close(self)  L386  
QC.embed(self, w)  L390  
QC.set_speaker_base(self, wavs)  L394  
split_words(words, ref)  L407  把辨識字詞分成「原句 / 犧牲短句」:回傳犧牲段起始索引 k(兩段各自與原文、短句的音節相似度依長度加權,取總和最大)。
cut_sacrifice(qc, w, text)  L420  從「原句 + 犧牲尾綴」的合成結果切出原句。回傳 (原句波形, 辨識文字, 字詞, info);找不到可確認的切點時波形
_align_key(u)  L450  
fa_text(text)  L454  對齊器(Qwen3-ForcedAligner)用的文字:prep_text 後的發音單位串起來(簡體、無標點,數字已轉
align_info(w, text, words)  L459  辨識字詞時間對回已知文本(辨識結果只拿來取時間):回傳 pauses = 每個句中停頓的實測靜音(tts_pause.m
comma_only(m)  L477  沒過的只有後處理補得起來的項目(POST_FIXABLE):句中停頓不足且每一處都補得起來(tts_pause.fixa
pron_targets(text, rules=False)  L490  回查讀音的位置 {text 位置: (原字(簡體), 應讀 tone3)}:發音表換字(職稱「長」->掌、動詞「量」->
pron_rule_bad(text, hyp, rules=False)  L504  回查位置(pron_targets)上,辨識出來的字若讀成原字的「另一個讀音」(長 -> 腸 chang2、量 -> 亮
asr_judge(text, hyp, rules=False)  L524  辨識文字與文案的比對(主品管 measure 與副辨識回查共用):回傳 sim_char / sim_pinyin / 
measure(qc, w, text, hyp=None, words=None)  L534  對最終音檔量測各項指標。回傳 (最終波形, 指標);只有「ASR 確認多出語助詞且其前有足夠靜音」時才會再裁尾。
from_cache(qc, path, text)  L563  既有音檔(舊快取):溫和裁切後直接量測。
from_synth(qc, chat, text, seed, rate, spk)  L573  合成「原句 + 犧牲尾綴」-> 裁頭 -> 切掉犧牲段 -> 量測。
from_plain(qc, chat, text, seed, rate, spk)  L585  不加犧牲尾綴的合成(舊作法,句尾可能被截)。只在加尾綴怎麼試都不過時拿來一起比分數
fit_spk(res)  L592  聲紋相似度隨語句長度上升(短句天生偏低),以整批(第一輪)的 sim ~ a + b*log(dur) 穩健迴歸為基準。
spk_thr(a, fit, dur)  L607  
check(m, base_f0, base_spc, a, fit)  L612  
_public(m)  L658  寫進報告的指標(去掉內部用欄位)。
main()  L663  

## pipeline/tts_cosy3.py
log(msg)  L64  
stop_retry(m, tries)  L68  主品管重錄迴圈要不要停:只差後處理補得起來的項目就不再換 seed;詞界長停頓、comma_runon 不算(comma
wait_vram(tag)  L73  排隊拿全機 GPU 鎖(gpu_lock.py;含 nvidia-smi <= 3000 MiB;父行程 make_ve
_norm(t)  L79  
engine_text(mtext)  L88  送進 CosyVoice 的文字:英文寫法 -> 書名號冒號刪除 -> 拼音標注 -> 簡體 -> 數字讀法/標點(標注
norm_hyp(t)  L99  辨識文字對齊 engine_text 的寫法:簡體 + 數字讀法/標點(同 engine_text 的後兩步)。
asr_inserts(engine, hyp1, hyp2)  L104  句中多唸字(品管 F,2026-10-22):主/副辨識在同一位置都比 engine_text 多出字 -> [dict
requal(tag, dry_run=False)  L112  --requal <tag>:不載模型,對 build/<tag>/tts_cosy3/ 的既有 qc.json 離線重
statement(text)  L136  
class Worker  L142  
Worker.__init__(self, ref, ref_text, device, log_path)  L143  
Worker._read(self, tag)  L156  
Worker.call(self, **job)  L162  
Worker.close(self)  L167  
load_mono(path)  L173  
resume_dir(tag)  L185  環境變數 TTS_RESUME_DIR 有設才啟用:<TTS_RESUME_DIR>/<tag>/;沒設回傳 None(
resume_key(text, seed, speed, voice, ref_text, device)  L191  一次合成嘗試的鍵:送引擎文字 + seed + speed + 參考音檔名與逐字稿 + 合成裝置。
synth_one(worker, rdir, key, text, seed, speed, out)  L197  一次合成嘗試 -> out(raw wav,裁切/FX 前);回傳 (worker 結果, 是否沿用續跑快取)。
resume_status(d)  L213  --resume-status:印續跑快取目錄(單一 tag 或 TTS_RESUME_DIR 根)有幾筆、幾 MB。
env_limit(name, default)  L221  重錄上限的預設值:環境變數 name(CV_TTS_MAX_RETRY / CV_TTS_RATE_SEEDS;Cola
main()  L235  

## pipeline/tts_cosy_text.py
_load(path)  L31  
_word_re(w)  L50  
unsay(text)  L54  @say 已把 cosy_terms 登錄的英文詞換成 ChatTTS 寫法(say_terms.json,例 EA -
_sub_term(text, w, v)  L73  整詞 w 換成 v。v 頭/尾是 CJK 字時,原文該詞緊鄰的空格若另一側也是 CJK 字(或中文標點),去掉那個空格
apply_terms(text, extra=None)  L99  英文整詞(前後不是英文字母或點)換成 CosyVoice 寫法;中文寫法兩側原本的英文空格在 CJK 旁會去掉(_sub
_zhu_at(text, i, w)  L116  text[i] 的「著」是否落在 ZHU_WORDS 的詞 w 裡(含 ZHU_NOT_NEXT 的排除)。
fix_zhe(text)  L122  非 ZHU_WORDS 的「著」換成「着」。回傳 (文字, 有沒有換)。
_pron_words(text)  L132  cosy_pron.json 詞表標注(長詞優先,標注後原詞已不存在,不會再被短詞命中)。回傳 (文字, 命中的詞)。
_compile_rules(raw)  L143  -> (chars, words, regs)。words = [(詞, 字, 位置, py|None=keep, un
_rule_tokens(raw)  L165  
_tokenizer_tokens(tokenizer_py=None)  L171  
_load_rules()  L175  
rule_events(text)  L189  多音字規則會標注的位置:[(位置, 字, 標注, 命中鍵, 來源 word|re|default, unverified
apply_rules(text)  L215  多音字語境規則單獨標注(不含詞表;apply_pron 才是合併版)。回傳 (文字, 命中鍵 list;鍵 = 「詞→標
_memory_marks(text)  L228  語境讀音記憶要換上標注的位置 {位置: (標注值, 命中鍵)};表空回 {}。
_trim_spans(spans, marks)  L238  記憶位置落在詞表區段內且標注不同:區段切開,讓出該字(其餘字沿用詞表標注);對不齊的區段不動。
_word_spans(text)  L255  cosy_pron.json 詞表在「原文」上的命中區段(長詞優先、區段不重疊;記憶改標注的字讓出,見 _trim_sp
_merge_memory(text, spans, ev, marks)  L273  規則事件併入記憶(來源 memory,記憶贏);值與原本相同的位置不動,命中鍵不變。
_live_events(text, spans)  L282  原文上的規則命中,去掉落在詞表區段內的(詞表贏);再併入語境讀音記憶。
annotate_mode(mode=None)  L301  table(現行)| all;mode 沒給讀環境變數 COSY_ANNOTATE,不認得的值當 table。
_token_set()  L308  
polyset_name(polyset=None)  L312  rules | risk(預設)| all;沒給讀環境變數 COSY_POLYSET,不認得的值當 risk。
_moe_pron()  L318  
_risky(readings)  L326  審訂表讀音去掉又音/讀音/語音,再去掉「只差輕聲」(輕聲讀音的音節另有帶調讀音)後,仍有 >= 2 個不同讀音。
_backlog_chars()  L335  
build_risk()  L342  risk 集合 = 審訂表有實質不同讀音的字(_risky)∪ pron_rules ∪ pron_backlog ∪ 
polyphone_chars(polyset=None)  L350  多音字集合(COSY_POLYSET):rules = pron_rules.json 的字;risk(預設)= pip
_mark_final(fin, tone)  L363  韻母加調號(a/e 優先、ou 標 o、其餘標最後一個母音);輕聲不標。
py_tokens(py3)  L371  tone3(zhang3、lv4、yue4、de5)-> 標注 `[zh][ǎng]`。寫法照 TERM_ANNOT /
_g2pw_row(text)  L391  g2pW 對整句的逐字 tone3(有裝且模型在才用);不可用回 None。
_pypinyin_row(text)  L405  pypinyin 詞級讀音(每段連續漢字整段丟進 lazy_pinyin,由它斷詞取詞音);沒裝回 None。
_memory_ok(text)  L422  state ok 的語境讀音記憶裡 py 是拼音標注的位置 {位置: 標注}(現行只套 fix=mark 的;all 模
poly_marks(text, mode=None, spans=None, ev=None, polyset=None)  L432  原文(pron_source)每個多音字位置 -> [(位置, 字, 標注|None, 來源, 是否 all 模式新增)
_e1_marks(text, spans, ev, mode=None, polyset=None)  L469  all 模式新增標注 [(位置, 字, 標注)];table 模式回 []。
apply_pron(text, mode=None, polyset=None)  L476  拼音標注:語境讀音記憶、詞表(cosy_pron)與多音字規則(pron_rules)都在原文上比對(規則看得到原字前後
pron_source(say)  L504  apply_pron 看到的文字:unsay -> 英文寫法 -> 書名號冒號刪除(語境讀音記憶的語境鍵以此為準)。
pron_text(say, mode=None)  L509  送配音的文字(@say 後)依 tts_cosy3.engine_text 同樣順序做到拼音標注為止:unsay -> 
_hit_value(h)  L515  命中鍵的標注:詞表的詞 -> PRON 標注;規則/著/E1 的鍵「詞→標注」「字→標注」-> 箭頭後面。
pron_hits(say)  L520  這句命中的讀音詞與其標注 {詞: 標注}(tts_cosy3 存進 .qc.json 的 pron_hits)。
pron_tokens(say)  L525  這句送進引擎的拼音標注 token 序列(engine_text 之後的簡體/數字正規化不動 token,可與舊紀錄的 
pron_changed(rec, say)  L530  音檔旁的 .qc.json 紀錄(rec)錄音時的讀音標注是否與目前讀音表不同(cosy_pron.json 改過 ->
term_hits(say)  L542  這句命中的英文寫法 {英文詞: 寫法}(同 apply_terms 的長詞優先順序;tts_cosy3 存進 .qc.j
_en_words(text)  L552  去掉拼音 token 後的英文字母單字序列(OpenCC 與數字/標點正規化不動英文字母,可比對舊紀錄的 engine_
terms_changed(rec, say)  L557  音檔旁的 .qc.json 紀錄錄音時的英文寫法(cosy_terms.json)是否與目前不同(Roblox 改 Ro
audit_cache(tts_dir)  L570  唯讀稽核配音快取目錄(含 sub/):回傳讀音或英文寫法已變更、下次配音會重錄的 [(單位, 文字)]。不動任何檔。
asr_rejects(text, hyps, table=None)  L585  英文詞唸錯回查(cosy_terms `_asr_reject`,純函式):句子含原文詞,且某個辨識結果含該詞的否決字串
unverified(text)  L600  這句用到的未聽審讀音標注與直接唸的英文詞(聽審頁優先聽用)。
analyze(texts)  L614  texts = 送配音的文字 list(@say 後)。回傳同 tts_terms.analyze 的格式:unappl
check_e1()  L637  E1 全標注可轉率(資訊,不影響 --check 結束碼):審訂表多音字的每個讀音能否轉成 tokenizer 有的標注
check_pron(tokenizer_py=None)  L655  讀音表(cosy_pron.json)與多音字規則(pron_rules.json)每個 [..] token 都必須在
_tidy(say)  L661  dry-run 用:跟 pron_text 同樣先做 unsay -> 英文寫法 -> 書名號冒號刪除,再進讀音標注。
dry_run(tag)  L666  讀 <tag>\script.txt 每句的 say 文字(@say 之後),數多音字規則會改到幾句;印摘要,不配音、不

## pipeline/tts_dispatch.py
log(msg='')  L56  
count_lines(tag)  L62  句數:<tag>\script.json 的 sections[].lines;沒有就數 script.txt 非空非 
estimate_hours(lines)  L81  
parse_publish(s)  L85  board 的 publish 字串 -> datetime(本地);只有日期 = 當天 PUBLISH_DEFAULT
board_publish(tag)  L98  
ledger_file()  L108  
read_ledger()  L112  
write_ledger(**kw)  L126  
_ts(s)  L133  
open_jobs(rows, backend, now=None)  L140  某後端進行中的 {tag: start 事件}(最後事件是 start);Kaggle 超過 KAGGLE_STALE_
weekly_used(rows, backend, now=None)  L157  近 WEEK_DAYS 天該後端已結束工作的 GPU 小時(沒填 gpu_hours 就用 end-start)。
kaggle_availability(tag, need_h, rows, now=None)  L176  -> (可用, 理由)。
colab_availability(tag, rows, publish, now=None, check_deadline=True)  L193  
survey(tag, now=None)  L203  -> (建議後端, {backend: (可用, 理由)}, 理由清單, 預估小時)。三個後端都評估,不因前一個可用就停
choose(tag, prefer, now=None)  L224  -> (backend|None, 理由清單, 預估小時);只處理使用者指定的 prefer。backend None 
board_set(tag, text)  L247  
kaggle_cmd_for(tag)  L254  
launch_kaggle(tag, foreground=False)  L258  foreground -> 回 kaggle_run run 的結束碼;否則 detached 子行程(log 寫 ru
pack_colab(tag)  L276  
run_import(zip_path)  L283  
now_iso()  L288  
local_command(tag)  L292  
colab_user_message(tag, zip_path)  L296  
colab_fallback_note(tag)  L307  
c0_status(tag)  L314  C0 試配狀態 -> (通過, 說明)。
advise(tag)  L323  沒給 --prefer:只印三後端狀態與建議,不做任何動作;回 EXIT_ASK。
verify_ok(tag)  L335  打包前:配音稿與凍結一致(tts_script.py --verify);不一致就擋(--refreeze-ok / C
dispatch(tag, prefer=None, dry_run=False, foreground=False, skip_c0=False)  L345  
colab_done(tag, zip_path)  L400  
colab_cancel(tag)  L415  
gpu_lock_first_line()  L422  
status()  L432  
main(argv=None)  L445  

## pipeline/tts_g2p.py
_bopomofo(s)  L54  注音 -> tone3。支援 ˊˇˋ˙(前綴或後綴)與尾端數字 1-5;沒標 = 一聲。解析不了回 None。
_fix_v(base)  L81  ü:jqxy 後寫 u(ju、xue、yun),其餘保持 v(lv、nve)。
norm_py(s)  L86  任何拼音/注音寫法 -> tone3 小寫(zhang3、lv4、xue4;輕聲 5)。解析不了回 None。
_split(r)  L118  
same_reading(a, b, neutral_loose=True)  L122  兩個讀音(任何寫法)是否算同一個。neutral_loose:同音節、其中一邊輕聲 -> 算同。任一邊解析不了 -> 視
_char_reading(c)  L135  單一個字的預設讀音(pypinyin);沒裝或查不到回 None。
mark_reading(py)  L145  送引擎的標注 -> tone3:`[zh][ǎng]` 拼起來轉;單一個字(「着」「的」)-> 該字預設讀音。
_syllable_units(ann)  L154  cosy_pron 詞表標注字串 -> 每個字的讀音 list:原字保留的位置 None,拼音 token 組 -> t
expected(text)  L182  規則表對「規則收的多音字」每個位置給的讀音 -> {位置: (字, tone3, 來源)}。
_warn(msg)  L214  
model_dir()  L220  
_make_converter(allow_download=False)  L224  建 g2pW 轉換器(style=pinyin,CPU)。HF_HOME 預設導到 tmp(不寫 C 槽)。
converter()  L240  延遲載入;失敗回 None 並印一次警告。
set_converter(conv)  L251  測試/外部注入預測器:callable(list[str]) -> list[list[str|None]](同 G2P
predict_many(texts, conv=None)  L259  -> 每句 [(位置, 字, tone3)](只含 pron_rules 有列的字、且 g2pW 有給讀音);g2pW 
predict(text, conv=None)  L282  一句 -> [(位置, 字, tone3)] 或 None(模型不可用)。位置 = 在傳入文字中的字元索引。
compare(text, preds, neutral_loose=True)  L288  規則表 vs g2pW(preds = predict 的輸出,text = 同一份原文)-> 不一致清單 [dict(
disagreements(text, conv=None, neutral_loose=True)  L295  tts_cosy3 用:這句(say 文字)g2pW 與規則表不一致的位置清單([] = 全一致);g2pW 不可用回 
disagreements_many(texts, conv=None, neutral_loose=True)  L302  批次版 disagreements,一次推論 -> {text: 不一致清單 | None}。g2pW 不可用或推論失敗
record_fields(result, text)  L319  品管紀錄要加的欄位:有結果才寫 g2p_disagree([] = 全一致也寫);None(不可用/失敗)不寫。
class Background  L325  背景執行緒批次算 disagreements_many(結果只依文字,不必擋主流程)。任何例外都吞掉記 log,該批退回
Background.__init__(self, texts, log=None, conv=None)  L330  
Background._run(self, conv)  L339  
Background.wait(self)  L348  -> {text: 不一致清單 | None};執行緒失敗或逾時回 {}。
_verified_keys()  L358  
verified_cases(sentences)  L362  已驗證答案 -> [dict(text, pos, ch, ans, src)]。
label_cases(path)  L390  --labels:TSV `句子<TAB>位置(0 起算)<TAB>正確拼音`(使用者聽審判定的獨立答案)。
corpus_sentences(limit=None)  L403  文案語料(所有 <片名>\script.txt 的句子,tts_pron_verify.corpus 同一套)+ 規則造
_pct(a, b)  L417  
evaluate(sentences, conv, extra_cases=(), neutral_loose=True)  L421  -> dict(preds={句: {位置: tone3}}, cases=[含 g2p/rule 判定], secs,
eval_report(ev, sentences, neutral_loose=True, top=40)  L437  markdown 準確率表。三個證據層級分開寫:
main()  L509  

## pipeline/tts_key.py
_sha1(s)  L19  
cmd_sig(tts_cmd)  L23  外部合成指令(字串清單)-> 引擎參數簽章。
audio_key(engine, sig, voice, rate, say)  L33  
full_key(audio, qc_ver=None)  L39  
audio_part(key_text)  L43  .key 檔內容 -> 音檔鍵(去掉品管版本)。
trim_key(key_text, wav_sha1, trim_ver, final, comma_profile='std')  L48  裁切後音檔(.trim.wav)的鍵:只看音檔鍵與音檔內容,品管版本變動不重轉。
legacy_key(engine, tts_cmd_text, voice, rate, say, suffix='')  L55  
legacy_trim_key(key_text, wav_sha1, trim_ver, final)  L59  

## pipeline/tts_moe.py
_open(path)  L31  
compact(entries)  L36  辭典條目 list -> (pron dict, words list, word_pron dict)。純函式(測試用
build(src)  L77  
load_word_pron()  L96  
load_pron()  L103  
load_words()  L110  
lookup(q, pron=None, words=None, word_pron=None)  L117  回傳可印的行(list[str])。
polyphones(pron=None, top=50)  L146  
main(argv=None)  L156  

## pipeline/tts_pause.py
units(text)  L63  發音單位 [(字串, 起始字元位置, 結束字元位置)]:中文一字一個、英文一個單字一個、數字一位一個;標點與空白不算。
hyp_units(words)  L68  辨識字詞 [(字詞, 起, 迄)] -> [(單位, 起, 迄)]:一個字詞內的各單位等分它的時間;阿拉伯數字換成中文數
align(ref, hyp, dur, key=None)  L78  ref = 原文的單位字串清單,hyp = hyp_units 的結果。回傳 (每個原文單位的 [起, 迄], 是否對到
char_map(a, b)  L112  a 的每個字元位置(0..len(a))對到 b 的字元位置:相同的區段一對一,被替換的區段(@say、發音表、數字讀法
char_starts(text, times, dur, pauses=())  L122  text 每個字元位置的秒數(長度 len(text)+1):發音單位 = 它開始的時間(英文單字內依字母等分);標點與
comma_params(text, profile='std', std_target=None)  L148  該單位文字適用的 dict(COMMA_MIN, COMMA_MAX, COMMA_TARGET)。std 一律回現行常
soft_skip(p)  L162  軟停頓(頓號)不足且補不起來(沒有低谷):不插、不列 comma_short / comma_bad。
out_of_range(pauses, text=None, profile='std')  L167  有任何一處句中停頓不在該單位適用的 [COMMA_MIN, COMMA_MAX] 內(決定要不要跑 fix_pauses
comma_bad(pauses, text=None, profile='std')  L174  修整後仍低於該單位適用下限的停頓位置 ["前一字|後一字"];軟停頓(頓號)不算。
comma_runon(pauses)  L180  模型連讀的句中標點 [dict(at, before)]:原始音檔(後處理前)的靜音 < COMMA_RUNON_MIN
runon_from_rec(rec)  L185  既有品管紀錄的連讀處(最終音檔已插過靜音,不能重量):有 comma_runon 欄位就用它;舊紀錄用 pause_fi
judge_runon(m)  L196  品管項 comma_runon(check 算完 fails/score 後呼叫):只在原始音檔量一次,後處理重量測的 
comma_inserted(rec)  L206  靠插入靜音補的逗號位置 ["前一字|後一字"](品管紀錄;頓號不算),listen_page 優先聽用。
attempt_rank(m)  L212  挑最佳嘗試的排序鍵(大者佳):連讀處數少的優先,其次品管分數。
retry_best(r, attempt, max_retry, stop)  L217  主品管重錄迴圈:r = dict(w, m, ok, tries)。attempt(r) -> (w, m, ok) 合
frame_db(w, sr, hop=HOP)  L232  
find_pause(env, lo_t, hi_t, hop=HOP)  L240  在 [lo_t, hi_t] 內找停頓:有靜音段(低於峰值 - COMMA_REL_DB)就取與這段時間重疊的最長那段(
measure_pauses(w, sr, text, times, soft_at=())  L274  text = 送配音的文字(prep_text 的結果),times = align 得到的各單位 [起, 迄]。
fixable(p)  L296  停頓不足時能不能用插入靜音補:該處有(短的)靜音,或至少有明顯的能量低谷。兩字連音、沒有低谷的不補(會切在字中間)。
_join(a, b, sr, gap=0)  L301  
fix_pauses(w, sr, pauses, text=None, profile='std', edits=None, std_target=None)  L311  依 measure_pauses 的結果修整波形(由後往前,前面的時間不受影響)。回傳 (新波形, {停頓的 i: "i
insert_mids(edits, sr)  L338  fix_pauses(edits=) 的紀錄 -> {停頓的 i: 插入的靜音中點在新波形中的秒數}(前面各處插入/剪除
load_qc(path)  L348  品管紀錄 .qc.json;沒有或壞掉回 None。
inserted_ats(rec)  L357  舊品管紀錄裡插入過靜音的停頓位置 {"前一字|後一字"}(pause_fix act=insert,與驗證過的 paus
_weight(u)  L365  單位的份量:英文算字母數,中文字算 3(約一個音節的字母數;同 tts_chattts._weight)。
head_match(ref, hyp, key=None)  L370  插入位置驗證(純函式):插入的靜音之前那段音檔的辨識結尾,是否對到原文該停頓標點前的字。
inner_runs(env)  L399  句內的靜音段 [(起格, 迄格)]:低於峰值 - COMMA_REL_DB,且不碰檔頭/檔尾。
word_bounds(text)  L418  詞邊界:jieba 斷 units(text) 串起來的字串,回傳發音單位序號集合 {k: 單位 k 與 k+1 之間是
_jieba()  L440  延遲載入 jieba(只載一次);字典快取放 repo 的 tmp\(不寫 C 槽)。失敗回 None。
stray_keep(s)  L457  該筆多餘停頓剪短後留下的靜音長度:詞邊界 STRAY_WB_KEEP,詞中 STRAY_KEEP。
wb_long(strays)  L462  詞界自發長停頓(kind="wb"、sil >= STRAY_WB_FAIL)的位置 [at];tts_cosy3 記 
find_strays(w, sr, text, times, pauses, min_sil=STRAY_TRIM_MIN, bounds=None)  L467  不在句中標點位置的靜音(>= min_sil 秒;其中 sil >= STRAY_MIN 的才算品管未過)。text/t
fix_strays(w, sr, strays)  L501  把多餘停頓剪到 stray_keep 秒(詞中 STRAY_KEEP、詞邊界 STRAY_WB_KEEP;由後往前):從
rms_db(x)  L519  dBFS;空的或全零回傳 -120。
clean_pauses(w, sr, pauses)  L524  把每個量到靜音的句中停頓 [t0, t1] 內部換成數位靜音,兩端各留 PAUSE_EDGE 秒淡出/淡入(長度不變)。
clean_tail(w, sr)  L542  句尾靜音區(最後一段語音之後)若能量先降後升(比先前最低點高 TAIL_RISE_DB 以上,且高於 TAIL_FLOO

## pipeline/tts_polyphone.py
toned(s)  L38  字串每個位置的帶調拼音(非中文字 = None);同一段連續中文字一起取,保留詞語語境。
readings(c)  L50  
_key(p)  L55  對齊用:去聲調、平翹舌與前後鼻音不分。
scan_unit(TC, text, asr)  L60  一個配音單位 -> [dict(char, said, expect, heard, heard_char, kind,
main()  L94  

## pipeline/tts_pron.py
_mark_and_fix(text)  L89  回傳 (送進 TTS 的文字, 被替換的「著」位置 {索引: 替換字})。通用表 WORDS 在最後套用(不產生位置紀錄
drop_title_colon(text)  L115  書名號內的冒號(半形與全形)直接刪掉:「《惡靈古堡:安魂曲》」連著唸,不產生停頓(prep_text 會把冒號換成逗號 
apply(text)  L121  送進 ChatTTS 的文字(繁體,尚未轉簡體)。沒有要修正的字時原樣回傳。
_fixed_same_len(text)  L126  換字後、尚未刪書名號冒號的文字(與 text 逐字對位,供 rule_positions/changes 使用)。
rule_positions(text)  L131  「著」以外被換字的位置 {text 的索引: 換上去的字}(通用表、職稱「長」、動詞「量」;語助詞 NO_CHECK 除
changes(text)  L141  聽審頁用:「著」以外的換字清單,如 ["多元長→掌"]。書名號內刪冒號不列入(同「著→者」,不是需要人耳確認的換字)。
key_text(text)  L149  快取鍵用的文字:沒被修正的句子就是原文(鍵與沒有這個機制時完全相同);被修正的句子用修正後文字。
qc_pair(text, hyp, norm)  L154  品管比對用。norm = tts_chattts.norm_text。

## pipeline/tts_pron_verify.py
class PyPhon  L45  真正的讀音查詢(pypinyin,走 tts_asr 的 _one / _key,與 pron_pos_bad 同一套鍵
PyPhon.__init__(self)  L48  
PyPhon.one(self, c)  L52  
PyPhon.all(self, c)  L55  
PyPhon.key(self, c, py=None)  L59  
default_norm(s)  L63  與品管同一個正規化(tts_chattts.norm_text:繁轉簡、去標點與數字)。
simp(c)  L72  
class Rule  L80  is_default=True:always 字的「預設標注」(model_default;id `得#default`
Rule.__init__(self, ch, idx, entry, default, is_default=False)  L83  
Rule.kind(self)  L93  
build_rules(raw=None)  L97  規則清單:每個 always 字的預設標注(model_default,`<字>#default`)+ 非預設讀音規則(
rule_of(rules, text, event)  L113  命中事件(CT.rule_events 的一項)屬於哪條規則。word 事件用「詞→標注」鍵;re 事件找檔內順序第一條
rule_hits(rules, mtext)  L135  一句(測量文字)命中的規則 -> {規則 id: ([位置], 命中鍵)}(含 always 字的預設標注 `<字>#d
corpus()  L149  所有 <片名>\script.txt 的句子 -> [(片名, 測量文字 mtext, say 文字)];依 。！？ 切
_gen(items, rng)  L183  由正規式語法樹造一段會比對成功的字串 -> (前文, 本體, 後文);正向 lookbehind 補在前、lookahe
synth_sentences(rule, rules, used, n)  L237  用規則造句(最多 n 句;造出的句子都經 rule_hits 確認真的被這條規則命中):words 型規則用詞套句型,r
plan(per_rule=2, only=None, seed=20261021)  L270  -> (items, rules, stats)。item = dict(id, rule, ch, py, mtext
locate(ref, hyp, targets, ph)  L305  ref / hyp 已正規化;targets {ref 位置: (原字, 應讀 tone3)}。回傳 {ref 位置: 
verdict(h, oc, want, ph, strict=False)  L318  辨識到的字 h 對原字 oc、應讀 want(tone3):miss 沒對上 / same 原字(看不出聲調)/ rig
combine(vs, sims_ok)  L337  主/副辨識的字級判定 -> wrong | undetermined | right。
prepare(text, targets_by_pos, norm)  L349  文案標出規則位置 -> (正規化後的 ref, {ref 位置: (原字, 應讀)}, [原文位置]);位置數對不上(正
judge_record(rec, targets_by_pos, norm=None, ph=None, sim_min=SIM_MIN)  L366  一筆 tts_cosy3 qc 紀錄(rec:measure_text/text、asr、asr2、sim、asr2_s
targets_for(item)  L393  item 的規則位置 -> {位置: (簡體原字, 應讀 tone3, strict)};strict = always
busy_reason()  L400  顯示卡已用 >3000 MiB 或有別的配音/出片行程就回原因字串,空閒回 None。
out_wav(work, seed, item)  L420  
synth(items, seeds, work, max_retry)  L424  每個 seed 一批呼叫 tts_cosy3(子行程);已有 .qc.json 的單位不重錄。-> 失敗的 seed l
read_rec(work, seed, item)  L449  
judge_all(items, seeds, work)  L454  -> [dict(item, seed, rec, judge|None)]。
record_memory(results, run, ph=None)  L465  判定結果寫進語境讀音記憶(rule_hits 的位置以 mtext 為準)。-> Counter(動作)。
_cell(s, n=60)  L478  
write_report(path, date, rules, items, results, seeds, args_note='')  L482  
main()  L527  

## pipeline/tts_report.py
frame_db(x, sr)  L25  
_newer(a, b)  L31  a 存在且不比 b 舊(b 不存在視為 a 較新)。
_read_wav(path)  L36  
load_timeline_voice(tag)  L41  回傳 (timeline dict, 配音軌單聲道 float, 取樣率)。完整渲染過 = timeline.json 
main()  L76  

## pipeline/tts_runon.py
load_recs(tag)  L26  
fill_soft(rec)  L30  舊紀錄的 pauses 沒有 soft:同 tts_chattts.align_info 由文字判頓號。
replay(tag)  L44  -> (句數, [(句號, [dict(at, before)])])。
report(tags)  L54  
sandbox(tag, lines, max_retry)  L63  
main()  L91  

## pipeline/tts_script.py
script_lines(tag)  L40  [(ln, say)],與 freeze.narration_lines 同源(say = 行尾 say 欄,否則 te
_units(v)  L55  標注值 -> [(ch|py, 內容)]:一般字一單位;拼音 token 聲母+韻母併成一單位。
readable(v)  L73  
annotate(orig, v)  L77  原文片段 + 標注值 -> 字[拼音](對不齊就整段 原文[拼音])。
pron_view(say)  L85  -> (顯示文字, 命中清單[str], unverified 規則事件[(位置, 字, 鍵, 來源)], 送引擎前的原
_pieces(s)  L116  
_ok_len(w)  L120  
extract_words(tag, lines, moe_words=None, sub_words=(), cut=None)  L124  抽本片專名 + 本片出現的教育部 2–4 字詞條。lines = [(ln, say)];cut = 斷詞函式(預設 j
verify(tag, out=print)  L169  0 = 一致或未凍結;1 = 不一致(列行號)。
_cell(s)  L207  
long_clauses(text)  L211  標點間子句寬度 > SUB_MAX_W(與字幕斷句同一個 _sub_pieces / _dw)-> [(子句, 寬度)]
build_script(tag, write_words=True, force_words=False)  L222  
main(argv=None)  L303  

## pipeline/tts_split.py
split_clauses(say)  L19  回傳 [(子句文字, 句後停頓秒)];最後一句的停頓為 0(行與行之間的停頓由時間軸負責)。

## pipeline/tts_tail.py
frame_db(w, sr, hop=0.005)  L21  每 hop 秒一格的 RMS(dB)。
_rel_db(seg, peak_db)  L31  
tail_stats(w, sr)  L38  句尾聲學指標(相對該句 10ms 影格 RMS 峰值)。
quiet_runs(w, sr, rel_db=GAP_REL_DB, min_len=0.15, hop=0.005)  L55  低於峰值 rel_db 的連續區段 [(起, 迄)](秒),含開頭與結尾的靜音。
trim_bounds(w, sr, head_keep=HEAD_KEEP, tail_keep=TAIL_KEEP, rel_db=TRIM_REL_DB)  L75  溫和裁靜音的保留範圍 (a, b)(樣本):門檻相對該句峰值,頭留 head_keep、尾留 tail_keep。全靜音
fade_out(x, sr, sec=FADE)  L88  尾端線性淡出;x 可為 (n,) 或 (n, 聲道)。回傳新陣列。
gentle_trim(w, sr)  L98  溫和裁靜音 + 尾端淡出。回傳 (波形, 頭裁秒數, 尾裁秒數)。

## pipeline/tts_term_qc.py
_pinyin(c)  L31  
_key(c)  L41  單字鍵:英數小寫;中文 = 不帶調拼音並模糊 zh/z、ch/c、sh/s、ng/n(同 tts_asr._key);沒
_keys(s)  L49  [(原字位置, 鍵)];只留英數與中日韓字(空白、標點、引號略過)。
phon(s)  L54  
ratio(a, b)  L58  
frag(text, hyp, a, b)  L62  原文 text[a:b] 在辨識文字 hyp 的對應片段:用拼音鍵對齊,取 [a, b) 之前最後一個對到的字之後、之後
cands(term, text=None)  L89  term 的可接受寫法:原詞拼寫 + cosy_terms 寫法 + _asr_alias(+ 全大寫縮寫的逐字母唸法,
sounds_like(f, cs)  L107  片段 f 與候選寫法 cs 的最高音近分數(拼音鍵字串相似度,0–1)。
direct_open(texts)  L118  texts = 送配音文字 list(第 i 個 = 第 i+1 行)。回傳 {詞: [行號]}:在 _direct、不
_lkey(t)  L128  
alias_back(hyp, text)  L132  辨識結果裡 _asr_alias 的音譯/別寫換回原文英文詞(只換這句文字有的詞;同 tts_cosy3.asr_loo
loose_misses(text, hyp, found_min=0.75, sound_min=SOUND_MIN)  L141  英文段在辨識裡找不到(同 asr_loose:別名換回後英數段相似度 < found_min)時,取該位置片段,與原詞/
en_terms(text)  L163  送引擎仍是英文的登錄詞位置 [(詞, 起, 迄)]:_direct 的詞 + cosy_terms 寫法含 3 個以上連
_frags(items)  L177  
inconsistent(items, min_sim=CONSIST_MIN, sound_min=SOUND_MIN, orig_min=ORIG_MIN)  L189  items = [(單位, 量測文字, 主辨識)]。同一詞 >= 2 句:多數寫法 = 與最多片段相似(>= min_s
off_major(text, hyp, majors, min_sim=CONSIST_MIN, orig_min=ORIG_MIN)  L212  重錄後檢查:這句仍直送英文的詞,片段與 majors 的多數寫法差異大且不接近原詞/別名 -> [dict(term, 
_records(tag)  L225  
report(tag, stray_fail)  L239  
stray_stats()  L263  全部 build/*/tts_cosy3 的詞界多餘停頓(stray_fix kind=wb 的 before)分布,與
main(argv=None)  L284  

## pipeline/tts_terms.py
script_texts(tag, root=None)  L25  
has_error(res)  L31  
report(res, n)  L35  
main()  L60  

## pipeline/tts_tone.py
semitone(f)  L55  
tone_of_pinyin(py)  L59  帶調拼音(數字調 1..5,5 = 輕聲)-> 聲調整數;沒有數字回 None。
f0_track(wav, sr)  L65  整段音檔的 F0 軌跡 -> (times, f0_hz);無聲幀為 nan。librosa.pyin,CPU。
estimate_range(wav=None, sr=None, track=None)  L75  說話者音域:有聲段 F0(半音)的 p10 / p90 / 中位數。可傳現成 track=(times, f0) 省掉重
_smooth(st)  L88  3 點中位數去掉單幀八度跳。
_main_run(times, sel, t0, t1, gap=5)  L96  擴窗後可能蓋到鄰字的有聲幀:有聲幀以 > gap 幀的無聲隔開成幾段,只留與核心 [t0, t1] 重疊最多的那段。
features(times, f0, t0, t1, rng, pad=WIN_PAD)  L112  字時段的 F0 特徵(正規化音域);有聲幀不足回 None。
decide(ft, th=None)  L129  特徵 -> (聲調, 餘裕)。順序:輕聲 > 三聲(凹) > 四 > 二 > 三聲(低) > 一聲。餘裕 = 決定性比較
classify_track(times, f0, t0, t1, rng, th=None, pad=WIN_PAD)  L146  
tone_at(wav, sr, t0, t1, speaker_range, th=None)  L155  單字時段 [t0, t1] 秒的聲調。前後各多取 0.3 秒讓 pyin 有上下文。
check_tones(wav, sr, say_t, hits, speaker_range=None, th=None, track=None)  L163  hits = [(pos, 預期聲調)];回傳每個命中字的 dict(pos, expected, got, ok, c

## pipeline/visual_check.py
cn2int(s)  L74  
cn_to_arabic(t)  L87  旁白裡的中文數字換成阿拉伯(三十九點九九 -> 39.99;五億 -> 5億)。只換含數字字元的連續段。
norm(s)  L93  
variants(s)  L99  
canon_num(tok)  L103  
strip_titles(t)  L112  去掉書名號內容、書名/產品裡的數字(現代戰爭4、PS5)、序數(第3個),剩下才是數據數字的判斷對象。
cn_parse(s)  L119  中文數字(含萬/億、小數「點」)轉數值:三萬一千 -> 31000;三十九點九九 -> 39.99。
canon_val(v)  L133  
number_values(text, strip=True)  L137  回傳 [(數值, 是否日期)]。阿拉伯數字認 萬/億 單位;中文數字(值 <= weak_cn_max 的兩年、一個略過
number_tokens(text)  L155  
num_in(v, pool)  L159  v 是否在 pool 裡(完全相等,或近似:v >= 100 差 10% 內如三萬一千多對 31517;v >= 10 
pos_words(text)  L169  
objects(text)  L184  具體物件(非數字):書名號、英文專名、jieba nr/nt/nz。
nouns(text)  L204  
load(tag, src=None)  L212  
tag_descs(notes)  L232  
shot_tags(notes)  L241  # 截圖 說明行列出的圖名(tgb_tax=…):用來判斷 img 標籤是否有定義。
img_prefix(notes)  L250  
hl_list(extra)  L258  
anim_of(ln, defs)  L267  回傳 (anim dict 或 None, 引用字串, 錯誤)。
anim_blob(a)  L279  
check(tag, top, defs, notes, lines, tl)  L285  
opening_checks(lines, defs)  L389  O 開場文字卡連續 >= open_text_run;Q 引言卡 @def 缺 who(每個 def 只報第一次出現的句
_anim_need(a, ref)  L417  該步動畫需要的秒數(build.anim_seconds;build 載不進來或該類型量不到就回傳 None)。
estimate_checks(lines)  L431  D:同圖連續估計 > img_est_max_sec 秒或 > img_est_max_lines 句;E:動畫步(第一
load_timeline(path, lines)  L465  回傳 dict(lines=[每句 dict],shots=[...]) 或 None;句數對不上時回傳 (None, 
timeline_checks(lines, tl, stats)  L477  
_kit_items(extra)  L507  
kit_cell(extra)  L513  該句 script 的 kit -> 畫面表 kit 欄文字:`callout:一團亂, arrow`(種類:對象文字;
_cell_types(cell)  L523  
kit_compare(lines, table_path)  L527  既有畫面表有 kit 欄時,與 script 的 kit 種類逐句比對:K1 表有 script 無、K2 script
write_table(tag, lines, W, E, tl, note, out_path=None)  L558  
main()  L589  

## pipeline/visual_suggest.py
_plan_get(plan, i)  L42  visual_plan 的鍵可以是 "3" 或 "3-5"。
line_visual(ln, plan_entry=None)  L53  一句的實際畫面。回傳 dict:
describe(d)  L83  
feature_suggest(text)  L88  只看句子本身,回傳 (建議類型, 理由)。
analyse(lines, spec)  L116  每句回傳 dict(i, text, act, sug, why, status, generic)。
report(tag, rows, limit=MAX_LINES)  L151  
main()  L180  

## pipeline/yt_queue.py
base_url()  L36  
call(method, endpoint, body=None, timeout=15)  L40  回傳 (status, text);連不上回傳 (None, 錯誤文字)。HTTP 錯誤照樣回傳狀態碼與內文。
video_path(arg)  L54  
action(endpoint, path, no_backend_msg=NO_BACKEND)  L59  POST {path}:回傳結束碼。2xx 與 409(已在佇列)為 0、連不上 2、其他 1。
enqueue(path)  L75  
_slot_after(h, m, now, lead_min)  L79  now(台北)之後第一個 h:m,且至少晚 lead_min 分鐘。
resolve_publish_at(spec, channel=None, now=None)  L87  --publish-at 值 -> 帶 +08:00 的 ISO 字串。spec:'auto'(或空)= 頻道預設檔次(
wait_video_id(name, timeout_s, interval=POLL_S, sleep=time.sleep, clock=time.monotonic)  L115  輪詢 GET /api/claude_queue 到檔名 name 的項目 done。回傳 (video_id 或 No
schedule_after_queue(path, publish_at, wait_min=SCHEDULE_WAIT_MIN, interval=POLL_S, sleep=time.sle...)  L145  等 path 這支片在佇列完成後 POST /api/videos/<video_id>/schedule {publi
_items(obj)  L163  寬鬆取出佇列項目清單:list、{items/queue/videos/jobs: list 或 dict}、或 {pa
_get(d, *keys)  L176  
fmt_row(it)  L184  
status()  L192  
main()  L215  

## pipeline/sci/make_brand.py
html()  L27  
ink(png_bytes)  L33  
bbox(m)  L38  
circle_mask(im, d)  L43  
main()  L52  

## pipeline/sci/make_film.py
bgm_mix_filter(total, bgm_vol, duck=False)  L41  BGM 增益 + 淡出 + 與配音混音的濾鏡字串(接在 [0:v] 之後;輸入 1 = 配音、2 = BGM,輸出 [a
sub_clean(text)  L52  字幕純文字:標點換半形空格(數字內的小數點保留),連續空格併一個、頭尾去空格。
plan(film, tts)  L66  回傳 (scenes, lines_final, total)。邊界一律落在 0.1 秒格線(整數 ds);句子音檔仍放
placeholder(frames, n, name, hue, size=(1920, 1080))  L113  
render_scene(tag, ent, hue, portrait=False)  L125  回傳 (frames 目錄, 狀態字串, 失敗細節列表)。
read_wav(path)  L155  
build_voice(flines, tts_dir, total, out, sfx=())  L162  
write_ass(flines, path, S=LANDSCAPE_SUB)  L182  
run(cmd, cwd=None)  L206  
main()  L212  

## pipeline/sci/make_lab.py
make(kind)  L17  

## pipeline/sci/make_sfx.py
put(buf, t, x)  L22  
env(n, a=0.004, tau=0.08)  L28  
marimba(f, d=0.32, g=0.5)  L33  
slap(rng, d=0.07, g=0.5, lo=1200, hi=5200)  L38  
thump(d=0.22, g=0.8, f0=120, f1=48)  L46  
slide(f0, f1, d=0.28, g=0.3)  L52  
make(kind)  L58  
make_outro()  L80  
main()  L89  

## pipeline/sci/make_thumb.py
hit(a, b)  L28  
main()  L32  

## pipeline/sci/render_clip.py
build_html(scene, portrait=False)  L26  
hit(b, z)  L42  
check(rows, meta, L, tpl=False)  L46  rows: [(t, [外框...], same)];回傳摘要行與是否通過。外框含描邊;陰影另加(右 5u、下 6u)。
main()  L117  

## pipeline/sci/voice_audition.py
top(s)  L48  
load_rows()  L57  
emb_tensor(row)  L69  
pick(rows)  L73  
synth_voice(code, pt, force)  L90  回傳 dict(f0s, passed, total, secs);音檔 wav 放 WORK\<code>\
to_mp3(wav, mp3)  L106  
build_audio(code, d)  L110  
page(rowsinfo)  L146  
main()  L165  
