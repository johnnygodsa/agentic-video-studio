"""網頁截圖規格工廠(F3-2):併自 assets_{wowi,wow,gd,gows,gta5,dei,sv3,tracer,re9l,re9o}_specs.py 的重複函式與共用字串。
新片的 assets_<tag>_news.py 直接 `from news_specs import ...`,SPECS 只寫呼叫工廠的參數(欄位說明見 news_lib.py 檔頭)。
舊的 assets_*_specs.py 不動(legacy);工廠輸出與舊版逐欄位相同(F3-0 以 dict 相等測試驗過)。

分類
  CSS/JS 片段   FONT NOBORDER NOCASE FLAT DARKFIX unclip cut_js block_css inl title_css body_css
  通用          art(文章頁)  para(單一段落)  gnn(巴哈 GNN)
  依網站        kotaku kotaku_head kotaku_art kotaku_para / gs_para(GameSpot) gd_para(Game Developer) gb_para(GamesBeat)
                ign_p press_start(ps) ps_art / gf(Game File) am(Aftermath) sec(SEC 10-K) steam(Steam 鑑賞家) / disc meta(暴雪論壇)
閱讀卡:任何工廠回傳的 dict 都可加 `mode="card"` 與 `card={...}`(欄位見 news_lib.py 檔頭「mode / card」;沒寫 mode 就是 page、行為不變)。
  例:`dict(art(...), mode="card", card=dict(layout="article", title="中文標題"))`;rules 照舊寫譯文,卡上的標題/摘錄/底列全部由 url+targets+rules 抽出。
暗色(mode=page):任何工廠回傳的 dict 可加 `dark="auto"|"native"|"force"|"js"|"off"` 覆寫個別站;沒寫 = auto(①原生深色 ②強制深色瀏覽器 ③校色 #15202b/#e7e9ea,原本就深色的頁略過),False = off,舊的 dark=False 規格行為不變。機制與各值意義見 news_lib.py 檔頭 dark 欄位與 docs/assets.md「暗色三層」。
共用常數:SITE_*、URL 與選擇器(K_*, GS_*, GF_P, AMP, ...)。每個工廠回傳 dict,可再 `["css"] += ...` 微調。
"""
# ---------- CSS / JS 片段 ----------
FONT = '"Noto Sans TC Static", "Noto Sans TC", sans-serif'   # 2026-10-22 起 Noto(原微軟正黑體);"Noto Sans TC Static" 的 @font-face 由 news_lib._open1 注入本機靜態檔
NOBORDER = "* {border-left: none !important; border-right: none !important;} *::before, *::after {display: none !important;}"
NOCASE = "text-transform: none !important; letter-spacing: normal !important;"

# 段落(p)內常有連結/強調的子元素:先攤平成純文字,前綴比對才會落在整段而不是第一個子元素;並解除祖先的 overflow 裁切
FLAT = r"""() => { for (const t of window.__targets) {
  if (t.matches('p')) t.textContent = t.textContent.replace(/\s+/g, ' ').trim();
  for (let a = t; a && a !== document.body; a = a.parentElement) {   // 原頁固定高度+overflow 裁字:祖先改成可見
    a.style.setProperty('overflow', 'visible', 'important'); a.style.setProperty('max-height', 'none', 'important');
    if (a !== t) a.style.setProperty('height', 'auto', 'important');
  }
} }"""

# 頁面本身是「深色頁首+淺色內文底」時 JS_DARK 會因第一個區塊的祖先是深色而整頁略過:改由規格自己把保留區塊、祖先與整頁底色換成 #15202b / #e7e9ea
DARKFIX = r"""() => { const BG = '#15202b', FG = '#e7e9ea';
  const parse = c => { const m = (c || '').match(/[\d.]+/g); if (!m || m.length < 3) return null;
    const v = m.map(Number); return {r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1}; };
  const lum = c => (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255;
  const sat = c => (Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b)) / 255;
  const all = new Set([document.documentElement, document.body]);
  for (const t of window.__targets) { for (let p = t; p; p = p.parentElement) all.add(p); for (const e of t.querySelectorAll('*')) all.add(e); }
  for (const e of all) { const cs = getComputedStyle(e), bg = parse(cs.backgroundColor), fg = parse(cs.color);
    if (bg && bg.a > 0.05) e.style.setProperty('background-color', BG, 'important');
    if (fg && lum(fg) < 0.6 && sat(fg) < 0.2) e.style.setProperty('color', FG, 'important'); }
  document.documentElement.style.setProperty('background-color', BG, 'important');
  document.body.style.setProperty('background-color', BG, 'important'); }"""


def flat_all(SPECS):
    """每張規格預設都先攤平段落(js 沒指定時用 FLAT);回傳同一個 SPECS"""
    for sp in SPECS.values():
        sp.setdefault("js", FLAT)
    return SPECS


def unclip(sel):
    """把目標的祖先全部改成 overflow 可見、不限高(原頁用固定高度+overflow 裁字,版面檢查會報被裁)"""
    return ("() => { for (let a = document.querySelector('%s'); a && a !== document.body; a = a.parentElement) "
            "{ a.style.setProperty('overflow', 'visible', 'important'); a.style.setProperty('max-height', 'none', 'important'); "
            "a.style.setProperty('height', 'auto', 'important'); } }" % sel)


def cut_js(idx, start, end):
    """把第 idx 個目標區塊(一整大段)縮成「start 起到 end 止」的原文片段(只取原文,不改字)"""
    return ("() => { const t = window.__targets[%d]; const s = t.textContent.replace(/\\s+/g, ' ').trim();"
            " const a = s.indexOf(%r); if (a < 0) throw new Error('cut start not found'); const b = s.indexOf(%r, a);"
            " if (b < 0) throw new Error('cut end not found'); t.innerHTML = '<span>' + s.slice(a, b + %d) + '</span>'; }"
            % (idx, start, end, len(end)))


def block_css(sel, w, fs, lh=1.6, extra=""):
    """中文頁:把保留區塊的寬度/字級固定下來(scale = 1920 / 區塊寬,所以寬度決定字有多大)"""
    return (f"{sel} {{width: {w}px !important; max-width: {w}px !important; min-width: 0 !important; margin: 0 !important; padding: 0 !important; "
            f"float: none !important; font-size: {fs}px !important; line-height: {lh} !important; font-family: {FONT} !important; "
            f"text-align: left !important; box-sizing: border-box !important; {extra}}}")


def inl(sel, fs, extra=""):
    """一行內的小字(署名、日期):行內區塊、寬度自動"""
    return (f"{sel} {{display: inline-block !important; width: auto !important; max-width: none !important; min-width: 0 !important; "
            f"margin: 10px 30px 6px 0 !important; padding: 0 !important; float: none !important; font-size: {fs}px !important; "
            f"line-height: 1.5 !important; font-family: {FONT} !important; opacity: 1 !important; {NOCASE} {extra}}}")


def title_css(sel, w, fs, extra=""):
    return block_css(sel, w, fs, 1.35, f"font-weight: 700 !important; margin-bottom: 18px !important; {NOCASE} {extra}")


def body_css(sel, w, fs, extra=""):
    return block_css(sel, w, fs, 1.55, f"margin-bottom: 0 !important; {NOCASE} {extra}")


# ---------- 通用 ----------
def art(url, ptag, targets, rules, site, w=1000, fs=34, vw=1100, title_sel=None, title_fs=52, extra=""):
    """通用文章頁:ptag 為內文段落選擇器;title_sel 為標題(加大、加寬)"""
    css = NOBORDER + block_css(ptag, w, fs, 1.65, "margin-bottom: 26px !important;") + extra
    if title_sel:
        css += (f" {title_sel} {{font-size: {title_fs}px !important; line-height: 1.4 !important;"
                f" margin-bottom: 48px !important; width: {w}px !important; max-width: {w}px !important;"
                " font-family: inherit !important;}")
    return dict(url=url, vw=vw, site=site, oy_max=200, targets=targets, css=css, rules=list(rules))


def para(url, site, sel, prefix, zh, w, fs, vw=1100, hdr=None, rule_key=None, lh=1.55, oy_max=200):
    """單一段落:prefix 為該段開頭英文(以…結尾做前綴比對);hdr 為找目標用的內含文字(預設 prefix 去掉…)"""
    return dict(url=url, vw=vw, site=site, oy_max=oy_max, targets=[(sel, hdr if hdr is not None else prefix.rstrip("…"))],
                css=NOBORDER + block_css(sel, w, fs, lh, "margin-bottom: 0 !important;"), rules=[(rule_key or prefix, zh)])


def gi_para(url, date_zh, prefix, zh, hdr, cut=None, w=1250, fs=40, vw=1350):
    """Game Informer 訪談(2026 版型,內文是 article 之後的裸 <p>):hdr 為找段落的內含文字;cut=(start, end) 把長段縮成原文片段"""
    sp = para(url, "Game Informer " + date_zh, "p", prefix, zh, w, fs, vw, hdr=hdr)
    if cut:
        sp["js"] = "() => { (%s)(); (%s)(); }" % (FLAT, cut_js(0, *cut))
    return sp


GNN = "https://gnn.gamer.com.tw/detail.php?sn=313167"
GNN_P = "div.GN-lbox3B div"        # 問答每段是一個 div,取內含指定文字的最小者
SRC_GNN = "=來源:巴哈姆特 GNN 訪談報導"


def gnn(targets, css="", rules=(), w=1000, fs=32, **kw):
    """巴哈姆特 GNN 訪談(中文原頁)"""
    return dict(url=GNN, vw=1100, site=SRC_GNN, oy_max=200, targets=targets, keep_en=["Clay Stone："],
                css=NOBORDER + block_css(GNN_P, w, fs, 1.65) + css, rules=list(rules), **kw)


# ---------- Kotaku ----------
K_H1, K_BY, K_TM, K_P = "h1.entry-title", "div.byline span.block", "div.byline time.updated", "div.entry-content > p"


def kotaku(url, date_en, date_zh, by_en, p_key, p_zh, h1_rule=None, w=1200, fs=44, vw=1300, with_by=True, with_h1=True, p_hdr=None, oy_max=200, with_tm=True):
    """Kotaku(2014 與 2026 同一版型):標題 + 署名 + 日期 + 一段內文"""
    targets = ([K_H1] if with_h1 else []) + ([(K_BY, "By")] if with_by else []) + ([(K_TM, date_en)] if with_tm else []) + [(K_P, p_hdr or p_key.rstrip("…")[:40])]
    rules = ([h1_rule] if h1_rule else []) + ([(by_en, "作者：" + by_en[3:])] if with_by else []) + ([(f"Published {date_en}", date_zh)] if with_tm else []) + [(p_key, p_zh)]
    css = (NOBORDER + title_css(K_H1, 1250, 58) + inl(f"{K_BY}, {K_TM}", 34) + body_css(K_P, w, fs))
    return dict(url=url, vw=vw, site="Kotaku", oy_max=oy_max, targets=targets, css=css, rules=rules, keep_en=[])


def kotaku_head(url, rules, w=1000):
    """Kotaku 新版型文章標題區:h1 + 副標(.post-excerpt)"""
    css = (NOBORDER + block_css("header.mt-4 h1", w, 62, 1.35, "font-weight: 700 !important; margin-bottom: 30px !important;")
           + block_css("header.mt-4 .post-excerpt", w, 38, 1.5, "color: #9fb0bf !important;"))
    return dict(url=url, vw=1100, site="Kotaku", oy_max=200, targets=["header.mt-4"], css=css, rules=list(rules))


def kotaku_art(url, rules, targets, w=1200, fs=36):
    """Kotaku 新版型:標題(header.mt-4 h1)+ 內文段落(div.entry-content p)"""
    css = (NOBORDER + block_css("header.mt-4 h1", w, 54, 1.35, "font-weight: 700 !important; margin-bottom: 30px !important;")
           + block_css("div.entry-content p", w, fs, 1.55, "margin-bottom: 0 !important;"))
    return dict(url=url, vw=1300, site="Kotaku", oy_max=200, targets=targets, css=css, rules=rules)


def kotaku_para(url, css_sel, prefix, zh, w=1200, fs=40, vw=1300, rule_key=None):
    """Kotaku 舊版型(2016)的一段:css_sel 為段落選擇器"""
    return para(url, "Kotaku", css_sel, prefix, zh, w, fs, vw, rule_key=rule_key)


# ---------- 其他新聞站 ----------
GS_REVIEW = "https://www.gamespot.com/reviews/grand-theft-auto-v-review/1900-6414475/"
GD_URL = "https://gamedeveloper.com/business/-gamers-don-t-have-to-be-your-audience-gamers-are-over-"
GD_P = "p.ContentParagraph"


def gs_para(prefix, zh, w=1000, fs=44, vw=1100, url=GS_REVIEW):
    """GameSpot 評測內文的一段(wp-block-paragraph)"""
    return para(url, "GameSpot", "p.wp-block-paragraph", prefix, zh, w, fs, vw)


def gd_para(key_start, prefix, zh, w=1300, fs=42, url=GD_URL):
    """Game Developer(原 Gamasutra)內文一段:key_start 找目標、prefix 做規則前綴"""
    return dict(url=url, vw=1400, site="Game Developer（原 Gamasutra）", oy_max=200, targets=[(GD_P, key_start)],
                css=NOBORDER + body_css(GD_P, w, fs), rules=[(prefix, zh)])


def gb_para(prefix, zh, url="https://gamesbeat.com/target-pulls-grand-theft-auto-v/"):
    """GamesBeat 文章一段"""
    return para(url, "GamesBeat", "article p", prefix, zh, 1250, 38, 1400)


IGN_P = "section.article-page p"


def ign_p(url, txt, rules, w=1000, fs=40, **kw):
    """IGN 內文段落"""
    return dict(url=url, vw=1100, site="IGN", oy_max=200, targets=[(IGN_P, txt)],
                css=block_css(IGN_P, w, fs, 1.65, "font-weight: 500 !important;"), rules=rules, **kw)


PS_URL = "https://press-start.com.au/features/2025/11/15/resident-evil-requiem-interview-putting-the-horror-in-survival-horror/"
PS_H, PS_P = "div.entry-content h3", "div.entry-content p"


def press_start(qtxt, atxts, rules, w=1000, qfs=30, afs=42, oy_max=200, **kw):
    """Press Start 專訪:qtxt=None 表示不放問題;atxts 內 "H:" 開頭者為 h3(問題),其餘為 p(回答)"""
    ts = ([(PS_H, qtxt)] if qtxt else []) + [(PS_H, t[2:]) if t.startswith("H:") else (PS_P, t) for t in atxts]
    return dict(url=PS_URL, vw=1100, site="Press Start", oy_max=oy_max, targets=ts,
                css=block_css(PS_H, w, qfs, 1.55, "text-transform: none !important; font-weight: 600 !important; color: #9fb0bf !important; margin: 0 0 22px 0 !important;")
                + block_css(PS_P, w, afs, 1.6, "font-weight: 500 !important; margin: 0 0 26px 0 !important;"),
                rules=rules, **kw)


def ps_art(rules, targets, w=1150, fs=38):
    """Press Start 專訪:h1 標題 + 一段內文"""
    css = (NOBORDER + "div.site-inner {background: none !important;} div.meta, div.title-wrap {float: none !important; width: auto !important; clear: both !important;}"
           + block_css("h1", w, 52, 1.35, "font-weight: 700 !important; margin-bottom: 30px !important;")
           + block_css("div.entry-content p", w, fs, 1.5, "margin-bottom: 0 !important;"))
    return dict(url=PS_URL, vw=1400, site="Press Start", oy_max=200, targets=targets, css=css, rules=rules)


GF_P = "div.available-content p"
AMP = "article.ghost-content p"


def gf(url, targets, rules, w=1000, fs=34):
    """Game File(Substack)文章"""
    return dict(url=url, vw=1100, site="Game File", oy_max=200, targets=targets,
                css=NOBORDER + block_css(GF_P, w, fs, 1.65, "margin-bottom: 26px !important;"), rules=list(rules))


def am(url, key, rules, **kw):
    """Aftermath 文章一段"""
    return art(url, AMP, [(AMP, key)], rules, "Aftermath", **kw)


UA_SEC = "ClaudeVideoResearch contact@example.invalid"   # SEC 要求自報身分
JS_TAG = "() => { for (const t of window.__targets) t.classList.add('deit'); }"   # 把目標區塊標上 class,方便 CSS 固定寬度與字級


def sec(url, key, zh, w=800, fs=32, company=None):
    """SEC 10-K 年報一段(site 的公司名由網址判斷,可用 company 指定;預設 EA / Take-Two)"""
    company = company or ("EA" if "/712515/" in url else "Take-Two")
    return dict(url=url, vw=900, site=f"SEC 10-K 年報({company})", ua=UA_SEC, oy_max=200, js=JS_TAG,
                targets=[("div", key)],
                css=NOBORDER + block_css(".deit", w, fs, 1.65, "text-indent: 0 !important; font-style: normal !important;")
                + ".deit * {font-family: inherit !important; font-size: inherit !important; font-style: normal !important;}",
                rules=[(key + "…", zh)])


ST_CSS = (" .ignore_controls, .follow_btn, .curator_avatar_image {display: none !important;}"
          " .page_content_ctn, .curator_header_ctn, .header_area, .curator_details {width: 760px !important; max-width: 760px !important;"
          " min-width: 0 !important; margin: 0 !important; padding-left: 0 !important; left: 0 !important; float: none !important;}"
          " .curator_name, .curator_name a {font-size: 52px !important; line-height: 1.3 !important;}"
          " .curator_url {font-size: 30px !important;} .num_followers {font-size: 64px !important; line-height: 1.2 !important;}"
          " .num_followers_text {font-size: 30px !important; line-height: 1.2 !important;}"
          " .follow_controls, .follow_btn_stats {width: auto !important; height: auto !important; position: static !important;"
          " float: none !important; display: block !important; margin: 10px 0 0 0 !important;}"
          " .recommendation {width: 760px !important; min-width: 0 !important; margin: 0 !important; height: auto !important;}"
          " .recommendation_midcol {font-size: 30px !important; width: auto !important; height: auto !important;}"
          " .recommendation_desc {font-size: 32px !important; line-height: 1.4 !important; height: auto !important; max-height: none !important;"
          " overflow: visible !important;}"
          " .recommendation_type_ctn, .recommendation_type_ctn span {font-size: 30px !important;}"
          " .recommendation_readmore, .recommendation_readmore a {font-size: 28px !important;}"
          " .curator_header_ctn, .header_area, .curator_details, .recommendation, .recommendation_midcol"
          " {height: auto !important; min-height: 0 !important; max-height: none !important; overflow: visible !important;}"
          " .discount_block {display: none !important;}"
          " .recommendation_readmore {display: none !important;}")
ST_KEEP = ["Sweet Baby Inc detected", "DEIDetected.com", "ELDEN RING", "Forza Horizon 5", "Gears of War: E-Day",
           "Woke and Censored Games Alert", "[deidetected.com]", "Followers"]


def steam(url, targets, rules, css="", js=None):
    """Steam 鑑賞家頁(dark=False;規則引擎要求每條都必須命中,所以各張只挑頁面上有的)"""
    sp = dict(url=url, vw=1100, site="Steam 鑑賞家頁面", oy_max=200, targets=targets, dark=False, keep_en=ST_KEEP,
              css=ST_CSS + css, rules=list(rules))
    if js:
        sp["js"] = js
    return sp


# ---------- 暴雪官方論壇(Discourse)----------
BNET = "https://us.forums.blizzard.com/en/wow"

# 相對日期("7d")改成 title 裡的絕對日期(頁面本來就有,只是藏在滑鼠提示),再由 rules 譯成中文
JS_DISC = r"""
  for (const e of document.querySelectorAll('.relative-date[title]')) e.textContent = e.getAttribute('title');
  for (const e of document.querySelectorAll('.secondary-details')) e.style.setProperty('display', 'none', 'important');
  for (const e of document.querySelectorAll('.primary-details > *')) if (!e.matches('.character-name') && !e.querySelector('.user-post-count')) e.style.setProperty('display', 'none', 'important');
  for (const e of document.querySelectorAll('.like-count')) e.textContent = e.textContent.trim() + ' 個讚';
"""

CSS_DISC = """
*, *::before, *::after {background-image: none !important;}
html, body, .wrap, #main-outlet {background-color: #15202b !important;}
body, .cooked, .cooked *, h1, h1 *, .topic-meta-data, .topic-meta-data * {font-family: "Noto Sans TC Static", "Noto Sans TC", sans-serif !important;}
.post__body, .topic-body {width: auto !important; max-width: none !important; margin: 0 !important;}
.post-info.edits, .read-state, .post-info svg, .post-info .b-post-statuses {display: none !important;}
.topic-meta-data {padding-bottom: 8px !important; border-bottom: 1px solid #38444d !important; margin-bottom: 18px !important;}
.cooked, .cooked li, .cooked p {font-size: 26px !important; line-height: 1.5 !important;}
.cooked p, .cooked li {margin: 0 0 14px 0 !important;}
.cooked em {font-style: normal !important;}
.cooked ul {margin: 8px 0 8px 26px !important;}
#topic-title, .title-wrapper, #main-outlet-wrapper, #main-outlet, .container.posts, .topic-area, .post-stream {padding: 0 !important; margin: 0 !important;}
.title-wrapper {margin-bottom: 14px !important;}
.topic-body, .post__row, .post__body, article {padding-top: 0 !important; margin-top: 0 !important;}
.post-menu-area, .post__menu-area {margin: 0 !important; padding: 0 !important;}
h1 {font-size: 34px !important; line-height: 1.35 !important; margin: 0 !important; padding: 0 24px !important;}
.like-count {font-size: 24px !important;}
"""


def disc(tid, pn, paras, rules, title=False, lis=False, vw=1100, keep=(), extra_css="", extra_js="", oy_max=200):
    """Discourse 單樓貼文:作者列 + 指定段落(p 或 li,以內含文字找)+ 讚數;title=True 另留標題"""
    tag = "li" if lis else "p"
    t = (["#topic-title h1"] if title else []) + [f"#post_{pn} .topic-meta-data"]
    t += [(f"#post_{pn} .cooked {tag}", s) for s in paras] + [f"#post_{pn} .like-count"]
    return dict(url=f"{BNET}/t/{tid}/{pn}", vw=vw, site="暴雪官方論壇", targets=t, js="() => {" + JS_DISC + extra_js + "}",
                css=CSS_DISC + extra_css, keep_en=list(keep), rules=rules, oy_max=oy_max)


def meta(user_zh, date_en, date_zh, title_en=None, title_zh=None):
    """作者列的共通規則:貼文數、日期(只留日期,不留時分)"""
    r = [(r"re:([\d,]+) posts", "$1 則貼文"), (date_en, date_zh)]
    if title_en:
        r.append((title_en, title_zh))
    return r
