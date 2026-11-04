/* snack 場景 s_shrink(句 60–62)縮水式通膨。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–2。
 * 句60:左側價牌「? 元」(一直不動)句首彈入;右側雞排由大到小三格(倍率 1、0.8、0.62)逐格出現。鴿子站左下。
 * 句61:大字牌「縮水式通膨」+ 小字「shrinkflation」句首彈入;雞排三格縮到下方;「價錢沒動」小牌在「價錢沒動」一詞時間彈在價牌下。
 * 句62:價牌、小牌、字牌、雞排退場;名牌「Pippa Malmgren」+ 副牌「經濟學家」句首彈入;「一般認為」小牌在該詞時間彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [
    { start: 0.095, end: 2.41, text: '價錢之外還有一招,就是東西變小。' },
    { start: 2.53, end: 6.225, text: '這招有個專門的名字叫縮水式通膨,價錢沒動,份量少了。' },
    { start: 6.345, end: 10.88, text: '現在這個用法,一般認為是一位叫瑪格倫的經濟學家帶起來的。' }];
  const U = 1.43, PU = 1.36;                          // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const PRICE = { x: 262, y: 235, fs: 110 };          // 左側價牌(寬約 323、高約 187)
  const NOTE = { x: 262, y: 400 };                    // 「價錢沒動」小牌(底緣約 445,鴿頭頂約 503)
  const MULT = [1, 0.8, 0.62], CW = 232, CH = 212, CB = 104;   // 雞排倍率、單位寬高、袋底在單位 +104
  const BIG = { b: 2.0, x0: 520, gap: 90, bottom: 710 };       // 句60 的雞排排法
  const SMALL = { b: 1.3, cx: 1120, gap: 70, bottom: 805 };    // 句61 起縮到下方
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || d.text };
    });
  }
  // 詞在句中的時間估計(起始字索引 ÷ 句長 × 句長秒數 + start),回傳格編號
  const wordFrame = (l, word) => K.frame(l.start + Math.max(0, l.text.indexOf(word)) / l.text.length * (l.end - l.start));

  // 三格雞排的 {cx, cy, s}(以袋底對齊 bottom)
  function cutlets(o) {
    const ws = MULT.map((m) => CW * o.b * m), total = ws.reduce((a, b) => a + b, 0) + o.gap * 2;
    let x = o.cx != null ? o.cx - total / 2 : o.x0;
    return MULT.map((m, i) => { const s = o.b * m, r = { cx: x + ws[i] / 2, cy: o.bottom - CB * s, s }; x += ws[i] + o.gap; return r; });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : 2;
    let s = '';

    if (ph < 2) {
      // 左側價牌:全場(到句62 前)不動
      s += Ch.priceFlip({ pal, x: PRICE.x, y: PRICE.y, from: '?', unit: '元', fs: PRICE.fs, k: k - F[0], id: 'price' });
      // 雞排三格:句60 逐格(0、7、14 格)出現,句61 起縮到下方
      const cs = ph === 0 ? cutlets({ b: BIG.b, x0: BIG.x0, gap: BIG.gap, bottom: BIG.bottom }) : cutlets({ b: SMALL.b, cx: SMALL.cx, gap: SMALL.gap, bottom: SMALL.bottom });
      cs.forEach((c, i) => {
        const q = ph === 0 ? k - F[0] - i * 7 : k - F[1] + 2, p = K.pop(q);
        if (p <= 0) return;
        s += K.paper(PS.chickenCutlet(pal), { x: c.cx, y: c.cy, scale: c.s, sx: p, sy: p, k: 'prop', id: 'cut' + i, enter: q < 2 });
      });
    }
    if (ph === 1) {                                                           // 句61:字牌 + 小字 + 價錢沒動
      const q = k - F[1], big = Ch.plate('縮水式通膨', 160, { fill: K.YELLOW, padX: 0.8 }), sm = Ch.plate('shrinkflation', 60, { chip: pal.main, padX: 0.8 });
      s += Ch.sheet(big.svg, { x: 1120, y: 240, rot: -1.5, u: U, k: q, kind: 'card', id: 'big', wide: true });
      s += Ch.sheet(sm.svg, { x: 1120, y: 450, rot: 1, u: U, k: q, kind: 'card', id: 'sm', wide: true });
      const nq = k - wordFrame(L[1], '價錢沒動'), np = Ch.plate('價錢沒動', 56, { fill: K.YELLOW, padX: 0.8 });
      s += Ch.sheet(np.svg, { x: NOTE.x, y: NOTE.y, rot: -2, u: U, k: nq, kind: 'src', id: 'note', wide: true });
    } else if (ph === 2) {                                                    // 句62:名牌 + 副牌 + 一般認為
      const q = k - F[2], nm = Ch.plate('Pippa Malmgren', 124, { chip: pal.main, padX: 0.8 }), sub = Ch.plate('經濟學家', 110, { fill: pal.main, ink: pal.onMain, padX: 0.8 });
      s += Ch.sheet(nm.svg, { x: 1130, y: 280, rot: -1, u: U, k: q, kind: 'card', id: 'name', wide: true });
      s += Ch.sheet(sub.svg, { x: 1130, y: 510, rot: 1.2, u: U, k: q, kind: 'card', id: 'sub', wide: true });
      const gq = k - wordFrame(L[2], '一般認為'), gp = Ch.plate('一般認為', 72, { fill: K.YELLOW, padX: 0.8 });
      s += Ch.sheet(gp.svg, { x: 1130, y: 710, rot: -1.5, u: U, k: gq, kind: 'src', id: 'gen', wide: true });
    }

    // 鴿子:站左下,句61 起疑惑
    const base = K.clip('idle', k), pose = Object.assign({}, ph === 1 ? K.expr(base, 'doubt') : base, { flip: 1 });
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(pose, { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main', enter: false });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_shrink', dur: 10.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
