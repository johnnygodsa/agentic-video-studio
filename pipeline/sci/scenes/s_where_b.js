/* snack 場景 s_where_b(句 79–82)四年累計。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 句79:標題牌「四年累計」;hbars(x 430–、max 12)四條依詞位置逐條出現:臺北 10.6、新北 10.0、高雄 9.9、臺中 9.8(四城固定色);「自算」黃牌句首後第 8 格(之後保留)。
 * 句80:第五條全國 9.6(灰)句首出現;「差不到」詞位置出現右側大括號加兩張黃牌「差不到 / 1 個百分點」。
 * 句81:鴿子走進左側(x 90–400)、bored(半閉眼、頭微垂)。
 * 句82:鴿子蹲跳起 → 行李箱從上方放下落地(壓扁回彈)→ 鴿子落在箱頂坐著(位置逐格由行李箱頂算出)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [
    { start: 0.055, end: 5.47, text: '臺北四年漲了 10.6%,新北是 10%,高雄 9.9%,臺中 9.8% 左右。' },
    { start: 5.59, end: 9.945, text: '全國平均是 9.6% 左右,最高跟最低差不到一個百分點。' },
    { start: 10.065, end: 11.33, text: '這個結果有點無聊。' },
    { start: 11.45, end: 14.46, text: '我本來還期待會冒出一個特別便宜的城市呢。' }];
  const U = 1.43, PU = 1.36, SU = 1.15;                // 紙片倍率、鴿子倍率(高約 309px)、行李箱倍率
  const FOOT = { x: 245, y: 820 }, WALK_N = 10, STEP = 30, SET_H = 120;
  // 四個城市固定色(之後場景沿用)
  const CITY = { 臺北: 'hsl(205 70% 52%)', 新北: 'hsl(130 45% 45%)', 臺中: 'hsl(25 90% 58%)', 高雄: 'hsl(280 50% 55%)' };
  const BARS = { x: 430, y: 232, w: 940, rowH: 104, gap: 12, labelW: 210, fs: 64, numFs: 72, max: 12, gx: 18 };
  const ROWS = 5, SPAN = ROWS * BARS.rowH + (ROWS - 1) * BARS.gap;     // 568:y 232–800
  const PY = [0, -170, -360, -300, -240];                              // 句82 鴿子起跳弧(q 0–4,腳底相對地面的位移)
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  // 詞的起始字索引 ÷ 句長 × 句長秒數 + start → 第幾格
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  // 右側大括號(中心在原點,高 SPAN - 40:彈入過衝 1.15 倍時底緣不進字幕帶)
  function brace() {
    const h = SPAN / 2 - 20;
    return `<path d="M -22 ${-h} C 0 ${-h} 0 ${-h + 14} 0 ${-h + 36} L 0 -40 C 0 -10 14 0 26 0 C 14 0 0 10 0 40 L 0 ${h - 36} C 0 ${h - 14} 0 ${h} -22 ${h}"` +
      ` fill="none" stroke="${K.INK}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>`;
  }

  // bored:半閉眼(眨眼格保留)、眼珠下沉、頭微垂
  const bored = (p) => Object.assign({}, p, { lid: Math.max(0.8, p.lid || 0), lidTilt: 0, pdx: -3, pdy: 6,
    headDy: (p.headDy || 0) + 4, headRot: (p.headRot || 0) - 4, flip: 1 });

  // 行李箱:q 為落下後第幾格;回傳 {x,y,sx,sy,enter,top(箱身頂)};k<0 回傳 null。底邊(腳)固定在落點。
  function suitcase(kS) {
    const d = K.drop(kS);
    if (!d) return null;
    const bottom = FOOT.y + d.dy * SET_H, cy = bottom - 94 * SU * d.sy;
    return { x: FOOT.x, y: cy, sx: d.sx, sy: d.sy, enter: !!d.enter, top: cy - 70 * SU * d.sy };
  }

  // 鴿子:句81 走進 + bored 站;句82 q0 蹲、q1–4 跳起讓位、q5 起落在箱頂(q6 起壓低坐著)
  function pigeonState(k, F2, F3) {
    const kArr = F2 + WALK_N;
    if (k < kArr) return { pose: bored(K.clip('walk', k - F2)), dx: (kArr - k) * STEP, y: FOOT.y, enter: true };
    if (k < F3) return { pose: bored(K.clip('idle', k)), dx: 0, y: FOOT.y, enter: false };
    const q = k - F3;
    if (q < 5) {
      const hp = K.clip('hop', [1, 2, 3, 3, 4][q]);
      return { pose: bored(hp), dx: 0, y: FOOT.y + PY[q], enter: true };
    }
    const sc = suitcase(q - 2), base = bored(K.clip('idle', k));
    return { pose: q >= 6 ? Object.assign(base, { squash: 0.92 }) : base, dx: 0, y: sc.top, enter: false };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // 標題牌與長條圖(全場保留)
    const tp = Ch.plate('四年累計', 72, { fill: K.YELLOW, padX: 1 });
    s += Ch.sheet(tp.svg, { x: BARS.x + tp.w / 2, y: 146, rot: -1, u: U, k: k - F[0], kind: 'sheet', id: 'title', wide: true });
    const kb = ['臺北', '新北', '高雄', '臺中'].map((n) => wordK(L[0], n));
    const bars = [
      { label: '臺北', value: 10.6, text: '10.6%', color: CITY.臺北, k: k - kb[0] },
      { label: '新北', value: 10.0, text: '10.0%', color: CITY.新北, k: k - kb[1] },
      { label: '高雄', value: 9.9, text: '9.9%', color: CITY.高雄, k: k - kb[2] },
      { label: '臺中', value: 9.8, text: '9.8%', color: CITY.臺中, k: k - kb[3] },
      { label: '全國', value: 9.6, text: '9.6%', grey: true, k: k - F[1] }];
    s += Ch.hbars({ pal, x: BARS.x, y: BARS.y, w: BARS.w, rowH: BARS.rowH, gap: BARS.gap, labelW: BARS.labelW, gapX: BARS.gx,
      fs: BARS.fs, numFs: BARS.numFs, max: BARS.max, id: 'cpi', bars });
    if (k >= F[0] + 8) {                                                       // 自算小牌
      const p = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
      s += Ch.sheet(p.svg, { x: 1740, y: 780, u: U, k: k - F[0] - 8, kind: 'src', id: 'self', wide: true });
    }

    // 句80:大括號 + 字牌(「差不到」詞位置)。括號置於最長那條的數值牌右側
    const kBr = wordK(L[1], '差不到');
    if (k >= kBr) {
      const vw = Ch.tw('10.6%', BARS.numFs) + BARS.numFs * 0.7, barMax = BARS.w - BARS.labelW - vw - 2 * BARS.gx;
      const endX = BARS.x + BARS.labelW + BARS.gx + barMax * 10.6 / BARS.max + BARS.gx + vw, bx = endX + 54, cy = BARS.y + SPAN / 2;
      s += Ch.sheet(brace(), { x: bx, y: cy, u: U, k: k - kBr, kind: 'brace', id: 'brace', wide: true });
      const p1 = Ch.plate('差不到', 64, { fill: K.YELLOW, padX: 0.7 }), p2 = Ch.plate('1 個百分點', 64, { fill: K.YELLOW, padX: 0.7 });
      const tx = bx + 30 + 22 + Math.max(p1.w, p2.w) / 2;
      s += Ch.sheet(p1.svg, { x: tx, y: cy - 56, u: U, k: k - kBr, kind: 'sheet', id: 'gap1', wide: true });
      s += Ch.sheet(p2.svg, { x: tx, y: cy + 56, u: U, k: k - kBr, kind: 'sheet', id: 'gap2', wide: true });
    }

    // 句81 起:鴿子(句82 加行李箱)
    if (k >= F[2]) {
      const pg = pigeonState(k, F[2], F[3]), kArr = F[2] + WALK_N;
      if (k >= kArr) s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
      if (k >= F[3] + 2) {
        const sc = suitcase(k - F[3] - 2);
        s += K.paper(PS.suitcase(pal), { x: sc.x, y: sc.y, scale: SU, sx: sc.sx, sy: sc.sy, k: 'prop', id: 'suit', enter: sc.enter });
      }
      s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: pg.y, scale: PU, id: 'main', enter: pg.enter });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_where_b', dur: 14.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
