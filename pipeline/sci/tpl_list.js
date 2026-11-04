/* 模板 list(F4-0):標題牌 + 清單(check/num/dot 全部自繪前綴,幾何同 Charts.checklist 但文字起點多留 0.3 倍字級)。
 * data: {title?, style:'check'|'num'|'dot', items:[{text,at?,word?,state?,icon?}], hi:[i], out?:{at,word?}, pigeon?}
 * state 只用於 check(預設 'check';'empty'|'q');icon('turtle.coin' 這類 Props 名)只用於 num/dot。
 * hi:num/dot 該列黃底;check 該列在文字區貼一片黃紙。觸發:標題在第 0 句開頭;各項依 at/word,省略則依序分配;勾號晚 2 格。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判】:max 項數、maxChars 每項字數、fsMax/fsMin 列字級範圍(實際字級由 C.fitBlock 取放得進內容區的最大值)、
  // rowR 行高 ÷ 字級、gapR 列距 ÷ 行高、minW 列寬下限、titleGap 標題牌與清單間距
  const LAYOUT = {
    landscape: { max: 6, maxChars: 14, fsMax: 84, fsMin: 56, rowR: 1.35, gapR: 0.1, minW: 760, titleGap: 32 },
    portrait: { max: 5, maxChars: 9, fsMax: 80, fsMin: 60, rowR: 1.35, gapR: 0.1, minW: 600, titleGap: 32 },
  };
  const LY = LAYOUT[C.LAY];
  const MARK = 2;                                   // 勾號晚幾格
  const CHECK = [[-0.5, 0.02], [-0.3, -0.18], [-0.1, 0.08], [0.38, -0.52], [0.58, -0.34], [-0.08, 0.48]];   // 同 Charts.checklist 的勾形
  const LEAD = 0.3;                                 // 前綴(框/勾)右緣到文字至少 0.3 × 字級(勾號右緣約 0.93 × 行高,所以文字起點再加 0.3 × 字級)

  // 幾何:群組 = 標題牌(選填)+ 清單,在內容區垂直置中、水平置中;字級取放得下的最大值
  function geo(d, pal) {
    const A = C.area(d.pigeon && d.pigeon.hide), items = d.items || [], n = Math.max(1, items.length);
    const tb = d.title ? C.titleBox(d.title) : null, head = tb ? tb.h + LY.titleGap : 0;
    const icons = items.map((it) => (it.icon ? C.iconOf(it.icon, pal) : null)), hasIcon = icons.some(Boolean);
    const size = (fs) => {
      const rowH = fs * LY.rowR, gap = rowH * LY.gapR, iw = hasIcon ? rowH * 0.9 : 0, lead = rowH + fs * LEAD + iw;
      const w = Math.max(LY.minW, lead + Math.max(0, ...items.map((it) => Ch.tw(it.text || '', fs))) + fs * 0.8);
      return { rowH, gap, iw, lead, w, H: n * rowH + (n - 1) * gap };
    };
    const F = C.fitBlock(A, { fsMax: LY.fsMax, fsMin: LY.fsMin, hOf: (fs) => head + size(fs).H, wOf: (fs) => Math.max(size(fs).w, tb ? tb.w : 0) });
    const z = size(F.fs), top = F.top + head;
    return Object.assign(z, { A, fs: F.fs, F, tb, icons, top, x: F.cx - z.w / 2, titleY: tb ? F.top + tb.h / 2 : 0, cy: (i) => top + i * (z.rowH + z.gap) + z.rowH / 2 });
  }

  function render(t, params) {
    const d = params.data || {}, L = C.lines(params), k = K.frame(t), pal = K.palette(params.hue), G = geo(d, pal);
    const items = d.items || [], Ks = C.assign(L, items), hi = d.hi || [], style = d.style || 'check', x = G.x, w = G.w;
    let s = C.title(d.title, k - C.trig(L, 0, null, 0), G.tb && { x: G.F.cx, y: G.titleY });
    if (style === 'check') {
      items.forEach((it, i) => {                     // 自繪(Charts.checklist 的文字起點固定,勾號會貼到字)
        const kk = k - Ks[i], st = it.state || 'check', b = G.rowH * 0.62, bx = -w / 2 + G.rowH / 2;
        if (kk < 0) return;
        s += Ch.sheet(C.rect(-w / 2, -G.rowH / 2, w, G.rowH, K.PAPER) + C.rect(bx - b / 2, -b / 2, b, b, K.INK) +
          C.rect(bx - b / 2 + 7, -b / 2 + 7, b - 14, b - 14, K.PAPER) + C.text(it.text, -w / 2 + G.lead, 0, G.fs, K.INK, 'start'),
          { x: x + w / 2, y: G.cy(i), k: kk, kind: 'check', id: 'tl' + i, wide: w / G.rowH > 3 });
        if (st === 'check') {
          s += Ch.sheet(`<polygon points="${CHECK.map((p) => `${(p[0] * b * 1.2).toFixed(2)},${(p[1] * b * 1.2).toFixed(2)}`).join(' ')}" fill="${pal.text}"/>`,
            { x: x + G.rowH / 2, y: G.cy(i), k: kk - MARK, kind: 'checkMark', id: 'tl' + i });
        } else if (st === 'q') {
          s += Ch.sheet(C.rect(-b / 2, -b / 2, b, b, K.INK) + C.text('?', 0, 0, b * 0.78, K.YELLOW),
            { x: x + G.rowH / 2, y: G.cy(i), rot: 5, k: kk - MARK, kind: 'checkQ', id: 'tl' + i });
        }
      });
      hi.forEach((i) => {                            // 黃紙貼在文字區(勾框與勾號留在外面)
        if (!items[i] || k < Ks[i]) return;
        const x0 = x + G.rowH * 0.96, ow = x + w - x0;
        s += Ch.sheet(C.rect(-ow / 2, -G.rowH / 2, ow, G.rowH, K.YELLOW) + C.text(items[i].text, x + G.lead - x0 - ow / 2, 0, G.fs, K.INK, 'start'),
          { x: x0 + ow / 2, y: G.cy(i), k: k - Ks[i], kind: 'hi', id: 'hi' + i, wide: ow / G.rowH > 3 });
      });
    } else {
      items.forEach((it, i) => {
        const b = G.rowH * 0.62, bx = -w / 2 + G.rowH / 2, isHi = hi.indexOf(i) >= 0;
        let c = C.rect(-w / 2, -G.rowH / 2, w, G.rowH, isHi ? K.YELLOW : K.PAPER);
        c += style === 'num' ? C.rect(bx - b / 2, -b / 2, b, b, K.INK) + C.text(String(i + 1), bx, 0, b * 0.72, K.YELLOW)
          : `<circle cx="${bx}" cy="0" r="${(G.rowH * 0.16).toFixed(2)}" fill="${pal.main}" stroke="none"/>`;
        if (G.icons[i]) c += Ch.icon(G.icons[i], -w / 2 + G.rowH + G.iw / 2, 0, G.rowH - 22);
        c += C.text(it.text, -w / 2 + G.lead, 0, G.fs, K.INK, 'start');
        s += Ch.sheet(c, { x: x + w / 2, y: G.cy(i), k: k - Ks[i], kind: 'row', id: 'row' + i, wide: w / G.rowH > 3 });
      });
    }
    s = C.exitWrap(s, k, C.outK(L, d.out), G.F.cx, G.F.cy);
    return K.wrap(pal, s + C.pigeon(t, L, d.pigeon, pal));
  }

  function check(params) {
    const d = params.data || {}, e = C.checkLines(params);
    if (e.length) return e;
    const L = C.lines(params), items = d.items || [], style = d.style || 'check';
    if (['check', 'num', 'dot'].indexOf(style) < 0) e.push(`style「${style}」只能是 check/num/dot`);
    if (!items.length) e.push('items 是空的');
    if (items.length > LY.max) e.push(`items ${items.length} 項,${C.LAY} 上限 ${LY.max}`);
    items.forEach((it, i) => {
      const n = [...String(it.text || '')].length;
      if (!n) e.push(`items[${i}] 缺 text`);
      if (n > LY.maxChars) e.push(`items[${i}]「${it.text}」${n} 字,上限 ${LY.maxChars}`);
      e.push(...C.checkTrig(L, it.at, it.word, `items[${i}]`));
      if (it.state && ['empty', 'check', 'q'].indexOf(it.state) < 0) e.push(`items[${i}].state「${it.state}」不認得`);
      if (it.icon && style === 'check') e.push(`items[${i}].icon:check 樣式不支援 icon`);
      if (it.icon && !C.iconOf(it.icon)) e.push(`items[${i}].icon「${it.icon}」找不到(格式 片名.圖解名)`);
    });
    (d.hi || []).forEach((i) => { if (!items[i]) e.push(`hi 索引 ${i} 不存在`); });
    e.push(...C.checkTrig(L, d.out && d.out.at, d.out && d.out.word, 'out'), ...C.checkPigeon(L, d.pigeon));
    if (e.length) return e;
    const G = geo(d, K.palette(params.hue));
    if (G.tb && G.tb.w > G.A.x1 - G.A.x0) e.push(`標題寬 ${Math.round(G.tb.w)}px 超出內容區`);
    if (G.w > G.A.x1 - G.A.x0) e.push(`列寬 ${Math.round(G.w)}px 超出內容區 ${G.A.x1 - G.A.x0}px`);
    if (G.F.h > G.A.y1 - G.A.y0) e.push(`可用高度不足:群組高 ${Math.round(G.F.h)}px > 內容區 ${Math.round(G.A.y1 - G.A.y0)}px(字級已降到下限 ${LY.fsMin})`);
    const Ks = C.assign(L, items), ko = C.outK(L, d.out);
    e.push(...C.checkHold(Math.max(...Ks) + (style === 'check' ? MARK : 0), ko == null ? Math.round(params.dur * 10) : ko));
    return e;
  }

  const API = { LAYOUT, render, check };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).list = API;
})();
