/* turtle 場景 §17 t_smell(句 61–67,29.5 秒)為什麼吃塑膠。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 分三段換景,換段時前一段的東西全部縮小退場:
 *   A(61–63):盤子上是海草海藻加「幾乎吃素」→ 換成塑膠碎片加「?」→ 水裡的塑膠袋 = 水母(輪廓很像)。
 *   B(64–66):「2020 實驗」水槽、海龜鼻子露出水面 → 三種氣味(波浪線紙片:灰=乾淨塑膠、藍=泡過海水的塑膠、綠=食物)依序飄向海龜,
 *            泡過海水與食物都讓海龜抬頭「!」,兩個「!」之間一個等號 → 泡過海水的塑膠冒香氣線、蓋上餐盤蓋。
 *   C(67):實驗牌加小牌「規模不大 人工飼養」;結論條由實線改成虛線邊「有這個可能」。
 * 鴿子在左下當觀察者(每句最多一個反應);內容全在 x 520 以右。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 800 };                 // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0.04, end: 3.135 }, { start: 3.255, end: 5.865 }, { start: 5.985, end: 9.3 }, { start: 9.42, end: 12.69 },
    { start: 12.81, end: 19.99 }, { start: 20.11, end: 23.42 }, { start: 23.54, end: 29.465 }];
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const PL = { x: 940, y: 465 };                   // 盤子中心
  const TK = { x: 1190, y: 627.5, w: 1290, h: 405 };   // 水槽(水面在上緣)
  const TT = { x: 1450, y: 600, box: 640, rot: -22 };  // 水槽裡的海龜
  const ITEM = { x: 800, y: 330 };                 // 水面上的氣味來源
  const f = (x) => +(+x).toFixed(2);
  const now = (k) => (k < 0 ? -1 : 3);             // 大紙片直接以原尺寸出現(不過衝,免得蓋進字幕帶)
  const GREY_W = 'hsl(200 8% 55%)', BLUE_W = 'hsl(205 80% 50%)', GREEN_W = 'hsl(130 55% 40%)';

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const sh = (c, x, y, kk, kind, id, ex) => Ch.sheet(c, Object.assign({ x, y, u: U, k: kk, kind, id }, ex));
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const rope = (d, w, col) => `<path d="${d}" fill="none" stroke="${K.PAPER}" stroke-width="${f(w + 7)}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  function tl(ch, x, y, size, kk, id, o) {
    const p = K.pop(kk);
    if (p <= 0) return '';
    return K.tile(ch, Object.assign({ x, y, size, u: U, sx: p, sy: p, id, enter: kk < 2 }, o));
  }
  // 一層:k < kIn 不畫;k >= kOut 起兩格縮小(以 cx,cy 為中心)後消失;draw(kEff) 用絕對格數(退場時傳 1e6 = 全部已出現)
  function layer(k, kIn, kOut, cx, cy, draw) {
    if (k < kIn) return '';
    if (kOut != null && k >= kOut) {
      const j = k - kOut;
      if (j >= OUT.length) return '';
      return `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${draw(1e6)}</g>`;
    }
    return draw(k);
  }

  // ---------- 圖解(場景內自畫) ----------
  const dishSvg = () => `<circle cx="0" cy="0" r="300" fill="${K.PAPER}"/><circle cx="0" cy="0" r="252" fill="hsl(200 22% 88%)" stroke="none"/>` +
    `<circle cx="0" cy="0" r="205" fill="none" stroke="hsl(200 18% 78%)" stroke-width="6"/>`;
  // 海草(直立葉片)加海藻(彎帶),置中、半徑約 250
  function weedSvg() {
    let s = rope('M -190 40 C -140 -60, -80 100, -20 0 S 100 -60, 170 30', 40, 'hsl(140 45% 28%)') +
      rope('M -170 -40 C -110 -130, -40 20, 30 -80 S 130 -120, 180 -50', 34, 'hsl(120 50% 38%)') +
      rope('M -150 110 C -80 40, -10 170, 60 90 S 150 60, 175 120', 36, 'hsl(150 40% 24%)');
    [[-60, 130, -150, -120], [-30, 140, -70, -170], [0, 145, 10, -190], [30, 140, 90, -160], [60, 130, 150, -110]].forEach(([bx, by, tx, ty], i) => {
      const mx = (bx + tx) / 2 + (i % 2 ? 16 : -16), my = (by + ty) / 2;
      s += `<path d="M ${bx - 14} ${by} Q ${f(mx - 12)} ${my} ${tx} ${ty} Q ${f(mx + 14)} ${my} ${bx + 14} ${by} Z" fill="hsl(${88 + i * 6} 55% ${42 + i * 2}%)"/>`;
    });
    return s;
  }
  const weedIc = () => ({ svg: weedSvg(), w: 460, h: 460 });
  const drop = (x, y) => `<g transform="translate(${x} ${y}) scale(1.9)"><path d="M 0 -16 C 16 4 14 18 0 18 C -14 18 -16 4 0 -16 Z" fill="hsl(205 80% 55%)"/></g>`;
  const bottleIc = (pal, soaked) => ({ svg: PT.LIST.bottle.fn(pal, {}) + (soaked ? drop(-64, -30) + drop(66, 10) + drop(-62, 62) : ''), w: 170, h: 220 });
  // 水平波浪線紙片:三條線(中心在原點,寬 260)
  function waveSvg(col) {
    let s = '';
    [-28, 0, 28].forEach((dy, i) => { s += rope(`M -130 ${dy} q 16.25 ${i % 2 ? 16 : -16} 32.5 0` + ' t 32.5 0'.repeat(7), 14, col); });
    return s;
  }
  // 往上的香氣線:三條直立波浪線(中心在原點,高 150)
  function aromaSvg() {
    let s = '';
    [-70, 0, 70].forEach((dx, i) => { s += rope(`M ${dx} 75 q ${i % 2 ? -16 : 16} -18.75 0 -37.5` + ' t 0 -37.5'.repeat(3), 14, BLUE_W); });
    return s;
  }
  function slabSvg(fill, op) {
    const d = `M ${-TK.w / 2} ${-TK.h / 2} q 40.3 -14 80.6 0` + ' t 80.6 0'.repeat(15) + ` V ${TK.h / 2} H ${-TK.w / 2} Z`;
    return `<path d="${d}" fill="${fill}"${op ? ` fill-opacity="${op}"` : ''}/>`;
  }
  const dishPath = () => `<path d="M -380 -35 L 380 -35 Q 380 35 300 35 L -300 35 Q -380 35 -380 -35 Z" fill="hsl(200 14% 82%)"/>`;
  function domeSvg() {                             // 餐盤蓋:底邊在 y=+165,頂端 -165,握把在上
    return `<path d="M -260 165 C -260 -275 260 -275 260 165 Z" fill="hsl(200 20% 80%)" fill-opacity=".6"/>` +
      `<circle cx="0" cy="-189" r="26" fill="hsl(200 14% 62%)"/><polygon points="-190,40 -168,-60 -120,-120 -146,-30 -166,48" fill="${K.PAPER}" fill-opacity=".75" stroke="none"/>`;
  }
  const dashBox = (w, h, r, dashed) => `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" rx="${r}" fill="${dashed ? K.PAPER : K.YELLOW}"/>` +
    (dashed ? `<rect x="${f(-w / 2 + 10)}" y="${f(-h / 2 + 10)}" width="${f(w - 20)}" height="${f(h - 20)}" rx="${r - 6}" fill="none" stroke="${K.INK}" stroke-width="8" stroke-dasharray="26 18"/>` : '');

  // ---------- 鴿子 ----------
  function pigeonPose(k, evs) {
    for (const e of evs) {
      const n = K.P.CLIPS[e.clip].frames.length;
      if (k >= e.k0 && k < e.k0 + n) return Object.assign({}, K.expr(K.clip(e.clip, k - e.k0), e.expr), { flip: 1 });
    }
    return Object.assign({}, K.expr(K.clip('idle', k), 'look'), { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const p1 = at(L[4], 0.02), p2 = at(L[4], 0.38), p3 = at(L[4], 0.62);
    const E = { noReact: at(L[4], 0.2), react: p2 + 4, ex2: p3 + 2, eq: p3 + 5, dome: at(L[5], 0.5), sticker: at(L[6], 0.3), dashed: at(L[6], 0.6) };
    const evs = [{ k0: F[1] + 3, clip: 'tilt', expr: 'think' }, { k0: E.react + 3, clip: 'shock', expr: 'surprised' },
      { k0: at(L[5], 0.1), clip: 'nod', expr: 'look' }, { k0: at(L[6], 0.4), clip: 'shrug', expr: 'doubt' }];

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, evs), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // ===== A:61–63 =====
    s += layer(k, F[0], F[2], PL.x, PL.y, (ke) => sh(dishSvg(), PL.x, PL.y, ke - F[0], 'prop', 'dish'));
    s += layer(k, F[0] + 1, F[1], PL.x, PL.y, (ke) => sh(weedSvg(), PL.x, PL.y, ke - F[0] - 1, 'prop', 'weed'));
    s += layer(k, F[0] + 1, F[1], 1560, 260, (ke) => sh(Ch.plate('幾乎吃素', 100, { fill: K.YELLOW }).svg, 1560, 260, ke - F[0] - 1, 'tag', 'veg', { rot: -2, wide: true }));
    const kTag2 = at(L[0], 0.45);
    s += layer(k, kTag2, F[1], 1560, 420, (ke) => sh(Ch.plate('海草 海藻', 72, {}).svg, 1560, 420, ke - kTag2, 'tag', 'veg2', { rot: 2, wide: true }));
    s += layer(k, F[1], F[2], PL.x, PL.y, (ke) => sh(Ch.icon(ic(pal, 'fragments', { n: 8 }), 0, 0, 480), PL.x, PL.y, ke - F[1], 'prop', 'frags'));
    s += layer(k, F[1] + 2, F[2], 1620, 360, (ke) => tl('?', 1620, 360, 240, ke - F[1] - 2, 'q', { fill: K.INK, ink: K.YELLOW, rot: 6 }));

    const CA = { x: 1200, y: 455 };                // 句63 的中心
    s += layer(k, F[2], F[3], CA.x, CA.y, (ke) => {
      const kk = ke - F[2];
      let c = sh(`<rect x="-635" y="-330" width="1270" height="660" fill="hsl(195 70% 84%)" stroke-linejoin="miter"/>` +
        rope('M -600 -280 q 50 -22 100 0' + ' t 100 0'.repeat(11), 10, 'hsl(195 60% 74%)') + rope('M -600 280 q 50 -22 100 0' + ' t 100 0'.repeat(11), 10, 'hsl(195 60% 74%)'),
      CA.x, CA.y, kk, 'prop', 'water', { wide: true });
      const kBag = kk - 1, kJ = ke - at(L[2], 0.3), kEq = ke - at(L[2], 0.55);
      c += sh(Ch.icon(ic(pal, 'bag', {}), 0, 0, 440), 890, 410, kBag, 'prop', 'bag');
      c += sh(Ch.plate('塑膠袋', 80, {}).svg, 890, 705, kBag - 1, 'tag', 'bagL', { rot: -2, wide: true });
      c += sh(Ch.icon(ic(pal, 'jellyfish', {}), 0, 0, 440), 1510, 410, kJ, 'prop', 'jelly');
      c += sh(Ch.plate('水母', 80, {}).svg, 1510, 705, kJ - 1, 'tag', 'jellyL', { rot: 2, wide: true });
      return c + tl('=', 1200, 420, 170, kEq, 'eqA', { rot: -4 });
    });

    // ===== B:64–66 =====
    const CB = { x: 1190, y: 480 };
    s += layer(k, F[3], F[4], 850, 185, (ke) => sh(Ch.plate('2020 實驗', 100, { fill: K.YELLOW }).svg, 850, 185, ke - F[3], 'tag', 'exp', { rot: -2, wide: true }));
    s += layer(k, F[3], F[5], CB.x, CB.y, (ke) => {
      const kk = ke - F[3], hu = ke >= E.react ? 75 : 40;
      return sh(slabSvg('hsl(195 65% 78%)'), TK.x, TK.y, now(kk), 'prop', 'tank', { wide: true }) +
        sh(Ch.icon(ic(pal, 'turtle', { headUp: hu }), 0, 0, TT.box), TT.x, TT.y, kk, 'prop', 'turtle', { rot: TT.rot }) +
        sh(slabSvg('hsl(200 75% 52%)', 0.32), TK.x, TK.y, now(kk), 'prop', 'water', { wide: true });
    });
    const phase = (kIn, label, icn, col, id) => (ke) => {
      const kk = ke - kIn;
      let c = sh(Ch.plate(label, 64, {}).svg, 800, 150, kk, 'tag', 'lab' + id, { rot: -1.5, wide: true });
      c += sh(Ch.icon(icn, 0, 0, 220), ITEM.x, ITEM.y, kk, 'prop', 'item' + id);
      [1000, 1210, 1420].forEach((x, i) => { c += sh(waveSvg(col), x, 310, kk - 2 - i * 2, 'wave', 'w' + id + i, { wide: true }); });
      return c;
    };
    s += layer(k, p1, p2, CB.x, CB.y, phase(p1, '乾淨塑膠', bottleIc(pal, false), GREY_W, 'a'));
    s += layer(k, p2, p3, CB.x, CB.y, phase(p2, '泡過海水的塑膠', bottleIc(pal, true), BLUE_W, 'b'));
    s += layer(k, p3, F[5], CB.x, CB.y, phase(p3, '食物', weedIc(), GREEN_W, 'c'));
    s += layer(k, E.noReact, p2, 1640, 215, (ke) => sh(Ch.plate('沒反應', 64, { fill: K.YELLOW }).svg, 1640, 215, ke - E.noReact, 'tag', 'none', { rot: 2, wide: true }));
    s += layer(k, E.react, F[5], CB.x, CB.y, (ke) => tl('!', 1510, 190, 120, ke - E.react, 'ex1', { fill: K.INK, ink: K.YELLOW, rot: -5 }));
    s += layer(k, E.ex2, F[5], CB.x, CB.y, (ke) => tl('!', 1770, 190, 120, ke - E.ex2, 'ex2', { fill: K.INK, ink: K.YELLOW, rot: 5 }));
    s += layer(k, E.eq, F[5], CB.x, CB.y, (ke) => tl('=', 1640, 190, 120, ke - E.eq, 'eqB', { rot: -3 }));

    const CD = { x: 1100, y: 520 };
    s += layer(k, F[5], F[6], CD.x, CD.y, (ke) => {
      const kk = ke - F[5];
      let c = sh(dishPath(), 900, 785, kk, 'prop', 'dish2', { wide: true });
      c += sh(Ch.icon(bottleIc(pal, true), 0, 0, 300), 900, 600, kk, 'prop', 'bottle2');
      c += sh(aromaSvg(), 900, 285, kk - 1, 'wave', 'aroma', { wide: true });
      c += sh(Ch.plate('泡過海水的塑膠', 64, {}).svg, 1560, 450, kk - 2, 'tag', 'lab2', { rot: 2, wide: true });
      return c + sh(domeSvg(), 900, 585, ke - E.dome, 'prop', 'dome');
    });

    // ===== C:67 =====
    if (k >= F[6]) {
      const kk = k - F[6];
      s += sh(`<rect x="-380" y="-240" width="760" height="480" fill="${K.PAPER}" stroke-linejoin="miter"/><rect x="-380" y="-240" width="760" height="24" fill="${pal.main}" stroke="none"/>` +
        txt('2020 實驗', 0, -140, 110, K.INK) + Ch.icon(ic(pal, 'turtle', { headUp: 40 }), -120, 60, 330) + Ch.icon(bottleIc(pal, true), 190, 60, 190),
      900, 380, kk, 'card', 'expCard', { wide: false });
      s += sh(Ch.plate('規模不大 人工飼養', 56, { fill: K.YELLOW }).svg, 1220, 600, k - E.sticker, 'tag', 'small', { rot: 3, wide: true });
      s += layer(k, F[6] + 1, E.dashed, 1560, 330, (ke) => sh(dashBox(504, 117, 14, false) + txt('聞起來像食物', 0, 0, 72, K.INK), 1560, 330, ke - F[6] - 1, 'bar', 'bar1', { rot: -1, wide: true }));
      if (k >= E.dashed) s += sh(dashBox(480, 140, 20, true) + txt('有這個可能', 0, 0, 72, K.INK), 1560, 330, k - E.dashed, 'bar', 'bar2', { rot: -1, wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_smell', dur: 29.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
