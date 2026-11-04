/* snack 場景 s_pay_a(句 94–98)薪水一:基本工資。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。淺底。
 * 句94:左上「台灣」國名牌(同 s_abroad 樣式,第 0 格彈入、全場保留)+ 其下台灣輪廓(高 200,句 96 起退場);hbars(x 430–1840、max 50)外食費 26.6% 在「外食費」處;
 *      hbars 上方標題帶「十年」「自算」黃牌(「十年」處、外食費後 1 秒,句 96 隨圖表上移退場);「主計總處」小牌外食費後 1.1 秒;整體物價 14.3% 在「整體物價」處。
 * 句95:肉類 31.8% 長條(句首);下方依序彈入肉塊(「肉類」後 0.5 秒)、滷肉飯(「滷肉飯」)、雞排(「雞排」)小圖。
 * 句96:圖表上移成上半(4 格);左下薪資袋彈入;0.7 秒後袋上「?」牌。
 * 句97:「?」退場、袋上方「基本工資」字牌、來源牌換「勞動部」;「20,008(2016)」→「29,500(2026)」加箭頭(各在該數字處);「+47.4%」黃牌加「自算」(「多了」處)。
 * 句98:上一句的圖解退場(來源牌換回主計總處);鴿子從左走入、跳一下、開心站定,胸前依序疊上滷肉飯、雞排、珍奶、地瓜球。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const DEF = [{ start: 0.07, end: 7.93 }, { start: 8.05, end: 12.68 }, { start: 12.8, end: 14.02 }, { start: 14.14, end: 20.77 }, { start: 20.89, end: 24.2 }];
  const DEFT0 = '再回來看台灣,外食費十年漲了 26.6%,同一段時間整體物價是 14.3%,外食漲得快要兩倍。';
  const CFS = 110, CPOS = { x: 105, y: 200 }, TWO = { x: 290, y: 420, box: 200 };   // 國名牌(同 s_abroad:左緣 105、中心 y 200)、台灣輪廓(國名牌正下方)
  const HEAD = { y: 185, x1: 700, x2: 990 };      // 標題帶:「十年」「自算」(hbars 上方)
  const U = 1.43, PU = 1.36;                          // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 }, WALK_N = 10, STEP = 30;
  const BARS = { x: 510, w: 1330, rowH: 104, gap: 8, labelW: 310, fs: 60, numFs: 72, max: 50 };
  const SLIDE = [270, 205, 150, 115, 100];            // 圖表 y 起點:句 94–95 在 270,句 96 起 4 格上移到 100
  const EXP = [1.15, 0.6];                            // 退場 2 格縮小
  const ENV = { x: 275, y: 680, u: 1.5 };             // 薪資袋(寬約 330、高約 210)
  const HAPPY = { lid: 0.3, lidTilt: 0, pdx: -3, pdy: 5, ps: 1, beak: 0.2 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || (i === 0 ? DEFT0 : '') };
    });
  }
  // 詞級時間(格):詞的起始字索引 ÷ 句長 × 句長秒數 + start,對齊 0.1 秒
  function wordFrame(l, tok) {
    const idx = l.text.indexOf(tok), r = idx < 0 ? 0 : idx / l.text.length;
    return Math.max(K.frame(l.start), K.frame(Math.round((l.start + r * (l.end - l.start)) * 10) / 10 + 0.001));
  }

  // px 紙片:kIn = 出現後第幾格;kOut >= 0 = 退場第幾格(2 格縮小後消失)
  function sh(content, o, kIn, kOut) {
    const u = o.u || U, out = kOut != null && kOut >= 0;
    const p = out ? EXP[kOut] : K.pop(kIn);
    if (!p || p <= 0) return '';
    return K.paper(`<g transform="scale(${(1 / u).toFixed(5)})" stroke-width="${f(4 * u)}">${content}</g>`,
      { x: o.x, y: o.y, rot: o.rot, scale: u, sx: p, sy: p, k: o.kind || 'label', id: o.id, enter: kIn < 2 || out, wide: true });
  }
  const ic = (pal, n, box) => Ch.icon({ svg: PS.LIST[n].fn(pal, {}), w: PS.LIST[n].w, h: PS.LIST[n].h }, 0, 0, box);

  // 數字牌 + 年份牌(同一組紙片):中心 (0,0) 為整組中心,數字在上、年份在下
  function numCard(pal, num, yr, fill, ink) {
    const a = Ch.plate(num, 80, { padX: 0.8, fill, ink }), b = Ch.plate(yr, 56, { padX: 0.8, fill: pal.pad });
    return `<g transform="translate(0 -52)">${a.svg}</g><g transform="translate(0 63)">${b.svg}</g>`;
  }
  const ARROW = `<rect x="-40" y="-13" width="50" height="26" fill="${K.INK}" stroke-linejoin="miter"/><polygon points="6,-34 46,0 6,34" fill="${K.INK}" stroke-linejoin="miter"/>`;

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kf = (i, dt) => K.frame(L[i].start + dt);
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : 4;
    const ko = k - F[4];                                                  // 句 98 起的退場格
    const y0 = k < F[2] ? SLIDE[0] : SLIDE[Math.min(k - F[2], SLIDE.length - 1)];
    let s = '';

    // 長條圖:全場保留
    const kEat = wordFrame(L[0], '外食費'), kAll = wordFrame(L[0], '整體物價'), kMeat = F[1], kOut2 = k >= F[2] ? k - F[2] : -1;
    s += Ch.hbars({ pal, x: BARS.x, y: y0, w: BARS.w, rowH: BARS.rowH, gap: BARS.gap, labelW: BARS.labelW, fs: BARS.fs, numFs: BARS.numFs, max: BARS.max, id: 'pay', bars: [
      { label: '整體物價', value: 14.3, text: '14.3%', color: 'hsl(205 70% 52%)', k: k - kAll },
      { label: '外食費', value: 26.6, text: '26.6%', k: k - kEat },
      { label: '肉類', value: 31.8, text: '31.8%', color: 'hsl(6 75% 55%)', k: k - kMeat }] });

    // 左上:「台灣」國名牌(全場保留)+ 其下台灣輪廓(句 96 起退場)
    const cp = Ch.plate('台灣', CFS, { fill: K.INK, ink: K.YELLOW, chip: pal.main });
    s += sh(cp.svg, { x: Math.round(CPOS.x + cp.w / 2), y: CPOS.y, kind: 'country', id: 'country' }, k - F[0]);
    s += sh(Ch.icon({ svg: PT.LIST.taiwan.fn(pal, {}), w: PT.LIST.taiwan.w, h: PT.LIST.taiwan.h }, 0, 0, TWO.box), { x: TWO.x, y: TWO.y, kind: 'map', id: 'taiwan' }, k - F[0], kOut2);

    // hbars 上方標題帶:「十年」「自算」(句 96 圖表上移時退場)
    s += sh(Ch.plate('十年', 100, { fill: K.YELLOW, padX: 1 }).svg, { x: HEAD.x1, y: HEAD.y, id: 'decade' }, k - wordFrame(L[0], '十年'), kOut2);
    s += sh(Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 }).svg, { x: HEAD.x2, y: HEAD.y, kind: 'src', id: 'self' }, k - (kEat + 10), kOut2);

    // 來源小牌:94–96 主計總處、97 勞動部、98 換回主計總處
    if (ph === 3) s += Ch.srcTag('勞動部', { pal, x: 1830, y: 120, anchor: 'right', k: k - F[3], id: 'src' });
    else s += Ch.srcTag('主計總處', { pal, x: 1830, y: 120, anchor: 'right', k: ph === 4 ? k - F[4] : k - (kEat + 11), id: 'src' });

    // 肉類下方小圖(句 95 起,隨圖表上移)
    const iy = y0 + 2 * (BARS.rowH + BARS.gap) + BARS.rowH + 60;
    [['meatChunk', 1300, kf(1, 0.5)], ['braisedPorkRice', 1430, kf(1, 2.2)], ['chickenCutlet', 1560, kf(1, 2.9)]].forEach((a) => {
      s += sh(ic(pal, a[0], 100), { x: a[1], y: iy, kind: 'prop', id: a[0] }, k - a[2]);
    });

    // 薪資袋(句 96 彈入、句 98 退場)與「?」「基本工資」
    if (k >= F[2] && !(ph === 4 && ko >= 2)) {
      const out = ph === 4, p = out ? EXP[ko] : K.pop(k - F[2]);
      s += K.paper(PS.LIST.payEnvelope.fn(pal, {}), { x: ENV.x, y: ENV.y, scale: ENV.u, sx: p, sy: p, k: 'prop', id: 'env', enter: out || k - F[2] < 2, wide: false });
    }
    if (k >= F[2] + 7 && ph < 4) s += Ch.triviaMark({ x: ENV.x, y: ENV.y + 66, size: 76, rot: -4, k: k - (F[2] + 7), kOut: ph === 3 ? k - F[3] : -1, id: 'q' });
    if (ph >= 3) {
      s += sh(Ch.plate('基本工資', 60, { padX: 1 }).svg, { x: ENV.x, y: 480, id: 'wage' }, k - F[3], ph === 4 ? ko : -1);
      const kA = kf(3, 2.1), kB = kf(3, 4.5), kP = kf(3, 5.7), kS = kf(3, 6.1), o = ph === 4 ? ko : -1;
      s += sh(numCard(pal, '20,008', '(2016)', K.PAPER, K.INK), { x: 700, y: 700, id: 'nA' }, k - kA, o);
      s += sh(ARROW, { x: 925, y: 648, id: 'arr' }, k - kB, o);
      s += sh(numCard(pal, '29,500', '(2026)', pal.main, pal.onMain), { x: 1150, y: 700, id: 'nB' }, k - kB, o);
      s += sh(Ch.plate('+47.4%', 88, { padX: 0.8, fill: K.YELLOW }).svg, { x: 1590, y: 648, id: 'pct' }, k - kP, o);
      s += sh(Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 }).svg, { x: 1590, y: 770, kind: 'src', id: 'self2' }, k - kS, o);
    }

    // 句 98:鴿子走入、跳、開心站定,胸前疊小吃
    if (ph === 4) {
      const kArr = F[4] + WALK_N;
      let p, dx = 0, enter = false;
      if (k < kArr) { p = K.clip('walk', k - F[4]); dx = (kArr - k) * STEP; enter = true; }
      else if (k < kArr + 6) p = K.clip('hop', k - kArr);
      else p = K.clip('idle', k);
      const pose = Object.assign({}, p, HAPPY, { flip: 1 });
      if (k >= kArr) s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
      s += K.pigeon(pose, { x: FOOT.x - dx, y: FOOT.y, scale: PU, id: 'main', enter });
      [['braisedPorkRice', 255, 745, 140, 0], ['chickenCutlet', 325, 712, 150, 8], ['bobaCup', 190, 680, 140, -8], ['sweetBall', 297, 642, 110, 0]].forEach((a, i) => {
        s += sh(ic(pal, a[0], a[3]), { x: a[1], y: a[2], rot: a[4], kind: 'prop', id: 'f' + i }, k - (kArr + 6 + 2 * i));
      });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_pay_a', dur: 24.3, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
