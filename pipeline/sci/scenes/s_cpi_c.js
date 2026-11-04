/* snack 場景 s_cpi_c(句 33–36)冠軍。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 全程:右下「主計總處」來源牌與「自算」黃牌(句33 起)。
 * 句33:最上面一條大長條衝出:中式早點 36.4%(黃底),左側皇冠。
 * 句34:蛋餅、豆漿、飯糰逐一彈入(只當圖,不標數字);鴿子舉起早餐袋(左下)。
 * 句35:早餐圖與袋子退場;第二條大長條火鍋 34.7%;火鍋圖彈入;「銅板美食」牌(句中)再蓋上紅叉。
 * 句36:上半全部與鴿子 2 格縮小退場;完整十條排行(x 430–1840、max 40、y 100–807)由上而下每 3 格一條;
 *       中式米食、其他家外食物右側小牌「討論榜 1 名」「討論榜 3 名」;句中(「多五塊」處)小人拿著「+5」出現在中式早點那條左前方,
 *       停 5 格後 4 格往右跑出畫面(逐格位置見 RUN);之後排行靜止到結束。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.03, end: 3.75 }, { start: 3.87, end: 5.93 }, { start: 6.05, end: 10.79 }, { start: 10.91, end: 18.725 }];
  const U = 1.43, PU = 1.36;                                   // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const SH = [146, 176], WT = [76, 30];                        // 翅膀肩與翅尖(鴿子單位座標)
  const LOW = [[120, 1.2], [50, 1.05]];
  const RED = 'hsl(4 78% 48%)';
  const BIG = { x0: 430, labelW: 380, rowH: 110, fs: 76, numFs: 100, barMax: 650, cy1: 155, cy2: 277 };   // 句33–35 的兩條大長條(y 100–332)
  const FIN = { x0: 430, labelW: 390, rowH: 65, fs: 56, numFs: 56, barMax: 545, y0: 100, pitch: 71 };    // 十條排行(y 97–807)
  const RANK = [['中式早點', 36.4], ['火鍋', 34.7], ['西式早點', 31.0], ['其他家外食物', 30.6], ['中式麵食', 30.1], ['中式米食', 28.1],
    ['中式以外料理', 25.3], ['西式速食', 23.7], ['中式餐廳料理', 20.1], ['咖啡飲料', 19.3]];
  const DTAG = { 3: '討論榜 3 名', 5: '討論榜 1 名' };                                                   // 其他家外食物(雞排)、中式米食(滷肉飯)
  const PX = { x: 170, y: 215, s: 1.1 }, PL = { x: 318, y: 150, fs: 72 };                              // 小人與「+5」牌
  const RUN = [200, 620, 1150, 2100];                                                                  // 起跑後第 1–4 格的向右位移(第 4 格已在畫面外)
  const ROW_STEP = 3, HOLD_N = 5;
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const T = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="${anchor || 'middle'}"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  // 一條橫向長條(標籤牌、長條、數值牌三片紙;與 hbars 同款,但數值牌與標籤牌同高,字才放得下)。回傳紙片字串
  function row(pal, g, o) {
    const gx = 18, lead = g.fs * 0.4, text = o.text, vw = Ch.tw(text, g.numFs) + g.numFs * 0.7, bh = g.rowH * 0.8;
    if (Ch.tw(o.label, g.fs) + lead + g.fs * 0.2 > g.labelW) throw new Error('s_cpi_c 標籤字溢出:' + o.label);
    const len = Math.max(12, g.barMax * o.value / 40), bx = g.x0 + g.labelW + gx, id = o.id;
    let s = Ch.sheet(R(-g.labelW / 2, -g.rowH / 2, g.labelW, g.rowH, o.hi ? K.YELLOW : K.PAPER) + T(o.label, -g.labelW / 2 + lead, 0, g.fs, K.INK, 'start'),
      { x: g.x0 + g.labelW / 2, y: o.cy, u: U, k: o.k, kind: 'hbarL', id: id + 'L', wide: true });
    s += Ch.sheet(R(-len / 2, -bh / 2, len, bh, pal.main), { x: bx + len / 2, y: o.cy, u: U, k: o.k, kind: 'hbar', id: id + 'B', wide: len / bh > 3 });
    s += Ch.sheet(R(-vw / 2, -g.rowH / 2, vw, g.rowH, o.hi ? K.INK : K.PAPER) + T(text, 0, 0, g.numFs, o.hi ? K.YELLOW : K.INK),
      { x: bx + len + gx + vw / 2, y: o.cy, u: U, k: o.k, kind: 'hbarV', id: id + 'V', wide: true });
    return { s, end: bx + len + gx + vw };
  }

  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  function tip(w) {                                            // 翅尖的畫面座標
    const a = w[0] * Math.PI / 180, vx = WT[0] * w[1], vy = WT[1];
    const px = SH[0] + vx * Math.cos(a) - vy * Math.sin(a), py = SH[1] + vx * Math.sin(a) + vy * Math.cos(a);
    return { x: FOOT.x + PU * (300 - px - 132), y: FOOT.y - 280 * PU + PU * py };
  }

  // 紅叉(單片:加號旋轉 45 度)
  function cross() {
    const a = 12, L = 62;
    const p = [[-a, -L], [a, -L], [a, -a], [L, -a], [L, a], [a, a], [a, L], [-a, L], [-a, a], [-L, a], [-L, -a], [-a, -a]];
    return `<g transform="rotate(45)"><polygon points="${p.map((v) => v.join(',')).join(' ')}" fill="${RED}" stroke-linejoin="miter"/></g>`;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), at = (i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
    const kPl = Math.max(at(2, 0.78), F[2] + 6), kX = Math.max(at(2, 0.9), kPl + 3);       // 「銅板美食」牌、紅叉
    const kRows = F[3] + 2;                                                              // 排行第一條出現的格
    const kP = Math.max(at(3, 0.61), kRows + ROW_STEP * 9 + 6 + 2);                         // 小人出現(「多五塊」處;不早於排行全部出現)
    const kR = kP + HOLD_N + 2;                                                          // 起跑
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    const popAt = (kk) => K.pop(kk);
    let s = '';

    if (k < F[3] + 2) {                                                                  // 句33–35 的上半部,句36 開頭 2 格縮小退場
      let g = '';
      const q0 = k - F[0];
      const r1 = row(pal, BIG, { id: 'b0', label: '中式早點', value: 36.4, text: '36.4%', hi: true, cy: BIG.cy1, k: q0 });
      g += r1.s;
      if (q0 >= 3) { const p = popAt(q0 - 3); g += prop('crown', {}, { x: 275, y: BIG.cy1, scale: 0.8, sx: p, sy: p, id: 'crown', enter: q0 - 3 < 2 }); }
      if (k >= F[1] && k < F[2] + 2) {                                                    // 句34:三樣早餐(句35 起 2 格縮小退場)
        let it = '';
        [['eggPancake', 790, F[1]], ['soyMilk', 1160, F[1] + 5], ['riceBall', 1500, F[1] + 10]].forEach((c) => {
          const kk = k - c[2];
          if (kk < 0) return;
          const p = popAt(kk);
          it += shr(prop(c[0], {}, { x: c[1], y: 450, scale: 1.45, sx: p, sy: p, id: c[0], enter: kk < 2 }), c[1], 450, k, F[2]);
        });
        g += it;
      }
      if (k >= F[2]) {                                                                    // 句35:火鍋條、火鍋圖、銅板美食加紅叉
        const q2 = k - F[2];
        g += row(pal, BIG, { id: 'b1', label: '火鍋', value: 34.7, text: '34.7%', cy: BIG.cy2, k: q2 }).s;
        const p = popAt(q2);
        g += prop('hotpot', {}, { x: 820, y: 530, scale: 1.9, sx: p, sy: p, id: 'hotpot', enter: q2 < 2 });
        if (k >= kPl) {
          const pl = Ch.plate('銅板美食', 72, {});
          g += Ch.sheet(pl.svg, { x: 1400, y: 530, rot: -2, u: U, k: k - kPl, kind: 'coinlab', id: 'coinlab' });
          if (k >= kX) g += Ch.sheet(cross(), { x: 1400 + pl.w / 2, y: 530, u: U, k: k - kX, kind: 'xmark', id: 'xmark' });
        }
      }
      // 鴿子與早餐袋(句34 舉袋、句35 放下)
      const idle = (e) => K.expr(K.clip('idle', k), e || 'normal'), wp = (w, e) => Object.assign({}, idle(e), { wing: w[0], wlen: w[1] });
      let pose = idle(), hold = null;
      if (k >= F[1] && k < F[2]) {
        const j = k - F[1], w = j === 0 ? [60, 1.1] : j === 1 ? [125, 1.25] : [170, 1.4];
        pose = wp(w, 'normal');
        if (j >= 2) hold = w;
      } else if (k >= F[2] && k < F[2] + 2) pose = wp(LOW[k - F[2]], 'normal');
      else if (k >= kPl) pose = idle('smug');
      pose = Object.assign({}, pose, { flip: 1 });
      g += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
      g += K.pigeon(pose, { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
      if (hold) { const tp = tip(hold); g += prop('breakfastBag', {}, { x: tp.x, y: tp.y + 73, scale: 0.8, id: 'bag' }); }
      s += shr(g, 960, 450, k, F[3]);
    }

    if (k >= kRows) {                                                                    // 句36:完整十條排行
      RANK.forEach((r, i) => {
        const cy = FIN.y0 + i * FIN.pitch + FIN.rowH / 2, kk = k - kRows - ROW_STEP * i;
        const rw = row(pal, FIN, { id: 'f' + i, label: r[0], value: r[1], text: r[1].toFixed(1) + '%', hi: i === 0, cy, k: kk });
        s += rw.s;
        if (DTAG[i]) {
          const pl = Ch.plate(DTAG[i], 40, { chip: pal.main });
          s += Ch.sheet(pl.svg, { x: rw.end + 14 + pl.w / 2, y: cy, u: U, k: kk - 3, kind: 'dtag', id: 'dt' + i, wide: true });
        }
      });
      if (k >= kP && k < kR + 4) {                                                       // 小人拿著「+5」,起跑後 4 格內跑出畫面
        const kk = k - kP, run = k >= kR ? RUN[k - kR] : 0, p = popAt(kk), pp = popAt(kk - 2);
        const rot = k >= kR ? 8 : 0;
        if (p > 0) s += K.paper(PS.LIST.person.fn(pal, {}), { x: PX.x + run, y: PX.y, rot, scale: PX.s, sx: p, sy: p, k: 'prop', id: 'person', enter: true });
        if (pp > 0) {
          const pl = Ch.plate('+5', PL.fs, { fill: K.YELLOW, padX: 0.8 });
          s += K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${pl.svg}</g>`,
            { x: PL.x + run, y: PL.y, rot: k >= kR ? 3 : -5, scale: U, sx: pp, sy: pp, k: 'plus', id: 'p5', enter: true, wide: true });
        }
      }
    }

    // 來源牌與「自算」小牌(全場保留,右下)
    s += Ch.srcTag('主計總處', { pal, x: 1830, y: 690, anchor: 'right', k: k - F[0], id: 'src' });
    const sp = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
    s += Ch.sheet(sp.svg, { x: 1740, y: 785, u: U, k: k - F[0] - 4, kind: 'src', id: 'self', wide: true });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_cpi_c', dur: 20.3, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
