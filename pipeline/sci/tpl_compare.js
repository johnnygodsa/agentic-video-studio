/* 模板 compare(F4-0b):兩欄對照板(Charts.twoCol);橫式左右並排,直式上下排(上 = left、下 = right)。
 * data: {left:{title,items:[文字],icon?,at?,word?}, right:{…}, hi:'left'|'right'|null, out?:{at,word?}, pigeon?}
 * hi 那一邊:主題襯底 + 黃底標題牌;另一邊灰底 + 墨底標題牌;hi 為 null 兩邊都用襯底與墨底標題(無焦點)。
 * 觸發:每一邊依 at/word(省略則 left 第 0 句、right 第 1 句),該邊條目從欄出現後第 2 格起每 2 格一條。
 * 直式兩欄疊起來放不下鴿子:直式一律不畫鴿子(寫了 pigeon 且沒 hide → 警告)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判】:max 每邊項數、maxChars 每項字數、fsMax/fsMin 條目字級範圍(實際由 C.fitBlock 取最大值)、titleR 欄標題字級 ÷ 條目字級(上限 titleMax)、
  // rowR 條目高 ÷ 字級、gapR 條目間距 ÷ 條目高、colGap 兩欄間距、padR 條目左右內距 ÷ 字級、side 條目離欄邊、bottom 欄底留白、maxW 群組寬上限
  const LAYOUT = {
    landscape: { max: 4, maxChars: 10, fsMax: 72, fsMin: 56, titleR: 1.1, titleMax: 84, rowR: 1.4, gapR: 0.14, colGap: 40, padR: 0.5, side: 20, bottom: 24, maxW: 1336 },
    portrait: { max: 4, maxChars: 10, fsMax: 72, fsMin: 60, titleR: 1.1, titleMax: 84, rowR: 1.35, gapR: 0.12, colGap: 36, padR: 0.5, side: 20, bottom: 20, maxW: 836 },
  };
  const LY = LAYOUT[C.LAY];
  const ITEM0 = 2, STEP = 2;                        // 條目:欄出現後第 2 格起,每 2 格一條
  const SIDES = ['left', 'right'];
  const inset = (A) => Object.assign({}, A, { x0: A.x0 + 12, x1: A.x1 - 12 });

  function geo(d) {
    const A = inset(C.area(K.portrait ? true : d.pigeon && d.pigeon.hide)), cols = SIDES.map((s) => d[s] || { items: [] });
    const n = Math.max(1, ...cols.map((c) => (c.items || []).length));
    const size = (fs) => {
      const tf = Math.min(LY.titleMax, fs * LY.titleR), th = Math.max(56, tf) * 1.62 + 32, rowH = fs * LY.rowR, gap = rowH * LY.gapR;
      const ib = tf * 1.62;                         // icon 邊長 = 標題牌高
      const need = Math.max(...cols.map((c) => Math.max(
        Math.max(0, ...(c.items || []).map((s) => Ch.tw(s, fs))) + 2 * fs * LY.padR + 2 * LY.side,
        Ch.tw(c.title || '', tf) + tf + 2 * (c.icon ? ib + 32 : LY.side))));
      const ph = th + n * rowH + (n - 1) * gap + LY.bottom;
      return { tf, th, rowH, gap, ib, need, ph };
    };
    const F = C.fitBlock(A, { fsMax: LY.fsMax, fsMin: LY.fsMin,
      hOf: (fs) => (K.portrait ? 2 * size(fs).ph + LY.colGap : size(fs).ph),
      wOf: (fs) => (K.portrait ? size(fs).need : 2 * size(fs).need + LY.colGap) });
    const z = size(F.fs), aw = Math.min(A.x1 - A.x0, LY.maxW);
    const colW = K.portrait ? aw : (aw - LY.colGap) / 2;
    // 每欄中心(x,y)
    const pos = K.portrait ? [{ x: F.cx, y: F.top + z.ph / 2 }, { x: F.cx, y: F.top + z.ph * 1.5 + LY.colGap }]
      : [-1, 1].map((s) => ({ x: F.cx + s * (colW + LY.colGap) / 2, y: F.top + z.ph / 2 }));
    return Object.assign(z, { A, F, fs: F.fs, colW, pos, cols });
  }

  function render(t, params) {
    const d = params.data || {}, L = C.lines(params), k = K.frame(t), pal = K.palette(params.hue), G = geo(d);
    const Ks = C.assign(L, G.cols), grey = `hsl(${pal.h} 18% 84%)`;
    let s = '';
    G.cols.forEach((c, i) => {
      const kk = k - Ks[i], p = G.pos[i], isHi = d.hi === SIDES[i], foc = d.hi == null || isHi;
      if (kk < 0) return;
      const side = { title: c.title, color: foc ? pal.pad : grey, titleFill: isHi ? K.YELLOW : K.INK, titleInk: isHi ? K.INK : K.PAPER, k: kk };
      // twoCol 只畫一欄:把該欄放在 left 或 right 的位置,另一邊留空(直式上下排也用這招)
      const off = (G.colW + LY.colGap) / 2, o = { y: p.y, w: 2 * G.colW + LY.colGap, h: G.ph, gap: LY.colGap, fs: G.tf, pal, id: 'cp' + i };
      s += i === 0 ? Ch.twoCol(Object.assign(o, { x: p.x + off, left: side })) : Ch.twoCol(Object.assign(o, { x: p.x - off, right: side }));
      const y0 = p.y - G.ph / 2 + G.th, iw = G.colW - 2 * LY.side;
      if (c.icon) {
        const ic = C.iconOf(c.icon, pal);
        s += Ch.sheet(Ch.icon(ic, 0, 0, G.ib - 16), { x: p.x + G.colW / 2 - LY.side - G.ib / 2, y: p.y - G.ph / 2 + 16 + G.ib / 2, k: kk, kind: 'cpIcon', id: 'cp' + i });
      }
      (c.items || []).forEach((it, j) => {
        s += Ch.sheet(C.rect(-iw / 2, -G.rowH / 2, iw, G.rowH, K.PAPER) + C.text(it, 0, 0, G.fs, K.INK),
          { x: p.x, y: y0 + j * (G.rowH + G.gap) + G.rowH / 2, k: kk - ITEM0 - STEP * j, kind: 'cpItem', id: `cp${i}_${j}`, wide: iw / G.rowH > 3 });
      });
    });
    s = C.exitWrap(s, k, C.outK(L, d.out), G.F.cx, G.F.cy);
    return K.wrap(pal, s + (K.portrait ? '' : C.pigeon(t, L, d.pigeon, pal)));
  }

  function check(params) {
    const d = params.data || {}, e = C.checkLines(params);
    if (e.length) return e;
    const L = C.lines(params);
    SIDES.forEach((sd) => {
      const c = d[sd];
      if (!c) { e.push(`缺 ${sd}`); return; }
      if (!c.title) e.push(`${sd} 缺 title`);
      const items = c.items || [];
      if (!items.length) e.push(`${sd}.items 是空的`);
      if (items.length > LY.max) e.push(`${sd}.items ${items.length} 項,上限 ${LY.max}`);
      items.forEach((it, j) => {
        const n = [...String(it || '')].length;
        if (!n) e.push(`${sd}.items[${j}] 是空字串`);
        if (n > LY.maxChars) e.push(`${sd}.items[${j}]「${it}」${n} 字,上限 ${LY.maxChars}`);
      });
      if (c.icon && !C.iconOf(c.icon)) e.push(`${sd}.icon「${c.icon}」找不到(格式 片名.圖解名)`);
      e.push(...C.checkTrig(L, c.at, c.word, sd));
    });
    if (d.hi != null && SIDES.indexOf(d.hi) < 0) e.push(`hi「${d.hi}」只能是 left/right/null`);
    e.push(...C.checkTrig(L, d.out && d.out.at, d.out && d.out.word, 'out'), ...C.checkPigeon(L, d.pigeon));
    if (e.length) return e;
    const G = geo(d), aw = G.A.x1 - G.A.x0, ah = G.A.y1 - G.A.y0 - 24;
    if (G.need > G.colW) e.push(`欄寬不足:需要 ${Math.round(G.need)}px > 每欄 ${Math.round(G.colW)}px(條目或欄標題太長)`);
    if (G.F.h > ah) e.push(`可用高度不足:群組高 ${Math.round(G.F.h)}px > 內容區 ${Math.round(ah)}px(字級已降到下限 ${LY.fsMin})`);
    if (G.F.w > aw) e.push(`群組寬 ${Math.round(G.F.w)}px 超出內容區 ${aw}px`);
    if (K.portrait && d.pigeon && !d.pigeon.hide) e.push('警告:直式 compare 不畫鴿子(兩欄上下排放不下)');
    const Ks = C.assign(L, G.cols), last = Math.max(...G.cols.map((c, i) => Ks[i] + ITEM0 + STEP * Math.max(0, (c.items || []).length - 1)));
    const ko = C.outK(L, d.out);
    e.push(...C.checkHold(last, ko == null ? Math.round(params.dur * 10) : ko));
    return e;
  }

  const API = { LAYOUT, render, check, geo };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).compare = API;
})();
