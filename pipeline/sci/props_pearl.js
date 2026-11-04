/* ChannelC:pearl 片(珍珠醋酸澱粉)的圖解(扁平色塊剪紙)。純函式,不依賴 DOM 與 kit.js。
 * 每個函式 fn(pal, o) 回傳「以單位繪製、中心在原點」的紙片內容,由呼叫端包成紙片:
 *   K.paper(PP.cup(pal, {ice:true}), {x, y, scale: u, k: 'prop', id: 'cup', wide: PP.LIST.cup.wide})
 * LIST[名] = {fn, w, h, zh, wide}:w/h 為建議外框(單位)。bag.labelBox 為標籤可疊字區。
 * 外形片繼承紙片的紙白描邊;細節(N 結尾的函式)不描邊。只用 polygon/path/rect/circle/text。
 * 參數:cup {ice} / pearl {hard} / chain {tags:0–8, bend:0..1} / pot {steam:false} / rice {hard} / clock {h:小時,可帶小數=分} /
 *   germ {full} / bag {text} / tongue {ang}。不用漸層、亂數、時鐘。 */
(function () {
  const Y = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7';
  const C = {
    brown: 'hsl(24 52% 32%)', wood: 'hsl(24 55% 40%)', woodD: 'hsl(24 55% 30%)', kraft: 'hsl(38 62% 68%)', kraftD: 'hsl(36 55% 54%)',
    tan: 'hsl(38 40% 78%)', grey: 'hsl(200 8% 62%)', greyD: 'hsl(200 10% 38%)', greyL: 'hsl(200 14% 82%)', red: 'hsl(4 68% 52%)',
    gold: 'hsl(42 88% 50%)', goldL: 'hsl(44 92% 62%)', pearl: 'hsl(20 30% 14%)', pearlL: 'hsl(20 22% 42%)', water: 'hsl(200 80% 72%)',
    starch: 'hsl(45 60% 88%)', cer: 'hsl(200 55% 88%)',
  };
  const NS = ' stroke="none"';
  const f = (x) => +(+x).toFixed(2);
  const pt = (a) => a.map((p) => f(p[0]) + ',' + f(p[1])).join(' ');
  const poly = (a, fill, ex) => `<polygon points="${pt(a)}" fill="${fill}"${ex || ''}/>`;
  const rect = (x, y, w, h, fill, rx, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}"${rx ? ` rx="${f(rx)}"` : ''} fill="${fill}"${ex || ''}/>`;
  const circ = (cx, cy, r, fill, ex) => `<circle cx="${f(cx)}" cy="${f(cy)}" r="${f(r)}" fill="${fill}"${ex || ''}/>`;
  const path = (d, fill, ex) => `<path d="${d}" fill="${fill}"${ex || ''}/>`;
  const ell = (cx, cy, rx, ry, fill, ex) => path(`M ${f(cx - rx)} ${f(cy)} a ${f(rx)} ${f(ry)} 0 1 0 ${f(2 * rx)} 0 a ${f(rx)} ${f(ry)} 0 1 0 ${f(-2 * rx)} 0 Z`, fill, ex);
  const polyN = (a, fill) => poly(a, fill, NS), rectN = (x, y, w, h, fill, rx) => rect(x, y, w, h, fill, rx, NS);
  const circN = (cx, cy, r, fill) => circ(cx, cy, r, fill, NS), pathN = (d, fill) => path(d, fill, NS);
  const ellN = (cx, cy, rx, ry, fill) => ell(cx, cy, rx, ry, fill, NS);
  const g = (tr, s) => `<g transform="${tr}">${s}</g>`;
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle" dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  // 單色線(無描邊)
  const line = (d, w, col) => `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  // 粗線(紙白襯底加色線)
  const rope = (d, w, col) => line(d, w + 7, PAPER) + line(d, w, col);

  // ================= 飲料 =================
  // 手搖杯(透明杯、奶茶色、杯底黑珍珠、粗吸管、封膜)。o: {ice:true 加冰塊}
  function cup(pal, o) {
    o = o || {};
    let s = poly([[-45, -70], [45, -70], [33, 100], [-33, 100]], 'hsl(195 50% 90%)') + polyN([[-41, -45], [41, -45], [31, 96], [-31, 96]], 'hsl(28 55% 62%)');
    [[-24, 84], [-8, 84], [8, 84], [24, 84], [-16, 69], [0, 69], [16, 69], [-8, 54], [8, 54]].forEach((p) => { s += circN(p[0], p[1], 8, C.pearl) + circN(p[0] - 2.5, p[1] - 3, 2, C.pearlL); });
    if (o.ice) {
      [[-18, -26, 14], [16, -14, -10], [-4, 14, 24]].forEach((c) => {
        s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, rectN(-14, -14, 28, 28, 'hsl(195 60% 95%)', 5) + rectN(-9, -9, 9, 9, 'hsl(195 80% 99%)', 2));
      });
    }
    s += ellN(-30, 18, 4.5, 38, 'hsl(195 60% 98%)') + rectN(-40, -45, 80, 5, 'hsl(28 50% 72%)');
    s += g('translate(10 0) rotate(8)', rect(-8, -138, 16, 220, pal.main, 3) + rectN(-8, -138, 16, 6, INK, 2));
    s += path('M -46 -72 Q 0 -110 46 -72 Z', 'hsl(195 45% 94%)') + rect(-50, -82, 100, 14, 'hsl(195 30% 78%)', 6);
    s += g('translate(10 0) rotate(8)', rect(-8, -138, 16, 56, pal.main, 3) + rectN(-8, -138, 16, 6, INK, 2));
    return g('translate(0 18)', s);
  }

  // 單顆黑珍珠(高光)。o: {hard:true 灰硬、表面裂紋}
  function pearl(pal, o) {
    o = o || {};
    if (!o.hard) {
      return circ(0, 0, 62, C.pearl) + ellN(-20, -26, 22, 11, C.pearlL) + ellN(-24, -29, 9, 4.5, PAPER);
    }
    const cr = 'hsl(200 10% 82%)';
    return circ(0, 0, 62, 'hsl(200 6% 40%)') + circN(-8, -8, 38, 'hsl(200 6% 46%)') + ellN(-24, -30, 14, 6, 'hsl(200 8% 62%)') +
      line('M -4 -60 L -14 -30 L 6 -14 L -6 14 L 14 30 L 8 60', 4, cr) + line('M -14 -30 L -44 -24', 3.5, cr) + line('M 6 -14 L 38 -26', 3.5, cr) +
      line('M -6 14 L -40 30', 3.5, cr) + line('M 14 30 L 44 20', 3, cr);
  }

  // 醋瓶(深琥珀玻璃、紅蓋、紙標籤寫「醋」)
  function vinegar(pal) {
    let s = path('M -22 -100 L 22 -100 L 22 -62 Q 62 -40 62 0 L 62 86 Q 62 100 48 100 L -48 100 Q -62 100 -62 86 L -62 0 Q -62 -40 -22 -62 Z', 'hsl(24 65% 30%)');
    s += ellN(-46, -4, 5, 40, 'hsl(28 60% 50%)') + rectN(-18, -96, 6, 30, 'hsl(28 60% 46%)', 2);
    s += rect(-28, -124, 56, 28, C.red, 6) + rectN(-22, -118, 10, 16, 'hsl(4 70% 64%)', 3);
    s += rect(-47, -20, 94, 80, PAPER, 6) + rectN(-47, -20, 94, 12, pal.main, 3) + rectN(-47, 48, 94, 12, pal.main, 3) + txt('醋', 0, 20, 58, INK);
    return g('translate(0 11)', s);
  }

  // 老婆餅(圓餅、酥皮紋、芝麻)
  function wifecake() {
    let s = circ(0, 0, 90, 'hsl(36 70% 62%)') + circN(0, 0, 76, 'hsl(38 72% 70%)');
    [['M -34 0 A 34 34 0 0 1 0 -34', 0], ['M -56 0 A 56 56 0 0 1 0 -56', 0], ['M 0 58 A 58 58 0 0 0 58 0', 0], ['M 0 36 A 36 36 0 0 0 36 0', 0]].forEach((a) => { s += line(a[0], 5, 'hsl(32 55% 48%)'); });
    [[-50, 28, 'hsl(30 55% 52%)', 14], [30, -50, 'hsl(30 55% 52%)', 12], [52, 40, 'hsl(30 55% 52%)', 10]].forEach((b) => { s += circN(b[0], b[1], b[3], b[2]); });
    [[-20, -60, 20], [58, -8, 70], [-66, -12, 120], [10, 66, 5], [-34, 50, 160], [22, 16, 40]].forEach((p) => { s += g(`translate(${p[0]} ${p[1]}) rotate(${p[2]})`, ellN(0, 0, 5, 2.6, PAPER)); });
    return s;
  }

  // ================= 澱粉與添加物 =================
  // 澱粉鏈:一串 8 顆圓珠相連。o: {tags:n 顆掛小方塊零件(主色), bend:0..1 彎曲程度}
  const TAG_ORDER = [1, 4, 6, 2, 5, 7, 0, 3];
  function chain(pal, o) {
    o = o || {};
    const N = 8, P = 50, Lc = (N - 1) * P, bend = Math.max(0, Math.min(1, +o.bend || 0)), nt = Math.max(0, Math.min(N, o.tags | 0));
    const th = bend * Math.PI * 1.3, pts = [];
    for (let i = 0; i < N; i++) {
      const sI = (i - (N - 1) / 2) * P;
      let x = sI, y = 0;
      if (th > 1e-3) { const R = Lc / th, a = sI / R; x = R * Math.sin(a); y = R * (1 - Math.cos(a)); }
      y += bend * Math.sin(i * 2.1) * 10;
      pts.push([x, y]);
    }
    const tagged = TAG_ORDER.slice(0, nt);
    const lo = pts.map((p) => p[1] - 23), hi = pts.map((p, i) => p[1] + (tagged.indexOf(i) >= 0 ? 62 : 23)), my = (Math.min.apply(null, lo) + Math.max.apply(null, hi)) / 2;
    pts.forEach((p) => { p[1] -= my; });
    let s = line('M ' + pts.map((p) => f(p[0]) + ' ' + f(p[1])).join(' L '), 9, C.kraftD);
    pts.forEach((p, i) => {
      if (tagged.indexOf(i) >= 0) s += rect(p[0] - 1.5, p[1] + 16, 3, 18, INK) + rect(p[0] - 14, p[1] + 32, 28, 28, pal.main, 4) + rectN(p[0] - 8, p[1] + 38, 9, 9, pal.paper || PAPER, 2);
    });
    pts.forEach((p) => { s += circ(p[0], p[1], 23, C.starch) + ellN(p[0] - 8, p[1] - 9, 8, 4.5, PAPER); });
    return s;
  }

  // 小鎖頭(金色鎖身、灰色鎖環、鑰匙孔)
  function lock() {
    return rope('M -28 -6 L -28 -38 A 28 28 0 0 1 28 -38 L 28 -6', 14, C.greyD) + rect(-46, -8, 92, 78, C.gold, 12) + rectN(-38, -2, 76, 12, C.goldL, 5) +
      circN(0, 26, 10, INK) + polyN([[-5, 30], [5, 30], [8, 54], [-8, 54]], INK);
  }

  // 原料袋(牛皮紙袋、紙標籤)。o: {text:標籤字,預設「澱粉」}。labelBox 為標籤區
  const BAG_LABEL = { x: -58, y: -44, w: 116, h: 78 };
  function bag(pal, o) {
    o = o || {};
    const t = o.text == null ? '澱粉' : String(o.text), size = Math.min(44, 104 / Math.max(1, t.length));
    let s = path('M -70 -80 L 70 -80 Q 86 0 78 90 Q 0 106 -78 90 Q -86 0 -70 -80 Z', C.kraft);
    s += rect(-72, -96, 144, 26, C.kraftD, 4);
    for (let i = -60; i <= 60; i += 20) s += rectN(i - 5, -88, 10, 5, C.kraft, 2);
    s += rect(BAG_LABEL.x, BAG_LABEL.y, BAG_LABEL.w, BAG_LABEL.h, PAPER, 6) + rectN(BAG_LABEL.x, BAG_LABEL.y, BAG_LABEL.w, 8, pal.main, 3) +
      txt(t, 0, -2, size, INK);
    s += pathN('M -66 62 Q 0 74 66 62', C.kraftD) + rectN(-50, 44, 100, 5, C.kraftD, 2);
    return g('translate(0 -1)', s);
  }

  // ================= 烹煮與保存 =================
  // 大鍋(裡面一堆黑珍珠,冒熱氣)。o: {steam:false 無熱氣}
  function pot(pal, o) {
    o = o || {};
    let s = '';
    if (o.steam !== false) {
      [-56, 0, 56].forEach((x, i) => {
        const y0 = -100 - (i === 1 ? 14 : 0);
        s += line(`M ${x} ${y0} q 14 -18 0 -36 q -14 -18 0 -36`, 10, PAPER) + line(`M ${x} ${y0} q 14 -18 0 -36 q -14 -18 0 -36`, 5, 'hsl(200 20% 92%)');
      });
    }
    s += ell(0, -26, 108, 14, C.pearl);
    const rows = [[-44, [-84, -58, -32, -6, 20, 46, 72]], [-62, [-71, -45, -19, 7, 33, 59]], [-80, [-58, -32, -6, 20, 46]], [-97, [-45, -19, 7, 33]]];
    rows.forEach((r) => { r[1].forEach((x) => { s += circ(x, r[0], 14, C.pearl) + circN(x - 4, r[0] - 5, 3.4, C.pearlL); }); });
    s += path('M -108 -26 L 108 -26 L 98 82 Q 96 100 78 100 L -78 100 Q -96 100 -98 82 Z', C.greyD);
    s += rectN(-84, -10, 12, 80, C.grey, 4) + rectN(-52, 4, 108, 8, C.greyL, 3);
    s += rect(-122, -36, 244, 20, C.greyL, 8);
    s += rect(-140, 6, 34, 16, C.greyD, 6) + rect(106, 6, 34, 16, C.greyD, 6);
    return g(`translate(0 ${o.steam !== false ? 43 : 5})`, s);
  }

  // 一碗白飯。o: {hard:true 灰硬、裂紋}
  function rice(pal, o) {
    o = o || {};
    const col = o.hard ? 'hsl(200 8% 70%)' : 'hsl(45 40% 96%)', gr = o.hard ? 'hsl(200 8% 58%)' : 'hsl(45 20% 84%)';
    let s = rect(-30, 66, 60, 16, C.cer, 4) + path('M -100 -10 L 100 -10 C 100 50, 50 70, 0 70 C -50 70, -100 50, -100 -10 Z', C.cer) + rectN(-95, 6, 190, 9, 'hsl(210 60% 50%)');
    s += path('M -95 -10 C -95 -70, -40 -90, 0 -90 C 40 -90, 95 -70, 95 -10 Z', col);
    [[-70, -30], [-40, -52], [-10, -66], [28, -58], [60, -36], [-52, -14], [-20, -34], [20, -28], [52, -12], [0, -48], [-76, -50], [76, -52]].forEach((p, i) => {
      s += g(`translate(${p[0]} ${p[1]}) rotate(${i * 40})`, ellN(0, 0, 8, 3.5, gr));
    });
    if (o.hard) s += line('M -6 -88 L 4 -66 L -12 -46 L 2 -28 L -8 -12', 3.5, 'hsl(200 10% 40%)') + line('M 4 -66 L 36 -60', 3, 'hsl(200 10% 40%)') + line('M -12 -46 L -44 -40', 3, 'hsl(200 10% 40%)');
    return g('translate(0 4)', s);
  }

  // 圓時鐘。o: {h:小時;帶小數 = 分鐘,如 2.5 = 2:30,預設 3}
  function clock(pal, o) {
    o = o || {};
    const h = o.h == null ? 3 : +o.h, ha = (h % 12) * 30, ma = (h % 1) * 360;
    let s = circ(0, 0, 86, pal.main) + circN(0, 0, 74, PAPER);
    for (let i = 0; i < 12; i++) s += g(`rotate(${i * 30})`, rectN(-2.5, -70, 5, i % 3 === 0 ? 14 : 8, INK, 1));
    s += g(`rotate(${f(ma)})`, rectN(-3, -58, 6, 60, INK, 3)) + g(`rotate(${f(ha)})`, rectN(-4.5, -40, 9, 42, INK, 3));
    s += circ(0, 0, 8, C.red);
    return s;
  }

  // 細菌小人(圓身、兩眼、拿叉子、短腳)。o: {full:true 肚子鼓、飽足臉}
  function germ(pal, o) {
    o = o || {};
    const full = !!o.full, G = 'hsl(95 50% 48%)';
    let s = '';
    for (let i = 0; i < 10; i++) { const a = i * 36 * Math.PI / 180, r = full ? 74 : 66; s += circN(Math.cos(a) * r, Math.sin(a) * r - 4, 7, G); }
    s += rect(-30, 50, 16, 26, G, 6) + rect(14, 50, 16, 26, G, 6);
    s += full ? ell(0, 2, 74, 68, G) + circN(0, 26, 46, 'hsl(95 55% 62%)') + line('M -22 26 Q 0 40 22 26', 3.5, 'hsl(95 40% 36%)') : circ(0, -4, 60, G);
    // 叉子
    s += g('translate(70 14) rotate(14)', rect(-3, -84, 6, 112, C.greyL, 2) + rect(-14, -96, 28, 6, C.greyL, 2) + [-12, 0, 12].map((x) => rect(x - 2, -122, 4, 30, C.greyL, 2)).join(''));
    s += circ(52, 18, 11, G);
    s += circ(-22, -22, 15, PAPER) + circ(22, -22, 15, PAPER) + circN(-20, -20, 7, INK) + circN(24, -20, 7, INK);
    s += full ? path('M -12 -2 Q 0 14 12 -2 Q 0 6 -12 -2 Z', INK) : path('M -16 -4 Q 0 14 16 -4 Z', INK) + rectN(-8, -4, 16, 5, PAPER, 1);
    return g(`translate(${full ? -16 : -20} 16)`, s);
  }

  // 直立溫度計,刻度 7 與 60 之間塗警示色
  function thermo() {
    const Yv = (v) => 84 - v * 1.7, W = 'hsl(10 88% 54%)';
    let s = rect(-15, -112, 30, 200, PAPER, 15) + circ(0, 100, 30, PAPER);
    s += rectN(-9, Yv(60), 18, Yv(7) - Yv(60), W) + circN(0, 100, 22, W) + rectN(-9, Yv(7), 18, 100 - Yv(7), W);
    for (let v = 0; v <= 100; v += 10) s += rectN(15, Yv(v) - 1.5, v === 0 || v === 100 ? 14 : 9, 3, INK, 1);
    s += rectN(15, Yv(7) - 2, 20, 4, INK, 1) + rectN(15, Yv(60) - 2, 20, 4, INK, 1);
    s += txt('60', 56, Yv(60), 30, INK) + txt('7', 50, Yv(7), 30, INK);
    return g('translate(-22 -9)', s);
  }

  // ================= 工廠與身體 =================
  // 小工廠(鋸齒屋頂、煙囪、水龍頭沖洗)。o: {water:false 無水}
  function factory(pal, o) {
    o = o || {};
    let s = rect(-52, -150, 30, 124, C.red, 3) + rectN(-52, -122, 30, 12, PAPER) + rectN(-52, -88, 30, 12, PAPER);
    s += circ(-34, -168, 18, C.greyL) + circ(-14, -192, 14, C.greyL);
    s += rect(-120, -30, 200, 114, C.tan, 4);
    for (let i = 0; i < 3; i++) s += poly([[-120 + i * 67, -30], [-120 + i * 67, -70], [-53 + i * 67, -30]], pal.main);
    [-96, -50, 6].forEach((x) => { s += rectN(x, -8, 34, 28, Y, 3); });
    s += rectN(40, 20, 28, 64, C.woodD, 3);
    // 水龍頭與水
    s += rect(80, 10, 52, 16, C.grey, 3) + rect(116, 10, 18, 40, C.grey, 4) + rect(112, 48, 26, 10, C.greyD, 3);
    if (o.water !== false) s += rectN(121, 60, 8, 20, C.water) + circN(125, 90, 5, C.water) + circN(117, 74, 3.5, C.water) + circN(133, 76, 3.5, C.water);
    s += rect(-130, 84, 280, 12, C.greyD, 3);
    return g('translate(-9 55)', s);
  }

  // 話筒(老式電話聽筒)
  function phone() {
    let s = rect(-80, -34, 160, 40, INK, 18) + rect(-92, -14, 48, 62, INK, 16) + rect(44, -14, 48, 62, INK, 16);
    s += rectN(-72, -28, 100, 8, 'hsl(0 0% 36%)', 4);
    [-76, -68, -60].forEach((x) => { s += circN(x + 4, 32, 3, 'hsl(0 0% 40%)'); });
    [52, 60, 68].forEach((x) => { s += circN(x + 4, 32, 3, 'hsl(0 0% 40%)'); });
    return g('translate(0 -6) rotate(-14)', s);
  }

  // 舌頭(粉紅、中溝、顆粒)。o: {ang:旋轉角度}
  function tongue(pal, o) {
    o = o || {};
    let s = path('M -48 -60 L 48 -60 L 48 -10 Q 48 70 0 70 Q -48 70 -48 -10 Z', 'hsl(350 70% 70%)') + line('M 0 -56 L 0 34', 4, 'hsl(350 55% 52%)');
    [[-26, -10], [24, -22], [-20, 30], [26, 22], [-30, 48], [30, 46], [0, 54]].forEach((p) => { s += circN(p[0], p[1], 4.5, 'hsl(350 62% 80%)'); });
    return g(`rotate(${+o.ang || 0})`, g('translate(0 -4)', s));
  }

  // 放大鏡(檢驗)
  function lens() {
    let s = g('translate(-16 -16) rotate(-45)', rect(-12, 66, 24, 84, C.wood, 8) + rectN(-12, 66, 24, 16, C.woodD, 4));
    s += circ(-16, -16, 72, C.greyD) + circN(-16, -16, 58, 'hsl(195 60% 90%)') + line('M -52 -30 A 40 40 0 0 1 -26 -54', 7, PAPER);
    return g('translate(-5 -5)', s);
  }

  // ================= 食物(各一) =================
  // 麵(碗、麵條、筷子)
  function noodle() {
    let s = g('translate(30 -40) rotate(34)', rect(-3, -90, 6, 150, C.wood, 2)) + g('translate(44 -44) rotate(28)', rect(-3, -90, 6, 150, C.woodD, 2));
    s += rect(-26, 66, 52, 14, C.cer, 4) + path('M -96 -8 L 96 -8 C 96 50, 50 72, 0 72 C -50 72, -96 50, -96 -8 Z', C.cer) + rectN(-91, 8, 182, 8, 'hsl(210 60% 50%)');
    s += path('M -88 -8 C -88 -62, -40 -78, 0 -78 C 40 -78, 88 -62, 88 -8 Z', 'hsl(44 85% 72%)');
    ['M -70 -20 Q -40 -50 -10 -24 T 50 -30', 'M -60 -40 Q -20 -66 20 -42 T 76 -26', 'M -78 -12 Q -30 -34 10 -12 T 80 -10'].forEach((d) => { s += line(d, 4, 'hsl(40 60% 54%)'); });
    return g('translate(0 23)', s);
  }

  // 冷凍食品盒(藍盒、雪花、「冷凍」)
  function frozen(pal) {
    let s = rect(-80, -62, 160, 134, 'hsl(205 70% 52%)', 10) + rectN(-80, -62, 160, 22, 'hsl(205 70% 66%)', 8);
    s += circN(0, -4, 42, PAPER);
    [0, 60, 120].forEach((a) => { s += g(`translate(0 -4) rotate(${a})`, rectN(-2.5, -34, 5, 68, 'hsl(205 70% 52%)', 2) + rectN(-12, -26, 24, 4, 'hsl(205 70% 52%)', 2) + rectN(-12, 22, 24, 4, 'hsl(205 70% 52%)', 2)); });
    s += txt('冷凍', 0, 50, 28, PAPER);
    return g('translate(0 -4)', s);
  }

  // 香腸(烤痕、高光)
  function sausage() {
    const d = 'M -92 22 Q 0 -34 92 22';
    let s = rope(d, 46, 'hsl(10 58% 42%)') + line('M -80 6 Q 0 -44 80 6', 8, 'hsl(10 55% 58%)');
    [0.2, 0.4, 0.6, 0.8].forEach((t) => {
      const x = -92 + 184 * t, y = 22 - 112 * t * (1 - t), sl = Math.atan2(-112 * (1 - 2 * t), 184) * 180 / Math.PI;
      s += g(`translate(${f(x)} ${f(y)}) rotate(${f(sl)})`, rectN(-3, -17, 6, 34, 'hsl(10 50% 22%)', 2));
    });
    return s;
  }

  // 魚丸串(竹籤、三顆魚丸)
  function fishball() {
    let s = rect(-4, -112, 8, 224, 'hsl(38 55% 70%)', 3) + polyN([[-4, 100], [4, 100], [0, 116]], 'hsl(38 55% 70%)');
    [-66, -6, 54].forEach((y) => { s += circ(0, y, 33, 'hsl(40 40% 91%)') + ellN(-12, y - 14, 9, 5, PAPER) + circN(10, y + 8, 2.6, 'hsl(36 40% 74%)') + circN(-8, y + 14, 2.2, 'hsl(36 40% 74%)') + circN(14, y - 8, 2, 'hsl(36 40% 74%)'); });
    return s;
  }

  // 水餃(半月形、捏褶)
  function dumpling() {
    let s = path('M -92 18 C -92 -58, 92 -58, 92 18 C 62 52, -62 52, -92 18 Z', 'hsl(42 50% 95%)');
    for (let i = 0; i < 7; i++) {
      const x = -66 + i * 22, y = -30 + Math.abs(i - 3) * 6;
      s += line(`M ${x} ${y} Q ${x + 6} ${y + 14} ${x + 2} ${y + 26}`, 4, 'hsl(40 30% 70%)');
    }
    s += line('M -70 28 Q 0 46 70 28', 3, 'hsl(40 30% 82%)');
    return g('translate(0 -2)', s);
  }

  // 名稱 → {fn, w, h(建議外框,單位), zh(總表上的名稱), wide}
  const LIST = {
    cup: { fn: cup, w: 116, h: 242, zh: '手搖杯' }, pearl: { fn: pearl, w: 126, h: 126, zh: '黑珍珠' }, vinegar: { fn: vinegar, w: 128, h: 230, zh: '醋瓶' },
    wifecake: { fn: wifecake, w: 182, h: 182, zh: '老婆餅' }, chain: { fn: chain, w: 420, h: 180, zh: '澱粉鏈', wide: true }, lock: { fn: lock, w: 96, h: 140, zh: '小鎖頭' },
    pot: { fn: pot, w: 284, h: 292, zh: '大鍋' }, rice: { fn: rice, w: 204, h: 176, zh: '白飯' }, clock: { fn: clock, w: 176, h: 176, zh: '時鐘' },
    germ: { fn: germ, w: 200, h: 190, zh: '細菌小人' }, thermo: { fn: thermo, w: 110, h: 246, zh: '溫度計' }, bag: { fn: bag, w: 166, h: 198, zh: '原料袋', labelBox: BAG_LABEL },
    phone: { fn: phone, w: 200, h: 130, zh: '話筒' }, tongue: { fn: tongue, w: 110, h: 140, zh: '舌頭' }, factory: { fn: factory, w: 284, h: 306, zh: '小工廠' },
    noodle: { fn: noodle, w: 196, h: 209, zh: '麵' }, frozen: { fn: frozen, w: 164, h: 138, zh: '冷凍食品' }, sausage: { fn: sausage, w: 188, h: 50, zh: '香腸' },
    fishball: { fn: fishball, w: 70, h: 232, zh: '魚丸串' }, dumpling: { fn: dumpling, w: 190, h: 90, zh: '水餃' }, lens: { fn: lens, w: 190, h: 190, zh: '放大鏡' },
  };

  const API = { C, LIST };
  Object.keys(LIST).forEach((n) => { API[n] = LIST[n].fn; });
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.PropsPearl = API;
})();
