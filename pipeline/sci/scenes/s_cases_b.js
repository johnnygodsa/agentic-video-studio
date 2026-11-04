/* snack 場景 s_cases_b(句 46–51)單店案例二。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–5。
 * 句46:雞排圖 + 招牌字「派克雞排」;日曆牌「2023 年 4 月」(左欄);價牌 80 元,約 55% 處翻成 85 元;對話泡(空的)從店招冒出。
 * 句47:泡內兩條橫條:「33–35 元」短、「55 元」長(「後來」處長出);小牌「創辦人受訪」。
 * 句48:「+20」黃牌。
 * 句49:泡、條、小牌、+20 退場;鴿子(pigeon.js 無 sad 表情:用 doubt 眉型加低頭)從右走入,拍拍雞排。
 * 句50:雞排整組退場;五顆雞蛋糕一排、日曆牌「2025」、小牌「報導指出」、價牌「5 顆 50 元」、每顆上方小牌「10」。
 * 句51:日曆牌與「10」退場;50 元硬幣 = 五顆雞蛋糕(中間等號);小旗插在雞蛋糕上。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [
    { start: 0.075, end: 5.725, text: '派克雞排 2023 年 4 月從 80 元變 85 元,創辦人受訪的時候講了一個數字。' },
    { start: 5.845, end: 10.545, text: '他說以前一片雞排的成本是三十三到三十五元,後來直接跳到 55 元。' },
    { start: 10.665, end: 12.545, text: '成本一口氣多了二十塊。' },
    { start: 12.665, end: 14.385, text: '老實說,我看了有點同情他。' },
    { start: 14.505, end: 20.545, text: '還有雞蛋糕,2025 年有報導拍到夜市的原味雞蛋糕五顆賣 50 元,等於一顆 10 元。' },
    { start: 20.665, end: 26.14, text: '一個五十塊的銅板換五顆雞蛋糕,這大概是銅板美食剩下的最後幾個據點了。' }];
  const U = 1.43, PU = 1.36, CS = 1.9, ES = 1.6, COINS = 2.8;   // 紙片倍率、鴿子倍率(高約 305px)、雞排倍率(441×403)、雞蛋糕倍率、硬幣倍率
  const CUT = { x: 840, y: 500 }, SIGN = { x: 900, y: 170, fs: 80 };
  const LEFT = { x: 300 };                                        // 左欄(日曆牌、價牌、硬幣)中心 x
  const BUB = { x: 1470, y: 440, fs: 56, rows: 4, blank: 11 };    // 對話泡 1120–1820 × 269–611
  const BAR = { x0: 1166, h: 80, fs: 72, sc: 6.4, y1: 371, y2: 509, gap: 16 };
  const FOOT = { x: 1290, y: 815 }, WALK_N = 8, STEP = 36;
  const EGGX = [813, 1039, 1265, 1491, 1717], EGGY = 470, TAGY = 300;
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { text: l.text || d.text, start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  // 鴿子:pigeon.js 沒有 sad 表情 → doubt(眉尾下垂)+ 低頭;句49 走入,站定後翅膀朝雞排輕拍(兩格一拍)
  function pigeonPose(k, F49, kArr) {
    if (k < kArr) return { pose: Object.assign({}, K.expr(K.clip('walk', k - F49), 'doubt'), { headRot: -12, headDy: 3 }), dx: (kArr - k) * STEP, enter: true };
    const j = k - kArr;
    return { pose: Object.assign({}, K.expr(K.clip('idle', k), 'doubt'), { headRot: -16, headDy: 4, wlen: 1.5, wing: j % 4 < 2 ? 186 : 160 }), dx: 0, enter: false };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    // 詞級時間:詞在句中的起始字索引 ÷ 句長 × 句長秒數 + 句首,取整格
    const fw = (i, sub) => { const l = L[i], n = l.text.indexOf(sub); return K.frame(l.start + (n < 0 ? 0 : n / l.text.length) * (l.end - l.start)); };
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : k < F[5] ? 4 : 5;
    let s = '';

    if (ph <= 3) {                                                           // 句46–49:雞排組
      const q = k - F[0], p = K.pop(q);
      s += K.paper(PS.chickenCutlet(pal), { x: CUT.x, y: CUT.y, scale: CS, sx: p, sy: p, k: 'prop', id: 'cutlet', enter: q < 2 });
      const sg = Ch.plate('派克雞排', SIGN.fs, { chip: pal.main });
      s += Ch.sheet(sg.svg, { x: SIGN.x, y: SIGN.y, rot: -1.5, u: U, k: q - 2, kind: 'sign', id: 'sign', wide: true });
      s += Ch.dateTag({ x: LEFT.x, y: 260, top: '2023 年', main: '4 月', size: 240, rot: -2, u: U, k: k - fw(0, '2023'), id: 'date' });
      s += Ch.priceFlip({ pal, x: LEFT.x, y: 620, from: 80, to: 85, unit: '元', fs: 110, u: U, k: k - fw(0, '從 80'),
        kFlip: k - K.frame(L[0].start + 0.55 * (L[0].end - L[0].start)), id: 'price' });
    }
    if (ph <= 2) {                                                           // 句46–48:對話泡、成本條、+20
      const q = k - fw(0, '創辦人'), blank = '　'.repeat(BUB.blank);
      s += Ch.bubble(Array(BUB.rows).fill(blank), { x: BUB.x, y: BUB.y, fs: BUB.fs, tail: 'tl', u: U, k: q, id: 'bubble' });
      if (ph >= 1) {
        const mk = (y, value, text, hi, k0, id) => {
          const g = k0 < 0 ? 0 : [0.25, 0.5, 0.75, 1][Math.min(k0, 3)], len = value * BAR.sc * g, pl = Ch.plate(text, BAR.fs, { padX: 0.6, fill: hi ? K.INK : K.PAPER, ink: hi ? K.YELLOW : K.INK });
          const px = BAR.x0 + value * BAR.sc + BAR.gap + pl.w / 2;
          let r = '';
          if (len > 0) r += Ch.sheet(R(-len / 2, -BAR.h / 2, len, BAR.h, hi ? pal.main : `hsl(${pal.h} 8% 72%)`), { x: BAR.x0 + len / 2, y, u: U, kind: 'hbar', id: id + 'b', wide: true });
          return r + Ch.sheet(pl.svg, { x: px, y, u: U, k: k0 - 4, kind: 'hbarV', id: id + 'v', wide: true });
        };
        s += mk(BAR.y1, 34, '33–35 元', false, k - F[1], 'c1');
        s += mk(BAR.y2, 55, '55 元', true, k - fw(1, '後來'), 'c2');
        s += Ch.srcTag('創辦人受訪', { pal, x: 1830, y: 140, anchor: 'right', u: U, k: k - F[1], id: 'src1' });
      }
      if (ph >= 2) {
        const pl = Ch.plate('+20', 100, { fill: K.YELLOW, padX: 0.8 });
        s += Ch.sheet(pl.svg, { x: 1640, y: 722, rot: 3, u: U, k: k - F[2], kind: 'num', id: 'plus20', wide: true });
      }
    }
    if (ph === 3) {                                                          // 句49:鴿子 sad,拍拍雞排
      const kArr = F[3] + WALK_N, pg = pigeonPose(k, F[3], kArr);
      if (k >= kArr) s += K.ground({ x: FOOT.x, y: FOOT.y + 4, w: 380, h: 22, u: U, pal });
      s += K.pigeon(pg.pose, { x: FOOT.x + pg.dx, y: FOOT.y, scale: PU, id: 'main', enter: pg.enter });
    }
    if (ph >= 4) {                                                           // 句50–51:雞蛋糕組
      const q = k - F[4];
      EGGX.forEach((x, i) => {
        const kk = q - 2 * i, p = K.pop(kk);
        s += K.paper(PS.eggCake(), { x, y: EGGY, scale: ES, sx: p, sy: p, k: 'prop', id: 'egg' + i, enter: kk < 2 });
      });
      s += Ch.srcTag('報導指出', { pal, x: 1830, y: 135, anchor: 'right', u: U, k: k - fw(4, '有報導'), id: 'src2' });
      s += Ch.priceFlip({ pal, x: 1265, y: 700, from: '5 顆 50', unit: '元', fs: 100, u: U, k: k - fw(4, '五顆'), id: 'price2' });
      if (ph === 4) {
        s += Ch.dateTag({ x: LEFT.x, y: EGGY, top: '年份', main: '2025', size: 260, rot: 2, u: U, k: k - fw(4, '2025'), id: 'date2' });
        const fT = fw(4, '等於一顆');
        EGGX.forEach((x, i) => {
          s += Ch.sheet(Ch.plate('10', 72).svg, { x, y: TAGY, rot: i % 2 ? 2 : -2, u: U, k: k - fT - 2 * i, kind: 'num', id: 'tag' + i });
        });
      } else {
        const q5 = k - F[5], p = K.pop(q5), pe = K.pop(q5 - 4);
        s += K.paper(PS.coin50(), { x: LEFT.x, y: EGGY, scale: COINS, sx: p, sy: p, k: 'prop', id: 'coin', enter: q5 < 2 });
        s += K.tile('=', { x: 545, y: EGGY, size: 140, rot: -3, u: U, fill: K.YELLOW, sx: pe, sy: pe, id: 'eq', enter: q5 - 4 < 2 });
        const fF = fw(5, '這大概');
        EGGX.forEach((x, i) => {
          const pole = R(-4, -52, 8, 104, K.INK), pen = `<polygon points="4,-52 74,-30 4,-8" fill="${pal.main}"/>`;
          s += Ch.sheet(pole + pen, { x: x + 10, y: 345, rot: i % 2 ? 3 : -3, u: U, k: k - fF - 2 * i, kind: 'flag', id: 'flag' + i });
        });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_cases_b', dur: 26.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
