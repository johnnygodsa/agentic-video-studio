/* snack 場景 s_where_a(句 74–78)搬家有用嗎。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 句74:台灣四城輪廓(高約 613px、放左半、四點灰)彈入;鴿子提行李箱(舉翼吊著)從左走入站左下。
 * 句75:右半 22 格空白排行榜(2 欄 × 11 列)彈入,格子全空。
 * 句76:依詞位置臺北、新北、臺中、高雄逐一亮點:地圖點亮、城市字牌加引線彈入、排行榜左欄前 4 格填上城市名(不寫數字);句首來源小牌「臺北市主計處通報」。
 * 句77:臺南、花蓮各一張黃色便條「看全國平均」(帶圖釘)貼在地圖對應位置(兩張相隔 3 格);地圖其餘縣市不標數字。
 * 句78:地圖、字牌、榜、便條整批縮小退場;算式紙「2022 × 2023 × 2024 × 2025」(下排四城色塊)彈入、「自算」黃牌(之後全場保留)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const PT = Wn.PropsTurtle || require('../props_turtle.js');
  const TXT = ['那搬到別的縣市,會不會漲得比較少?', '我本來想排一張全台二十二個縣市的排行榜,結果排不出來。', '照臺北市主計處的統計通報,有在編自己物價指數的縣市只列了四個,臺北、新北、臺中和高雄。',
    '其他縣市沒有自己的數字,你住臺南還是花蓮,在官方資料上看到的都是全國平均。', '這四個城市,我把 2022 年到 2025 年每一年的漲幅連乘起來,這也是自己算的。'];
  const DEF = [{ start: 0.01, end: 2.37 }, { start: 2.49, end: 6.62 }, { start: 6.74, end: 13.15 }, { start: 13.27, end: 19.12 }, { start: 19.24, end: 25.13 }];
  const U = 1.43, PU = 1.36;                          // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 250, y: 810 }, WALK_N = 10, STEP = 30;
  const MAP = { x: 700, y: 468, s: 2.2 };             // 台灣四城:高約 613px(含描邊),中心 (700,468)
  const WING = { wing: 160, wlen: 1 }, SH = [146, 176], WT = [76, 30], SUIT_U = 0.75;   // 吊行李箱的翼姿勢
  const CITY = [{ name: '臺北', key: '臺北、', col: 'hsl(210 75% 52%)' }, { name: '新北', key: '新北', col: 'hsl(135 55% 42%)' },
    { name: '臺中', key: '臺中', col: 'hsl(24 90% 52%)' }, { name: '高雄', key: '高雄', col: 'hsl(280 55% 52%)' }];
  const LAB_R = 560, LAB_Y = [215, 318, 421], KS_L = 741, KS_Y = 725;   // 標籤欄右緣、三個標籤中心 y;高雄標籤左緣與中心 y
  const BD = { x: 1440, y: 453, w: 780, h: 706, cw: 368, ch: 62, gx: 8, py: 64, padX: 18 };   // 排行榜 x 1050–1830、y 100–806
  const NOTE = [{ name: '臺南', ll: [120.21, 23.00], x: 665, y: 505 }, { name: '花蓮', ll: [121.60, 23.98], x: 870, y: 315 }];
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const NS = (s) => s.replace('stroke-linejoin="miter"', 'stroke="none"');
  const T = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="${anchor || 'middle'}"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const mx = (x) => MAP.x + MAP.s * x, my = (y) => MAP.y + MAP.s * y;
  const shr = (str, x, y, k, k0) => {                  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
    if (!str) return '';
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || TXT[i] };
    });
  }

  // 排行榜:22 格(左欄 11、右欄 11),前 4 格依 kc 填上城市名
  function board(pal, kc, k, kb) {
    const tint = `hsl(${pal.h} 35% 88%)`, y0 = -BD.h / 2 + (BD.h - (10 * BD.py + BD.ch)) / 2 + BD.ch / 2;
    let c = R(-BD.w / 2, -BD.h / 2, BD.w, BD.h, K.PAPER);
    for (let i = 0; i < 22; i++) {
      const col = Math.floor(i / 11), row = i % 11, cx = -BD.w / 2 + BD.padX + BD.cw / 2 + col * (BD.cw + BD.gx), cy = y0 + row * BD.py;
      c += R(cx - BD.cw / 2, cy - BD.ch / 2, BD.cw, BD.ch, tint);
      if (i < 4 && k >= kc[i]) {
        const p = K.pop(k - kc[i]);
        c += `<g transform="translate(${f(cx)} ${f(cy)}) scale(${p})">` + R(-BD.cw / 2, -BD.ch / 2, BD.cw, BD.ch, K.YELLOW) +
          NS(R(-BD.cw / 2, -BD.ch / 2, 18, BD.ch, CITY[i].col)) + T(CITY[i].name, 12, 0, 56, K.INK) + '</g>';
      }
    }
    const p = K.pop(kb), sp = 1 + (p - 1) * 0.35;                       // 榜很大:彈入過衝縮小,避免第 1 格壓進字幕帶
    return K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${c}</g>`,
      { x: BD.x, y: BD.y, scale: U, sx: sp, sy: sp, k: 'board', id: 'board', enter: kb < 2, wide: true });
  }

  // 城市字牌加引線(引線自字牌邊到圓點邊)
  function cityLabel(i, pal, k) {
    const D = PS.taiwan4Pos()[i], dx0 = mx(D.x), dy0 = my(D.y), pl = Ch.plate(CITY[i].name, 56, { chip: CITY[i].col, padX: 1 });
    const left = i === 3, cx = left ? KS_L + pl.w / 2 : LAB_R - pl.w / 2, cy = left ? KS_Y : LAB_Y[i];
    const ex = left ? -pl.w / 2 : pl.w / 2, tx = dx0 - cx, ty = dy0 - cy, len = Math.hypot(tx - ex, ty), r = 10 * MAP.s + 6;
    const ux = (tx - ex) / len, uy = ty / len, d = `M ${f(ex)} 0 L ${f(tx - ux * r)} ${f(ty - uy * r)}`;
    const c = `<path d="${d}" fill="none" stroke="${K.PAPER}" stroke-width="15" stroke-linecap="round"/><path d="${d}" fill="none" stroke="${K.INK}" stroke-width="7" stroke-linecap="round"/>` + pl.svg;
    return Ch.sheet(c, { x: cx, y: cy, u: U, k, kind: 'label', id: 'city' + i, wide: true });
  }

  // 黃色便條「看全國平均」加圖釘(圖釘在地圖該縣市位置)
  function note(n, k) {
    const pl = Ch.plate('看全國平均', 56, { fill: K.YELLOW, padX: 0.6 }), xy = PT.twXY(n.ll[0], n.ll[1]), px = mx(xy[0]) - n.x, py = my(xy[1]) - n.y;
    const ex = Math.max(-pl.w / 2 + 12, Math.min(pl.w / 2 - 12, px)), ey = (py > 0 ? 1 : -1) * pl.h / 2;
    const c = `<path d="M ${f(px)} ${f(py)} L ${f(ex)} ${f(ey)}" fill="none" stroke="${K.INK}" stroke-width="7" stroke-linecap="round"/>` + pl.svg +
      `<circle cx="${f(px)}" cy="${f(py)}" r="13" fill="${K.INK}"/>`;
    return Ch.sheet(c, { x: n.x, y: n.y, u: U, k, kind: 'note', id: 'note_' + n.name, wide: true });
  }

  // 算式紙:上排連乘算式,下排四城色塊
  function formula(pal, k) {
    const s = '2022 × 2023 × 2024 × 2025', W = 1560, H = 300, fs = Math.min(120, Math.floor(1470 / Ch.tw(s, 1)));
    if (fs < 100 || Ch.tw(s, fs) > W - 60) throw new Error('s_where_a 算式字級不足或溢出:' + fs);
    let c = R(-W / 2, -H / 2, W, H, K.PAPER) + NS(R(-W / 2, -H / 2, 22, H, pal.main)) + T(s, 0, -52, fs, K.INK);
    CITY.forEach((ct, i) => {
      const gx = -450 + i * 300;
      c += `<circle cx="${f(gx - 72)}" cy="88" r="23" fill="${ct.col}"/>` + T(ct.name, gx - 38, 88, 56, K.INK, 'start');
    });
    return Ch.sheet(c, { x: 1010, y: 320, u: U, k, kind: 'sheet', id: 'formula', wide: true });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kArr = F[0] + WALK_N;
    const at = (i, key) => { const p = L[i].text.indexOf(key); return K.frame(L[i].start + (p < 0 ? 0.6 : p / L[i].text.length) * (L[i].end - L[i].start)); };
    const kc = [at(2, CITY[0].key)];
    for (let i = 1; i < 4; i++) kc.push(Math.max(at(2, CITY[i].key), kc[i - 1] + 3));
    const kn = [F[3], F[3] + 3], kEx = F[4], kFor = F[4] + 2, kSelf = F[4] + 6;
    let old = '';

    // 左半:台灣四城(句74 起)
    {
      const q = k - F[0], p = K.pop(q), on = kc.map((c) => (k >= c ? 1 : 0));
      old += K.paper(PS.LIST.taiwan4.fn(pal, { on }), { x: MAP.x, y: MAP.y, scale: MAP.s, sx: p, sy: p, k: 'prop', id: 'taiwan', enter: q < 2, wide: PS.LIST.taiwan4.wide });
    }
    if (k >= F[1]) old += board(pal, kc, k, k - F[1]);                                                    // 句75:空白榜
    if (k >= F[2]) old += Ch.srcTag('臺北市主計處通報', { pal, x: 90, y: 125, anchor: 'left', k: k - F[2], id: 'src' });   // 句76:來源
    for (let i = 0; i < 4; i++) if (k >= kc[i]) old += cityLabel(i, pal, k - kc[i]);                     // 句76:逐城亮點
    NOTE.forEach((n, i) => { if (k >= kn[i]) old += note(n, k - kn[i]); });                               // 句77:便條
    let s = shr(old, 960, 450, k, kEx);

    if (k >= kFor) s += formula(pal, k - kFor);                                                           // 句78:算式紙
    if (k >= kSelf) {
      const p = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
      s += Ch.sheet(p.svg, { x: 1790 - p.w / 2, y: 575, u: U, k: k - kSelf, kind: 'src', id: 'self', wide: true });
    }

    // 鴿子提著行李箱(全程舉翼吊著)
    const walking = k < kArr, dx = walking ? (kArr - k) * STEP : 0;
    const base = walking ? K.clip('walk', k - F[0]) : K.expr(K.clip('idle', k), 'normal');
    const pose = Object.assign({}, base, WING, { flip: 1 });
    const a = WING.wing * Math.PI / 180, vx = WT[0] * WING.wlen, vy = WT[1];
    const px = SH[0] + vx * Math.cos(a) - vy * Math.sin(a), py = SH[1] + vx * Math.sin(a) + vy * Math.cos(a);
    const tipX = FOOT.x - dx + PU * (300 - px - 132), tipY = FOOT.y - 280 * PU + PU * py;
    if (!walking) s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(pose, { x: FOOT.x - dx, y: FOOT.y, scale: PU, id: 'main', enter: walking });
    s += K.paper(PS.LIST.suitcase.fn(pal), { x: tipX + 25, y: tipY + 88 * SUIT_U, scale: SUIT_U, k: 'prop', id: 'suitcase', wide: PS.LIST.suitcase.wide, enter: walking });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_where_a', dur: 25.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
