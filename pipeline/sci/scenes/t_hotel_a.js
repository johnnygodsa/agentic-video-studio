/* turtle 場景 §27 t_hotel_a(句 104–109,27.4 秒)備品屬於哪一邊。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句104:兩欄板(有用的部分/沒那麼有用),備品(牙刷加小瓶)停在中間。
 * 句105:數字卡「4.6 億個」(句首就在)→ 50% 箭頭與「2,100 公噸」;小牌「官方上路前估算」。
 * 句106:巨大方塊(600px,標「1,210 萬公噸」),30% 旁邊一個約 8px 的小點、45% 放大鏡指著它並標「2,100 公噸」、70% 大字「不到萬分之二」、85% 小牌「自算」。
 * 句107:表格兩列(上路前估算/上路後實際減少),第二列的值 40% 出現「查無公布數字」加「?」。
 * 句108:左邊牙刷→焚化爐的路線,海龜在右邊,中間沒有線。
 * 句109:焚化爐、20% 灰渣堆掉出、45% 箭頭與掩埋坑(灰渣進坑)、80% 備品減少 → 灰渣堆少一截(舊高度淡影加新高度)。
 * 純圖表場景,無鴿子;每個事件在該句 start 之後依句長比例出現,同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 紙片倍率(與其他 turtle 場景一致)
  const DEF = [{ start: 0.055, end: 1.95 }, { start: 2.07, end: 7.81 }, { start: 7.93, end: 12.225 }, { start: 12.345, end: 15.84 },
    { start: 15.96, end: 21.385 }, { start: 21.505, end: 27.33 }];
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const iconSheet = (pal, n, o, x, y, box, p) => Ch.sheet(Ch.icon(ic(pal, n, o), 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: n, wide: PT.LIST[n].wide }, p));
  const plateSheet = (str, fs, o, p) => { const q = Ch.plate(str, fs, o); return Ch.sheet(q.svg, Object.assign({ u: U, kind: 'plate', id: str, wide: true }, p)); };
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  // 粗箭頭(px):起點 → 尖端。o: {th,hw,hl,fill,k,id}
  function arrow(x0, y0, x1, y1, o) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, px = -uy, py = ux, th = o.th, hw = o.hw, hl = o.hl;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, bx = x1 - ux * hl, by = y1 - uy * hl;
    const pts = [[x0 + px * th / 2, y0 + py * th / 2], [bx + px * th / 2, by + py * th / 2], [bx + px * hw / 2, by + py * hw / 2], [x1, y1],
      [bx - px * hw / 2, by - py * hw / 2], [bx - px * th / 2, by - py * th / 2], [x0 - px * th / 2, y0 - py * th / 2]];
    return Ch.sheet(`<polygon points="${pts.map((p) => `${f(p[0] - cx)},${f(p[1] - cy)}`).join(' ')}" fill="${o.fill}"/>`,
      { x: cx, y: cy, u: U, k: o.k, kind: 'arrow', id: o.id, wide: Math.min(Math.abs(dx), Math.abs(dy)) < 0.33 * Math.max(Math.abs(dx), Math.abs(dy)) });
  }
  const box = (w, h, fill) => `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;

  // ---------- 句106:巨大方塊、小點、放大鏡 ----------
  const SQ = { x: 480, y: 450, s: 600 };
  const DOT = { x: 880, y: 640, s: 8 };
  const LENS = { x: 1330, y: 530, r: 165 };
  function magnifier(pal, k) {
    const r = LENS.r, ink = K.INK;
    let c = `<circle r="${r}" fill="${pal.bg}" stroke="${ink}" stroke-width="26"/>` +
      `<g transform="rotate(45)"><rect x="${r + 8}" y="-22" width="150" height="44" fill="${ink}" stroke="none"/></g>` +
      `<rect x="-36" y="-36" width="72" height="72" fill="${K.INK}" stroke-width="5"/>`;
    return Ch.sheet(c, { x: LENS.x, y: LENS.y, u: U, k, kind: 'lens', id: 'lens' });
  }
  function beam(pal, k) {                          // 小點到放大鏡之間的兩條光線(淡色三角)
    const a = Math.atan2(DOT.y - LENS.y, DOT.x - LENS.x), pt = (d) => [LENS.x + LENS.r * Math.cos(a + d) - DOT.x, LENS.y + LENS.r * Math.sin(a + d) - DOT.y];
    const p1 = pt(-0.5), p2 = pt(0.5);
    return Ch.sheet(`<polygon points="0,0 ${f(p1[0])},${f(p1[1])} ${f(p2[0])},${f(p2[1])}" fill="${pal.pad}" stroke="none"/>`,
      { x: DOT.x + (p1[0] + p2[0]) / 3, y: DOT.y + (p1[1] + p2[1]) / 3, u: U, k, kind: 'beam', id: 'beam' });
  }

  // ---------- 句109:掩埋坑 ----------
  const PIT = { x: 1330, y: 570, w: 840, h: 420 };
  function pitSheet(k) {
    const w = PIT.w, h = PIT.h;
    const c = box(w, h, 'hsl(28 45% 36%)') + `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="70" fill="hsl(120 35% 45%)" stroke="none"/>` +
      `<polygon points="${-w / 2 + 60},${-h / 2 + 70} ${w / 2 - 60},${-h / 2 + 70} ${w / 2 - 120},${h / 2 - 20} ${-w / 2 + 120},${h / 2 - 20}" fill="hsl(28 40% 20%)" stroke="none"/>`;
    return Ch.sheet(c, { x: PIT.x, y: PIT.y, u: U, k, kind: 'pit', id: 'pit' });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : k < F[5] ? 4 : 5;
    const q = Math.max(0, k - F[ph]);
    const pq = (p) => k - at(L[ph], p);            // 句內 p 比例處起算的第幾格
    const greyI = `hsl(${pal.h} 8% 42%)`;
    let s = '';

    if (ph === 0) {                                // 句104:兩欄板、備品停中間
      s += Ch.twoCol({ pal, u: U, x: 960, y: 460, w: 1740, h: 740, gap: 24, fs: 72, id: 'tc',
        left: { title: '有用的部分', color: `hsl(${pal.h} 10% 88%)`, titleFill: `hsl(${pal.h} 8% 80%)`, titleInk: greyI },
        right: { title: '沒那麼有用', color: pal.pad, titleFill: K.YELLOW, titleInk: K.INK } });
      s += iconSheet(pal, 'toothbrush', {}, 960, 430, 560, { rot: -6, id: 'brush' });
      s += iconSheet(pal, 'miniBottle', {}, 960, 660, 300, { id: 'mini' });
    } else if (ph === 1) {                         // 句105:兩張數字卡
      s += Ch.bigNum({ pal, u: U, x: 560, y: 260, num: '4.6 億個', fs: 180, id: 'n1' });
      s += arrow(950, 300, 1240, 450, { th: 36, hw: 100, hl: 80, fill: pal.main, k: pq(0.5), id: 'a1' });
      s += Ch.bigNum({ pal, u: U, x: 1260, y: 590, num: '2,100 公噸', fs: 180, k: pq(0.52), id: 'n2' });
      s += Ch.srcTag('官方上路前估算', { pal, u: U, x: 1820, y: 770, anchor: 'right', fs: 44, id: 'src' });
    } else if (ph === 2) {                         // 句106:巨大方塊與小點
      s += Ch.sheet(box(SQ.s, SQ.s, pal.main), { x: SQ.x, y: SQ.y, u: U, kind: 'block', id: 'block' });
      s += plateSheet('1,210 萬公噸', 80, { fill: K.YELLOW }, { x: SQ.x, y: SQ.y, rot: -1.5, id: 'lb' });
      s += Ch.sheet(`<rect x="-4" y="-4" width="8" height="8" fill="${K.INK}"/>`, { x: DOT.x, y: DOT.y, u: 0.6, k: pq(0.3), kind: 'dot', id: 'dot' });
      s += beam(pal, pq(0.45)) + magnifier(pal, pq(0.45));
      s += plateSheet('2,100 公噸', 64, { fill: K.YELLOW }, { x: 1050, y: 752, rot: 1.5, k: pq(0.5), id: 'lb2' });
      s += Ch.bigNum({ pal, u: U, x: 1330, y: 195, num: '不到萬分之二', fs: 150, k: pq(0.7), id: 'tiny' });
      s += Ch.srcTag('自算', { pal, u: U, x: 1810, y: 345, anchor: 'right', fs: 44, k: pq(0.85), id: 'src' });
    } else if (ph === 3) {                         // 句107:表格
      const rows = [['上路前估算', '2,100 公噸', K.PAPER, 0], ['上路後實際減少', '查無公布數字', K.YELLOW, 0.4]];
      rows.forEach((r, i) => {
        const y = 326 + i * 248;
        s += Ch.sheet(box(700, 220, K.PAPER) + txt(r[0], 0, 0, 84, K.INK), { x: 570, y, u: U, kind: 'cell', id: 'lab' + i, wide: true });
        const v = box(760, 220, i ? r[2] : K.PAPER) + txt(r[1], 0, 0, 84, i ? K.INK : pal.text);
        s += Ch.sheet(v, { x: 1300, y, u: U, k: i ? pq(r[3]) : undefined, kind: 'cell', id: 'val' + i, wide: true });
      });
      s += K.tile('?', { x: 1752, y: 574, size: 110, rot: 5, u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(pq(0.55)), sy: K.pop(pq(0.55)), id: 'q' });
    } else if (ph === 4) {                         // 句108:牙刷→焚化爐,海龜在另一側
      s += iconSheet(pal, 'toothbrush', {}, 220, 420, 540, { rot: 90, id: 'brush' });
      s += plateSheet('牙刷', 64, {}, { x: 222, y: 765, rot: -1.5, id: 'lbB' });
      s += arrow(340, 430, 570, 430, { th: 36, hw: 100, hl: 80, fill: pal.main, k: pq(0.15), id: 'a' });
      s += iconSheet(pal, 'incinerator', {}, 790, 430, 520, { k: pq(0.2), id: 'inc' });
      s += plateSheet('焚化爐', 64, {}, { x: 790, y: 765, rot: 1.5, k: pq(0.2), id: 'lbI' });
      s += iconSheet(pal, 'turtle', { expr: 'speechless' }, 1500, 430, 640, { k: pq(0.55), id: 'turtle' });
      s += plateSheet('海龜', 64, {}, { x: 1500, y: 765, rot: -1.5, k: pq(0.55), id: 'lbT' });
    } else {                                       // 句109:灰渣堆與掩埋坑
      s += iconSheet(pal, 'incinerator', {}, 330, 360, 460, { id: 'inc' });
      const kp = pq(0.2), shrink = pq(0.8) >= 0;
      const pile = Ch.icon(ic(pal, 'ashPile', {}), 0, 0, 320);                // 灰渣堆 320×137
      const gx = `<g opacity=".35">${pile}</g>`;
      const small = `<g transform="translate(0 68) scale(1 0.55) translate(0 -68)">${pile}</g>`;
      s += Ch.sheet(shrink ? gx + small : pile, { x: 330, y: 735, u: U, k: kp, kind: 'prop', id: 'ash' });
      if (shrink) s += plateSheet('少一截', 72, { fill: K.YELLOW }, { x: 700, y: 610, rot: 1.5, k: pq(0.8), id: 'less' });
      s += arrow(530, 730, 880, 730, { th: 36, hw: 100, hl: 80, fill: pal.main, k: pq(0.45), id: 'a' });
      s += pitSheet(pq(0.45));
      s += plateSheet('掩埋坑', 64, { fill: K.YELLOW }, { x: PIT.x, y: 290, rot: -1.5, k: pq(0.45), id: 'lbP' });
      [[1180, 715, 0.5], [1330, 715, 0.58], [1480, 715, 0.66], [1255, 610, 0.74], [1405, 610, 0.82]].forEach((a, i) => {
        s += iconSheet(pal, 'ashPile', {}, a[0], a[1], 230, { k: pq(a[2]), id: 'ap' + i });
      });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_hotel_a', dur: 27.4, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
