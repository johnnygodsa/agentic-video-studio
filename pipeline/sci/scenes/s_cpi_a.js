/* snack 場景 s_cpi_a(句 24–28)主計總處外食費細項。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 句24:資料夾(主計總處,掀開)左側彈入;十二張細項卡 4 欄 × 3 列(x 470–1840、y 110–800)每格一張彈入。
 * 句25:卡與資料夾退場;中央算式紙「2025 年平均 ÷ 2016 年平均」;右下「自算」黃牌(之後全場保留)。
 * 句26:算式紙退場;hbars(x 430–1840、rows 3–5,max 40,之後場景往上加條)由下而上每 6 格一條:幼兒園 7.2、學生營養午餐 17.5、咖啡飲料 19.3(hi);右上來源牌。
 * 句27:左側窄欄「討論榜」1–5(字 56px,欄 x 90–400、y 80–470,鴿子站在欄下);從第 4 名拉墨色粗線到咖啡飲料那條標籤左緣(句首後第 4 格);鴿子走進來、surprised。
 * 句28:鴿子閉眼揉兩下、前傾看、回正、再前傾看。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.07, end: 5.2 }, { start: 5.32, end: 11.4 }, { start: 11.52, end: 18.6 }, { start: 18.72, end: 23.3 }, { start: 23.42, end: 25 }];
  const U = 1.43, PU = 1.36, FU = 1.34;              // 紙片倍率、鴿子倍率(高約 309px)、資料夾倍率(寬約 337px)
  const FOOT = { x: 245, y: 820 }, WALK_N = 10, STEP = 30;
  const NAMES = ['中式早點', '火鍋', '西式早點', '其他家外食物', '中式麵食', '中式米食', '中式以外料理', '西式速食',
    '中式餐廳料理', '在外點用之咖啡飲料', '學生營養午餐', '幼兒園點心費'];
  const CARD = { w: 318, h: 210, fs: 56, x0: 472, y0: 110, gx: 28, gy: 30 };   // 4 欄 × 3 列佔 x 472–1828、y 110–800(含描邊距右緣 ≥ 84)
  const RANK = ['滷肉飯', '水餃', '雞排', '手搖飲', '牛肉麵'];
  const COL = { x: 96, w: 310, h: 58, fs: 56, pitch: 60, y0: 117 };           // 討論榜欄(x 96–406):標題在 y0,名次 1–5 往下;整欄 y 88–460 讓鴿子頭頂(約 y 503)留 ≥40px
  const BARS = { x: 430, y: 464, w: 1410, rowH: 104, gap: 12, labelW: 590 };  // 6 列版面(起於 y 116、列距 116)的後 3 列
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

  // 細項卡:一行或兩行(超過 5 字分兩行),文字置中偏右(左側主色條)
  function card(name, pal) {
    const ls = name.length <= 4 ? [name] : [name.slice(0, Math.ceil(name.length / 2)), name.slice(Math.ceil(name.length / 2))], chip = 14;
    ls.forEach((l) => { if (Ch.tw(l, CARD.fs) > CARD.w - chip - 20) throw new Error('s_cpi_a 卡片字溢出:' + l); });
    let c = R(-CARD.w / 2, -CARD.h / 2, CARD.w, CARD.h, K.PAPER) + R(-CARD.w / 2, -CARD.h / 2, chip, CARD.h, pal.main).replace('stroke-linejoin="miter"', 'stroke="none"');
    ls.forEach((l, i) => { c += T(l, chip / 2, (i - (ls.length - 1) / 2) * CARD.fs * 1.32, CARD.fs, K.INK); });
    return c;
  }

  // 討論榜一列:名次方塊(主色)+ 名稱;i<0 = 標題
  function rankRow(i, pal) {
    const { w, h, fs } = COL, hi = i === 3;
    if (i < 0) return R(-w / 2, -TH / 2, w, TH, K.INK) + T('討論榜', 0, 0, fs, K.PAPER);
    return R(-w / 2, -h / 2, w, h, hi ? K.YELLOW : K.PAPER) + R(-w / 2, -h / 2, h, h, pal.main).replace('stroke-linejoin="miter"', 'stroke="none"') +
      T(String(i + 1), -w / 2 + h / 2, 0, fs, pal.onMain) + T(RANK[i], -w / 2 + h + 14, 0, fs, K.INK, 'start');
  }
  const TH = 76;                                                              // 標題牌高(字高 56 × 1.35 = 75.6);中心 y=121
  const rankY = (i) => (i < 0 ? COL.y0 + 4 : COL.y0 + 77 + i * COL.pitch);   // 標題 y 83–159(外框扣描邊後頂 ≥ 80);第 1 名牌頂 165(列距 60、牌高 58)

  // 句28 鴿子動作:0–1 驚訝站著;2–4 閉眼左右晃(揉眼睛);5–6 前傾看;7–8 回正;9 起前傾看並維持
  function pigeonPose(k, F, kArr) {
    let p, dx = 0, enter = false;
    const lean = { headDx: -10, headRot: -6, headDy: 2 };
    if (k < kArr) { p = K.clip('walk', k - F[3]); dx = (kArr - k) * STEP; enter = true; }
    else if (k < F[4]) p = K.expr(K.clip('idle', k), 'surprised');
    else {
      const j = k - F[4], base = K.clip('idle', k);
      if (j < 2) p = K.expr(base, 'surprised');
      else if (j < 5) p = Object.assign(K.expr(base, 'doubt'), { lid: 1, headDx: [-3, 3, -3][j - 2], headDy: 1 });
      else if (j < 7 || j >= 9) p = Object.assign(K.expr(base, 'doubt'), lean);
      else p = K.expr(base, 'doubt');
    }
    return { pose: Object.assign({}, p, { flip: 1 }), dx, enter };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[2 + 1] ? 2 : k < F[4] ? 3 : 4;
    let s = '';

    if (ph === 0) {                                                          // 句24:資料夾 + 十二張卡
      const q = k - F[0], p = K.pop(q);
      s += K.paper(PS.folder(pal, { open: true, label: '主計總處' }), { x: 258, y: 457, scale: FU, sx: p, sy: p, k: 'prop', id: 'folder', enter: q < 2 });
      NAMES.forEach((n, i) => {
        s += Ch.sheet(card(n, pal), { x: CARD.x0 + CARD.w / 2 + (i % 4) * (CARD.w + CARD.gx), y: CARD.y0 + CARD.h / 2 + Math.floor(i / 4) * (CARD.h + CARD.gy),
          u: U, k: q - (2 + i), kind: 'card', id: 'c' + i, wide: true });
      });
    } else if (ph === 1) {                                                   // 句25:算式紙
      const pl = Ch.plate('2025 年平均 ÷ 2016 年平均', 112, { chip: pal.main, padX: 1 });
      s += Ch.sheet(pl.svg, { x: 960, y: 430, rot: -1, u: U, k: k - F[1], kind: 'sheet', id: 'formula', wide: true });
    } else {                                                                 // 句26 起:長條圖全場保留
      const q = k - F[2];
      s += Ch.hbars({ pal, x: BARS.x, y: BARS.y, w: BARS.w, rowH: BARS.rowH, gap: BARS.gap, labelW: BARS.labelW, fs: 60, numFs: 72, max: 40, id: 'cpi', bars: [
        { label: '在外點用之咖啡飲料', value: 19.3, text: '19.3%', hi: true, k: q - 12 },
        { label: '學生營養午餐', value: 17.5, text: '17.5%', grey: true, k: q - 6 },
        { label: '幼兒園點心費', value: 7.2, text: '7.2%', grey: true, k: q }] });
      s += Ch.srcTag('主計總處 消費者物價指數', { pal, x: 1830, y: 120, anchor: 'right', k: q, id: 'src' });
    }
    if (k >= F[1] + 8) {                                                     // 自算小牌:句25 起保留
      const p = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
      s += Ch.sheet(p.svg, { x: 1740, y: 780, u: U, k: k - F[1] - 8, kind: 'src', id: 'self', wide: true });
    }
    if (ph >= 3) {                                                           // 句27 起:討論榜、連線、鴿子
      const q = k - F[3];
      for (let i = -1; i < 5; i++) s += Ch.sheet(rankRow(i, pal), { x: COL.x + COL.w / 2, y: rankY(i), u: U, k: q, kind: 'rank', id: 'r' + i, wide: true });
      const ax = COL.x + COL.w + 4, ay = rankY(3), bx = BARS.x - 8, by = BARS.y + BARS.rowH / 2, dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy), th = 14;
      const nx = -dy / len * th / 2, ny = dx / len * th / 2;
      const pts = [[-dx / 2 + nx, -dy / 2 + ny], [dx / 2 + nx, dy / 2 + ny], [dx / 2 - nx, dy / 2 - ny], [-dx / 2 - nx, -dy / 2 - ny]];
      s += Ch.sheet(`<polygon points="${pts.map((v) => `${f(v[0])},${f(v[1])}`).join(' ')}" fill="${K.INK}"/>`,
        { x: (ax + bx) / 2, y: (ay + by) / 2, u: U, k: q - 4, kind: 'link', id: 'link', wide: true });
      const kArr = F[3] + WALK_N, pg = pigeonPose(k, F, kArr);
      if (k >= kArr) s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
      s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: FOOT.y, scale: PU, id: 'main', enter: pg.enter });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_cpi_a', dur: 25, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
