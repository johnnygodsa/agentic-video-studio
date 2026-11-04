/* turtle 場景 §28 t_hotel_b(句 110–115,30.2 秒)回答網紅。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句110:待查清單三列(第二列已打勾),20% 第一列「付錢就安全?」黃底亮起。
 * 句111:左排「放在房間」8 人全拿牙刷(句首就在);30% 右排「要開口」8 人全拿並加小牌「示意」,60% 其中 6 人放下牙刷只剩 2 人拿;85% 塑膠袋加硬幣。
 * 句112:焚化爐與付錢的牙刷(帶硬幣)句首就在;40% 免費的牙刷、55% 等號、65% 兩支箭頭進焚化爐、78% 結論小牌「海龜:沒差 數量:有減」。
 * 句113:清單回來,第一、二列打勾,第三列「為了省錢?」30% 框裡出現「?」。
 * 句114:「省錢」(句首)、30%「減量」兩個箭頭指同一方向;55% 房價牌「?」。
 * 句115:告示(海龜加「一次性備品會傷害海龜」)句首就在;30–60% 「會傷害海龜」下方由左至右畫出主色底線(逐格變長);60% 右側證據量表五格只亮最低一格。畫面停滿整句。
 * 純圖表場景,無鴿子;每個事件在該句 start 之後依句長比例出現,同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 紙片倍率(與其他 turtle 場景一致)
  const DEF = [{ start: 0.05, end: 4.04 }, { start: 4.16, end: 10.37 }, { start: 10.49, end: 15.69 }, { start: 15.81, end: 18.58 },
    { start: 18.7, end: 25.355 }, { start: 25.475, end: 30.165 }];
  const f = (x) => +(+x).toFixed(2);
  const LABELS = ['付錢就安全?', '都送去燒?', '為了省錢?'];
  const LIST = { x: 180, y: 130, w: 1560, rowH: 190, gap: 40, fs: 100 };

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
  const box = (w, h, fill) => `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  // 粗箭頭(px):起點 → 尖端。o: {th,hw,hl,fill,k,id}
  function arrow(x0, y0, x1, y1, o) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, px = -uy, py = ux, th = o.th, hw = o.hw, hl = o.hl;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, bx = x1 - ux * hl, by = y1 - uy * hl;
    const pts = [[x0 + px * th / 2, y0 + py * th / 2], [bx + px * th / 2, by + py * th / 2], [bx + px * hw / 2, by + py * hw / 2], [x1, y1],
      [bx - px * hw / 2, by - py * hw / 2], [bx - px * th / 2, by - py * th / 2], [x0 - px * th / 2, y0 - py * th / 2]];
    return Ch.sheet(`<polygon points="${pts.map((p) => `${f(p[0] - cx)},${f(p[1] - cy)}`).join(' ')}" fill="${o.fill}"/>`,
      { x: cx, y: cy, u: U, k: o.k, kind: 'arrow', id: o.id, wide: Math.min(Math.abs(dx), Math.abs(dy)) < 0.33 * Math.max(Math.abs(dx), Math.abs(dy)) });
  }

  // ---------- 待查清單(句110、113) ----------
  const rowY = (i) => LIST.y + i * (LIST.rowH + LIST.gap) + LIST.rowH / 2;
  function checklist(pal, states, o) {
    o = o || {};
    let s = '';
    if (o.hiRow != null && o.kHi >= 0) {                                       // 該列黃底亮起(畫在清單下面)
      s += Ch.sheet(box(LIST.w + 56, LIST.rowH + 48, K.YELLOW), { x: LIST.x + LIST.w / 2, y: rowY(o.hiRow), u: U, k: o.kHi, kind: 'hi', id: 'hi', wide: true });
    }
    return s + Ch.checklist({ pal, u: U, x: LIST.x, y: LIST.y, w: LIST.w, rowH: LIST.rowH, gap: LIST.gap, fs: LIST.fs, id: 'todo',
      items: LABELS.map((label, i) => ({ label, state: states[i], kState: o.kState && o.kState[i] })) });
  }

  // ---------- 句111:小人排 ----------
  // 小人(圓頭加身體色塊,不畫手);hold = 拿牙刷(在身側)。中心在原點,約 150×200
  function person(pal, i, hold) {
    const skin = `hsl(${24 + Math.floor(K.hash(i * 3.7 + 1) * 3) * 6} 55% ${72 + Math.floor(K.hash(i * 5.1 + 2) * 3) * 4}%)`;
    let c = `<rect x="-44" y="-26" width="88" height="118" rx="14" fill="hsl(205 50% 52%)"/><circle cx="0" cy="-72" r="38" fill="${skin}"/>`;
    if (hold) c += `<g transform="translate(60 16) rotate(75)">${Ch.icon(ic(pal, 'toothbrush', {}), 0, 0, 160)}</g>`;
    return c;
  }
  const PX0 = 520, PITCH = 135;
  function peopleRow(pal, y, holds, id, k) {
    let s = '';
    for (let i = 0; i < 8; i++) s += Ch.sheet(person(pal, i, holds[i]), { x: PX0 + i * PITCH, y, u: U, k, kind: 'person', id: id + i });
    return s;
  }

  // ---------- 句115:告示(沿用 t_hook 的畫法)、證據量表 ----------
  const NOTICE = { x: 560, y: 450, w: 520, h: 660 };
  function noticeSheet(pal) {
    const w = NOTICE.w, h = NOTICE.h;
    const c = `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="80" fill="${pal.main}" stroke="none"/>` +
      `<circle cx="0" cy="${-h / 2 + 40}" r="18" fill="${PT.C.red}"/>` +
      Ch.icon(ic(pal, 'turtle', {}), 0, -70, 420) + txt('一次性備品', 0, 160, 76, K.INK) + txt('會傷害海龜', 0, 250, 76, K.INK);
    return Ch.sheet(c, { x: NOTICE.x, y: NOTICE.y, u: U, kind: 'notice', id: 'notice' });
  }
  const UL = { x0: NOTICE.x - 215, w: 430, y: NOTICE.y + 250 + 58, th: 16 };    // 「會傷害海龜」下方的底線(字寬 380,左右各長 25)
  function underline(pal, frac) {
    if (frac <= 0) return '';
    const w = UL.w * frac;
    return Ch.sheet(`<rect x="${f(-w / 2)}" y="-8" width="${f(w)}" height="${UL.th}" fill="${pal.main}" stroke="none"/>`,
      { x: UL.x0 + w / 2, y: UL.y, u: U, kind: 'ul', id: 'ul', wide: true });
  }
  const GAUGE = { x: 1420, y: 500, w: 340, cell: 100, gap: 14 };
  function gauge(pal, k) {
    let s = '';
    for (let i = 0; i < 5; i++) {                                              // i = 0 最上格(最強),4 最下格(最低)
      const lit = i === 4, y = GAUGE.y + (i - 2) * (GAUGE.cell + GAUGE.gap);
      s += Ch.sheet(box(GAUGE.w, GAUGE.cell, lit ? K.YELLOW : `hsl(${pal.h} 8% 80%)`), { x: GAUGE.x, y, u: U, k, kind: 'gauge', id: 'g' + i, wide: true });
    }
    return s + plateSheet('證據', 72, { fill: K.INK, ink: K.YELLOW }, { x: GAUGE.x, y: 150, rot: -1.5, k, id: 'gl' });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : k < F[5] ? 4 : 5;
    const pq = (p) => k - at(L[ph], p);            // 句內 p 比例處起算的第幾格
    let s = '';

    if (ph === 0) {                                // 句110:清單、第一列亮起
      s += checklist(pal, ['empty', 'check', 'empty'], { hiRow: 0, kHi: pq(0.2) });
    } else if (ph === 1) {                         // 句111:小人排與塑膠袋加硬幣
      s += peopleRow(pal, 300, [1, 1, 1, 1, 1, 1, 1, 1], 'a');
      s += plateSheet('放在房間', 64, { fill: K.YELLOW }, { x: 270, y: 300, rot: -1.5, id: 'lbA' });
      const keep = pq(0.6) >= 0 ? [0, 0, 1, 0, 0, 1, 0, 0] : [1, 1, 1, 1, 1, 1, 1, 1];
      s += peopleRow(pal, 610, keep, 'b', pq(0.3));
      s += plateSheet('要開口', 64, { fill: K.YELLOW }, { x: 270, y: 610, rot: 1.5, k: pq(0.3), id: 'lbB' });
      s += Ch.srcTag('示意', { pal, u: U, x: 1500, y: 770, anchor: 'right', fs: 44, k: pq(0.3), id: 'src' });
      s += iconSheet(pal, 'bag', { col: 'hsl(40 20% 90%)' }, 1690, 330, 320, { k: pq(0.85), id: 'bag' });
      s += iconSheet(pal, 'coin', {}, 1690, 620, 200, { k: pq(0.88), id: 'coin' });
    } else if (ph === 2) {                         // 句112:兩支牙刷進同一座焚化爐
      s += iconSheet(pal, 'incinerator', {}, 1480, 410, 560, { id: 'inc' });
      s += iconSheet(pal, 'toothbrush', {}, 560, 270, 560, { id: 'b1' });
      s += iconSheet(pal, 'coin', {}, 170, 270, 160, { id: 'coin' });
      s += iconSheet(pal, 'toothbrush', {}, 560, 590, 560, { k: pq(0.4), id: 'b2' });
      s += Ch.sheet(box(200, 36, K.INK) + `<g transform="translate(0 66)">${box(200, 36, K.INK)}</g>`, { x: 560, y: 397, u: U, k: pq(0.55), kind: 'eq', id: 'eq' });
      s += arrow(860, 300, 1190, 380, { th: 36, hw: 100, hl: 80, fill: pal.main, k: pq(0.65), id: 'a1' });
      s += arrow(860, 590, 1190, 480, { th: 36, hw: 100, hl: 80, fill: pal.main, k: pq(0.65), id: 'a2' });
      s += plateSheet('海龜:沒差 數量:有減', 64, { fill: K.YELLOW }, { x: 700, y: 760, rot: -1.5, k: pq(0.78), id: 'concl' });
    } else if (ph === 3) {                         // 句113:第三列「?」
      s += checklist(pal, ['empty', 'check', 'q'], { hiRow: 2, kHi: pq(0.3), kState: [null, null, pq(0.3)] });
      s += K.label('海龜沒差 數量有減', { x: LIST.x + LIST.w - 380, y: rowY(0), fs: 64, id: 'ans0' });   // 第一列不打勾(打勾會被讀成「付錢就安全」)
    } else if (ph === 4) {                         // 句114:兩個箭頭同方向,房價「?」
      s += plateSheet('省錢', 110, { fill: K.YELLOW }, { x: 270, y: 260, rot: -1.5, id: 'l1' });
      s += arrow(480, 260, 1250, 260, { th: 40, hw: 120, hl: 100, fill: pal.main, id: 'a1' });
      s += plateSheet('減量', 110, { fill: K.YELLOW }, { x: 270, y: 620, rot: 1.5, k: pq(0.3), id: 'l2' });
      s += arrow(480, 620, 1250, 620, { th: 40, hw: 120, hl: 100, fill: pal.main, k: pq(0.3), id: 'a2' });
      const sc = K.pop(pq(0.55));
      if (sc > 0) s += K.tile('?', { x: 1560, y: 440, size: 380, rot: 3, u: U, fill: K.INK, ink: K.YELLOW, sx: sc, sy: sc, id: 'q', enter: pq(0.55) < 2 });
      s += plateSheet('房價', 80, { fill: K.YELLOW }, { x: 1560, y: 700, rot: -1.5, k: pq(0.55), id: 'lbH' });
    } else {                                       // 句115:告示、底線、證據量表
      s += noticeSheet(pal);
      const n = Math.max(1, at(L[5], 0.6) - at(L[5], 0.3)), kk = k - at(L[5], 0.3);
      s += underline(pal, kk < 0 ? 0 : Math.min(1, (kk + 1) / n));
      s += gauge(pal, pq(0.6));
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_hotel_b', dur: 30.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
