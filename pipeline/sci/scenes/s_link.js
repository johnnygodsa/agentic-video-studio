/* snack 場景 s_link(句 70–73)夜市與巷口。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 全場:左夜市攤車(招牌「夜市」,x 105–495)、右自畫小店面(招牌「巷口」,x 1450–1790),同一高度(y 330–690)。
 * 句70:兩邊彈入;中間肉塊、瓦斯桶、「時薪」牌依詞「肉」「瓦斯」「時薪」的位置比例逐一彈入。
 * 句71:中間物件退場;三條直向長條(同基線 y 590)一起往上長高;長條頂端數值牌;「手牽手」處畫出頂端連線;「自算」牌與來源牌「主計總處」。
 * 句72:長條與小牌退場;兩邊各一張等高的價牌「? 元」;鴿子由左走到右(位置由格數計算),走到定位後站定。
 * 句73:攤車下方「攤位租金 ?」牌;「查不到」黃色便條(詞「查不到」處)蓋在「?」上;「這條」處鴿子左邊出現行李箱(轉場用);之後靜止。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [
    { start: 0.06, end: 5.4, text: '夜市和巷口的小吃店,用的是同一批肉、同一桶瓦斯,請人一樣要付時薪。' },
    { start: 5.52, end: 14, text: '官方那個其他家外食物漲 30.6%,旁邊的中式米食、中式麵食也都在三成上下,幾乎是手牽手一起上去的。' },
    { start: 14.12, end: 17.85, text: '你在夜市覺得貴,回到巷口吃碗麵,價錢也沒有比較客氣。' },
    { start: 17.97, end: 23, text: '夜市還多一筆攤位租金,不過各地收多少我查不到可靠的數字,這條就不亂講了。' }];
  const U = 1.43, PU = 1.36, SU = 1.15;                    // 紙片倍率、鴿子倍率(高約 309px)、攤車倍率
  const STALL = { x: 300, y: 510 }, SHOP = { x: 1620, y: 510, w: 340, h: 360 };
  const BASE = 590, PITCH = 290, CX = 972, BW = 200;          // 長條基線、欄距、中心 x、條寬
  const BARS = [{ label: ['其他家', '外食物'], value: 30.6, text: '30.6%', hi: true }, { label: ['中式', '麵食'], value: 30.1, text: '30.1%' },
    { label: ['中式', '米食'], value: 28.1, text: '28.1%' }];
  const GROW = [0.12, 0.3, 0.5, 0.7, 0.88, 1.05, 1];
  const WALK = { x0: 700, x1: 1100, y: 790 };                 // 鴿子腳底:起點、終點、地面
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const RN = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const T = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const exitS = (j) => (j < 0 ? 1 : j < 2 ? [1.15, 0.6][j] : 0);   // 退場:兩格縮小後消失

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  // 詞的起始字位置比例換算成格編號
  const frameAt = (l, w) => { const ix = l.text.indexOf(w); return K.frame(l.start + (ix < 0 ? 0 : ix) / l.text.length * (l.end - l.start)); };

  // 以 px 繪製的紙片(同 Charts.sheet,但縮放可自訂)
  function px(content, o) {
    const sx = o.sx == null ? 1 : o.sx, sy = o.sy == null ? 1 : o.sy;
    if (sx <= 0 || sy <= 0) return '';
    return K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
      { x: o.x, y: o.y, rot: o.rot, scale: U, sx, sy, k: o.kind, id: o.id, enter: o.enter, wide: true });
  }
  const popScale = (k) => K.pop(k);

  // 小店面(方形店面、遮陽棚、字牌「巷口」),中心在原點,寬 340、高 360
  function shop(pal) {
    let s = R(-160, -60, 320, 239, 'hsl(40 60% 90%)') + R(-130, 30, 110, 90, 'hsl(40 95% 76%)') + R(-130, 74, 110, 6, K.INK).replace('stroke-linejoin="miter"', 'stroke="none"') +
      R(34, 50, 90, 130, 'hsl(24 45% 38%)') + `<circle cx="104" cy="118" r="7" fill="${K.YELLOW}" stroke="none"/>`;
    const N = 6, bw = 340 / N, r = bw / 2;
    for (let i = 0; i < N; i++) {
      const x0 = -170 + i * bw, x1 = x0 + bw;
      s += `<path d="M ${f(x0)} -180 L ${f(x1)} -180 L ${f(x1)} -122 A ${f(r)} ${f(r)} 0 0 1 ${f(x0)} -122 Z" fill="${i % 2 ? 'hsl(40 60% 96%)' : pal.main}"/>`;
    }
    const sg = Ch.plate('巷口', 64, {});
    return s + `<g transform="translate(0 -40)">${sg.svg}</g>`;
  }

  // 長條下方標籤(兩行)
  function barLabel(lines2, hi) {
    const fs = 56, ps = lines2.map((l) => Ch.plate(l, fs, hi ? { fill: K.YELLOW } : {})), h = ps[0].h, gap = 6, y0 = -(h + gap) / 2;
    return ps.map((p, i) => `<g transform="translate(0 ${f(y0 + i * (h + gap))})">${p.svg}</g>`).join('');
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // ---- 左右店面:全場 ----
    {
      const q = k - F[0], p = popScale(q);
      s += K.paper(PS.LIST.stall.fn(pal, { sign: '夜市' }), { x: STALL.x, y: STALL.y, scale: SU, sx: p, sy: p, k: 'prop', id: 'stall', wide: PS.LIST.stall.wide, enter: q < 2 });
      s += px(shop(pal), { x: SHOP.x, y: SHOP.y, sx: p, sy: p, kind: 'prop', id: 'shop', enter: q < 2 });
    }

    // ---- 句70:中間三樣共用的東西 ----
    if (k < F[1] + 2) {
      const j = k - F[1], e = exitS(j);
      const kM = k - frameAt(L[0], '肉'), kG = k - frameAt(L[0], '瓦斯'), kW = k - frameAt(L[0], '時薪');
      if (e > 0) {
        const pm = popScale(kM) * e, pg = popScale(kG) * e, pw = popScale(kW) * e;
        if (pm > 0) s += K.paper(PS.LIST.meatChunk.fn(pal), { x: 780, y: 620, scale: 1.5, sx: pm, sy: pm, k: 'prop', id: 'meat', enter: kM < 2 });
        if (pg > 0) s += K.paper(PS.LIST.gasTank.fn(pal), { x: 1160, y: 600, scale: 1.55, sx: pg, sy: pg, k: 'prop', id: 'gas', enter: kG < 2 });
        if (pw > 0) s += px(Ch.plate('時薪', 100, { fill: K.YELLOW }).svg, { x: CX, y: 300, sx: pw, sy: pw, kind: 'label', id: 'wage', enter: kW < 2, rot: -2 });
      }
    }

    // ---- 句71:三條長條(句72 起兩格退場) ----
    if (k >= F[1] && k < F[2] + 2) {
      const q = k - F[1], e = exitS(k - F[2]), g = GROW[Math.min(q, GROW.length - 1)];
      BARS.forEach((b, i) => {
        const cx = CX + (i - 1) * PITCH, h = b.value * 10 * g;
        s += px(R(-BW / 2, -h, BW, h, pal.main), { x: cx, y: BASE, sx: e, sy: e, kind: 'bar', id: 'bar' + i, enter: q < GROW.length });
        s += px(barLabel(b.label, b.hi), { x: cx, y: BASE + 12 + 103 + 3, sx: popScale(q) * e, sy: popScale(q) * e, kind: 'barL', id: 'bl' + i, enter: q < 2 });
        const tg = Ch.plate(b.text, 72, Object.assign({ padX: 0.4 }, b.hi ? { fill: K.INK, ink: K.YELLOW } : {}));
        s += px(tg.svg, { x: cx, y: BASE - b.value * 10 * g - 22 - tg.h / 2, sx: popScale(q - 6) * e, sy: popScale(q - 6) * e, kind: 'barN', id: 'bn' + i, enter: q - 6 < 2 });
      });
      s += px(R(-400, -6, 800, 12, K.INK), { x: CX, y: BASE + 6, sx: popScale(q) * e, sy: e, kind: 'base', id: 'base', enter: q < 2 });
      // 頂端連線:「手牽手」處由左至右畫出
      const kl = k - frameAt(L[1], '手牽手');
      if (kl >= 0) {
        const tops = [[CX - PITCH - 100, BASE - 306], [CX - PITCH, BASE - 306], [CX, BASE - 301], [CX + PITCH, BASE - 281], [CX + PITCH + 100, BASE - 281]];
        const frac = Math.min(1, (kl + 1) / 5), xc = tops[0][0] + (tops[4][0] - tops[0][0]) * frac, pts = [];
        for (let i = 0; i < 5; i++) {
          if (tops[i][0] <= xc) pts.push(tops[i]);
          else { const a = tops[i - 1], b = tops[i], r = (xc - a[0]) / (b[0] - a[0]); pts.push([xc, a[1] + (b[1] - a[1]) * r]); break; }
        }
        const my = BASE - 293, str = pts.map((v) => `${f(v[0] - CX)},${f(v[1] - my)}`).join(' ');
        s += px(`<polyline points="${str}" fill="none" stroke="${K.PAPER}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>` +
          `<polyline points="${str}" fill="none" stroke="${K.INK}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>`,
        { x: CX, y: my, sx: e, sy: e, kind: 'link', id: 'link', enter: kl < 2 });
      }
      // 來源牌與自算牌
      const sp = Ch.plate('主計總處', 40, { chip: pal.main, padX: 0.8 }), cp = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
      s += px(sp.svg, { x: 1790 - sp.w / 2, y: 150, sx: popScale(q - 8) * e, sy: popScale(q - 8) * e, kind: 'src', id: 'src', enter: q - 8 < 2 });
      s += px(cp.svg, { x: 1790 - cp.w / 2, y: 245, sx: popScale(q - 10) * e, sy: popScale(q - 10) * e, kind: 'src', id: 'self', enter: q - 10 < 2 });
    }

    // ---- 句72 起:兩邊等高價牌、鴿子 ----
    if (k >= F[2]) {
      const q = k - F[2];
      s += Ch.priceFlip({ pal, x: STALL.x, y: 215, from: '?', unit: '元', fs: 100, k: q, id: 'pfL', u: U });
      s += Ch.priceFlip({ pal, x: SHOP.x, y: 215, from: '?', unit: '元', fs: 100, k: q, id: 'pfR', u: U });
      const n = Math.max(10, K.frame(L[2].end - L[2].start) - 5), arr = q >= n, wx = WALK.x0 + (WALK.x1 - WALK.x0) * Math.min(1, q / n);
      const base = arr ? K.clip('idle', k) : K.clip('walk', q);
      const pose = Object.assign({}, K.expr(base, arr ? 'doubt' : 'normal'), { flip: 1 });
      if (arr) s += K.ground({ x: WALK.x1 + 20, y: WALK.y + 4, w: 340, h: 22, u: U, pal });
      s += K.pigeon(pose, { x: wx, y: WALK.y, scale: PU, id: 'main', enter: q < 2 });
    }

    // ---- 句73:攤位租金牌、便條、行李箱 ----
    if (k >= F[3]) {
      const q = k - F[3], rp = Ch.plate('攤位租金 ?', 64, {});
      s += px(rp.svg, { x: STALL.x, y: 745, sx: popScale(q), sy: popScale(q), kind: 'label', id: 'rent', enter: q < 2 });
      const kn = k - frameAt(L[3], '查不到');
      if (kn >= 0) {
        const np = Ch.plate('查不到', 64, { fill: K.YELLOW, padX: 0.6 }), pn = popScale(kn);
        s += px(np.svg, { x: 528, y: 752, rot: -4, sx: pn, sy: pn, kind: 'note', id: 'note', enter: kn < 2 });
      }
      const ks = k - frameAt(L[3], '這條');
      if (ks >= 0) {
        const p = popScale(ks);
        s += K.paper(PS.LIST.suitcase.fn(pal), { x: 800, y: 670, scale: 1.2, sx: p, sy: p, k: 'prop', id: 'suitcase', enter: ks < 2 });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_link', dur: 23.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
