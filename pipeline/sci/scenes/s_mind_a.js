/* snack 場景 s_mind_a(句 104–109)計算機實驗。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–5。
 * 句104:鴿子站左下(doubt),頭上冒出大腦。
 * 句105:大腦退場;左右兩家小店中間一條路,汽車(逐格位置)由左開到右;名牌「Tversky & Kahneman」;字牌「多開 20 分鐘」「省 5 美元」。
 * 句106:鴿子向左走出畫面;左板「15 美元」:計算機、10×10 方格亮 68 格、大字「68%」。
 * 句107:右板「125 美元」:計算機、方格亮 29 格、大字「29%」。
 * 句108:方格與大字退場;兩板各掉下一枚「5 美元」黃色圓牌。
 * 句109:全部換成兩條比例條:5 / 15 佔三分之一、5 / 125 佔 4%;右下「自算」黃牌。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const DEF = [
    { start: 0.1, end: 3.22, text: '還有一個原因跟數學無關,問題出在你的腦袋。' },
    { start: 3.34, end: 11.165, text: '心理學家特沃斯基和康納曼做過一個實驗,問大家願不願意多開二十分鐘的車去另一家店,只為了省 5 美元。' },
    { start: 11.285, end: 15.125, text: '如果要買的是 15 美元的計算機,有 68% 的人說願意。' },
    { start: 15.245, end: 20.515, text: '換成 125 美元的計算機,同樣省 5 美元,願意的人剩下 29% 而已。' },
    { start: 20.635, end: 22.36, text: '省下來的錢一模一樣呀。' },
    { start: 22.48, end: 24.79, text: '人卻是看比例在決定要不要計較。' }];
  const U = 1.43, PU = 1.36;                                   // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const SHOP = { w: 270, h: 280, ay: 450, ax: 605, bx: 1515 };  // 店中心 y = 450(y 310–590);A 中心 x 605、B 中心 x 1515
  const ROAD = { x0: 450, x1: 1780, y0: 600, y1: 740 };
  const CAR = { x0: 640, x1: 1480, y: 668, s: 1.5 };
  const PANEL = { x: 960, y: 455, w: 1500, h: 660, gap: 30, fs: 72 };
  const COIN = { r: 165, dx: 70, y: 590, fs: 90 };
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const RN = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || d.text };
    });
  }
  // 第 i 句中某詞出現的格(用詞在句中的位置比例估)
  const wordK = (L, i, w) => { const l = L[i], j = l.text.indexOf(w); return K.frame(l.start + (j < 0 ? 0 : j / l.text.length) * (l.end - l.start)); };

  // 小店面(單位 px,中心在原點):頂部條紋遮陽棚、窗、門
  function shop(col) {
    const { w, h } = SHOP;
    let c = R(-w / 2, -h / 2, w, h, K.PAPER);
    for (let i = 0; i < 6; i++) c += RN(-w / 2 + i * w / 6, -h / 2, w / 6, 84, i % 2 ? K.PAPER : col);
    c += RN(-w / 2 + 24, -h / 2 + 118, 104, 92, 'hsl(200 45% 82%)') + RN(w / 2 - 24 - 84, h / 2 - 136, 84, 136, K.INK);
    c += `<circle cx="${f(w / 2 - 24 - 20)}" cy="${f(h / 2 - 66)}" r="7" fill="${K.YELLOW}" stroke="none"/>`;
    return c;
  }
  // 一枚寫「5 美元」的黃色圓牌;kk = 掉落後第幾格
  function coin(pal, x, y, kk, id) {
    const d = K.drop(kk);
    if (!d) return '';
    const r = COIN.r, c = `<g transform="scale(${f(1 / U)})" stroke-width="${f(4 * U)}"><circle r="${r}" fill="${K.YELLOW}"/>` +
      `<circle r="${r - 16}" fill="none" stroke="${K.INK}" stroke-width="6"/>` +
      `<text x="0" y="0" font-family="GenSen" font-size="${COIN.fs}" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">5 美元</text></g>`;
    return K.paper(c, { x, y: y + d.dy * (y + r) + (1 - d.sy) * r, scale: U, sx: d.sx, sy: d.sy, k: 'coin', id, enter: !!d.enter });
  }
  // 兩板的一側:計算機、方格、大字(grid=false 時只留計算機)
  function side(pal, p, kk, n, kFillAt, k, grid, id) {
    let s = K.paper(PS.LIST.calculator.fn(pal, {}), { x: p.x - 215, y: 405, scale: 1.3, sx: K.pop(kk - 1), sy: K.pop(kk - 1), k: 'prop', id: 'calc' + id, enter: kk - 1 < 2 });
    if (!grid) return s;
    s += Ch.dotGrid({ pal, x: p.x + 110, y: 405, size: 260, n, color: pal.text, u: U, k: kk - 3, kFill: k - kFillAt, per: 10, id: 'dg' + id });
    s += Ch.bigNum({ x: p.x, y: 672, num: n + '%', fs: 150, u: U, k: k - (kFillAt + 3), id: 'bn' + id });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = F.reduce((a, v, i) => (k >= v ? i : a), 0);
    let s = '';

    // ---- 句104–105:鴿子與大腦、店與車
    if (ph <= 1) {
      const q = k - F[0], pose = K.expr(K.clip('idle', k), ph === 0 ? 'doubt' : 'look');
      s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
      s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main', enter: q < 2 });
      if (ph === 0) {
        const p = K.pop(q - 2);
        if (p > 0) s += K.paper(PS.LIST.brain.fn(pal, {}), { x: 297, y: 368, scale: 0.9, sx: p, sy: p, k: 'prop', id: 'brain', enter: q - 2 < 2 });
      }
    }
    if (ph === 1) {
      const q = k - F[1], dStart = wordK(L, 1, '問大家'), dEnd = Math.max(dStart + 4, K.frame(L[1].end - 0.5));
      const kStay = wordK(L, 1, '多開'), kSave = wordK(L, 1, '省 5');
      s += Ch.sheet(R(-ROAD.x1 / 2 + ROAD.x0 / 2, -(ROAD.y1 - ROAD.y0) / 2, ROAD.x1 - ROAD.x0, ROAD.y1 - ROAD.y0, `hsl(${pal.h} 12% 40%)`) +
        Array.from({ length: 9 }, (_, i) => RN(-(ROAD.x1 - ROAD.x0) / 2 + 60 + i * 150, -5, 80, 10, K.PAPER)).join(''),
        { x: (ROAD.x0 + ROAD.x1) / 2, y: (ROAD.y0 + ROAD.y1) / 2, u: U, k: q, kind: 'road', id: 'road', wide: true });
      s += Ch.sheet(shop(pal.main), { x: SHOP.ax, y: SHOP.ay, u: U, k: q, kind: 'prop', id: 'shopA' });
      s += Ch.sheet(shop(K.YELLOW), { x: SHOP.bx, y: SHOP.ay, u: U, k: q, kind: 'prop', id: 'shopB' });
      const prog = Math.max(0, Math.min(1, (k - dStart) / (dEnd - dStart))), bob = k >= dStart && k < dEnd ? (k % 2) * -3 : 0;
      s += K.paper(PT.LIST.car.fn(pal, { col: pal.main }), { x: CAR.x0 + (CAR.x1 - CAR.x0) * prog, y: CAR.y + bob, scale: CAR.s, sx: K.pop(q), sy: K.pop(q), k: 'prop', id: 'car', enter: q < 2 });
      s += Ch.plate && Ch.sheet(Ch.plate('Tversky & Kahneman', 64, { chip: pal.main }).svg, { x: 940, y: 150, rot: -1, u: U, k: q - 2, kind: 'name', id: 'name', wide: true });
      s += Ch.sheet(Ch.plate('多開 20 分鐘', 72, { chip: pal.main }).svg, { x: 1060, y: 420, rot: 1, u: U, k: k - kStay, kind: 'tag', id: 'tagA', wide: true });
      s += Ch.sheet(Ch.plate('省 5 美元', 72, { fill: K.YELLOW }).svg, { x: 1515, y: 215, rot: -1.5, u: U, k: k - kSave, kind: 'tag', id: 'tagB', wide: true });
    }

    // ---- 句106–108:兩板
    if (ph >= 2 && ph <= 4) {
      const q = k - F[2];
      if (q < 6) {                                              // 鴿子向左走出畫面
        const pose = Object.assign({}, K.clip('walk', q), { flip: 0 });
        s += K.pigeon(pose, { x: FOOT.x - 60 * q, y: FOOT.y, scale: PU, id: 'main', enter: true });
      }
      const o = { pal, x: PANEL.x, y: PANEL.y, w: PANEL.w, h: PANEL.h, gap: PANEL.gap, fs: PANEL.fs, u: U, id: 'tc',
        left: { title: '15 美元', titleFill: K.YELLOW, titleInk: K.INK, k: k - (F[2] + 4) },
        right: { title: '125 美元', titleFill: K.YELLOW, titleInk: K.INK, k: k - F[3] } };
      const pos = Ch.twoColPos(o), kL = k - (F[2] + 4), kR = k - F[3];
      s += Ch.twoCol(o);
      if (kL >= 0) s += side(pal, pos[0], kL, 68, Math.max(wordK(L, 2, '68%'), F[2] + 8), k, ph <= 3, 'L');
      if (ph >= 3) s += side(pal, pos[1], kR, 29, Math.max(wordK(L, 3, '29%'), F[3] + 6), k, ph <= 3, 'R');
      if (ph === 4) {
        s += coin(pal, pos[0].x + COIN.dx, COIN.y, k - F[4], 'coinL');
        s += coin(pal, pos[1].x + COIN.dx, COIN.y, k - F[4], 'coinR');
      }
    }

    // ---- 句109:兩條比例條
    if (ph === 5) {
      const q = k - F[5];
      s += Ch.ratioBar({ pal, x: 960, y: 310, w: 1400, h: 110, fs: 72, u: U, id: 'rbA', segs: [
        { value: 5, label: '5 / 15', text: '三分之一', side: 'up', color: K.YELLOW, k: q },
        { value: 10, label: '15 美元', side: 'up', color: pal.pad, k: q }] });
      s += Ch.ratioBar({ pal, x: 960, y: 610, w: 1400, h: 110, fs: 72, u: U, id: 'rbB', segs: [
        { value: 5, label: '5 / 125', text: '4%', side: 'up', color: K.YELLOW, k: q - 7 },
        { value: 120, label: '125 美元', side: 'down', color: pal.pad, k: q - 7 }] });
      const p = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
      s += Ch.sheet(p.svg, { x: 1740, y: 780, u: U, k: q - 3, kind: 'src', id: 'self', wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_mind_a', dur: 24.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
