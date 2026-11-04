/* snack 場景 s_boba(句37–40)珍奶之爭;「?」記號。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 開頭:「?」記號從右上角彈入(句40 結尾前 5 格退場)。
 * 句37:大珍奶杯(高約 450px)置中彈入;左右店招牌「翰林茶館」「春水堂」從外側 6 格擠向中間,到位時杯子被擠扁兩格。
 * 句38:左牌「1986」在「1986」詞位出現、右牌「1988」加「(常見說法)」在「1988」詞位出現;「告上法院」詞位法槌從上方落在杯子上方(壓扁回彈)。
 * 句39:上一句全部退場;日曆牌「2019」(「2019」詞位)加「報導指出」小牌;天平(tilt 0,兩邊一樣高)在「結果」詞位、牌「沒有人贏」在「沒有人贏」詞位。
 * 句40:上一句退場;價牌「? 元」不動;三杯小珍奶由左側出餐位一杯一杯往右滑到檯面上(逐格位置由時間算出);「?」記號在句尾前 5 格退場。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [
    { start: 0.045, end: 3.63, text: '講到手搖飲,珍珠奶茶是誰發明的,台灣自己吵了很久。' },
    { start: 3.75, end: 10.935, text: '台南的翰林茶館說是 1986 年,台中的春水堂比較常見的說法是 1988 年,兩家還真的告上法院。' },
    { start: 11.055, end: 13.98, text: '判決在 2019 年出來,結果是沒有人贏。' },
    { start: 14.1, end: 17.06, text: '官司打完,珍奶照樣賣,也沒有哪一杯變便宜。' }];
  const U = 1.43, CUP = { x: 960, y: 540, u: 1.9 }, GAVEL = { x: 960, y: 200, u: 1.0, fall: 160 };
  const SIGN = { y: 400, fs: 80, yearFs: 120, noteFs: 56, gapY: 24, xl0: 340, xl1: 520, xr0: 1580, xr1: 1400, moveN: 6 };
  const BAL = { x: 960, y: 400, u: 1.9 }, DATE = { x: 330, y: 400, size: 300 }, WIN = { x: 960, y: 715, fs: 110 }, SRC = { x: 1830, y: 780 };
  const PRICE = { x: 960, y: 300, fs: 150 };
  const CUPS = { y: 625, u: 1.3, x0: 330, step: 80, slots: [1360, 1060, 760], starts: [0, 7, 14] };   // 遞出順序:先送最遠的,杯子不互相穿過
  const BAR = { x: 1060, y: 798, w: 1500, h: 36 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: typeof l.text === 'string' && l.text ? l.text : d.text };
    });
  }
  // 詞級時間:詞的起始字索引 ÷ 句長 × 句長秒數 + start,對齊 0.1 秒,回傳格編號
  function wordF(l, word) {
    const i = l.text.indexOf(word), r = i < 0 ? 0 : i / l.text.length;
    return K.frame(Math.round((l.start + r * (l.end - l.start)) * 10) / 10);
  }
  const ex = (e) => (e < 0 ? 1 : [1.15, 0.6][e] || 0);                       // 退場兩格:放大一下再縮小,第三格起消失

  // 自己包的彈入紙片(可乘退場倍率):content 為 px 繪製(同 Ch.sheet)
  function pp(content, o) {
    const u = o.u || U, e = o.ex == null ? 1 : o.ex, p = K.pop(o.q) * e;
    if (p <= 0) return '';
    return K.paper(`<g transform="scale(${(1 / u).toFixed(5)})" stroke-width="${f(4 * u)}">${content}</g>`,
      { x: o.x, y: o.y, rot: o.rot, scale: u, sx: p * (o.sx || 1), sy: p * (o.sy || 1), k: o.kind || 'sheet', id: o.id, enter: o.q < 2 || e !== 1, wide: true });
  }
  // 把整串紙片字串以中心縮放(給 Ch 元件做退場用)
  const shrink = (str, cx, cy, s) => (s === 1 ? str : s <= 0 ? '' : `<g transform="translate(${f(cx)} ${f(cy)}) scale(${s}) translate(${f(-cx)} ${f(-cy)})">${str}</g>`);

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kExit = K.frame(L[3].end) - 5;
    let s = '';

    // ---- 句37–38:大珍奶杯、兩塊店招、法槌 ----
    const e0 = k - F[2];
    if (e0 < 2) {
      const e = ex(e0), q = k - F[0], mv = Math.min(Math.max(q, 0), SIGN.moveN) / SIGN.moveN;
      const lx = Math.round(SIGN.xl0 + (SIGN.xl1 - SIGN.xl0) * mv), rx = Math.round(SIGN.xr0 + (SIGN.xr1 - SIGN.xr0) * mv);
      const sq = (q >= SIGN.moveN && q < SIGN.moveN + 2) ? 0.92 : 1;           // 被兩邊擠到的瞬間
      // 店招名牌
      const nm = [['翰林茶館', lx, 'nl'], ['春水堂', rx, 'nr']];
      nm.forEach((n) => {
        const p = Ch.plate(n[0], SIGN.fs, { chip: pal.main, padX: 1 });
        s += pp(p.svg, { x: n[1], y: SIGN.y, q, ex: e, kind: 'sign', id: n[2] });
      });
      // 年份牌(詞級)
      const yh = Ch.plate('1986', SIGN.yearFs, { fill: K.YELLOW, padX: 0.8 }).h;
      const ny = Ch.plate('x', SIGN.fs, { chip: pal.main }).h, yy = SIGN.y + ny / 2 + SIGN.gapY + yh / 2;
      s += pp(Ch.plate('1986', SIGN.yearFs, { fill: K.YELLOW, padX: 0.8 }).svg, { x: SIGN.xl1, y: yy, q: k - wordF(L[1], '1986'), ex: e, kind: 'year', id: 'yl' });
      const qr = k - wordF(L[1], '1988');
      s += pp(Ch.plate('1988', SIGN.yearFs, { fill: K.YELLOW, padX: 0.8 }).svg, { x: SIGN.xr1, y: yy, q: qr, ex: e, kind: 'year', id: 'yr' });
      const ny2 = yy + yh / 2 + 22 + Ch.plate('x', SIGN.noteFs).h / 2;
      s += pp(Ch.plate('(常見說法)', SIGN.noteFs, { padX: 0.8 }).svg, { x: SIGN.xr1, y: ny2, q: qr, ex: e, kind: 'note', id: 'yn' });
      // 大珍奶杯
      const p = K.pop(q) * e;
      if (p > 0) s += K.paper(PS.bobaCup(pal), { x: CUP.x, y: CUP.y, scale: CUP.u, sx: p * sq, sy: p, k: 'prop', id: 'cup', enter: q < 2 || e !== 1 });
      // 法槌(句38「告上法院」)
      const qg = k - wordF(L[1], '告上法院'), d = K.drop(qg);
      if (d) s += K.paper(PS.gavel(pal), { x: GAVEL.x, y: GAVEL.y + d.dy * GAVEL.fall, scale: GAVEL.u, sx: d.sx * e, sy: d.sy * e, k: 'prop', id: 'gavel', enter: !!d.enter || e !== 1 });
    }

    // ---- 句39:2019、天平、沒有人贏、報導指出 ----
    const e1 = k - F[3];
    if (k >= F[2] && e1 < 2) {
      const e = ex(e1), qd = k - wordF(L[2], '2019'), qb = k - wordF(L[2], '結果'), qw = k - wordF(L[2], '沒有人贏');
      s += shrink(Ch.dateTag({ x: DATE.x, y: DATE.y, size: DATE.size, top: '判決', main: '2019', color: pal.main, k: qd, id: 'date' }), DATE.x, DATE.y, e);
      s += shrink(Ch.srcTag('報導指出', { pal, x: SRC.x, y: SRC.y, anchor: 'right', k: qd, id: 'src' }), SRC.x - 110, SRC.y, Math.min(e, 1));
      const pb = K.pop(qb) * e;
      if (pb > 0) s += K.paper(PS.balance(pal, { tilt: 0 }), { x: BAL.x, y: BAL.y, scale: BAL.u, sx: pb, sy: pb, k: 'prop', id: 'balance', enter: qb < 2 || e !== 1, wide: true });
      s += pp(Ch.plate('沒有人贏', WIN.fs, { fill: K.YELLOW, padX: 0.8 }).svg, { x: WIN.x, y: WIN.y, q: qw, ex: e, kind: 'sheet', id: 'win' });
    }

    // ---- 句40:價牌不動、三杯珍奶往右遞出 ----
    if (k >= F[3]) {
      const q = k - F[3];
      s += pp(`<rect x="${-BAR.w / 2}" y="${-BAR.h / 2}" width="${BAR.w}" height="${BAR.h}" fill="${pal.pad}" stroke-linejoin="miter"/>`, { x: BAR.x, y: BAR.y, q, kind: 'ground', id: 'bar' });
      s += Ch.priceFlip({ pal, x: PRICE.x, y: PRICE.y, from: '?', unit: '元', fs: PRICE.fs, k: q, id: 'pf' });
      CUPS.slots.forEach((sx, i) => {
        const qc = q - CUPS.starts[i];
        if (qc < 0) return;
        const x = Math.min(sx, CUPS.x0 + CUPS.step * qc), p = K.pop(qc);
        s += K.paper(PS.bobaCup(pal), { x, y: CUPS.y, scale: CUPS.u, sx: p, sy: p, k: 'prop', id: 'c' + i, enter: qc < 2 });
      });
    }

    // ---- 「?」記號:全程,句40 結尾前 5 格退場 ----
    s += Ch.triviaMark({ k: k - F[0], kOut: k >= kExit ? k - kExit : -1 });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_boba', dur: 17.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
