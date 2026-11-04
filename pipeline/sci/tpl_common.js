/* ChannelC:場景模板共用(F4-0,規格 projects\framework\sci_tpl_spec.md §1–§3)。需先載入 pigeon.js、kit.js、charts.js。
 * 掛 window.Tpl = { common };各模板 tpl_<名>.js 掛 window.Tpl.<名> = { render(t, params), check(params) }。
 * 時間觸發:元素寫 at(場景內句索引,0 起)與選填 word(該句裡的字串)→ 觸發格 = 句首 + 字索引 ÷ 句長 × 句長秒數(同 s_rank_a 的 wordK)。
 * 省略 at = 依序分配(第 i 個掛第 min(i, 句數-1) 句開頭;與前一個同格或更早時順延 3 格)。模板沒有 DEF 備援:lines 不合 → check 錯誤。
 * check 回傳字串陣列:「警告」開頭的只提示(如停留不足 1.5 秒),其餘是錯誤(render_clip 印「模板錯誤」並中止)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('./kit.js'), Ch = Wn.Charts || require('./charts.js');
  const FULL = 3;                                   // K.pop 表第 3 格起完全出現
  const HOLD = 15;                                  // 最後一個元素完全出現後到場景結束(或退場)至少 15 格 = 1.5 秒
  const STAGGER = 3;                                // 依序分配撞格時的順延格數
  const OUT = [0.7, 0.4, 0.15];                     // 退場:0.3 秒(3 格)縮掉,之後不畫

  // 內容區(px):x0,x1,y0,y1;直式下緣讓給鴿子(不畫鴿子時到字幕帶上 40px)
  // 鴿子:橫式 K.L.pigeon;直式內容區下方中央、倍率 × 0.8
  const PIGEON = {
    landscape: { x: K.LAYOUT.landscape.pigeon.x, y: K.LAYOUT.landscape.pigeon.y, u: K.LAYOUT.landscape.pigeon.u },
    portrait: { x: 510, y: 1290, u: K.LAYOUT.portrait.pigeon.u * 0.8 },
  };
  const PG_H = 234;                                 // 鴿子 idle 實測高度(u=2 時 467px)(單位;× u = px),直式內容區下緣據此讓位
  // 鴿子實際外框(px,idle 全部表情的聯集,含嘴與描邊,實測 F4-0b):橫式左緣 1368.9(嘴尖)、直式上緣 829.5
  const PG_LEFT = 1368, PG_X_GAP = 40;              // 橫式內容區右界 = 鴿子外框左緣 − 40
  const LAY = K.portrait ? 'portrait' : 'landscape';
  function area(hidePigeon) {
    if (!K.portrait) return { x0: 80, x1: hidePigeon ? 1440 : PG_LEFT - PG_X_GAP, y0: 120, y1: K.L.SUB_BAND[0] - 30 };
    const pg = PIGEON.portrait;
    return { x0: 80, x1: 940, y0: 120, y1: hidePigeon ? K.L.SUB_BAND[0] - 40 : pg.y - PG_H * pg.u - 24 };
  }
  // 標題牌【判】:橫式左上 (100,110) fs 72;直式上方置中 y 200 fs 80;黃底
  const TITLE = { landscape: { x: 100, top: 110, fs: 84 }, portrait: { cx: 510, cy: 200, fs: 88 } };   // fs = 上限,太寬自動縮(下限 56)

  // fitBlock(A, {fsMax, fsMin, hOf(fs), wOf(fs)}):取最大字級 fs(步進 2)使群組高 hOf、寬 wOf 放得進內容區 A。
  // 回傳 {fs, h, w, top, cx, cy}:群組垂直置中於 A(top = 群組上緣、cy = 群組中心;上下各留 12px 給紙片傾斜與陰影)、水平中線 cx = A 中線。放不下時 fs = fsMin(由模板 check 報錯)。
  function fitBlock(A, o) {
    const aw = A.x1 - A.x0, ah = A.y1 - A.y0 - 24;
    let fs = o.fsMax;
    while (fs > o.fsMin && (o.hOf(fs) > ah || o.wOf(fs) > aw)) fs -= 2;
    fs = Math.max(fs, o.fsMin);
    const h = o.hOf(fs), top = A.y0 + 12 + (ah - h) / 2;
    return { fs, h, w: o.wOf(fs), top, cx: (A.x0 + A.x1) / 2, cy: top + h / 2 };
  }

  // ---------- 句子 ----------
  function lines(params) {
    const L = (params && params.lines) || [];
    return L.map((l) => ({ start: +l.start, end: +l.end, text: String(l.text || '') }));
  }
  function checkLines(params) {
    const L = (params && params.lines) || [];
    if (!L.length) return ['缺 lines(模板沒有預設句子)'];
    const e = [];
    L.forEach((l, i) => {
      if (!isFinite(l.start) || !isFinite(l.end) || l.end < l.start || !l.text) e.push(`lines[${i}] 缺 start/end/text 或 end < start`);
    });
    return e;
  }

  // ---------- 觸發格 ----------
  // 單一觸發:回傳格;at 省略時用 dflt
  function trig(L, at, word, dflt) {
    const i = at == null ? dflt : at, l = L[Math.max(0, Math.min(i, L.length - 1))];
    if (!l) return 0;
    if (word == null) return K.frame(l.start);
    const j = Math.max(0, l.text.indexOf(word));
    return K.frame(l.start + j / l.text.length * (l.end - l.start));
  }
  // 依序分配:items[i].at/word;回傳每個元素的觸發格
  function assign(L, items) {
    const out = [];
    items.forEach((it, i) => {
      let k = trig(L, it.at, it.word, Math.min(i, L.length - 1));
      if (it.at == null && it.word == null && i && k <= out[i - 1]) k = out[i - 1] + STAGGER;
      out.push(k);
    });
    return out;
  }
  // 檢查 at/word:回傳錯誤字串陣列;name = 錯誤訊息裡的欄位名
  function checkTrig(L, at, word, name) {
    if (at != null && (!Number.isInteger(at) || at < 0 || at >= L.length)) return [`${name}.at=${at} 超出句索引 0–${L.length - 1}`];
    if (word != null) {
      const l = L[at == null ? 0 : at];
      if (at == null) return [`${name}.word 需同時寫 at`];
      if (!l || l.text.indexOf(word) < 0) return [`${name}.word「${word}」不在第 ${at} 句「${l ? l.text : ''}」裡`];
    }
    return [];
  }
  // 停留:lastK = 最後一個元素的觸發格;endK = 場景結束格(或退場格)
  function checkHold(lastK, endK) {
    const hold = endK - (lastK + FULL);
    return hold < HOLD ? [`警告:最後一個元素完全出現後只停 ${(hold / 10).toFixed(1)} 秒(< 1.5)`] : [];
  }

  // ---------- 退場 ----------
  // data.out = {at,word}:回傳退場格(沒寫 = null)
  const outK = (L, out) => (out ? trig(L, out.at, out.word, L.length - 1) : null);
  // 把一組內容以 (cx,cy) 為中心縮掉;k = 目前格。退場後回傳 ''
  function exitWrap(s, k, ko, cx, cy) {
    if (ko == null || k < ko) return s;
    const i = k - ko;
    if (i >= OUT.length) return '';
    const sc = OUT[i];
    return `<g transform="translate(${cx} ${cy}) scale(${sc}) translate(${-cx} ${-cy})">${s}</g>`;
  }

  // ---------- 標題牌 ----------
  // pos = {x,y} 標題牌中心(省略 = 規格預設位置:橫式左上、直式上方置中);字級 TITLE.fs 為上限,寬過內容區就逐步縮
  function titleBox(s, pos) {
    const T = TITLE[LAY], A = area(true);
    let fs = T.fs, p = Ch.plate(s, fs, { fill: K.YELLOW });
    while (p.w > A.x1 - A.x0 - 40 && fs > 56) { fs -= 4; p = Ch.plate(s, fs, { fill: K.YELLOW }); }
    const c = pos || (K.portrait ? { x: T.cx, y: T.cy } : { x: T.x + p.w / 2, y: T.top + p.h / 2 });
    return { x: c.x, y: c.y, w: p.w, h: p.h, p };
  }
  function title(s, k, pos) {
    if (!s) return '';
    const b = titleBox(s, pos);
    return Ch.sheet(b.p.svg, { x: b.x, y: b.y, rot: -1.5, k, kind: 'title', id: 'title', wide: true });
  }

  // ---------- 鴿子 ----------
  // data.pigeon = {expr: 名 | [每句表情], clip:'idle'|…, hide:false};表情只用 pigeon.js 的 EXPR
  function checkPigeon(L, pg) {
    if (!pg) return [];
    const e = [], ex = pg.expr == null ? [] : Array.isArray(pg.expr) ? pg.expr : [pg.expr];
    ex.forEach((n) => { if (!K.P.EXPR[n]) e.push(`pigeon.expr「${n}」不在 ${Object.keys(K.P.EXPR).join('/')}`); });
    if (Array.isArray(pg.expr) && pg.expr.length !== L.length) e.push(`pigeon.expr 陣列 ${pg.expr.length} 個,句數 ${L.length}`);
    if (pg.clip && !K.P.CLIPS[pg.clip]) e.push(`pigeon.clip「${pg.clip}」不存在`);
    return e;
  }
  function pigeon(t, L, pg, pal) {
    pg = pg || {};
    if (pg.hide) return '';
    const k = K.frame(t), at = PIGEON[LAY];
    let li = 0;
    L.forEach((l, i) => { if (t + 1e-6 >= l.start) li = i; });
    const name = Array.isArray(pg.expr) ? pg.expr[li] : pg.expr || 'normal';
    const p = K.clip(pg.clip || 'idle', k), e = K.P.EXPR[name] || K.P.EXPR.normal;
    const pose = Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0) });   // 眨眼格保留
    return K.ground({ x: at.x - 10, y: at.y + 4, w: 150 * at.u, h: 11 * at.u, u: 1.4, pal }) +
      K.pigeon(pose, { x: at.x, y: at.y, scale: at.u, id: 'tpl' });
  }

  // 字寬是否放得進內容區
  const fits = (w, A) => w <= A.x1 - A.x0;

  // ---------- 繪製小工具(px;放進 Ch.sheet 內) ----------
  const f = (x) => +(+x).toFixed(2);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const text = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}"` +
    ` text-anchor="${anchor || 'middle'}" dominant-baseline="central" fill="${fill}" stroke="none">${esc(s)}</text>`;
  // 圖解:'turtle.coin' → PropsTurtle.LIST.coin → {svg,w,h}(給 Ch.icon);找不到回傳 null
  function iconOf(name, pal) {
    const m = /^(\w+)\.(\w+)$/.exec(String(name || ''));
    if (!m) return null;
    const lib = Wn['Props' + m[1][0].toUpperCase() + m[1].slice(1)], it = lib && lib.LIST && lib.LIST[m[2]];
    return it ? { svg: it.fn(pal || K.palette(46), {}), w: it.w, h: it.h } : null;
  }

  const common = { K, Ch, FULL, HOLD, LAY, PIGEON, PG_LEFT, PG_X_GAP, TITLE, area, fitBlock, lines, checkLines, trig, assign, checkTrig, checkHold, outK, exitWrap,
    titleBox, title, checkPigeon, pigeon, fits, rect, text, iconOf };
  const Tpl = Wn.Tpl || {};
  Tpl.common = common;
  if (typeof module !== 'undefined') module.exports = common;
  if (typeof window !== 'undefined') window.Tpl = Tpl;
})();
