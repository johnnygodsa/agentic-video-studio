/* turtle 場景 §25 t_works(句 91–97,29.9 秒)限塑有用的部分。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 純圖表場景,無鴿子;每句換景,前一句的東西整組退場。同時在動的非文字元素 ≤ 2 組。
 * 句91:兩欄板「有用」「沒那麼有用」(都是空的,灰)。句92:左欄亮。
 * 句93:整個畫面給左欄內容:牌「2019 吸管限用」、「前一年」長條(100)在句首,「2019 年」長條(73)、虛線缺口與大字「−27%」依序出現;小牌「淨灘資料」;不標絕對數。
 * 句94:塑膠袋、飲料杯、免洗餐具三個圖在句首,各帶一支向下大箭頭依序彈出;不標數字。
 * 句95:兩條長條「管制前 200 億個」(句首)、「現在 91.7 億個」(長度照比例),小牌「官方說法」。
 * 句96:「戶外」小景(馬路與沙灘)在句首,吸管、塑膠袋、飲料杯、免洗餐具一起掉下來落在上面。
 * 句97:沙灘前後對比(各 760×520):左邊垃圾多、右邊少。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 紙片倍率(與其他 turtle 場景一致)
  const DEF = [{ start: 0.04, end: 2.5 }, { start: 2.62, end: 3.93 }, { start: 4.05, end: 11.98 }, { start: 12.1, end: 16.61 },
    { start: 16.73, end: 22.76 }, { start: 22.88, end: 27.79 }, { start: 27.91, end: 29.88 }];
  const RED = 'hsl(6 75% 55%)';
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const absSheet = (content, cx, cy, o) => Ch.sheet(`<g transform="translate(${f(-cx)} ${f(-cy)})">${content}</g>`, Object.assign({ x: cx, y: cy, u: U }, o));
  const iconSheet = (pal, n, o, x, y, box, p) => Ch.sheet(Ch.icon(ic(pal, n, o), 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: n, wide: PT.LIST[n].wide }, p));
  const plateSheet = (str, fs, o, p) => { const q = Ch.plate(str, fs, o); return Ch.sheet(q.svg, Object.assign({ u: U, kind: 'plate', id: str, wide: true }, p)); };
  const txtL = (s, x, y, fs, ink) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${fs}" text-anchor="start" dominant-baseline="central" fill="${ink}" stroke="none">${s}</text>`;
  // 橫條:左端 x0、中心 y、長 len、高 h;字寫在條內左側
  function bar(x0, y, len, h, fill, ink, label, fs, p) {
    return absSheet(rect(x0, y - h / 2, len, h, fill) + txtL(label, x0 + 36, y, fs, ink), x0 + len / 2, y, Object.assign({ kind: 'bar', wide: len > 3 * h }, p));
  }
  // 向下粗箭頭(中心 x,頂 y0,尖端 y1)
  function downArrow(x, y0, y1, fill, p) {
    const th = 44, hw = 120, hl = 85, bx = y1 - hl, cy = (y0 + y1) / 2;
    const pts = [[-th / 2, y0], [th / 2, y0], [th / 2, bx], [hw / 2, bx], [0, y1], [-hw / 2, bx], [-th / 2, bx]];
    return Ch.sheet(`<polygon points="${pts.map((q) => `${f(q[0])},${f(q[1] - cy)}`).join(' ')}" fill="${fill}"/>`, Object.assign({ x, y: cy, u: U, kind: 'arrow', id: 'down' }, p));
  }
  // 掉落紙片:內容 hPx 高、落點底邊 yBottom;用 K.drop 的位移與壓扁(底邊固定)
  function dropSheet(content, x, yBottom, hPx, k, id, rot) {
    const d = K.drop(k);
    if (!d) return '';
    const y = yBottom - hPx / 2 + d.dy * 560 + (1 - d.sy) * hPx / 2;
    return K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
      { x, y, rot, scale: U, sx: d.sx, sy: d.sy, k: 'prop', id, enter: !!d.enter });
  }
  // bigNum 寬度(與 Charts.bigNum 同式),用來把數字牌貼在長條尾端
  const bigW = (num, unit, fs, ufs) => Ch.tw(num, fs) + Ch.tw(unit, ufs) + fs * 0.08 + fs * 0.5;

  // ---------- 句93 ----------
  function scene93(pal, k0, L) {
    const kk = (p) => k0 - at(L, p), Y1 = 340, Y2 = 520, X0 = 120, LEN = 1000;
    let s = plateSheet('2019 吸管限用', 84, { fill: K.YELLOW }, { x: 440, y: 168, rot: -1.5, id: 'tag' });
    s += bar(X0, Y1, LEN, 150, `hsl(${pal.h} 12% 74%)`, K.INK, '前一年', 72, { id: 'b1' });
    s += Ch.srcTag('淨灘資料', { x: 1830, y: 710, anchor: 'right', fs: 48, pal, u: U, id: 'src' });
    s += plateSheet('每公里撿到的吸管', 64, {}, { x: 408, y: 710, rot: 1, id: 'note' });
    if (kk(0.3) >= 0) s += bar(X0, Y2, LEN * 0.73, 150, pal.main, pal.onMain, '2019 年', 72, { k: kk(0.3), id: 'b2' });
    if (kk(0.55) >= 0) {
      s += absSheet(`<rect x="${X0 + LEN * 0.73}" y="${Y2 - 75}" width="${LEN * 0.27}" height="150" fill="hsl(6 75% 90%)" stroke="${RED}" stroke-width="10" stroke-dasharray="26 16"/>`,
        X0 + LEN * 0.865, Y2, { k: kk(0.55), kind: 'gap', id: 'gap' });
      s += Ch.bigNum({ x: 1500, y: 520, num: '−27%', fs: 180, u: U, k: kk(0.55), id: 'n27' });
    }
    return s;
  }

  // ---------- 句94 ----------
  function scene94(pal, k0, L) {
    const kk = (p) => k0 - at(L, p), X = [380, 960, 1540], N = ['bag', 'cup', 'cutlery'], Z = ['塑膠袋', '飲料杯', '免洗餐具'], P = [0.35, 0.5, 0.62];
    let s = '';
    N.forEach((n, i) => {
      s += iconSheet(pal, n, {}, X[i], 270, 300, { id: n });
      s += plateSheet(Z[i], 64, {}, { x: X[i], y: 485, rot: i % 2 ? 1.2 : -1.2, id: 'z' + i });
      if (kk(P[i]) >= 0) s += downArrow(X[i], 560, 805, pal.text, { k: kk(P[i]), id: 'dn' + i });
    });
    return s;
  }

  // ---------- 句95 ----------
  function scene95(pal, k0, L) {
    const kk = (p) => k0 - at(L, p), X0 = 100, LEN = 1000, Y1 = 250, Y2 = 500, FS = 150, UFS = 64;
    const L2 = LEN * 91.7 / 200;
    let s = bar(X0, Y1, LEN, 170, `hsl(${pal.h} 12% 74%)`, K.INK, '管制前', 72, { id: 'b1' });
    s += Ch.bigNum({ x: X0 + LEN + 30 + bigW('200', '億個', FS, UFS) / 2, y: Y1, num: '200', unit: '億個', fs: FS, unitFs: UFS, u: U, id: 'n200' });
    s += plateSheet('一年的塑膠袋用量', 64, {}, { x: 388, y: 710, rot: 1, id: 'note' });
    if (kk(0.08) >= 0) s += Ch.srcTag('官方說法', { x: 1830, y: 710, anchor: 'right', fs: 48, pal, u: U, k: kk(0.08), id: 'src' });
    if (kk(0.55) >= 0) {
      s += bar(X0, Y2, L2, 170, pal.main, pal.onMain, '現在', 72, { k: kk(0.55), id: 'b2' });
      s += Ch.bigNum({ x: X0 + L2 + 30 + bigW('91.7', '億個', FS, UFS) / 2, y: Y2, num: '91.7', unit: '億個', fs: FS, unitFs: UFS, u: U, k: kk(0.55), id: 'n917' });
    }
    return s;
  }

  // ---------- 句96 ----------
  const OUT_Y = 420, OUT_H = 400;
  function outdoors() {
    // 馬路(左)與沙灘(右)
    let road = rect(100, OUT_Y, 860, OUT_H, 'hsl(215 10% 42%)'), lane = '';
    for (let i = 0; i < 6; i++) lane += R(110 + i * 145, 690, 90, 14, 'hsl(48 20% 88%)');
    let sand = rect(960, OUT_Y, 860, OUT_H, 'hsl(42 60% 78%)') + R(960, OUT_Y, 860, 80, 'hsl(195 55% 58%)');
    for (let i = 0; i < 5; i++) sand += R(1000 + i * 170, OUT_Y + 34, 100, 10, 'hsl(195 55% 72%)');
    [[1090, 760], [1330, 800], [1560, 740], [1750, 790], [1200, 560]].forEach((p) => { sand += `<circle cx="${p[0]}" cy="${p[1]}" r="9" fill="hsl(42 40% 62%)" stroke="none"/>`; });
    return absSheet(road + lane, 530, OUT_Y + OUT_H / 2, { kind: 'road', id: 'road', wide: true }) +
      absSheet(sand, 1390, OUT_Y + OUT_H / 2, { kind: 'beach', id: 'beach', wide: true });
  }
  function scene96(pal, k0, L) {
    const kd = k0 - at(L, 0.3), XS = [360, 700, 1240, 1590], NS = ['bag', 'cup', 'cutlery', 'straw'], BOX = 250, YB = 790;
    let s = outdoors();
    s += plateSheet('馬路', 56, {}, { x: 300, y: 470, rot: -1, id: 'tr' }) + plateSheet('沙灘', 56, {}, { x: 1420, y: 520, rot: 1, id: 'tb' });
    s += plateSheet('戶外', 100, { fill: K.YELLOW }, { x: 960, y: 190, rot: -2, id: 'out' });
    NS.forEach((n, i) => {
      const o = PT.LIST[n], sc = Math.min(BOX / o.w, BOX / o.h);
      s += dropSheet(Ch.icon(ic(pal, n, {}), 0, 0, BOX), XS[i], YB, o.h * sc, kd, n, i % 2 ? 5 : -5);
    });
    return s;
  }

  // ---------- 句97 ----------
  const BEACH = { w: 760, h: 520, y: 410, xs: [540, 1380] };
  function beach(pal, cx, items, kk, tag) {
    const top = BEACH.y - BEACH.h / 2, sea = 150;
    let c = rect(cx - BEACH.w / 2, top, BEACH.w, BEACH.h, 'hsl(42 60% 78%)') + R(cx - BEACH.w / 2, top, BEACH.w, sea, 'hsl(195 55% 58%)');
    for (let i = 0; i < 4; i++) c += R(cx - 320 + i * 170, top + 40 + (i % 2) * 36, 110, 10, 'hsl(195 55% 74%)');
    let s = absSheet(c, cx, BEACH.y, { k: kk, kind: 'beach', id: 'bch' + tag, wide: true });
    items.forEach((it, i) => { s += iconSheet(pal, it[0], {}, cx + it[1], BEACH.y + it[2], 170, { rot: it[3], k: kk, id: 'tr' + tag + i }); });
    return s;
  }
  function scene97(pal, k0) {
    const kk = k0;                                 // 句首兩片一起出現
    const many = [['bag', -250, -10, -8], ['cup', 0, -40, 6], ['bottle', 250, -10, 12], ['cutlery', -170, 150, -6], ['straw', 90, 160, 14], ['bag', 300, 150, 5]];
    const few = [['cup', -90, 50, 6], ['straw', 150, 140, -10]];
    let s = beach(pal, BEACH.xs[0], many, kk, 'A') + beach(pal, BEACH.xs[1], few, kk, 'B');
    s += plateSheet('管制前', 72, {}, { x: BEACH.xs[0], y: 765, rot: -1.5, k: kk, id: 'la' });
    s += plateSheet('管制後', 72, { fill: K.YELLOW }, { x: BEACH.xs[1], y: 765, rot: 1.5, k: kk, id: 'lb' });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    let ph = 0;
    F.forEach((fr, i) => { if (k >= fr) ph = i; });
    const kp = k - F[ph];
    let s = '';
    if (ph <= 1) {                                 // 句91–92:兩欄板
      const grey = `hsl(${pal.h} 18% 84%)`;
      s += Ch.twoCol({ pal, u: U, x: 960, y: 450, w: 1740, h: 720, gap: 24, fs: 84, id: 'tc',
        left: { title: '有用', color: ph === 1 ? pal.main : grey }, right: { title: '沒那麼有用', color: grey } });
    } else if (ph === 2) s += scene93(pal, k, L[2]);
    else if (ph === 3) s += scene94(pal, k, L[3]);
    else if (ph === 4) s += scene95(pal, k, L[4]);
    else if (ph === 5) s += scene96(pal, k, L[5]);
    else s += scene97(pal, kp);
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_works', dur: 29.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
