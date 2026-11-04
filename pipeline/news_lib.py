"""網頁截圖共用引擎(F3-0):新片的 assets_<tag>_news.py 只剩 SPECS(+HL)與 `main(SPECS, tag, HL)` 一行。
用法:  python -X utf8 pipeline/assets_<tag>_news.py [name ...] [--only a,b] [--check] [--dump] [--relabel a,b] [--overview [檔]] [--out 資料夾]
由 assets_re9_news.py(截圖引擎)與 assets_gd_news.py(版面檢查、墨跡檢查、ua/noscroll)合併而來;其餘 6 份 assets_*_news.py 與 gd 版
只差輸出前綴與 specs 模組名,已參數化。舊檔不動(legacy)。

做法:無頭 Edge(Playwright)開真實網頁 -> 只留指定區塊 -> 英文換繁體中文 -> 白底頁改暗色 -> 以 1920 寬截圖,
並由 DOM 逐字矩形產出 <prefix><name>.boxes.json(text/box/chars)與 .layout.json(版面檢查資料)。

規格 SPECS:{name: dict};欄位
  url vw        網址、版面寬度(CSS px,越窄字越大)       targets  要保留的區塊 [css] 或 [(css, 內含文字)],由上而下排列
  rules         [(英文全文, 中文)];`…` 結尾=前綴比對、`re:`=正規式(中文可用 $1);中文含 <span 時以 innerHTML 寫入;找不到會報錯
  site          右下角標籤的網站名(不帶 =;由 add_label 加「中文翻譯 · 原文:」)     css / js  額外注入的 CSS / 截圖前執行的 JS
  dark          通用暗色三層(PLAN_閱讀卡 §2B):auto(預設)=①emulate_media dark(原生深色)->②仍亮就改用強制深色瀏覽器(WebContentsForceDark,圖片不反相)->③JS_CAL 校色
                (底 #15202b/主字 #e7e9ea);原本就是深色的頁(light 下也暗)三層都略過。native=①+③  force=①+②+③  js=舊版 JS_DARK 整套變色  off(或 False)=不處理
                cookies + cookie_domain  只用於 Steam 年齡確認欄位     keep_en  允許留英文的字
  parts + gap/bg/tag   合成圖(多個子規格直向堆疊)    oy_max  置中上移上限    padx/pady/edge_px/top_px  留邊(預設 padx=34 edge_px=64 top_px=44)
  ua            該頁 User-Agent(SEC 要求自報身分;預設一般 Edge UA)    noscroll  True=不捲動 lazy-load 且不點 No thanks 類按鈕
  wait          開頁後等 JS 載入的毫秒數(預設 4000;暴雪論壇/商城這類慢載入的頁面設 10000)
  hl            建議底線詞(也可另傳 HL 字典);截圖時另出底線序列 <prefix><name>_hl/ + .hl.json(計畫 §2C,docs/assets.md「紅線序列」)
  mode          "page"(預設;沒寫就是 page,行為與舊版完全相同)| "card"(閱讀卡,計畫 PLAN_閱讀卡 §2A:不截真實頁,抽出標題/署名/段落/og:image
                套 templates/readercard/*.html,同一支瀏覽器開本機 HTML 再走同樣的量框/截圖/底線序列;url/targets/rules 仍用來抽取與翻譯)
  card          mode=card 的選用設定 {layout: article|para|post, title(標題中文), title_sel(原頁標題選擇器,有 title 時預設 h1), byline_sel, date_sel,
                name_sel/time_sel/likes_sel(post 用), hero(False=不放圖), lang("zh"=原文是中文,底列只寫「原文:網站名」)};卡上字全部來自原頁或 rules 的譯文
  kind          "text" | "photo"(選填,2026-10-22 PLAN_閱讀卡 #4):寫入 .layout.json 的 kind,決定 build.py 的鏡頭動態(text = 極慢 zoom+水平漂移、不傾斜;
                photo = tilt/zoom 輪替)。沒寫:card 模式 = text;page 模式 = 文字框面積占截圖區 > KIND_TEXT_AREA(40%)為 text,否則 photo
--narrow 窄版(F3-4,Shorts 直式用):視窗寬 <= NARROW_VW、頁內字級至少 NARROW_MIN_PX、輸出 NARROW_W 寬(高度依內容),
  檔名 <prefix><name>_p.png/.boxes.json/.layout.json;build --portrait 找得到 <img>_p.png 就改用它直接繪製。
--out 指定輸出資料夾(預設 images/;回歸測試用 tmp/f30);--check 讀同一資料夾。
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import paths as P
from assets_lib import FH, FW, IMG, add_label, font, ink_check

MIN_EDGE, MIN_FS = 40, 20   # 版面檢查:左右離邊下限(px)、字高警告線(px)
MIN_TOP, INK_TOL = 24, 8    # 墨跡檢查:離上邊下限、框與墨跡容許誤差(px)
NARROW_W, NARROW_VW, NARROW_MIN_PX = 1000, 680, 36   # 窄版:輸出寬、頁面視窗寬上限、頁內最小字級(css px)
NARROW_CSS_W = 620          # 窄版:spec css 裡所有 width/max-width 超過此值的一律壓到此值(DSF 約 1.47,36px 字成片約 53px;
                            # build 再把文字欄縮放到 x 60-940(Shorts 右側按鈕區 x>940 不可有字),縮放比約 1,字級仍 >= 48)
NARROW_EDGE_PX = 24         # 窄版左右留邊(輸出 px;build 依文字框重新定位,留邊只為不貼邊)
NARROW_LABEL_FS = 54        # 窄版「中文翻譯 · 原文」標籤字級(縮 0.9 後 >= 48)
JS_MINFONT = """(minPx) => {
  for (const el of document.querySelectorAll('body *')) {
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs && fs < minPx) { el.style.setProperty('font-size', minPx + 'px', 'important'); el.style.setProperty('line-height', '1.35', 'important'); }
  }
}"""
JS_HIDE_FLOAT = """() => {
  // 窄版:浮動小圖示(固定/黏住的按鈕、沒有文字的絕對定位小圓鈕)隱藏;含保留區塊的元素不動
  const keep = window.__targets || [];
  for (const el of document.querySelectorAll('body *')) {
    if (keep.some(t => el.contains(t) || t === el)) continue;
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    const small = r.width > 0 && r.width <= 160 && r.height <= 160 && !(el.innerText || '').trim();
    if (cs.position === 'fixed' || cs.position === 'sticky' || (cs.position === 'absolute' && small))
      el.style.setProperty('visibility', 'hidden', 'important');
  }
}"""
EDGE_PX, TOP_PX = 64, 44    # 截圖時的留邊目標(成片 px):左右、上(引擎換算成頁面 px)
UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"

# ---------- 頁內 JS ----------

JS_PREP = r"""
([targets, css]) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  // 1) cookie / 隱私彈窗:優先按「拒絕非必要」
  for (const b of document.querySelectorAll('button, a, [role=button]')) {
    const t = norm(b.innerText).toLowerCase();
    if (/^(reject( all| non-?essential)?|decline( all)?|only necessary|deny|necessary only|disagree|no thanks)$/.test(t)) { try { b.click(); } catch (e) {} }
  }
  // 2) 解除鎖捲動 / 模糊
  for (const e of [document.documentElement, document.body]) {
    e.style.setProperty('overflow', 'visible', 'important'); e.style.setProperty('filter', 'none', 'important');
  }
  // 3) 解析 targets
  const els = [];
  for (const [css_, txt] of targets) {
    let found = null;
    for (const e of document.querySelectorAll(css_)) {
      if (!txt || norm(e.innerText).includes(txt)) {
        if (!found || e.textContent.length < found.textContent.length) found = e;   // 取最小的符合者
        if (!txt) break;
      }
    }
    if (!found) return {error: 'target not found: ' + css_ + ' ' + (txt || '')};
    els.push(found);
  }
  window.__targets = els;
  // 4) fixed / sticky 浮層(排除 targets 內外祖先)
  for (const e of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(e);
    if ((cs.position === 'fixed' || cs.position === 'sticky') && !els.some(t => t.contains(e) || e.contains(t)))
      e.style.setProperty('display', 'none', 'important');
  }
  // 5) 隱藏非 targets
  const anc = new Set();
  for (const t of els) for (let p = t.parentElement; p; p = p.parentElement) anc.add(p);
  for (const e of document.body.querySelectorAll('*')) {
    if (anc.has(e) || els.some(t => t.contains(e))) continue;
    e.style.setProperty('display', 'none', 'important');
  }
  const st = document.createElement('style');
  st.textContent = 'h1,h2,h3,.topic{text-wrap:balance}' + (css || '');
  document.head.appendChild(st);
  document.documentElement.lang = 'zh-Hant-TW';
  return {ok: true};
}
"""

JS_TRANSLATE = r"""
(rules) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const missing = [];
  for (const [key, zh] of rules) {
    const isRe = key.startsWith('re:');
    const rx = isRe ? new RegExp('^' + key.slice(3) + '$', 'i') : null;
    const prefix = !isRe && key.endsWith('…'), k = prefix ? key.slice(0, -1) : key;
    let best = null;
    for (const t of window.__targets) {
      for (const e of [t, ...t.querySelectorAll('*')]) {
        const s = norm(e.textContent);
        if (isRe ? rx.test(s) : (prefix ? s.startsWith(k) : s === k)) { if (!best || s.length <= norm(best.textContent).length) best = e; }
      }
    }
    if (!best) { missing.push(key); continue; }
    const val = isRe ? norm(best.textContent).replace(rx, zh) : zh;
    if (val.includes('<span')) best.innerHTML = val; else best.textContent = val;
  }
  return missing;
}
"""

JS_LEFTOVER = r"""
() => {
  const out = [];
  for (const t of window.__targets) {
    const w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) {
      const s = n.data.replace(/\s+/g, ' ').trim();
      if (s && /[A-Za-z]{2,}/.test(s) && !/[一-鿿]/.test(s) && n.parentElement && n.parentElement.checkVisibility()) out.push(s.slice(0, 90));
    }
  }
  return out;
}
"""

JS_MEASURE = r"""
() => {
  window.scrollTo(0, 0);
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const t of window.__targets) {
    const r = t.getBoundingClientRect();
    x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom);
  }
  return {x0, y0, x1, y1};
}
"""

# 逐字矩形 -> 以行分組(每行一個 run)
JS_RUNS = r"""
() => {
  const runs = [];
  const rg = document.createRange();
  for (const t of window.__targets) {
    const w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) {
      if (!n.data.trim() || !n.parentElement || !n.parentElement.checkVisibility()) continue;
      let cur = null;
      for (let i = 0; i < n.data.length; i++) {
        rg.setStart(n, i); rg.setEnd(n, i + 1);
        const rs = rg.getClientRects();
        if (!rs.length) continue;
        const r = rs[0];
        if (r.width <= 0.01 || r.height <= 0) continue;
        const cy = (r.top + r.bottom) / 2;
        if (!cur || Math.abs(cy - cur.cy) > cur.h * 0.6 || r.left < cur.x1 - cur.h) {
          cur = {text: '', x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, cy, h: r.height, chars: []};
          runs.push(cur);
        }
        cur.text += n.data[i]; cur.chars.push([r.left, r.right]);
        cur.x1 = Math.max(cur.x1, r.right); cur.y0 = Math.min(cur.y0, r.top); cur.y1 = Math.max(cur.y1, r.bottom);
      }
    }
  }
  return runs.map(r => ({text: r.text, box: [r.x0, r.y0, r.x1, r.y1], chars: r.chars}));
}
"""

# 紅線(計畫 §2C):把 hl 命中詞包成 <span class="hl">(比對同 build.py find_hl_boxes:忽略空白與大小寫、可跨元素),
# 一個 span 只佔一行(跨行就拆開);包之前先記每段首字的位置,包完量不到同一位置就回報 shift(版面被 span 改動,不出序列)。
# 回傳 {shift, bars: [各 span 的詞序(依文件序)]},span 帶 data-k(詞序)/ data-b(底線序號)
HL_MAX = 4   # 同一詞最多標幾處(同 build.py HL_MAX)
JS_HL_WRAP = r"""
([kws, maxn]) => {
  const seq = [];
  for (const t of window.__targets) {
    const w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) {
      if (!n.data.trim() || !n.parentElement || !n.parentElement.checkVisibility()) continue;
      for (let i = 0; i < n.data.length; i++) if (!/\s/.test(n.data[i])) seq.push([n, i, n.data[i].toLowerCase()]);
    }
  }
  const flat = seq.map(x => x[2]).join('');
  const used = new Set(), segs = [];
  kws.forEach((kw, k) => {
    const q = kw.replace(/\s+/g, '').toLowerCase();
    let pos = 0, cnt = 0;
    while (q && cnt < maxn) {
      const i = flat.indexOf(q, pos);
      if (i < 0) break;
      pos = i + q.length;
      let clash = false;
      for (let j = i; j < pos; j++) if (used.has(j)) clash = true;
      if (clash) continue;
      cnt++;
      let cur = null;
      for (let j = i; j < pos; j++) {
        used.add(j);
        const [n, o] = seq[j];
        if (cur && cur.n === n) cur.e = o + 1;
        else { cur = {n, s: o, e: o + 1, k}; segs.push(cur); }
      }
    }
  });
  const rg = document.createRange();
  const rectAt = (n, o) => { rg.setStart(n, o); rg.setEnd(n, o + 1); const r = rg.getClientRects()[0]; return r ? [r.left, r.top] : null; };
  // 同一 text node 由後往前包,前段的 offset 才不會失效
  const byNode = new Map();
  for (const g of segs) { if (!byNode.has(g.n)) byNode.set(g.n, []); byNode.get(g.n).push(g); }
  const order = [...byNode.values()].flatMap(a => a.sort((x, y) => y.s - x.s));
  const spans = [];
  let shift = 0;
  for (const g of order) {
    // 依行切段(行 = 字框中線差 > 0.6 字高)
    const parts = [];
    let last = null;
    for (let o = g.s; o < g.e; o++) {
      rg.setStart(g.n, o); rg.setEnd(g.n, o + 1);
      const r = rg.getClientRects()[0];
      if (!r) continue;
      const cy = (r.top + r.bottom) / 2;
      if (!last || Math.abs(cy - last.cy) > r.height * 0.6) { last = {s: o, e: o + 1, cy, x: r.left, y: r.top}; parts.push(last); }
      else last.e = o + 1;
    }
    for (const p of parts.reverse()) {
      rg.setStart(g.n, p.s); rg.setEnd(g.n, p.e);
      const sp = document.createElement('span');
      sp.className = 'hl'; sp.dataset.k = g.k;
      rg.surroundContents(sp);
      spans.push([sp, p.x, p.y]);
    }
  }
  for (const [sp, x, y] of spans) {
    const r = sp.getClientRects()[0];
    if (!r || Math.abs(r.left - x) > 0.5 || Math.abs(r.top - y) > 0.5 || sp.getClientRects().length !== 1) shift++;
  }
  const all = [...document.querySelectorAll('span.hl')];
  all.forEach((sp, i) => { sp.dataset.b = i; });
  return {shift, bars: all.map(sp => +sp.dataset.k)};
}
"""
# 只顯示底線的圖層:文字、底色、框線、圖片全透明(JS_DARK 用的是行內 !important,所以逐元素寫行內),
# span.hl::after 以 --p(0..1)由左至右露出。
# border-color 只寫在本來就有框線的元素上:WordPress 區塊樣式有 `html :where([style*="; border-color"]) {border-style: solid}`
# (Press Start 實測),行內一寫 border-color 就讓每一層祖先多出 medium=3px 框線,內文下移約 3px × 層數(ps 圖 33px,
# 底線落到截圖區外)。改完仍由 _hl_layers 比對圖層前後 span 位置,位移 > HL_SHIFT_MAX 就不出序列
JS_HL_LAYER = r"""
(css) => {
  const T = 'transparent';
  const props = [['color', T], ['-webkit-text-fill-color', T], ['background', T], ['box-shadow', 'none'],
                 ['text-shadow', 'none'], ['outline-color', T], ['text-decoration-color', T]];
  const bw = g => parseFloat(g.borderTopWidth) + parseFloat(g.borderRightWidth) + parseFloat(g.borderBottomWidth) + parseFloat(g.borderLeftWidth);
  const els = [document.documentElement, ...document.querySelectorAll('body, body *')];
  const bd = new Set(els.filter(e => bw(getComputedStyle(e)) > 0));   // 先量完再寫,寫入不影響判斷
  for (const e of els) {
    for (const [k, v] of props) e.style.setProperty(k, v, 'important');
    if (bd.has(e)) e.style.setProperty('border-color', T, 'important');
    if (/^(IMG|SVG|VIDEO|CANVAS|PICTURE|IFRAME)$/i.test(e.tagName)) e.style.setProperty('visibility', 'hidden', 'important');
  }
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
}
"""
JS_HL_RECTS = "() => [...document.querySelectorAll('span.hl')].map(s => { const r = s.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })"
HL_SHIFT_MAX = 1   # 圖層頁與主圖的 span 位置容許差(css px)
HL_LAYER_CSS = """
body *::before, body *::after {
  color: transparent !important; -webkit-text-fill-color: transparent !important; background: transparent !important;
  border-color: transparent !important; box-shadow: none !important; text-shadow: none !important; }
span.hl { position: relative !important; --p: 0; }
span.hl::after { content: "" !important; display: block !important; visibility: visible !important; position: absolute !important; left: -0.15em; right: -0.15em;
  top: var(--uy, 100%); height: 0.12em; border-radius: 0.06em; background: #ff2d2d !important;
  clip-path: inset(0 calc((1 - var(--p)) * 100%) 0 0); }
"""
HL_STEPS = 10   # p = 0, 0.1 … 1.0
HL_UL_BASE = 0.2   # 底線上緣 = 基線下 0.2em(CJK 字底約在基線下 0.1em);截圖區放不下時往上收
# 每個 span 量基線(在圖層頁上量;插 0 大小 inline-block 探針、量完拔掉),寫 --uy = 底線上緣離 span 上緣的 px;ymax = 截圖區下緣(頁面 css y)
JS_HL_BASE = r"""
([base, ymax]) => {
  for (const s of document.querySelectorAll('span.hl')) {
    const pr = document.createElement('span');
    pr.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
    s.appendChild(pr);
    const bl = pr.getBoundingClientRect().bottom, r = s.getBoundingClientRect();
    pr.remove();
    const e = parseFloat(getComputedStyle(s).fontSize);
    const uy = Math.min(bl - r.top + base * e, ymax - scrollY - r.top - 0.12 * e - 2);
    s.style.setProperty('--uy', uy + 'px');
  }
}
"""


JS_BLOCKS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const out = [];
  const BL = 'p,h1,h2,h3,h4,h5,h6,li,blockquote,div,section,article,header,figure,ul,ol';
  for (const t of window.__targets) for (const e of [t, ...t.querySelectorAll('*')]) {
    if (!e.checkVisibility() || !norm(e.textContent)) continue;
    if ([...e.children].some(c => c.matches(BL) && norm(c.textContent))) continue;
    out.push(norm(e.textContent));
  }
  return out;
}
"""

# ---------- 擷取 ----------


# 白底頁面改成暗色模式(規則見 CLAUDE.md「網頁截圖」):只改保留區塊與其祖先的配色,圖片不動;原本就是深色的頁面不處理
DARK_BG, DARK_FG = "#15202b", "#e7e9ea"
JS_DARK = r"""
([BG, FG]) => {
  const parse = c => { const m = (c || '').match(/[\d.]+/g); if (!m || m.length < 3) return null;
    const v = m.map(Number); return {r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1}; };
  const lum = c => (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255;
  const sat = c => (Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b)) / 255;
  const els = window.__targets || [];
  if (!els.length) return {dark: false};
  // 頁面是否為亮底:從第一個保留區塊往上找第一個不透明的背景色(都透明 = 瀏覽器預設白底)
  let base = {r: 255, g: 255, b: 255, a: 1};
  for (let e = els[0]; e; e = e.parentElement) {
    const c = parse(getComputedStyle(e).backgroundColor);
    if (c && c.a > 0.5) { base = c; break; }
  }
  if (lum(base) < 0.5) return {dark: false};
  const all = new Set([document.documentElement, document.body]);
  for (const t of els) {
    for (let p = t; p; p = p.parentElement) all.add(p);
    for (const e of t.querySelectorAll('*')) all.add(e);
  }
  const todo = [];
  for (const e of all) {            // 先全部讀完再寫,避免繼承色在途中改變判斷
    const cs = getComputedStyle(e), o = {e};
    const bg = parse(cs.backgroundColor);
    if (bg && bg.a > 0.05 && lum(bg) > 0.35) o.bg = lum(bg) > 0.9 ? BG : '#1c2a38';   // 淺灰區塊留一點層次
    const fg = parse(cs.color);
    if (fg && lum(fg) < 0.6) {
      if (sat(fg) < 0.2) o.fg = lum(fg) < 0.35 ? FG : '#9fb0bf';                      // 黑字 -> 淺字;灰字 -> 次要色
      else { const k = 0.55; o.fg = `rgb(${Math.round(fg.r + (255 - fg.r) * k)},${Math.round(fg.g + (255 - fg.g) * k)},${Math.round(fg.b + (255 - fg.b) * k)})`; }  // 有顏色的字(連結)保留色相、提亮
    }
    const bd = parse(cs.borderTopColor);
    if (bd && bd.a > 0.05 && lum(bd) > 0.5 && parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth) > 0) o.bd = '#38444d';
    todo.push(o);
  }
  for (const o of todo) {
    if (o.bg) o.e.style.setProperty('background-color', o.bg, 'important');
    if (o.fg) o.e.style.setProperty('color', o.fg, 'important');
    if (o.bd) o.e.style.setProperty('border-color', o.bd, 'important');
  }
  document.documentElement.style.setProperty('background-color', BG, 'important');
  document.body.style.setProperty('background-color', BG, 'important');
  document.documentElement.style.setProperty('color-scheme', 'dark');
  return {dark: true};
}
"""

# 通用暗色三層的探測與校色(計畫 PLAN_閱讀卡 §2B)。JS_DARK 是舊版整套變色(dark="js" 或 DARK_DEFAULT="js" 時才用),新流程只用這兩段
# JS_BASELUM:第一個保留區塊往上找第一個不透明背景的亮度(0-1;都透明 = 瀏覽器預設白底 = 1)。emulate dark 後仍高 = 網站沒有原生深色
JS_BASELUM = r"""
() => {
  const els = window.__targets || [];
  if (!els.length) return 0;
  for (let e = els[0]; e; e = e.parentElement) {
    const m = (getComputedStyle(e).backgroundColor || '').match(/[\d.]+/g);
    if (!m || m.length < 3) continue;
    const v = m.map(Number), a = v.length > 3 ? v[3] : 1;
    if (a > 0.5) return (0.299 * v[0] + 0.587 * v[1] + 0.114 * v[2]) / 255;
  }
  return 1;
}
"""
# JS_CAL(第三層,校色):只把「保留區塊與祖先的不透明底色」統一成 BG、近黑/近白的中性主字統一成 FG;灰字、有色字、圖片、邊框都不動
JS_CAL = r"""
([BG, FG]) => {
  const parse = c => { const m = (c || '').match(/[\d.]+/g); if (!m || m.length < 3) return null;
    const v = m.map(Number); return {r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1}; };
  const lum = c => (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255;
  const sat = c => (Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b)) / 255;
  const els = window.__targets || [];
  const anc = new Set([document.documentElement, document.body]), all = new Set();
  for (const t of els) { for (let p = t; p; p = p.parentElement) anc.add(p); for (const e of t.querySelectorAll('*')) all.add(e); }
  for (const e of anc) { const b = parse(getComputedStyle(e).backgroundColor); if (b && b.a > 0.5) e.style.setProperty('background-color', BG, 'important'); }
  // 淺底元素內的字不動(2026-10-22:Bluesky「追蹤」鈕白底深字被改成淺字而看不見):字色只在「實際底色是深色」時才改。
  // 實際底色 = 自己或最近一層不透明背景的亮度 > 0.6 算淺底;ancestor 的底色上面已統一成 BG(深),不受影響;沒有不透明底色視為深(頁面底色最後是 BG)
  const cache = new Map();
  const bgLum = e => {
    if (!e) return 0;
    if (cache.has(e)) return cache.get(e);
    const b = parse(getComputedStyle(e).backgroundColor);
    const v = b && b.a > 0.5 ? lum(b) : bgLum(e.parentElement);
    cache.set(e, v); return v;
  };
  for (const e of [...anc, ...all]) {
    const f = parse(getComputedStyle(e).color);
    if (f && sat(f) < 0.2 && (lum(f) < 0.35 || lum(f) > 0.75) && bgLum(e) <= 0.6) e.style.setProperty('color', FG, 'important');
  }
  document.documentElement.style.setProperty('background-color', BG, 'important');
  document.body.style.setProperty('background-color', BG, 'important');
  return true;
}
"""


# 回傳 {runs, rects, gfx}。runs = 逐行文字框(分組方式同 JS_RUNS,順序一一對應;rects 為其頁面座標):cov=被別的元素蓋住、clip=被 overflow 祖先裁掉、fs=字級(頁面 px)、h=框高
JS_LAYOUT = r"""
() => {
  const rg = document.createRange(), out = [], runs = [];
  const rel = (a, b) => a === b || a.contains(b) || b.contains(a);
  const rectOf = (n, i) => { rg.setStart(n, i); rg.setEnd(n, i + 1); const rs = rg.getClientRects(); return rs.length ? rs[0] : null; };
  const probe = (n, i) => {   // 該字中心點 elementFromPoint(必要時先捲動到可見)
    let r = rectOf(n, i); if (!r) return null;
    const cy = (r.top + r.bottom) / 2;
    if (cy < 0 || cy > innerHeight - 1) { scrollTo(0, scrollY + cy - innerHeight / 2); r = rectOf(n, i); }
    return document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
  };
  const finish = c => {
    const el = c.node.parentElement, pts = [c.i0, c.im, c.i1];
    let cov = false;
    for (const i of pts) { const h = probe(c.node, i); if (h && !rel(h, el)) cov = true; }
    scrollTo(0, 0);
    const R = c.rect;   // 此行框(捲回 0 後的座標,見下)
    let clip = false;
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
      const b = a.getBoundingClientRect();
      const L = b.left + a.clientLeft, T = b.top + a.clientTop, Rr = L + a.clientWidth, B = T + a.clientHeight;
      if (R[0] < L - 1 || R[2] > Rr + 1 || R[1] < T - 1 || R[3] > B + 1) clip = true;
    }
    out.push({cov, clip, fs: parseFloat(getComputedStyle(el).fontSize), h: R[3] - R[1]});
  };
  scrollTo(0, 0);
  for (const t of window.__targets) {
    const w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) {
      if (!n.data.trim() || !n.parentElement || !n.parentElement.checkVisibility()) continue;
      let cur = null;
      for (let i = 0; i < n.data.length; i++) {
        const r = rectOf(n, i);
        if (!r || r.width <= 0.01 || r.height <= 0) continue;
        const cy = (r.top + r.bottom) / 2;
        if (!cur || Math.abs(cy - cur.cy) > cur.h * 0.6 || r.left < cur.x1 - cur.h) {
          cur = {node: n, i0: i, im: i, i1: i, cy, h: r.height, x1: r.right, rect: [r.left, r.top, r.right, r.bottom], idx: []};
          cur.idx.push(i);
          runs.push(cur);
        }
        cur.idx.push(i); cur.i1 = i; cur.x1 = Math.max(cur.x1, r.right);
        cur.rect = [Math.min(cur.rect[0], r.left), Math.min(cur.rect[1], r.top), Math.max(cur.rect[2], r.right), Math.max(cur.rect[3], r.bottom)];
      }
    }
  }
  for (const c of runs) { c.im = c.idx[c.idx.length >> 1]; finish(c); }
  // 非文字圖形(圖片、圖示、沒有字的背景圖區塊):墨跡檢查要略過,不然緊鄰文字的圖會被當成「框外有字」
  const gfx = [];
  for (const t of window.__targets) for (const e of [t, ...t.querySelectorAll('*')]) {
    if (!e.checkVisibility()) continue;
    if (!(/^(img|svg|canvas|video)$/i.test(e.tagName) || (getComputedStyle(e).backgroundImage !== 'none' && !e.textContent.trim()))) continue;
    const b = e.getBoundingClientRect();
    if (b.width > 1 && b.height > 1) gfx.push([b.left, b.top, b.right, b.bottom]);
  }
  // 有底色的按鈕/膠囊(Follow 之類淺底圓角色塊):底色與頁面底色亮度差 >0.15、高 <=120 寬 <=600;色塊併入 gfx,按鈕內的字仍是文字框
  const lumOf = c => { const m = c.match(/[\d.]+/g); if (!m || m.length < 3 || (m.length > 3 && +m[3] < 0.9)) return null;
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(+m[0]) + 0.7152 * f(+m[1]) + 0.0722 * f(+m[2]); };
  const baseLum = e => { for (let p = e.parentElement; p; p = p.parentElement) { const l = lumOf(getComputedStyle(p).backgroundColor); if (l !== null) return l; } return 1; };
  for (const t of window.__targets) for (const e of [t, ...t.querySelectorAll('*')]) {
    if (!e.checkVisibility()) continue;
    const cs = getComputedStyle(e), l = lumOf(cs.backgroundColor);
    if (l === null) continue;
    if (!(e.matches('button,[role=button]') || parseFloat(cs.borderTopLeftRadius) >= 6)) continue;
    const b = e.getBoundingClientRect();
    if (b.width > 1 && b.height > 1 && b.height <= 120 && b.width <= 600 && Math.abs(l - baseLum(e)) > 0.15) gfx.push([b.left, b.top, b.right, b.bottom]);
  }
  return {runs: out, rects: runs.map(c => c.rect), gfx};
}
"""


_FW = {",": "，", ":": "：", ";": "；", "!": "！", "?": "？", "(": "（", ")": "）"}
_CJK = "　-〿一-鿿＀-￯"


def fw(s):
    """中文旁的半形標點改全形(規格裡可直接打半形)"""
    import re
    return re.sub(rf"(?<=[{_CJK}])[,:;!?()]|[,:;!?()](?=[{_CJK}])", lambda m: _FW[m.group(0)], s)


JS_DOCSIZE = r"""
() => {
  const b = document.body, e = document.documentElement;
  return [Math.max(b.scrollWidth, e.scrollWidth, b.offsetWidth, e.offsetWidth, b.clientWidth, e.clientWidth),
          Math.max(b.scrollHeight, e.scrollHeight, b.offsetHeight, e.offsetHeight, b.clientHeight, e.clientHeight)];
}
"""


def _frame_color(img):
    """圖片最外圈最常見的顏色(補邊用)"""
    from collections import Counter
    w, h = img.size
    px = [img.getpixel((x, y)) for x in range(0, w, 3) for y in (0, h - 1)]
    px += [img.getpixel((x, y)) for y in range(0, h, 3) for x in (0, w - 1)]
    return Counter(px).most_common(1)[0][0]


# ---------- 擷取 ----------

_PREP_NOCLICK = JS_PREP.replace("try { b.click(); } catch (e) {}", "")   # noscroll:不點「No thanks」類連結(SiliconANGLE 的會觸發整頁重載)


def _wait_load(pg, ms=4000, noscroll=False):
    pg.wait_for_timeout(ms)
    if noscroll:
        pg.wait_for_timeout(1200)
        return
    # 觸發 lazy-load
    pg.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}scrollTo(0,0)}")
    pg.wait_for_timeout(1200)


# ---- 通用暗色三層(spec 欄位 dark:auto|native|force|js|off;說明見檔頭與 docs/assets.md「暗色」)----
DARK_DEFAULT = "auto"    # 沒寫 dark 的 spec 用這個;True 視同預設,False = off
FORCE_ARGS = ["--enable-features=WebContentsForceDark:inversion_method/cielab_based/image_behavior/none"]   # 圖片不反相
_PW = None                # build() 註冊的 playwright 實例(第二層要另開強制深色的瀏覽器)
_FB = None                # 強制深色瀏覽器(用到才開,build 結束時關)
_DARK_LAYER = {}          # (url, targets) -> 實際用了哪層:dark0(原本深色)|native|force|js|off;auto 只探測一次,量測與截圖兩次開頁共用


class _NeedForce(Exception):
    pass


def _dark_mode(sp):
    d = sp.get("dark", DARK_DEFAULT)
    return "off" if d is False else DARK_DEFAULT if d is True else d


def _dark_key(sp):
    return (sp["url"], repr(sp["targets"]))


def _force_browser():
    """第二層用:啟動參數層級的功能旗標無法對單一 context 開關,所以另開一支帶旗標的瀏覽器,只有真的需要的頁面才開(沒有 build() 註冊的 playwright 時回 None)"""
    global _FB
    if _FB is None and _PW is not None:
        _FB = _PW.chromium.launch(channel="msedge", headless=True, args=FORCE_ARGS)
    return _FB


def _open(browser, sp, dsf, dump=False, layout=False, hook=None):
    """開頁 -> 保留區塊 -> 翻譯;回傳 (ctx, page, 量測框, 版面資料或 None)。layout=True 時量每個文字框(截圖那一次才需要)
    暗色三層(PLAN_閱讀卡 §2B):①emulate_media dark(網站原生深色)②沒有原生 -> 強制深色瀏覽器(WebContentsForceDark)③JS_CAL 校色。
    dark=auto 先探測(emulate 後底色仍亮才升級),結果記在 _DARK_LAYER;native/force/js/off 直接指定"""
    mode, key = _dark_mode(sp), _dark_key(sp)
    if mode == "auto":
        mode = _DARK_LAYER.get(key, "probe")
    if mode == "force":
        fb = _force_browser()
        if fb is None:
            print("  [暗色] 沒有強制深色瀏覽器可用,改走舊 JS 變色")
            mode = "js"
        else:
            browser = fb
    try:
        r = _open1(browser, sp, dsf, dump, layout, hook, mode)
    except _NeedForce:
        _DARK_LAYER[key] = "force"
        return _open(browser, dict(sp, dark="force"), dsf, dump, layout, hook)
    if _dark_mode(sp) == "auto" and key not in _DARK_LAYER:
        _DARK_LAYER[key] = r[4]
    return r[:4]


NOTO_HOST = "https://noto-font.invalid/"   # 頁面是 http(s),不能直接載 file:// 字型:用 context.route 把這個虛擬網址導到本機靜態檔
NOTO_FACE = ('@font-face {font-family: "Noto Sans TC Static"; font-weight: 400; src: url("%sreg.ttf");} '
             '@font-face {font-family: "Noto Sans TC Static"; font-weight: 700; src: url("%sbold.ttf");} ' % (NOTO_HOST, NOTO_HOST))


def _serve_noto(route):
    f = P.FONT_BOLD if route.request.url.endswith("bold.ttf") else P.FONT_REG
    route.fulfill(path=str(f), content_type="font/ttf", headers={"Access-Control-Allow-Origin": "*"})


def _open1(browser, sp, dsf, dump, layout, hook, plan):
    """plan: off | js(舊版整套變色) | native(emulate dark + 校色) | probe(emulate dark 後探測:原本深色 -> dark0 全略過;原生深色 -> native;仍亮 -> 升級 force 或退回 js) | force(強制深色瀏覽器 + 校色)。
    多回傳第 5 項 = 實際層"""
    dark_scheme = plan in ("native", "probe", "force")
    ctx = browser.new_context(viewport={"width": sp["vw"], "height": 1000}, locale="en-US", device_scale_factor=dsf,
                              user_agent=sp.get("ua", UA_WEB), color_scheme="dark" if dark_scheme else "light", bypass_csp=True)
    ctx.route(NOTO_HOST + "**", _serve_noto)
    if sp.get("cookies"):
        ctx.add_cookies([dict(name=k, value=v, domain=sp["cookie_domain"], path="/") for k, v in sp["cookies"].items()])
    pg = ctx.new_page()
    pg.goto(sp["url"], wait_until="domcontentloaded", timeout=60000)
    _wait_load(pg, sp.get("wait", 4000), noscroll=sp.get("noscroll", False))
    prep = _PREP_NOCLICK if sp.get("noscroll") else JS_PREP
    r = pg.evaluate(prep, [[t if isinstance(t, (list, tuple)) else (t, "") for t in sp["targets"]], NOTO_FACE + sp.get("css", "")])
    if "error" in r:
        raise RuntimeError(f"{sp['url']}: {r['error']}")
    if sp.get("js"):
        pg.evaluate(sp["js"])
    layer = plan
    if plan == "probe":    # 第一層之後底色仍亮 = 網站沒有原生深色;切回 light 仍暗 = 原本就是深色(三層都略過)
        if pg.evaluate(JS_BASELUM) < 0.5:
            pg.emulate_media(color_scheme="light")
            pg.wait_for_timeout(200)
            layer = "dark0" if pg.evaluate(JS_BASELUM) < 0.5 else "native"
            pg.emulate_media(color_scheme="dark")
            pg.wait_for_timeout(200)
        elif _PW is not None:
            ctx.close()
            raise _NeedForce()
        else:
            layer = "js"
    if sp.get("min_px"):   # 窄版:頁內字放大
        pg.evaluate(JS_MINFONT, sp["min_px"])
    if sp.get("hide_float"):   # 窄版:浮動小圖示
        pg.evaluate(JS_HIDE_FLOAT)
    if dump and dsf == 1:
        for t in pg.evaluate(JS_BLOCKS):
            print("   >", json.dumps(t, ensure_ascii=False))
    if hook:   # 翻譯前的原文(閱讀卡抽原題用)
        hook(pg)
    miss = pg.evaluate(JS_TRANSLATE, [[k, fw(z)] for k, z in sp["rules"]])
    if miss:
        raise RuntimeError("規則找不到對應文字:\n  " + "\n  ".join(m[:80] for m in miss))
    if layer == "js":         # 舊版:整套變色(白底才動,原本深色略過)
        pg.evaluate(JS_DARK, [DARK_BG, DARK_FG])
    elif layer in ("native", "force"):    # 第三層:只校色(JS_CAL:底色 -> #15202b、主字 -> #e7e9ea);dark0 不動
        pg.evaluate(JS_CAL, [DARK_BG, DARK_FG])
    if dsf == 1:
        keep = set(sp.get("keep_en", []))
        left = [s for s in pg.evaluate(JS_LEFTOVER) if s not in keep]
        if left:
            print("  [未翻譯英文]", *left, sep="\n    ")
    pg.wait_for_timeout(500)
    m = pg.evaluate(JS_MEASURE)
    lay = None
    if layout:
        try:
            lay = pg.evaluate(JS_LAYOUT)
        except Exception as e:  # 量測失敗不影響截圖
            print("  [版面量測失敗]", str(e)[:200])
    return ctx, pg, m, lay, layer


# ---------- 閱讀卡(mode: card;計畫 PLAN_閱讀卡 §2A) ----------

CARD_DIR = P.TMP / "cards"
CARD_TPL = Path(__file__).resolve().parent / "templates" / "readercard"
CARD_FONT_BOLD = P.ROOT / "fonts" / "NotoSansTC-SubBold.ttf"
CARD_FONT_REG = P.ROOT / "fonts" / "NotoSansTC-Regular-static.ttf"   # 內文,wght=400 靜態檔(不用系統字型)
from text_wrap import card_cut as _card_cut, wbr_html as _wbr_html  # noqa: E402  共用斷詞(2026-10-22 抽出)
CARD_TITLE_EN_MAX = 110   # 標題下的英文原題最長字數,超過截短加「……」

# 翻譯前:抓原頁的 meta 與標題/署名/日期/貼文欄位原文(元素記在 window.__cardEls,翻譯後再讀一次譯文)
JS_CARD_META = r"""
(c) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const q = s => { try { return s ? document.querySelector(s) : null; } catch (e) { return null; } };
  const mt = k => { const m = document.querySelector('meta[property="' + k + '"],meta[name="' + k + '"]'); return m ? m.content : ''; };
  const els = {};
  for (const k of ['title', 'byline', 'date', 'name', 'time', 'likes']) { const e = q(c[k + '_sel']); if (e) els[k] = e; }
  window.__cardEls = els;
  const en = {}; for (const k in els) en[k] = norm(els[k].textContent);
  const t = document.querySelector('time[datetime]');
  return {en, site: mt('og:site_name'), image: mt('og:image'), pub: mt('article:published_time') || (t ? t.dateTime : '')};
}
"""
# 翻譯後:各欄位譯文 + 段落(targets 內不屬於標題/署名等欄位的文字;<br> 當段落分隔)
JS_CARD_PARAS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const els = window.__cardEls || {}, special = Object.values(els), zh = {}, paras = [];
  for (const k in els) zh[k] = norm(els[k].textContent);
  for (const t of window.__targets) {
    if (special.some(e => e === t || e.contains(t))) continue;
    const c = t.cloneNode(true);
    c.querySelectorAll('br').forEach(b => b.replaceWith('\n'));
    // page 模式為了逐行對齊,譯文在 <br> 處斷行;card 模式交給瀏覽器排版,所以同一個 target 內單個 <br> 的片段合併成一段
    // (前一片段以「…」結尾 = 摘錄之間的分隔,另起一段);連續兩個 <br> 才是明確的段落分隔
    for (const blk of c.textContent.split(/\n{2,}/)) {
      let cur = '';
      for (const s of blk.split('\n')) {
        const v = norm(s); if (!v) continue;
        if (cur && /[…]$/.test(cur)) { paras.push(cur); cur = ''; }
        cur += (/[A-Za-z0-9]$/.test(cur) && /^[A-Za-z0-9]/.test(v) ? ' ' : '') + v;
      }
      if (cur) paras.push(cur);
    }
  }
  return {zh, paras};
}
"""


def _split_site(site):
    """spec 的 site(「網站名 2026/10」或「=來源:xxx」)拆成 (網站名, 日期)"""
    s = re.sub(r"^來源[:：]", "", site.lstrip("="))
    m = re.match(r"^(.*?)\s+(\d{4}(?:/\d{1,2}){0,2})$", s)
    return (m.group(1), m.group(2)) if m else (s, "")


def _cut(s, n):
    return s if len(s) <= n else s[:n].rstrip(" ,.;:、，") + "……"


def card_render(layout, v):
    """模板 + 變數 -> HTML(變數值已是 HTML;CSS/JS 內嵌,單檔可直接開)"""
    t = (CARD_TPL / f"{layout}.html").read_text(encoding="utf-8")
    for k, val in v.items():
        t = t.replace("{{" + k + "}}", val)
    css = (CARD_TPL / "card.css").read_text(encoding="utf-8").replace("{{FONT_BOLD}}", CARD_FONT_BOLD.as_uri()).replace("{{FONT_REG}}", CARD_FONT_REG.as_uri())
    return t.replace("{{CSS}}", css).replace("{{JS}}", (CARD_TPL / "card.js").read_text(encoding="utf-8"))


def card_prepare(browser, sp):
    """mode: card -> 抽取原頁內容、寫 tmp/cards/<name>.json/.html,回傳指向本機 HTML 的 spec(其餘流程與 page 完全相同)"""
    import html as H
    c, name = dict(sp.get("card") or {}), sp.get("_name", "card")
    if c.get("title") and not c.get("title_sel"):
        c["title_sel"] = "h1"
    holder = {}
    ctx, pg, _, _ = _open(browser, dict(sp, mode="page", dark=False), 1, hook=lambda p: holder.update(meta=p.evaluate(JS_CARD_META, c)))
    try:
        meta, got = holder["meta"], pg.evaluate(JS_CARD_PARAS)
        hero, hero_fail = None, None   # hero_fail:寫進 tmp/cards/<名>.json,make_version 的「畫面優先看清單」讀
        want_hero = c.get("hero", True) and c.get("layout", "article") == "article"
        if want_hero and meta["image"]:
            try:
                r = ctx.request.get(meta["image"], headers={"Referer": sp["url"]}, timeout=20000)
                if r.ok and len(r.body()) > 2000:
                    CARD_DIR.mkdir(parents=True, exist_ok=True)
                    hero = CARD_DIR / f"{name}_hero.jpg"
                    hero.write_bytes(r.body())
                else:
                    print(f"  [卡] hero 圖抓失敗({r.status}),退回純文字版")
                    hero_fail = f"hero 圖抓失敗({r.status})"
            except Exception as e:
                print(f"  [卡] hero 圖抓失敗({str(e)[:80]}),退回純文字版")
                hero_fail = f"hero 圖抓失敗({str(e)[:40]})"
        elif want_hero:
            print("  [卡] 原頁沒有 og:image,純文字版")
            hero_fail = "原頁沒有 og:image"

    finally:
        ctx.close()
    en, zh = meta["en"], got["zh"]
    if not got["paras"]:
        raise RuntimeError(f"{name}: 閱讀卡抽不到段落(targets 內沒有非標題文字)")
    site_name, date = _split_site(sp["site"])
    if c.get("lang") != "zh" and zh.get("date") and en.get("date") != zh["date"]:
        date = zh["date"]
    title = zh.get("title") if zh.get("title") and zh["title"] != en.get("title") else c.get("title")   # 標題沒被 rules 翻譯就用 card.title
    e = H.escape
    foot = ("原文:" if c.get("lang") == "zh" else "中文翻譯 · 原文:") + site_name + (f" · {date}" if date else "")
    v = dict(site=e(site_name), date_html=f"<span>{e(date)}</span>" if date else "", foot=e(fw(foot)),
             paras_html="".join(f"<p>{_wbr_html(p)}</p>" for p in got["paras"]), title="", title_en_html="", byline_html="", hero_html="",
             initial="", name="", time_html="", stats_html="")
    layout = c.get("layout") or ("article" if title else "para")
    if layout == "article":
        if not title:
            raise RuntimeError(f"{name}: article 版型要有標題(rules 翻譯標題,或 card.title 給中文)")
        v["title"] = _wbr_html(fw(title))
        if en.get("title"):
            v["title_en_html"] = f'<div class="title-en">{e(_cut(en["title"], CARD_TITLE_EN_MAX))}</div>'
        if en.get("byline") or zh.get("byline"):
            v["byline_html"] = f'<div class="byline">{e(zh.get("byline") or en["byline"])}</div>'
        if hero:
            v["hero_html"] = f'<div class="hero"><img src="{hero.as_uri()}"></div>'
    elif layout == "post":
        who = zh.get("name") or en.get("name") or site_name
        v.update(name=e(who), initial=e(who[:1]), time_html=f'<div class="time">{e(zh.get("time") or en.get("time") or date)}</div>')
        if zh.get("likes") or en.get("likes"):
            v["stats_html"] = f'<div class="stats">{e(zh.get("likes") or en["likes"])}</div>'
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    hf = CARD_DIR / f"{name}.html"
    hf.write_text(card_render(layout, v), encoding="utf-8")
    shown = _cut(en.get("title") or "", CARD_TITLE_EN_MAX)
    keep_en = [x for x in [site_name, en.get("title"), shown, shown[:90], en.get("byline"), en.get("name"), zh.get("name"), zh.get("byline")] if x]
    out = dict(sp, mode="page", url=hf.as_uri(), vw=1920, targets=[".card"], rules=[], css="", js=None, dark=False, wait=700, noscroll=True,
               padx=60, pady=60, edge_px=0, top_px=0, keep_en=keep_en + list(sp.get("keep_en", [])))
    for k in ("cookies", "cookie_domain", "ua", "min_px", "hide_float"):
        out.pop(k, None)
    pg2 = browser.new_page(viewport={"width": 1920, "height": 1080})   # 讀字級自適應結果(寫進 json,有問題印警告)
    try:
        pg2.goto(hf.as_uri())
        pg2.wait_for_function("document.documentElement.dataset.fit === '1'", timeout=10000)
        info = pg2.evaluate("window.__cardInfo")
    finally:
        pg2.close()
    data = dict(name=name, layout=layout, url=sp["url"], site=site_name, date=date, title=title, title_en=en.get("title"),
                byline=zh.get("byline") or en.get("byline"), paragraphs=got["paras"], hero=str(hero) if hero else None, fit=info,
                hero_fail=hero_fail)
    hf.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    warn = []
    if info["lines"] > 6:
        warn.append(f"摘錄 {info['lines']} 行 > 6")
    if info["title_lines"] > 2:
        warn.append(f"標題 {info['title_lines']} 行 > 2")
    if info["blank"] > info["cap"]:
        warn.append(f"主欄留白 {info['blank']}px > 卡高 25%({info['cap']}px)")
    if not info["sw"]:
        warn.append("主欄橫向溢出")
    print(f"  [卡] {layout} 摘錄 {info['fs']}px {info['lines']} 行 留白 {info['blank']}px"
          + (f" 標題 {info['title_fs']}px {info['title_lines']} 行" if info.get("title_fs") else "") + (" hero" if hero and not info.get("hero_dropped") else "") + (" [hero 因摘錄太長移除]" if info.get("hero_dropped") else ""))
    if warn:
        print("  [卡·警告]", "; ".join(warn))
    return out


def _hl_layers(pg, kws, vclip, cbox, width):
    """底線圖層序列(計畫 §2C):主圖截完後在同一頁包 span、只留底線,每條底線 p = 1/HL_STEPS … 1 各截一張,
    裁切/補邊/縮放與主圖完全相同(錯位 0)。回傳 [dict(k=詞序, x, y, frames=[RGBA × (HL_STEPS+1),第 0 張為 p=0 空圖])],
    座標為 capture 輸出圖像素;包 span 改動版面時回傳 [](build 走舊畫法)"""
    import io
    r = pg.evaluate(JS_HL_WRAP, [list(kws), HL_MAX])
    if r["shift"]:
        print(f"  [紅線] 包 span 後有 {r['shift']} 段位置改變,不出底線序列(build 改用舊畫法)")
        return []
    if not r["bars"]:
        return []
    vx0, vy0, vx1, vy1 = vclip
    cx0, cy0, cw, chh = cbox
    before = pg.evaluate(JS_HL_RECTS)
    pg.evaluate(JS_HL_LAYER, HL_LAYER_CSS)
    after = pg.evaluate(JS_HL_RECTS)
    moved = [(i, round(max(abs(a - c) for a, c in zip(r0, r1)), 1)) for i, (r0, r1) in enumerate(zip(before, after))
             if max(abs(a - c) for a, c in zip(r0, r1)) > HL_SHIFT_MAX]
    if moved:
        print(f"  [紅線] 切成底線圖層後 span 位置改變 {moved[:4]}(條序, 最大位移 px),與主圖對不齊,不出底線序列(build 改用舊畫法)")
        return []
    pg.evaluate(JS_HL_BASE, [HL_UL_BASE, cy0 + chh])   # 在圖層頁上量基線(與截圖同一版面)
    # 每條底線只在自己 span 附近找像素(頁面上漏網的圖示/emoji 不算進來):左右各 0.3em、下方 0.4em,換成輸出像素
    f = width / cw
    wins = [[(a - cx0) * f, (t - cy0) * f, (c - cx0) * f, (d - cy0) * f] for a, t, c, d in pg.evaluate(
        "() => [...document.querySelectorAll('span.hl')].map(s => { const r = s.getBoundingClientRect(),"
        " e = parseFloat(getComputedStyle(s).fontSize); return [r.left - 0.3 * e, r.top, r.right + 0.3 * e, r.bottom + 0.4 * e]; })")]

    def shot():
        png = pg.screenshot(clip=dict(x=vx0, y=vy0, width=vx1 - vx0, height=vy1 - vy0), full_page=True, omit_background=True)
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        if vx0 > cx0 or vy0 > cy0 or vx1 < cx0 + cw or vy1 < cy0 + chh:
            ks = im.width / (vx1 - vx0)
            full = Image.new("RGBA", (round(cw * ks), round(chh * ks)), (0, 0, 0, 0))
            full.paste(im, (round((vx0 - cx0) * ks), round((vy0 - cy0) * ks)))
            im = full
        if im.width != width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        return im

    out = []
    for b, k in enumerate(r["bars"]):
        frames = []
        for st in range(1, HL_STEPS + 1):
            pg.evaluate("([b, p]) => document.querySelectorAll('span.hl').forEach(s => s.style.setProperty('--p', s.dataset.b == b ? p : 0))",
                        [b, st / HL_STEPS])
            frames.append(shot())
        w = [max(0, round(wins[b][0])), max(0, round(wins[b][1])), round(wins[b][2]), round(wins[b][3])]
        bb = frames[-1].getchannel("A").crop(w).getbbox()
        bb = bb and (bb[0] + w[0], bb[1] + w[1], bb[2] + w[0], bb[3] + w[1])
        if not bb:
            print(f"  [紅線] 第 {b} 條底線在 span 附近 {w} 截不到像素(整張 {frames[-1].getchannel('A').getbbox()}),略過")
            continue
        out.append(dict(k=k, x=bb[0], y=bb[1], frames=[Image.new("RGBA", (bb[2] - bb[0], bb[3] - bb[1]), (0, 0, 0, 0))]
                        + [f.crop(bb) for f in frames]))
    return out


def capture(browser, sp, width=FW, dump=False, hl=None, hl_out=None):
    """回傳 (PIL.Image 寬 width, runs[像素,相對該圖左上], 版面資料)。兩段式:先 DSF=1 量測,再以 DSF=width/內容寬 截圖
    選用欄位:edge_px = 成片上左右至少留幾 px(換算成 padx 下限)、top_px = 成片上緣至少留幾 px(只加大上方留邊)
    hl(底線詞)+ hl_out(list):另把底線圖層序列附加到 hl_out(見 _hl_layers)"""
    import io
    import math
    if sp.get("mode") == "card":
        sp = card_prepare(browser, sp)
    padx, pady = sp.get("padx", 14), sp.get("pady", 10)
    ctx, pg, m, _ = _open(browser, sp, 1, dump)
    ctx.close()
    if dump:
        print("   measure", {k: round(v) for k, v in m.items()})
    if sp.get("edge_px"):   # 內容愈寬倍率愈小,頁面 px 要墊愈多
        e = sp["edge_px"]
        padx = max(padx, math.ceil(e * (m["x1"] - m["x0"]) / (width - 2 * e)))
    padt = pady
    if sp.get("top_px"):
        padt = max(pady, math.ceil(sp["top_px"] * ((m["x1"] - m["x0"]) + 2 * padx) / width))
    cw, chh = (m["x1"] - m["x0"]) + 2 * padx, (m["y1"] - m["y0"]) + padt + pady
    sc = width / cw
    ctx, pg, m2, lay = _open(browser, sp, sc, dump, layout=True)
    cx0, cy0 = m2["x0"] - padx, m2["y0"] - padt
    # 截取區超出文件範圍(區塊貼著頁面左/上緣,或撐出頁面右緣)時 Playwright 會把 clip 裁進文件內:
    # 圖變窄、原點不再是 (cx0, cy0),之後又被拉回 width -> 文字貼邊且與框錯位。改成自己裁、再把缺的邊補回去
    dw, dh = pg.evaluate(JS_DOCSIZE)
    vx0, vy0, vx1, vy1 = max(0, cx0), max(0, cy0), min(dw, cx0 + cw), min(dh, cy0 + chh)
    png = pg.screenshot(clip=dict(x=vx0, y=vy0, width=vx1 - vx0, height=vy1 - vy0), full_page=True)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if vx0 > cx0 or vy0 > cy0 or vx1 < cx0 + cw or vy1 < cy0 + chh:
        ks = img.width / (vx1 - vx0)
        full = Image.new("RGB", (round(cw * ks), round(chh * ks)), _frame_color(img))
        full.paste(img, (round((vx0 - cx0) * ks), round((vy0 - cy0) * ks)))
        img = full
    pg.evaluate("scrollTo(0, 0)")
    runs = pg.evaluate(JS_RUNS)
    if hl and hl_out is not None:   # 主圖與 boxes 已取完,才包 span、改成底線圖層
        hl_out.extend(_hl_layers(pg, hl, (vx0, vy0, vx1, vy1), (cx0, cy0, cw, chh), width))
    ctx.close()
    k = img.width / cw
    out = []
    for r_ in runs:
        b = r_["box"]
        out.append(dict(text=r_["text"],
                        box=[round((b[0] - cx0) * k), round((b[1] - cy0) * k), round((b[2] - cx0) * k), round((b[3] - cy0) * k)],
                        chars=[[round((a - cx0) * k), round((c - cx0) * k)] for a, c in r_["chars"]]))
    if img.width != width:
        f = width / img.width
        img = img.resize((width, round(img.height * f)), Image.LANCZOS)
        for o in out:
            o["box"] = [round(v * f) for v in o["box"]]
            o["chars"] = [[round(a * f), round(c * f)] for a, c in o["chars"]]
    return img, out, lay


def _bg(img):
    return img.getpixel((4, 4))


def _tag(canvas, text, x=18, y=14):
    """子塊左上角網站名標籤(僅合成圖用)"""
    d = ImageDraw.Draw(canvas)
    f = font(34, True)   # assets_lib.font = Noto Sans TC 粗體(2026-10-22 起)
    w = d.textlength(text, font=f)
    d.rounded_rectangle((x, y, x + w + 28, y + 56), 10, fill=(0, 0, 0))
    d.text((x + 14, y + 9), text, font=f, fill=(255, 255, 255))


def compose(browser, sp, dump=False, hl=None, hl_out=None):
    """單頁 -> 1920x1080 畫布;parts -> 直向堆疊。回傳 (canvas, runs, info);info = 單頁的 {lay, img_h, oy}(合成圖為 None)
    hl + hl_out:底線圖層序列(座標已換成畫布像素)附加到 hl_out"""
    if "parts" not in sp:
        bars = []
        img, runs, lay = capture(browser, sp, dump=dump, hl=hl, hl_out=bars)
        if img.height > FH - 70 and sp.get("mode") != "card":
            print(f"  [警告] 內容高 {img.height} > {FH - 70},底部可能被標籤/字幕壓到")
        oy = max(0, min((FH - img.height) // 2, sp.get("oy_max", 40)))
        canvas = Image.new("RGB", (FW, FH), _bg(img))
        canvas.paste(img, (0, oy))
        for r in runs:
            r["box"][1] += oy
            r["box"][3] += oy
        if hl_out is not None:
            hl_out.extend(dict(b, y=b["y"] + oy) for b in bars)
        return canvas, runs, dict(lay=lay, img_h=img.height, oy=oy)
    parts, gap, y = [], sp.get("gap", 26), 0
    for p in sp["parts"]:
        bars = []
        img, runs, _ = capture(browser, p, p.get("width", FW), dump=dump, hl=hl, hl_out=bars)
        parts.append((img, runs, p, bars))
    TAG_H = 68  # 網站名標籤列(在每塊上方,不蓋住內容)
    total = sum(i.height + (TAG_H if p.get("tag") else 0) for i, _, p, _ in parts) + gap * (len(parts) - 1)
    if total > FH - 70:
        print(f"  [警告] 堆疊高 {total} > {FH - 70}")
    canvas = Image.new("RGB", (FW, max(FH, total)), sp.get("bg", (21, 32, 43)))
    allruns = []
    for img, runs, p, bars in parts:
        x = (FW - img.width) // 2
        if p.get("tag"):
            _tag(canvas, p["tag"], x + 8, y + 4)
            y += TAG_H
        canvas.paste(img, (x, y))
        for r in runs:
            r["box"] = [r["box"][0] + x, r["box"][1] + y, r["box"][2] + x, r["box"][3] + y]
            r["chars"] = [[a + x, c + x] for a, c in r["chars"]]
            allruns.append(r)
        if hl_out is not None:
            hl_out.extend(dict(b, x=b["x"] + x, y=b["y"] + y) for b in bars)
        y += img.height + gap
    return canvas, allruns, None


def _narrow_sp(sp):
    """窄版 spec:視窗寬 <= NARROW_VW、css 寬度壓到 NARROW_CSS_W、頁內字至少 NARROW_MIN_PX、輸出 NARROW_W 寬、隱藏浮動小圖示。"""
    css = re.sub(r"((?<![-\w])(?:max-)?width:\s*)(\d+)px", lambda m: f"{m.group(1)}{min(int(m.group(2)), NARROW_CSS_W)}px", sp.get("css", ""))
    css += " body * {white-space: normal !important; flex-wrap: wrap !important;}"   # 不換行的列在窄版會超出右緣
    return dict(sp, vw=min(sp.get("vw", NARROW_VW), NARROW_VW), css=css, min_px=NARROW_MIN_PX, width=NARROW_W,
                padx=10, edge_px=NARROW_EDGE_PX, hide_float=True)


def compose_narrow(browser, sp, dump=False):
    """窄版:單頁 / parts 直向堆疊成 NARROW_W 寬的圖(不放進 1920x1080 畫布),底下多留標籤列。回傳同 compose。"""
    lab_h = NARROW_LABEL_FS + 44
    if "parts" not in sp:
        sp = _narrow_sp(sp)
        img, runs, lay = capture(browser, sp, NARROW_W, dump=dump)
        canvas = Image.new("RGB", (NARROW_W, img.height + lab_h), _bg(img))
        canvas.paste(img, (0, 0))
        return canvas, runs, dict(lay=lay, img_h=img.height, oy=0)
    parts, gap = [capture(browser, _narrow_sp(p), NARROW_W, dump=dump) + (p,) for p in sp["parts"]], sp.get("gap", 26)
    TAG_H = 68
    total = sum(i.height + (TAG_H if p.get("tag") else 0) for i, _, _, p in parts) + gap * (len(parts) - 1)
    canvas = Image.new("RGB", (NARROW_W, total + lab_h), sp.get("bg", (21, 32, 43)))
    allruns, y = [], 0
    for img, runs, _, p in parts:
        if p.get("tag"):
            _tag(canvas, p["tag"], 8, y + 4)
            y += TAG_H
        canvas.paste(img, (0, y))
        for r in runs:
            r["box"] = [r["box"][0], r["box"][1] + y, r["box"][2], r["box"][3] + y]
            allruns.append(r)
        y += img.height + gap
    return canvas, allruns, None


def _save_layout(out, sp, canvas, runs, info):
    """存 .layout.json:截取區(畫布座標)+ 每個 run 的 cov/clip/字級(換算成成片像素)+ gfx(非文字圖形的框,畫布像素)"""
    lay = info["lay"] if info else None
    if "parts" in sp or lay is None or len(lay["runs"]) != len(runs):
        print("  [版面資料略過]", "合成圖" if "parts" in sp else f"量測筆數 {None if lay is None else len(lay['runs'])} != runs {len(runs)}")
        return
    oy = info["oy"]
    items = []
    for r, L in zip(runs, lay["runs"]):
        k = (r["box"][3] - r["box"][1]) / L["h"] if L["h"] else 1
        items.append(dict(cov=L["cov"], clip=L["clip"], fs=round(L["fs"] * k, 1)))
    gfx = []
    if runs and lay["gfx"]:   # 頁面座標 -> 畫布像素:拿最寬的一行(頁面框 p <-> 畫布框 b)換算
        i = max(range(len(runs)), key=lambda j: lay["rects"][j][2] - lay["rects"][j][0])
        p, b = lay["rects"][i], runs[i]["box"]
        k = (b[2] - b[0]) / (p[2] - p[0])
        gfx = [[max(0, round(b[j % 2] + (g[j] - p[j % 2]) * k)) for j in range(4)] for g in lay["gfx"]]
    Path(out).with_suffix(".layout.json").write_text(
        json.dumps(dict(region=[0, oy, canvas.width, oy + info["img_h"]], runs=items, gfx=gfx, kind=_layout_kind(sp, canvas, runs, info)),
                   ensure_ascii=False), encoding="utf-8")


def _save_tag_text(out, site):
    """出處標籤字串寫進 .layout.json 的 tag_text(2026-10-22;build.py 把標籤改成 kit lower 下標籤時用,舊圖沒有就退回右下角標);
    沒有 .layout.json(合成圖等)就不寫。"""
    f = Path(out).with_suffix(".layout.json")
    if not f.exists():
        return
    d = json.loads(f.read_text(encoding="utf-8"))
    d["tag_text"] = site[1:] if site.startswith("=") else f"中文翻譯 · 原文:{site}"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


KIND_TEXT_AREA = 0.40   # page 模式:文字框面積占截圖區 > 這個比例就算文字類(build.py 文字類用緩慢 zoom+漂移,不傾斜)


def _layout_kind(sp, canvas, runs, info):
    """.layout.json 的 kind:"text"(閱讀卡、以文字為主的頁)| "photo"(照片/實機截圖為主,build.py 仍輪用 tilt)。
    spec 明寫 kind 就照寫;card 模式一律 text;page 模式看文字框面積占截圖區的比例。"""
    if sp.get("kind") in ("text", "photo"):
        return sp["kind"]
    if sp.get("mode") == "card":
        return "text"
    area = canvas.width * info["img_h"]
    txt = sum(max(0, r["box"][2] - r["box"][0]) * max(0, r["box"][3] - r["box"][1]) for r in runs)
    return "text" if area > 0 and txt / area > KIND_TEXT_AREA else "photo"


# ---------- 指令 ----------

def _norm_specs(SPECS):
    """接受 {name: spec} 或 [spec(含 name)]"""
    return dict(SPECS) if isinstance(SPECS, dict) else {s["name"]: s for s in SPECS}


def _save_hl(out, kws, bars, size):
    """底線序列:<圖>_hl/b<序>_p<00..10>.png + <圖>.hl.json(build.py prep_hl 讀;格式見 docs/assets.md「紅線序列」)。
    先清掉舊序列,沒有底線就只清不寫(build 看不到 .hl.json 就走舊畫法)"""
    import shutil
    d, idx = out.parent / f"{out.stem}_hl", out.with_suffix(".hl.json")
    if d.exists():
        shutil.rmtree(d)
    idx.unlink(missing_ok=True)
    if not bars:
        return
    d.mkdir()
    rows = []
    bars = sorted(enumerate(bars), key=lambda t: (t[1]["k"], t[0]))   # 詞序 -> 文件序(同 build.py find_hl_boxes 的順序)
    for j, (_, b) in enumerate(bars):
        files = []
        for i, fr in enumerate(b["frames"]):
            fn = f"{d.name}/b{j}_p{i:02d}.png"
            fr.save(out.parent / fn)
            files.append(fn)
        rows.append(dict(kw=kws[b["k"]], x=b["x"], y=b["y"], w=b["frames"][0].width, h=b["frames"][0].height, files=files))
    idx.write_text(json.dumps(dict(ver=1, size=list(size), p=[i / HL_STEPS for i in range(HL_STEPS + 1)], bars=rows),
                              ensure_ascii=False), encoding="utf-8")


def build(SPECS, names=None, prefix="", out_dir=IMG, dump=False, narrow=False, HL=None):
    from playwright.sync_api import sync_playwright
    SPECS, HL = _norm_specs(SPECS), HL or {}
    names = names or list(SPECS)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    global _PW, _FB
    with sync_playwright() as p:
        _PW = p
        b = p.chromium.launch(channel="msedge", headless=True)
        for n in names:
            sp = {"padx": 34, "edge_px": EDGE_PX, "top_px": TOP_PX, **SPECS[n]}   # 左右、上方多留邊,避免文字貼邊
            sp["_name"] = n
            if dump:  # 先看原文:不套翻譯規則(找不到也不報錯);閱讀卡也看原頁
                sp = dict(sp, rules=[], mode="page")
            print("==", n, flush=True)
            kws, bars = ([] if narrow or dump else list(HL.get(n, sp.get("hl", [])))), []
            try:
                canvas, runs, info = compose_narrow(b, sp, dump) if narrow else compose(b, sp, dump, hl=kws, hl_out=bars)
            except Exception as e:  # 單頁失敗不影響其餘
                print("  [失敗]", str(e)[:600])
                continue
            if narrow:
                add_label(canvas, sp["site"], NARROW_LABEL_FS)
            elif sp.get("mode") != "card":   # 閱讀卡的出處在卡內底列
                add_label(canvas, sp["site"])
            if dump:
                continue
            out = out_dir / f"{prefix}{n}{'_p' if narrow else ''}.png"
            canvas.save(out)
            out.with_suffix(".boxes.json").write_text(json.dumps(runs, ensure_ascii=False), encoding="utf-8")
            _save_layout(out, sp, canvas, runs, info)
            if not narrow and sp.get("mode") != "card":
                _save_tag_text(out, sp["site"])
            _save_hl(out, kws, bars, canvas.size)
            print(f"  ok {out.name} {canvas.size} runs={len(runs)}" + (f" 底線序列 {len(bars)} 條" if kws else ""))
        b.close()
        if _FB is not None:
            _FB.close()
        _PW = _FB = None


def _flat(runs):
    return [(ei, ci, ch.lower()) for ei, e in enumerate(runs) for ci, ch in enumerate(e["text"]) if not ch.isspace()]


# ---- 渲染前檢查常數(PLAN_閱讀卡 §3、PLAN_畫面優化六項 C;2026-10-22)----
CARD_RECT = (60, 60, 1860, 1020)   # 閱讀卡在 1920x1080 輸出上的位置(card.css .card 1800x960 @ (60,60) + card_prepare 回傳 spec 的 padx/pady=60)
CARD_SUB_TOP = 1080 - 240          # 字幕帶上緣(= 1080 - build.IMG_BOTTOM_KEEP 240):卡內文字框底緣不可超過(不 import build)
CARD_MARGIN = 40                   # 卡內所有文字離卡邊下限(px)
CARD_TITLE_MAX, CARD_EXCERPT_MAX = 2, 6
HL_X_TOL, HL_Y_MAX = 0.2, 0.25     # 底線紅色像素:x 超出該行詞範圍的容許(字寬倍數)、上緣離該行 box 下緣的上限(行高倍數)
HL_Y_MIN = -0.15                   # 底線上緣可高於 box 下緣多少(行高倍數;box 是字形墨跡框,底線上緣在基線下 0.2em)
DARK_LUM_MAX = 0.5                 # 暗色沒生效:卡面/頁面底色(中位數亮度 0-1)高於這個就報錯
FLAT_TOL, FLAT_MAX = 6, 0.35       # C:純色塊 = 各通道容差 ±6 的連通區域;佔重點區 > 35% 警告
FLAT_OPEN, FLAT_GROW = 80, 0.5     # 先做開運算去掉比 80px 窄的色帶(行距、欄距不算空白區塊);文字框的外包矩形外擴 0.5 倍行高當重點區
CARD_COLORS = [(0x1c, 0x2a, 0x38), (0x15, 0x20, 0x2b)]   # 卡面、卡外底色:閱讀卡內正常留白,不算純色塊


def check(SPECS, HL=None, names=None, prefix="", out_dir=IMG):
    """HL 建議詞都要在 .boxes.json 找到(比對同 build.py find_hl_boxes:忽略空白與大小寫、可跨行)+ 版面檢查 + 墨跡檢查
    + 紅線序列檢查 + 暗色檢查 + 閱讀卡檢查 + 純色塊警告(C);回傳錯誤數(警告不算)"""
    SPECS, HL, out_dir = _norm_specs(SPECS), HL or {}, Path(out_dir)
    bad, stat, warns = 0, [], 0
    for n in names or list(SPECS):
        f = out_dir / f"{prefix}{n}.boxes.json"
        if not f.exists():
            print(f"{n}: 缺 boxes.json")
            bad += 1
            continue
        runs = json.loads(f.read_text(encoding="utf-8"))
        flat = "".join(c for _, _, c in _flat(runs))
        sp = SPECS[n]
        card = sp.get("mode") == "card"
        print(f"{n}: runs={len(runs)}")
        bad += _check_layout(out_dir, prefix, n, runs)
        bad += _check_ink(out_dir, prefix, n, runs, None if card else sp["site"], stat)
        if card:
            bad += _check_card(n, runs)
        bad += _check_dark(out_dir, prefix, n, sp)
        warns += _check_flat(out_dir, prefix, n, runs, card)
        kws = list(HL.get(n, sp.get("hl", [])))
        hlj = out_dir / f"{prefix}{n}.hl.json"
        for kw in kws:
            k = re.sub(r"\s+", "", kw).lower()
            ok = k in flat
            one = any(k in re.sub(r"\s+", "", x["text"]).lower() for x in runs)   # 同一行(底線不跨行)
            # 有底線序列(.hl.json)時,跨行命中本來就是每行一條,由 _check_hl 逐條驗,跨行本身不算錯;沒序列(舊畫法)才要求不跨行
            bad += (not ok) or (not one and not hlj.exists())
            print(f"  {'OK ' if ok else '找不到'} hl: {kw}" + ("" if one or not ok or hlj.exists() else "  [跨行]"))
        if hlj.exists():
            bad += _check_hl(out_dir, n, runs, kws, hlj)
    if stat:
        ng = [n for n, r in stat if r["errs"]]
        print(f"[墨跡總結] 合格 {len(stat) - len(ng)}/{len(stat)} 最小離邊 左{min(r['left'] for _, r in stat)} 右{min(r['right'] for _, r in stat)}"
              f" 上{min(r['top'] for _, r in stat)} 框偏移最大 {max(max(abs(v) for v in r['off']) for _, r in stat):.0f}px"
              f" 框外最大 {max(r['over'] for _, r in stat)}px 未合格:{' '.join(ng) or '無'}")
    if warns:
        print(f"[純色塊警告] {warns} 張(重點區內單色連通區域 > {FLAT_MAX:.0%};確認不是空白頁/載入中/廣告空框)")
    return bad


def _check_card(n, runs):
    """閱讀卡檢查(PLAN §3):文字離卡邊 >= CARD_MARGIN、文字框底緣 <= CARD_SUB_TOP(字幕帶)、標題 <= 2 行、摘錄 <= 6 行(後兩者讀 card_prepare 寫的 tmp/cards/<名>.json 的字級結果);
    hero 抓失敗已在 card_prepare 印警告並退回純文字版(hero=None),這裡只印目前狀態"""
    x0, y0, x1, y1 = CARD_RECT
    errs = [f"{r['text'][:10]}(左{r['box'][0] - x0}/右{x1 - r['box'][2]}/上{r['box'][1] - y0}/下{y1 - r['box'][3]}) 離卡邊 < {CARD_MARGIN}" for r in runs
            if min(r["box"][0] - x0, x1 - r["box"][2], r["box"][1] - y0, y1 - r["box"][3]) < CARD_MARGIN]
    errs += [f"{r['text'][:10]}(底緣 {r['box'][3]}) 進字幕帶 > {CARD_SUB_TOP}" for r in runs if r["box"][3] > CARD_SUB_TOP][:6]
    info = ""
    jf = CARD_DIR / f"{n}.json"
    if jf.exists():
        d = json.loads(jf.read_text(encoding="utf-8"))
        fit = d.get("fit") or {}
        tl, ex = fit.get("title_lines", 0), fit.get("lines", 0)
        info = f" 標題 {tl} 行 摘錄 {ex} 行 " + ("hero" if d.get("hero") and not fit.get("hero_dropped") else "純文字版")
        if tl > CARD_TITLE_MAX:
            errs.append(f"標題 {tl} 行 > {CARD_TITLE_MAX}")
        if ex > CARD_EXCERPT_MAX:
            errs.append(f"摘錄 {ex} 行 > {CARD_EXCERPT_MAX}")
    else:
        info = " 無 tmp/cards 字級資料,行數檢查略過"
    print(f"  [卡]{info} 錯誤 {len(errs)}")
    for e in errs[:6]:
        print("    " + e)
    return len(errs)


def _hl_pieces(runs, kws, fs=None):
    """同 JS_HL_WRAP 的比對(忽略空白與大小寫、最多 HL_MAX 處、不重疊)-> [(kw, [x0, x1, y0, y1, 字數, em])…],每個命中依行切成一段;em = 該段字級(fs = layout.json 每個 run 的字級,沒有就用字寬)"""
    seq = _flat(runs)
    flat = "".join(c for _, _, c in seq)
    used, out = set(), []
    for kw in kws:
        q = re.sub(r"\s+", "", kw).lower()
        pos = cnt = 0
        while q and cnt < HL_MAX:
            i = flat.find(q, pos)
            if i < 0:
                break
            pos = i + len(q)
            if any(j in used for j in range(i, pos)):
                continue
            cnt += 1
            used.update(range(i, pos))
            cur = None
            for j in range(i, pos):
                ei, ci, _ = seq[j]
                bx, (cx0, cx1) = runs[ei]["box"], runs[ei]["chars"][ci]
                h, cy = bx[3] - bx[1], (bx[1] + bx[3]) / 2
                if cur is None or abs(cy - cur["cy"]) > h * 0.6:
                    cur = dict(cy=cy, p=[cx0, cx1, bx[1], bx[3], 0, 0])
                    out.append((kw, cur["p"]))
                p = cur["p"]
                p[0], p[1], p[2], p[3], p[4] = min(p[0], cx0), max(p[1], cx1), min(p[2], bx[1]), max(p[3], bx[3]), p[4] + 1
                p[5] = max(p[5], fs[ei] if fs else cx1 - cx0)
    return out


def _check_hl(out_dir, n, runs, kws, hlj):
    """紅線序列檢查(PLAN §3):每條底線(.hl.json;跨行命中本來就是每行一條)p=1.0 那張的紅色像素 x 範圍 ⊆ 該行命中詞範圍 ± HL_X_TOL 字寬,
    上緣在該行 box 下緣 HL_Y_MIN~HL_Y_MAX 行高內;每個命中的每一行都要有至少一條。回傳錯誤數"""
    import numpy as np
    d = json.loads(hlj.read_text(encoding="utf-8"))
    lf = Path(out_dir) / hlj.name.replace(".hl.json", ".layout.json")
    lay = json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else {}
    pcs = _hl_pieces(runs, kws, [r["fs"] for r in lay["runs"]] if len(lay.get("runs", [])) == len(runs) else None)
    errs, hit = [], [False] * len(pcs)
    for b in d["bars"]:
        a = np.asarray(Image.open(Path(out_dir) / b["files"][-1]).convert("RGBA"))
        m = (a[..., 3] > 128) & (a[..., 0] > 200) & (a[..., 1] < 110) & (a[..., 2] < 110)
        ys, xs = np.nonzero(m)
        if not len(xs):
            errs.append(f"{b['kw']}:底線層沒有紅色像素")
            continue
        rx0, rx1, ry0 = b["x"] + int(xs.min()), b["x"] + int(xs.max()) + 1, b["y"] + int(ys.min())
        ok = False
        for j, (kw, (x0, x1, y0, y1, nc, em)) in enumerate(pcs):
            if kw != b["kw"]:
                continue
            tol, h = HL_X_TOL * max(em, (x1 - x0) / max(nc, 1)), y1 - y0   # 「字寬」= 字級(CJK 等寬;英文字母窄但底線兩端固定外延 0.15em,不能用平均字寬)
            if rx0 >= x0 - tol and rx1 <= x1 + tol and y1 + HL_Y_MIN * h <= ry0 <= y1 + HL_Y_MAX * h:
                hit[j] = ok = True
                break
        if not ok:
            errs.append(f"{b['kw']}:紅色 x{rx0}-{rx1} y{ry0} 不在任何命中行的範圍內")
    errs += [f"{kw}:命中片段(x{p[0]}-{p[1]} y{p[2]}-{p[3]})沒有底線" for (kw, p), h in zip(pcs, hit) if not h]
    print(f"  [紅線] 底線 {len(d['bars'])} 條 / 命中行 {len(pcs)} 段 錯誤 {len(errs)}")
    for e in errs[:6]:
        print("    " + e)
    return len(errs)


def _check_dark(out_dir, prefix, n, sp):
    """暗色檢查(PLAN §3):截完量全圖亮度中位數(0-1,Rec.601),> DARK_LUM_MAX = 暗色沒生效。spec dark=False/off 的略過"""
    if _dark_mode(sp) == "off":
        return 0
    import numpy as np
    a = np.asarray(Image.open(Path(out_dir) / f"{prefix}{n}.png").convert("RGB"), float)
    lum = float(np.median((0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) / 255))
    print(f"  [暗色] 底色亮度中位數 {lum:.2f}" + (f" > {DARK_LUM_MAX} 錯誤:暗色沒生效" if lum > DARK_LUM_MAX else ""))
    return int(lum > DARK_LUM_MAX)


def _check_flat(out_dir, prefix, n, runs, card):
    """C:純色塊警告。重點區 = 文字框與圖形框的外包矩形外擴 FLAT_GROW 倍行高(沒有文字框 = 整個截取區,抓空白頁);
    取重點區內最常見的幾個顏色,各通道 ±FLAT_TOL 內的像素先做開運算(去掉窄色帶)再取最大連通區域,佔重點區 > FLAT_MAX 就警告。
    有內容時(閱讀卡、有文字框/圖形框的頁面)頁面底色不算:閱讀卡排除卡面/卡外底色(CARD_COLORS),截圖排除畫布左上角色與 DARK_BG(正常留白);
    只看其他顏色(白底面板、灰色廣告空框、hero 位置的空白框)。完全沒有文字框也沒有圖形框 = 空白頁,底色也要算。回傳警告數 0/1(不算錯誤)"""
    import numpy as np
    from scipy import ndimage as ndi
    out_dir = Path(out_dir)
    a = np.asarray(Image.open(out_dir / f"{prefix}{n}.png").convert("RGB"))[::4, ::4].astype(np.int16)
    H, W = a.shape[:2]
    lf = out_dir / f"{prefix}{n}.layout.json"
    L = json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else {}
    rx0, ry0, rx1, ry1 = [v // 4 for v in L.get("region", [0, 0, W * 4, H * 4])]
    boxes = [r["box"] for r in runs] + list(L.get("gfx", []))
    if card:
        rx0, ry0, rx1, ry1 = [v // 4 for v in CARD_RECT]
    elif boxes:
        lh = float(np.median([b[3] - b[1] for b in boxes])) * FLAT_GROW / 4
        rx0, ry0 = max(rx0, int(min(b[0] for b in boxes) / 4 - lh)), max(ry0, int(min(b[1] for b in boxes) / 4 - lh))
        rx1, ry1 = min(rx1, int(max(b[2] for b in boxes) / 4 + lh)), min(ry1, int(max(b[3] for b in boxes) / 4 + lh))
    roi = a[max(ry0, 0):min(ry1, H), max(rx0, 0):min(rx1, W)]
    if roi.size == 0:
        return 0
    flat = roi.reshape(-1, 3)
    key = (flat[:, 0].astype(np.int64) << 16) | (flat[:, 1].astype(np.int64) << 8) | flat[:, 2].astype(np.int64)
    cols, cnt = np.unique(key, return_counts=True)
    best, best_c = 0.0, None
    k = max(3, FLAT_OPEN // 4)
    skip = ([] if not (card or boxes) else CARD_COLORS if card else [tuple(int(v) for v in a[1, 1]), tuple(int(DARK_BG[i:i + 2], 16) for i in (1, 3, 5))])
    for c in cols[np.argsort(-cnt)][:6]:
        rgb = np.array([(c >> 16) & 255, (c >> 8) & 255, c & 255])
        if any(np.abs(rgb - np.array(e)).max() <= FLAT_TOL for e in skip):
            continue
        m = np.abs(roi - rgb).max(axis=2) <= FLAT_TOL
        m = ndi.binary_opening(m, structure=np.ones((k, k), bool))
        if not m.any():
            continue
        lab, _ = ndi.label(m)
        fr = float(np.bincount(lab.ravel())[1:].max()) / m.shape[0] / m.shape[1]
        if fr > best:
            best, best_c = fr, tuple(int(v) for v in rgb)
    warn = best > FLAT_MAX
    try:   # 結構化輸出給 look_list.py(畫面優先看清單);不影響判定
        fd = P.TMP / "look_list" / "flat"
        fd.mkdir(parents=True, exist_ok=True)
        (fd / f"{prefix}{n}.json").write_text(json.dumps(dict(frac=round(best, 3), color=best_c, warn=bool(warn)), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    print(f"  [純色塊] 重點區最大單色連通區域 {best:.0%}" + (f" 色 {best_c}  警告:可能是空白頁/載入中/廣告空框" if warn else ""))
    return int(warn)


def _carve_gfx(gfx, runs, pad=3):
    """gfx 框(有底色的按鈕/膠囊)裡有文字框時,把文字框挖掉只留四周色塊,字本身仍要驗墨跡(ink_check 的 skip 區內不看墨跡)"""
    out = [list(g) for g in gfx]
    for r in runs:
        bx0, by0, bx1, by1 = r["box"]
        bx0, by0, bx1, by1 = bx0 - pad, by0 - pad, bx1 + pad, by1 + pad
        nxt = []
        for g in out:
            x0, y0, x1, y1 = g
            if bx1 <= x0 or bx0 >= x1 or by1 <= y0 or by0 >= y1:
                nxt.append(g); continue
            for q in ([x0, y0, x1, by0], [x0, by1, x1, y1], [x0, max(y0, by0), bx0, min(y1, by1)], [bx1, max(y0, by0), x1, min(y1, by1)]):
                if q[2] > q[0] and q[3] > q[1]:
                    nxt.append(q)
        out = nxt
    return out


def _check_ink(out_dir, prefix, n, runs, site, stat):
    """墨跡檢查(看 PNG 像素):回傳錯誤數,結果附加到 stat"""
    img = Image.open(out_dir / f"{prefix}{n}.png").convert("RGB")
    lf = out_dir / f"{prefix}{n}.layout.json"   # 圖片、圖示的位置(截圖時從頁面量的)不當成字
    gfx = json.loads(lf.read_text(encoding="utf-8")).get("gfx", []) if lf.exists() else []
    r = ink_check(img, runs, skip=([add_label(Image.new("RGB", img.size), site)] if site else []) + _carve_gfx(gfx, runs), edge=MIN_EDGE, top=MIN_TOP, tol=INK_TOL)
    print(f"  [墨跡] 離邊 左{r['left']} 右{r['right']} 上{r['top']} 框偏移中位 左{r['off'][0]:+.0f}/右{r['off'][1]:+.0f}"
          f" 框外最大 {r['over']}px 錯誤 {len(r['errs'])}")
    for e in r["errs"][:6]:
        print("    " + e)
    stat.append((n, r))
    return len(r["errs"])


def _check_layout(out_dir, prefix, n, runs):
    """版面檢查(讀 .layout.json):回傳錯誤數。沒資料就略過並提示重截"""
    f = out_dir / f"{prefix}{n}.layout.json"
    if not f.exists():
        print("  [版面] 無 .layout.json,略過(重截後才有資料)")
        return 0
    d = json.loads(f.read_text(encoding="utf-8"))
    if len(d["runs"]) != len(runs):
        print("  [版面] layout 與 boxes 筆數不符,請重截")
        return 1
    x0r, y0r, x1r, y1r = d["region"]
    edge, cov, clip, out, small = 1e9, [], [], [], []
    for r, L in zip(runs, d["runs"]):
        b, t = r["box"], r["text"][:14]
        edge = min(edge, b[0] - x0r, x1r - b[2])
        if b[0] < x0r + MIN_EDGE or b[2] > x1r - MIN_EDGE:
            out.append(f"{t}(左{b[0] - x0r}/右{x1r - b[2]})")
        elif b[1] < y0r - 1 or b[3] > y1r + 1:
            out.append(f"{t}(上下出區)")
        if L["cov"]:
            cov.append(t)
        if L["clip"]:
            clip.append(t)
        if L["fs"] < MIN_FS:
            small.append(f"{t}({L['fs']})")
    bad = len(out) + len(cov) + len(clip)
    print(f"  [版面] 離邊最小 {edge}px 出區/邊不足 {len(out)} 被蓋 {len(cov)} 被裁 {len(clip)} 小字警告 {len(small)}")
    for lab, xs in (("出區/離邊<%d" % MIN_EDGE, out), ("被蓋", cov), ("被裁", clip), ("警告 字高<%d" % MIN_FS, small)):
        if xs:
            print(f"    {lab}:", " | ".join(xs[:6]))
    return bad


def relabel(SPECS, names, prefix="", out_dir=IMG, old_prefix="=來源:"):
    """只換現有 PNG 的標籤(舊式「來源:xxx」-> 現行格式),內容與 .boxes.json 不動(重截被擋的圖用)"""
    SPECS = _norm_specs(SPECS)
    for n in names:
        f = Path(out_dir) / f"{prefix}{n}.png"
        img = Image.open(f).convert("RGB")
        x0, y0, x1, y1 = add_label(Image.new("RGB", img.size), old_prefix + SPECS[n]["site"])
        ImageDraw.Draw(img).rectangle((x0 - 1, y0 - 1, x1 + 1, y1 + 1), fill=img.getpixel((x0 - 6, y0 - 6)))
        add_label(img, SPECS[n]["site"])
        img.save(f)
        print("relabel", f.name)


def overview(SPECS, prefix="", out_dir=IMG, out=None):
    """總覽圖:各圖縮圖並排、標圖名(寬 <= 2400)"""
    SPECS, out_dir = _norm_specs(SPECS), Path(out_dir)
    names = [n for n in SPECS if (out_dir / f"{prefix}{n}.png").exists()]
    cols, tw, gap, lab = 4, 576, 16, 34
    th = round(tw * FH / FW)
    rows = -(-len(names) // cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * (th + lab + gap) + gap), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    f = font(24, True)
    for i, n in enumerate(names):
        x, y = gap + (i % cols) * (tw + gap), gap + (i // cols) * (th + lab + gap)
        sheet.paste(Image.open(out_dir / f"{prefix}{n}.png").convert("RGB").resize((tw, th), Image.LANCZOS), (x, y + lab))
        d.text((x + 4, y + 2), f"{prefix}{n}", font=f, fill=(255, 255, 255))
    out = Path(out or out_dir / f"{prefix}overview.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print("overview", out, sheet.size)


def _opt(args, flag):
    """取出並移除 flag 與其後一個值(沒有 flag 回傳 None)"""
    if flag not in args:
        return None
    i = args.index(flag)
    v = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
    return v


def _names(args):
    return [x for a in args for x in a.split(",") if x]


def main(SPECS, tag, HL=None, prefix=None, argv=None):
    """新片 news 檔的入口。tag 為片名(預設輸出前綴 <tag>_,舊片沿用短前綴時用 prefix 覆寫,例 gd_)。"""
    args = list(sys.argv[1:] if argv is None else argv)
    prefix = f"{tag}_" if prefix is None else prefix
    out_dir = Path(_opt(args, "--out") or IMG)
    only = _names([_opt(args, "--only") or ""])
    rl = _opt(args, "--relabel")
    if rl is not None:
        relabel(SPECS, _names([rl]), prefix, out_dir)
        sys.exit(0)
    if "--overview" in args:
        i = args.index("--overview")
        arg = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") else None
        del args[i:i + (2 if arg else 1)]
        overview(SPECS, prefix, out_dir, arg or P.output_dir(tag) / f"{prefix}images_overview.png")
        sys.exit(0)
    if "--check" in args:
        args.remove("--check")
        sys.exit(1 if check(SPECS, HL, only or _names(args) or None, prefix, out_dir) else 0)
    dump = "--dump" in args   # 只列出保留區塊內各文字區塊的原文(撰寫 rules 用),規則找不到時不中斷
    if dump:
        args.remove("--dump")
    narrow = "--narrow" in args   # 窄版(Shorts 直式用)
    if narrow:
        args.remove("--narrow")
    build(SPECS, only or _names(args), prefix, out_dir, dump, narrow, HL)
