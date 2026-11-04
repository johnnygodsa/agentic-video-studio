/* 模板 timeline(F4-0b):標題牌 + 時間軸(自繪;Charts.route 的站點全亮/全灰不能做單一焦點)。
 * data: {title?, nodes:[{year,label,at?,word?}], hi:[i], out?:{at,word?}, pigeon?}
 * 橫式:水平軸,年份牌在軸上方、標籤牌在軸下方;相鄰標籤放不下就上下兩層交錯(第二層加細柄連到軸)。
 * 直式:垂直軸,年份牌在軸左(靠右對齊)、標籤牌在軸右(靠左對齊)。
 * hi:該節點黃圓、年份墨底黃字、標籤黃底(單一焦點);其餘紙白圓、主色字年份、紙白標籤。軸段在後一節點出現時一起出現(主色)。
 * 觸發:標題在第 0 句開頭;各節點依 at/word,省略則依序分配。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判】:max 節點數、fsMax/fsMin 標籤字級範圍(實際由 C.fitBlock 取最大值)、yearR 年份字級 ÷ 標籤字級、yPad/lPad 年份牌/標籤牌左右內距合計(em)、
  // plateR 牌高 ÷ 字級(比 Ch.plate 的 1.62 矮,直式 5 節點加標題才放得下)、
  // rR 節點半徑 ÷ 字級、thR 軸粗 ÷ 字級、gapY 年份/標籤牌離節點、tierGap 兩層標籤間距、sep 同層相鄰牌最小間距、
  // rowGapR(直式)列距 ÷ 列高、colGap(直式)年份/標籤牌離節點、maxW 群組寬上限、titleGap 標題牌與軸群組間距
  const LAYOUT = {
    landscape: { max: 6, fsMax: 72, fsMin: 56, yearR: 1.0, yPad: 0.4, lPad: 0.8, plateR: 1.3, rR: 0.36, thR: 0.24, gapY: 18, tierGap: 14, sep: 16, maxW: 1336, titleGap: 32 },
    portrait: { max: 5, fsMax: 80, fsMin: 60, yearR: 1.0, yPad: 0.4, lPad: 0.8, plateR: 1.3, rR: 0.34, thR: 0.24, rowGapR: 0.12, colGap: 24, maxW: 836, titleGap: 32 },
  };
  const LY = LAYOUT[C.LAY];
  const inset = (A) => Object.assign({}, A, { x0: A.x0 + 12, x1: A.x1 - 12 });
  // 字牌(中心在原點):{w,h,svg};高 = plateR × 字級
  function pl(s, fs, pad, fill, ink) {
    const w = Ch.tw(s, fs) + fs * pad, h = fs * LY.plateR;
    return { w, h, svg: C.rect(-w / 2, -h / 2, w, h, fill || K.PAPER) + C.text(s, 0, 0, fs, ink || K.INK) };
  }
  const yPlate = (s, fs, fill, ink) => pl(String(s), fs * LY.yearR, LY.yPad, fill, ink);
  const lPlate = (s, fs, fill) => pl(String(s || ''), fs, LY.lPad, fill);

  // 橫式在字級 fs 下的版面:tiers 層數、need 需要寬、m0/m1 首末節點離群組邊、H 軸群組高
  function sizeL(nodes, fs, aw) {
    const n = nodes.length, yw = nodes.map((p) => yPlate(p.year, fs).w), lw = nodes.map((p) => lPlate(p.label, fs).w);
    const yh = fs * LY.yearR * LY.plateR, lh = fs * LY.plateR, r = fs * LY.rR;
    const m0 = Math.max(yw[0], lw[0]) / 2, m1 = Math.max(yw[n - 1], lw[n - 1]) / 2;
    let py = 0, p1 = 0, p2 = 0;
    for (let i = 0; i + 1 < n; i++) {
      py = Math.max(py, (yw[i] + yw[i + 1]) / 2 + LY.sep);
      p1 = Math.max(p1, (lw[i] + lw[i + 1]) / 2 + LY.sep);
      if (i + 2 < n) p2 = Math.max(p2, ((lw[i] + lw[i + 2]) / 2 + LY.sep) / 2);
      p2 = Math.max(p2, lw[i] / 2 + LY.sep, lw[i + 1] / 2 + LY.sep);   // 第二層的柄不可穿過相鄰標籤
    }
    const w1 = m0 + m1 + (n - 1) * Math.max(py, p1), w2 = m0 + m1 + (n - 1) * Math.max(py, p2);
    const tiers = n > 2 && w1 > aw ? 2 : 1, need = tiers === 1 ? w1 : w2;
    return { yw, lw, yh, lh, r, m0, m1, tiers, need, H: yh + 2 * LY.gapY + 2 * r + tiers * lh + (tiers - 1) * LY.tierGap };
  }
  // 直式:左欄年份、右欄標籤
  function sizeP(nodes, fs) {
    const n = nodes.length, yw = nodes.map((p) => yPlate(p.year, fs).w), lw = nodes.map((p) => lPlate(p.label, fs).w);
    const rowH = Math.max(fs * LY.yearR, fs) * LY.plateR, gap = rowH * LY.rowGapR, r = fs * LY.rR, ywMax = Math.max(0, ...yw), lwMax = Math.max(0, ...lw);
    return { yw, lw, rowH, gap, r, ywMax, need: ywMax + 2 * LY.colGap + 2 * r + lwMax, H: n * rowH + (n - 1) * gap };
  }

  function geo(d) {
    const A = inset(C.area(d.pigeon && d.pigeon.hide)), nodes = d.nodes || [];
    const aw = Math.min(A.x1 - A.x0, LY.maxW), tb = d.title ? C.titleBox(d.title) : null, head = tb ? tb.h + LY.titleGap : 0;
    const sz = (fs) => (K.portrait ? sizeP(nodes, fs) : sizeL(nodes, fs, aw));
    const F = C.fitBlock(A, { fsMax: LY.fsMax, fsMin: LY.fsMin, hOf: (fs) => head + sz(fs).H, wOf: (fs) => Math.max(sz(fs).need, tb ? tb.w : 0) });
    const z = sz(F.fs), n = nodes.length;
    if (K.portrait && n > 1) {                      // 直式節點少:拉長列距讓群組高達內容區 45%(列距上限 1.5 列高),再重新置中
      const ah = A.y1 - A.y0, want = ah * 0.45 - head - n * z.rowH;
      if (want > (n - 1) * z.gap) {
        z.gap = Math.min(z.rowH * 1.5, want / (n - 1)); z.H = n * z.rowH + (n - 1) * z.gap;
        F.h = head + z.H; F.top = A.y0 + 12 + (ah - 24 - F.h) / 2; F.cy = F.top + F.h / 2;
      }
    }
    const top = F.top + head;
    let pts;
    if (K.portrait) {                               // 群組(年份欄 + 軸 + 標籤欄)水平置中
      const x0 = F.cx - z.need / 2, ax = x0 + z.ywMax + LY.colGap + z.r;
      pts = nodes.map((p, i) => ({ x: ax, y: top + i * (z.rowH + z.gap) + z.rowH / 2,
        yx: ax - z.r - LY.colGap - z.yw[i] / 2, lx: ax + z.r + LY.colGap + z.lw[i] / 2 }));
      pts.forEach((p) => { p.yy = p.y; p.ly = p.y; });
    } else {                                        // 軸撐滿群組寬,首末節點讓出半個牌寬
      const x0 = F.cx - aw / 2, pitch = n > 1 ? (aw - z.m0 - z.m1) / (n - 1) : 0, ay = top + z.yh + LY.gapY + z.r;
      pts = nodes.map((p, i) => {
        const tier = z.tiers === 2 ? i % 2 : 0, x = x0 + z.m0 + i * pitch;
        return { x, y: ay, tier, yx: x, yy: ay - z.r - LY.gapY - z.yh / 2, lx: x, ly: ay + z.r + LY.gapY + z.lh / 2 + tier * (z.lh + LY.tierGap) };
      });
    }
    return Object.assign(z, { A, aw, F, fs: F.fs, tb, top, pts, titlePos: tb && { x: F.cx, y: F.top + tb.h / 2 } });
  }

  function render(t, params) {
    const d = params.data || {}, L = C.lines(params), k = K.frame(t), pal = K.palette(params.hue), G = geo(d);
    const nodes = d.nodes || [], Ks = C.assign(L, nodes), hi = d.hi || [], th = G.fs * LY.thR, P = G.pts;
    let s = C.title(d.title, k - C.trig(L, 0, null, 0), G.titlePos), segs = '', dots = '', tags = '';
    nodes.forEach((nd, i) => {
      const kk = k - Ks[i], p = P[i], isHi = hi.indexOf(i) >= 0;
      if (kk < 0) return;
      if (i) {                                      // 軸段:前一節點到本節點
        const a = P[i - 1], len = Math.hypot(p.x - a.x, p.y - a.y);
        segs += Ch.sheet(K.portrait ? C.rect(-th / 2, -len / 2, th, len, pal.main) : C.rect(-len / 2, -th / 2, len, th, pal.main),
          { x: (a.x + p.x) / 2, y: (a.y + p.y) / 2, k: kk, kind: 'tlSeg', id: 'tl' + i, wide: !K.portrait });
      }
      dots += Ch.sheet(`<circle cx="0" cy="0" r="${G.r.toFixed(2)}" fill="${isHi ? K.YELLOW : K.PAPER}"/>` +
        `<circle cx="0" cy="0" r="${(G.r * 0.4).toFixed(2)}" fill="${K.INK}" stroke="none"/>`, { x: p.x, y: p.y, k: kk, kind: 'tlNode', id: 'tl' + i });
      const yp = yPlate(nd.year, G.fs, isHi ? K.INK : K.PAPER, isHi ? K.YELLOW : pal.text);
      tags += Ch.sheet(yp.svg, { x: p.yx, y: p.yy, k: kk, kind: 'tlYear', id: 'tl' + i, wide: yp.w / yp.h > 3 });
      const lp = lPlate(nd.label, G.fs, isHi ? K.YELLOW : K.PAPER);
      const stem = p.tier ? p.ly - lp.h / 2 - p.y - G.r : 0;       // 第二層:細柄從節點下緣連到牌上緣
      tags += Ch.sheet((stem > 0 ? C.rect(-3, -lp.h / 2 - stem, 6, stem, K.INK) : '') + lp.svg,
        { x: p.lx, y: p.ly, k: kk, kind: 'tlLabel', id: 'tl' + i, wide: lp.w / lp.h > 3 });
    });
    s += segs + dots + tags;
    s = C.exitWrap(s, k, C.outK(L, d.out), G.F.cx, G.F.cy);
    return K.wrap(pal, s + C.pigeon(t, L, d.pigeon, pal));
  }

  function check(params) {
    const d = params.data || {}, e = C.checkLines(params);
    if (e.length) return e;
    const L = C.lines(params), nodes = d.nodes || [];
    if (nodes.length < 2) e.push(`nodes ${nodes.length} 個,至少 2 個`);
    if (nodes.length > LY.max) e.push(`nodes ${nodes.length} 個,${C.LAY} 上限 ${LY.max}`);
    nodes.forEach((p, i) => {
      if (p.year == null || p.year === '') e.push(`nodes[${i}] 缺 year`);
      if (!p.label) e.push(`nodes[${i}] 缺 label`);
      e.push(...C.checkTrig(L, p.at, p.word, `nodes[${i}]`));
    });
    (d.hi || []).forEach((i) => { if (!nodes[i]) e.push(`hi 索引 ${i} 不存在`); });
    e.push(...C.checkTrig(L, d.out && d.out.at, d.out && d.out.word, 'out'), ...C.checkPigeon(L, d.pigeon));
    if (e.length) return e;
    const G = geo(d), ah = G.A.y1 - G.A.y0 - 24;
    if (G.tb && G.tb.w > G.A.x1 - G.A.x0) e.push(`標題寬 ${Math.round(G.tb.w)}px 超出內容區`);
    if (G.need > G.aw) e.push(`年份或標籤太寬:需要 ${Math.round(G.need)}px > 內容區 ${Math.round(G.aw)}px(字級已降到下限 ${LY.fsMin})`);
    if (G.F.h > ah) e.push(`可用高度不足:群組高 ${Math.round(G.F.h)}px > 內容區 ${Math.round(ah)}px(字級已降到下限 ${LY.fsMin})`);
    const ko = C.outK(L, d.out);
    e.push(...C.checkHold(Math.max(...C.assign(L, nodes)), ko == null ? Math.round(params.dur * 10) : ko));
    return e;
  }

  const API = { LAYOUT, render, check, geo };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).timeline = API;
})();
