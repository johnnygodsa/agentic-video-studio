/* snack 場景 s_mind_b(句 110–111)小吃踩在這個點上。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–1。
 * 句110:左半雞排彈入、鴿子從右走入(站雞排右側,頭上之後連冒七個對話泡排成弧形);「八十五塊」處字牌「85 + 5」;
 *   「你會唸」處起每 3 格一個泡(貴/…);「一整個禮拜」處小牌「一整個禮拜」。
 *   右半:「三萬塊」處手機彈入;「多五百」處字牌「30,000 + 500」;「連看」處背對的小人彈入(表示沒看)。
 * 句111:左右兩組縮小退場;價牌「? 元」彈入;放大鏡(鏡片直徑約 490px)照在價牌上,鏡片裡一個很大的「1 元」。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const DEF = [
    { start: 0.01, end: 7.245, text: '小吃剛好踩在這個點上,八十五塊的雞排多五塊你會唸一整個禮拜,三萬塊的手機多五百你可能連看都沒看。' },
    { start: 7.365, end: 11.78, text: '東西越便宜,每一塊錢看起來就越大,小吃要漲價又不被罵幾乎辦不到。' }];
  const U = 1.43, PU = 1.36;                                       // 紙片倍率、鴿子倍率(高約 309px)
  const CUT = { x: 320, y: 500, s: 1.45 }, PL85 = { x: 320, y: 705, fs: 110 };   // 雞排與字牌「85 + 5」
  const FOOT = { x: 770, y: 815 }, WALK_N = 10, STEP = 30;         // 鴿子腳底落點、走入格數與每格步幅
  const BUB = { fs: 56, cx: 720, n: 7, pitch: 140, apex: 170, drop: 100 };   // 七個泡:x 300–1140,弧頂 y 170、兩端 y 270
  const BUBTXT = ['貴', '…', '貴', '貴', '…', '貴', '…'];
  const TAG1 = { x: 1010, y: 420, fs: 64 };                        // 小牌「一整個禮拜」
  const PHONE = { x: 1370, y: 400, s: 2.0 }, PL30 = { x: 1405, y: 705, fs: 110 }, PERSON = { x: 1670, y: 400, s: 1.7 };
  const MAG = { x: 1050, y: 445, s: 3.5 }, TAG2 = { x: 800, y: 640, fs: 150 }, BIG = { fs: 160 };   // 放大鏡原點、價牌、鏡片內大字
  const LENS = { x: MAG.x - 26 * MAG.s, y: MAG.y - 26 * MAG.s };   // 鏡片中心(放大鏡單位 (-26,-26))
  const f = (x) => +(+x).toFixed(2);
  const T = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { text: l.text || d.text, start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
  const shr = (str, x, y, k, k0) => {
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    // 詞級時間:詞在句中的起始字索引 ÷ 句長 × 句長秒數 + 句首,取整格
    const fw = (i, sub) => { const l = L[i], n = l.text.indexOf(sub); return K.frame(l.start + (n < 0 ? 0 : n / l.text.length) * (l.end - l.start)); };
    let s = '';

    if (k < F[1] + 2) {                                                      // 句110:左右兩組(句111 起 2 格縮小退場)
      const q = k - F[0], p = K.pop(q);
      const kB = fw(0, '你會唸'), kArr = F[0] + WALK_N;
      let left = '', right = '';
      // 左:雞排 + 字牌 + 泡弧 + 小牌 + 鴿子
      left += K.paper(PS.chickenCutlet(pal), { x: CUT.x, y: CUT.y, scale: CUT.s, sx: p, sy: p, k: 'prop', id: 'cutlet', enter: q < 2 });
      const p85 = Ch.plate('85 + 5', PL85.fs, { fill: K.YELLOW, padX: 0.7 });
      left += Ch.sheet(p85.svg, { x: PL85.x, y: PL85.y, rot: -2, u: U, k: k - fw(0, '八十五'), kind: 'num', id: 'p85', wide: true });
      for (let i = 0; i < BUB.n; i++) {
        const c = (i - (BUB.n - 1) / 2) / ((BUB.n - 1) / 2);
        left += Ch.bubble(BUBTXT[i], { x: BUB.cx + (i - (BUB.n - 1) / 2) * BUB.pitch, y: BUB.apex + BUB.drop * c * c, fs: BUB.fs, tail: null, rot: i % 2 ? 2 : -2,
          u: U, k: k - (kB + 3 * i), id: 'bub' + i });
      }
      const tg = Ch.plate('一整個禮拜', TAG1.fs, { fill: K.PAPER, padX: 0.8 });
      left += Ch.sheet(tg.svg, { x: TAG1.x, y: TAG1.y, rot: 1.5, u: U, k: k - fw(0, '一整個禮拜'), kind: 'src', id: 'week', wide: true });
      let pose, dx = 0, enter = false;
      if (k < kArr) { pose = K.clip('walk', k - F[0]); dx = (kArr - k) * STEP; enter = true; }
      else {
        pose = K.clip('idle', k);
        if (k >= kB) pose = K.expr(pose, 'doubt');
      }
      if (k >= kArr) left += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
      left += K.pigeon(Object.assign({}, pose, { flip: 0 }), { x: FOOT.x + dx, y: FOOT.y, scale: PU, id: 'main', enter });
      // 右:手機 + 字牌 + 背對的小人
      const kPh = fw(0, '三萬塊'), pPh = K.pop(k - kPh);
      right += K.paper(PT.LIST.phone.fn(pal, {}), { x: PHONE.x, y: PHONE.y, scale: PHONE.s, sx: pPh, sy: pPh, k: 'prop', id: 'phone', enter: k - kPh < 2 });
      const p30 = Ch.plate('30,000 + 500', PL30.fs, { fill: K.YELLOW, padX: 0.7 });
      right += Ch.sheet(p30.svg, { x: PL30.x, y: PL30.y, rot: 1.5, u: U, k: k - fw(0, '多五百'), kind: 'num', id: 'p30', wide: true });
      const kPe = fw(0, '連看'), pPe = K.pop(k - kPe);
      const back = PS.person(pal, {}) + '<circle cx="0" cy="-66" r="29" fill="hsl(24 30% 20%)"/>';   // 髮色蓋住整個頭 = 背對
      right += K.paper(back, { x: PERSON.x, y: PERSON.y, scale: PERSON.s, sx: pPe, sy: pPe, k: 'prop', id: 'person', enter: k - kPe < 2 });
      s += shr(left, 640, 450, k, F[1]) + shr(right, 1400, 450, k, F[1]);
    } else {                                                                 // 句111:價牌「? 元」+ 放大鏡
      const kT = F[1] + 2, kM = F[1] + 4, kO = F[1] + 7;
      s += Ch.priceFlip({ pal, x: TAG2.x, y: TAG2.y, from: '?', unit: '元', fs: TAG2.fs, rot: -2, u: U, k: k - kT, id: 'pf' });
      const pm = k < kM ? 0 : (k - kM < 2 ? [0.6, 0.9][k - kM] : 1);
      if (pm > 0) s += K.paper(PS.magnifier(), { x: MAG.x, y: MAG.y, scale: MAG.s, sx: pm, sy: pm, k: 'prop', id: 'mag', wide: true, enter: k - kM < 2 });
      const po = K.pop(k - kO);
      if (po > 0) s += K.paper(T('1 元', 0, 0, BIG.fs, K.INK), { x: LENS.x, y: LENS.y, sx: po, sy: po, k: 'num', id: 'one', wide: true, enter: k - kO < 2 });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_mind_b', dur: 11.8, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
