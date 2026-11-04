/* ChannelC:snack 片(小吃漲價)的圖解(扁平色塊剪紙)。純函式,不依賴 DOM 與 kit.js。
 * 每個函式 fn(pal, o) 回傳「以單位繪製、中心在原點」的紙片內容,由呼叫端包成紙片:
 *   K.paper(PS.stall(pal, {sign:'骰子牛'}), {x, y, scale: u, k: 'prop', id: 'stall', wide: PS.LIST.stall.wide})
 * LIST[名] = {fn, w, h, zh, wide}:w/h 為建議外框(單位),wide = 扁長(紙片濾鏡要放寬)。
 * 有可疊字的留白區者另有矩形(單位,中心原點座標系):stall.signBox、payEnvelope.labelBox。
 * 外形片繼承紙片的紙白描邊;細節(N 結尾的函式)不描邊。只用 polygon/path/rect/circle/text(舞台量外框只認這些)。
 * 顏色:pal(K.palette(24))加固定色(品牌黃、墨、紙白)與 C 的輔助色。不用漸層、亂數、時鐘。
 * 唯一跨檔依賴:taiwan4 呼叫 PropsTurtle.taiwan / twXY(舞台先載入 props_turtle.js)。 */
(function () {
  const Y = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7';
  const C = {
    brown: 'hsl(24 52% 32%)', brownL: 'hsl(26 50% 44%)', wood: 'hsl(24 55% 40%)', woodD: 'hsl(24 55% 30%)', kraft: 'hsl(38 62% 68%)', kraftD: 'hsl(36 55% 54%)',
    tan: 'hsl(38 40% 78%)', grey: 'hsl(200 8% 62%)', greyD: 'hsl(200 10% 38%)', greyL: 'hsl(200 14% 82%)', red: 'hsl(4 68% 52%)',
    gold: 'hsl(42 88% 50%)', goldL: 'hsl(44 92% 62%)', night: 'hsl(24 45% 14%)',
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
  // 粗線(紙白襯底加色線)
  const rope = (d, w, col) => `<path d="${d}" fill="none" stroke="${PAPER}" stroke-width="${f(w + 7)}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;

  // ================= 夜市 =================
  // 夜市攤車(兩輪推車、遮雨棚、棚下橫招牌、檯面)。o: {sign:2–4 字, awning:棚色, lit:true}。招牌字內嵌;signBox 為招牌區
  const STALL_SIGN = { x: -100, y: -70, w: 200, h: 48 };
  function stall(pal, o) {
    o = o || {};
    const lit = o.lit !== false, aw = o.awning || pal.main, sign = o.sign == null ? '骰子牛' : String(o.sign);
    let s = rectN(-132, -82, 264, 110, lit ? 'hsl(40 95% 76%)' : 'hsl(24 18% 38%)');           // 棚下背板(亮燈時暖光)
    [-96, 96].forEach((x) => { s += circ(x, 122, 28, INK) + circN(x, 122, 11, C.grey); });
    s += rect(-140, 36, 280, 80, C.wood, 6) + rectN(-126, 50, 252, 52, C.woodD, 4) + rectN(-24, 70, 48, 8, Y, 4);
    s += rect(-146, -80, 10, 106, C.greyD, 3) + rect(136, -80, 10, 106, C.greyD, 3);
    s += rect(-152, 22, 304, 18, C.tan, 5);
    // 檯面上:鐵盤與肉塊、湯鍋
    s += rect(-118, 6, 104, 16, C.greyL, 4);
    [-106, -82, -58, -34].forEach((x) => { s += rectN(x - 10, -8, 22, 16, C.brown, 3); });
    s += rect(36, -8, 76, 30, C.greyD, 6) + ellN(74, -8, 38, 6, 'hsl(24 60% 50%)');
    // 遮雨棚:梯形加下緣半圓,單數格換紙白
    const N = 8, bw = 330 / N, tw = 280 / N, r = bw / 2;
    let d = 'M -165 -100 L -140 -155 L 140 -155 L 165 -100';
    for (let i = N - 1; i >= 0; i--) d += ` A ${f(r)} ${f(r)} 0 0 1 ${f(-165 + i * bw)} -100`;
    s += path(d + ' Z', aw);
    for (let i = 1; i < N; i += 2) {
      const xb0 = -165 + i * bw, xb1 = xb0 + bw, xt0 = -140 + i * tw, xt1 = xt0 + tw;
      s += pathN(`M ${f(xt0)} -155 L ${f(xt1)} -155 L ${f(xb1)} -100 A ${f(r)} ${f(r)} 0 0 1 ${f(xb0)} -100 Z`, 'hsl(40 60% 96%)');
    }
    // 棚下兩顆燈泡
    [-122, 122].forEach((x) => { s += rectN(x - 1.5, -82, 3, 7, INK) + circ(x, -68, 9, lit ? Y : C.greyL); });
    // 招牌
    s += rect(STALL_SIGN.x, STALL_SIGN.y, STALL_SIGN.w, STALL_SIGN.h, INK, 6) +
      txt(sign, 0, STALL_SIGN.y + STALL_SIGN.h / 2 + 2, Math.min(46, Math.floor(176 / Math.max(1, sign.length))), lit ? Y : 'hsl(40 15% 62%)');
    return s;
  }

  // 一串燈泡(下垂的線加 n 顆)。o: {n:8, w:900, sag:40, on:true}。線兩端在 y=0,整體垂直置中
  function bulbString(pal, o) {
    o = o || {};
    const n = o.n || 8, w = o.w || 900, sag = o.sag == null ? 40 : o.sag, on = o.on !== false, cy = 2 * sag;
    const X = (t) => (w / 2) * (2 * t - 1), Yy = (t) => 2 * (1 - t) * t * cy;
    let s = rope(`M ${f(-w / 2)} 0 Q 0 ${f(cy)} ${f(w / 2)} 0`, 5, INK);
    for (let i = 0; i < n; i++) {
      const t = (i + 0.5) / n, x = X(t), y = Yy(t);
      s += g(`translate(${f(x)} ${f(y)})`, rect(-5, -2, 10, 13, INK, 2) + circ(0, 27, 17, on ? Y : C.greyL) + (on ? ellN(-6, 21, 4.5, 6.5, PAPER) : ''));
    }
    return g(`translate(0 ${f(-(sag + 40) / 2)})`, s);
  }

  // 百元鈔(橫向紅鈔,左右「100」,中間橢圓留白,不畫人像)
  function bill100() {
    return rect(-150, -70, 300, 140, 'hsl(2 66% 52%)', 8) + rectN(-140, -60, 280, 120, 'hsl(2 58% 60%)', 5) +
      ellN(0, 0, 52, 50, 'hsl(10 70% 90%)') + ellN(0, 0, 44, 42, 'hsl(6 60% 82%)') +
      txt('100', -96, -2, 44, 'hsl(10 80% 94%)') + txt('100', 96, -2, 44, 'hsl(10 80% 94%)') +
      rectN(-130, 40, 60, 5, 'hsl(2 50% 70%)', 2) + rectN(70, 40, 60, 5, 'hsl(2 50% 70%)', 2) + rectN(-130, -48, 60, 5, 'hsl(2 50% 70%)', 2) + rectN(70, -48, 60, 5, 'hsl(2 50% 70%)', 2);
  }
  // 50 元硬幣(金黃)、10 元硬幣(銀灰、較小)
  function coin50() {
    return circ(0, 0, 50, C.gold) + circN(0, 0, 42, C.goldL) + circN(0, 0, 38, C.gold) + txt('50', 0, 2, 46, 'hsl(30 65% 24%)');
  }
  function coin10() {
    return circ(0, 0, 42, 'hsl(200 6% 66%)') + circN(0, 0, 35, C.greyL) + circN(0, 0, 31, 'hsl(200 8% 72%)') + txt('10', 0, 2, 36, C.greyD);
  }

  // 骰子牛紙盒(淺紙盒裡 8 塊褐色方塊肉、兩支竹籤)
  function diceBeef(pal) {
    const cube = (x, y, a) => g(`translate(${x} ${y}) rotate(${a})`, rect(-17, -17, 34, 34, C.brown, 5) + rectN(-12, -12, 24, 9, C.brownL, 3));
    let s = '';
    [[-44, -84, -5], [44, -84, 6], [-66, -54, -6], [-22, -56, 5], [22, -56, -4], [66, -54, 7], [-44, -28, 4], [0, -30, -6], [44, -28, 5]].slice(0, 8).forEach((c) => { s += cube(c[0], c[1], c[2]); });
    s += poly([[56, -42], [62, -45], [92, -126], [86, -128]], 'hsl(40 55% 60%)') + poly([[-24, -30], [-18, -34], [-46, -122], [-52, -120]], 'hsl(40 55% 60%)');
    s += poly([[-100, -8], [100, -8], [84, 70], [-84, 70]], 'hsl(40 45% 86%)') + rectN(-92, 18, 184, 14, pal.main) + rect(-106, -14, 212, 12, 'hsl(38 40% 72%)', 3);
    return g('translate(0 28)', s);
  }

  // ================= 辦公 =================
  // 資料夾(牛皮紙)。o: {open:false, label:'', noLabel:false}。open 時掀開露出白紙;noLabel 不畫正面白標籤
  function folder(pal, o) {
    o = o || {};
    const open = !!o.open, lab = o.label ? String(o.label) : '', nl = !!o.noLabel;
    let s = poly([[-112, -88], [-56, -88], [-42, -72], [112, -72], [112, 82], [-112, 82]], C.kraftD);
    if (open) {
      s += g('rotate(2)', rect(-92, -84, 196, 130, 'hsl(40 22% 88%)', 3)) + g('rotate(-3)', rect(-96, -76, 196, 126, PAPER, 3));
      for (let i = 0; i < 4; i++) s += g('rotate(-3)', rectN(-76, -52 + i * 22, i === 3 ? 90 : 150, 6, C.greyL, 3));
      s += poly([[-112, 16], [112, 16], [122, 84], [-122, 84]], C.kraft);
      if (!nl) s += rectN(-48, 36, 96, 30, PAPER, 3) + (lab ? txt(lab, 0, 52, Math.min(24, Math.floor(88 / lab.length)), INK) : '');
    } else {
      s += rect(-112, -62, 224, 144, C.kraft, 6);
      if (!nl) s += rectN(-64, -8, 128, 50, PAPER, 4) + (lab ? txt(lab, 0, 18, Math.min(32, Math.floor(120 / lab.length)), INK) : '');
    }
    return s;
  }

  // 鬧鐘(指針指 7 點)
  function alarm() {
    let s = '';
    [-1, 1].forEach((d) => { s += circ(52 * d, -54, 26, C.gold) + circN(52 * d, -54, 17, C.goldL) + g(`translate(${46 * d} 74) rotate(${-30 * d})`, rect(-6, -14, 12, 38, INK, 5)); });
    s += rect(-7, -96, 14, 22, C.greyD, 4) + circ(0, 0, 72, C.red) + circN(0, 0, 58, PAPER);
    for (let i = 0; i < 12; i++) s += g(`rotate(${i * 30})`, rectN(i % 3 === 0 ? -3 : -2, -54, i % 3 === 0 ? 6 : 4, i % 3 === 0 ? 12 : 8, INK, 1.5));
    s += g('rotate(210)', rectN(-4.5, -32, 9, 36, INK, 4)) + rectN(-3, -46, 6, 50, INK, 3) + circN(0, 0, 7, C.red);
    return s;
  }

  // 記錄板(板夾加紙、三條橫線)
  function clipboard() {
    return rect(-70, -95, 140, 190, C.wood, 8) + rectN(-56, -70, 112, 152, PAPER, 3) +
      rectN(-42, -42, 84, 8, C.greyD, 4) + rectN(-42, -12, 84, 8, C.greyD, 4) + rectN(-42, 18, 56, 8, C.greyD, 4) + rectN(-42, 48, 70, 8, C.greyL, 4) +
      rect(-32, -110, 64, 32, C.greyD, 6) + rectN(-20, -102, 40, 10, C.greyL, 4);
  }

  // 薪資袋(牛皮紙信封、封口、正面白色標籤區)。labelBox 為標籤區
  const ENV_LABEL = { x: -78, y: 28, w: 156, h: 32 };
  function payEnvelope() {
    return rect(-110, -70, 220, 140, C.kraft, 8) + polyN([[-110, -70], [110, -70], [0, 12]], C.kraftD) + polyN([[-110, 70], [-18, 6], [-6, 14]], 'hsl(38 55% 60%)') + polyN([[110, 70], [18, 6], [6, 14]], 'hsl(38 55% 60%)') +
      circN(0, 10, 9, C.red) + rectN(ENV_LABEL.x, ENV_LABEL.y, ENV_LABEL.w, ENV_LABEL.h, PAPER, 4);
  }

  // 計算機(深色機身、淺色顯示窗、4×4 按鍵)
  function calculator(pal) {
    let s = rect(-60, -90, 120, 180, 'hsl(215 12% 25%)', 12) + rectN(-48, -76, 96, 36, 'hsl(90 40% 82%)', 4) + rectN(20, -64, 20, 6, 'hsl(215 12% 25%)', 2) + rectN(8, -54, 32, 6, 'hsl(215 12% 25%)', 2);
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) {
      const col = c === 3 ? (r === 3 ? Y : pal.main) : C.greyL;
      s += rectN(-48 + c * 25.33, -26 + r * 26, 20, 20, col, 4);
    }
    return s;
  }

  // ================= 食物 =================
  // 雞排(大片不規則金黃炸物裝在紙袋裡,露出上半)
  function chickenCutlet(pal) {
    let s = poly([[-112, -10], [-102, -58], [-66, -88], [-24, -84], [14, -104], [60, -90], [98, -64], [114, -24], [104, 24], [0, 34], [-96, 26]], 'hsl(36 88% 55%)');
    [[-80, -50, 9, 'hsl(32 80% 42%)'], [-40, -66, 7, 'hsl(44 92% 72%)'], [-6, -52, 10, 'hsl(32 80% 42%)'], [34, -76, 8, 'hsl(44 92% 72%)'], [66, -48, 11, 'hsl(32 80% 42%)'],
      [92, -22, 7, 'hsl(44 92% 72%)'], [-96, -14, 7, 'hsl(44 92% 72%)'], [-58, -22, 9, 'hsl(44 92% 72%)'], [14, -22, 8, 'hsl(32 80% 42%)'], [46, -14, 7, 'hsl(44 92% 72%)'], [-20, -10, 6, 'hsl(32 80% 42%)']]
      .forEach((c) => { s += circN(c[0], c[1], c[2], c[3]); });
    s += poly([[-82, 0], [82, 0], [66, 104], [-66, 104]], 'hsl(38 50% 80%)') + rectN(-82, 0, 164, 8, 'hsl(38 45% 68%)') + rectN(-70, 44, 140, 22, pal.main);
    return s;
  }

  // 手搖杯珍奶(透明杯、奶茶色、底部黑珍珠、粗吸管、封膜)
  function bobaCup(pal) {
    let s = poly([[-45, -70], [45, -70], [33, 100], [-33, 100]], 'hsl(195 50% 90%)') + polyN([[-41, -45], [41, -45], [31, 96], [-31, 96]], 'hsl(28 55% 62%)');
    const pearl = 'hsl(20 30% 14%)';
    [[-24, 84], [-8, 84], [8, 84], [24, 84], [-16, 69], [0, 69], [16, 69], [-8, 54], [8, 54]].forEach((p) => { s += circN(p[0], p[1], 8, pearl); });
    s += ellN(-30, 18, 4.5, 38, 'hsl(195 60% 98%)') + rectN(-40, -45, 80, 5, 'hsl(28 50% 72%)');
    s += g('translate(10 0) rotate(8)', rect(-8, -138, 16, 220, pal.main, 3) + rectN(-8, -138, 16, 6, INK, 2));
    s += path('M -46 -72 Q 0 -110 46 -72 Z', 'hsl(195 45% 94%)') + rect(-50, -82, 100, 14, 'hsl(195 30% 78%)', 6);
    s += g('translate(10 0) rotate(8)', rect(-8, -138, 16, 56, pal.main, 3) + rectN(-8, -138, 16, 6, INK, 2));
    return g('translate(0 18)', s);
  }

  // 滷肉飯(碗、白飯、褐色滷肉、一片黃蘿蔔)
  function braisedPorkRice() {
    const cer = 'hsl(200 55% 88%)';
    let s = rect(-30, 86, 60, 16, cer, 4) + path('M -100 -10 L 100 -10 C 100 60, 50 90, 0 90 C -50 90, -100 60, -100 -10 Z', cer) + rectN(-95, 8, 190, 9, 'hsl(210 60% 50%)') + rectN(-82, 34, 164, 5, 'hsl(210 60% 62%)');
    s += path('M -95 -10 C -95 -70, -40 -90, 0 -90 C 40 -90, 95 -70, 95 -10 Z', 'hsl(45 40% 94%)');
    [[-70, -30], [-40, -14], [50, -20], [78, -34], [10, -12], [-82, -46]].forEach((p, i) => { s += g(`translate(${p[0]} ${p[1]}) rotate(${i * 40})`, ellN(0, 0, 8, 3.5, 'hsl(45 20% 84%)')); });
    s += pathN('M -72 -42 C -72 -80, -30 -92, 0 -90 C 38 -92, 74 -78, 72 -42 C 60 -24, 40 -34, 28 -22 C 14 -34, -14 -20, -30 -32 C -46 -22, -62 -26, -72 -42 Z', 'hsl(22 60% 26%)');
    [[-40, -62, 17, 11], [4, -74, 20, 12], [40, -58, 16, 11], [-8, -46, 14, 9]].forEach((c) => { s += ellN(c[0], c[1], c[2], c[3], 'hsl(24 55% 38%)'); });
    [[-30, -70, 6, 3.5], [22, -62, 6, 3.5], [48, -48, 5, 3]].forEach((c) => { s += ellN(c[0], c[1], c[2], c[3], 'hsl(36 60% 76%)'); });
    s += g('translate(60 -56) rotate(28)', rect(-20, -10, 40, 20, 'hsl(50 95% 60%)', 5) + rectN(-12, -4, 24, 4, 'hsl(46 90% 70%)', 2));
    return g('translate(0 -6)', s);
  }

  // 地瓜球。o: {cut:false, bubble:0.3, skin:0.5, hollow:0}
  // 氣泡位置(單位 = 麵糰半徑 ri):中心一顆、內圈六顆、外圈六顆小的;半徑在畫的時候依上限與間距裁小
  const BUB = (() => {
    const a = [[0, 0, 0.30]];
    [0.24, 0.22, 0.25, 0.21, 0.24, 0.22].forEach((r, i) => { const t = i * Math.PI / 3 + 0.2; a.push([0.62 * Math.cos(t), 0.62 * Math.sin(t), r]); });
    [0.10, 0.09, 0.11, 0.10, 0.09, 0.10].forEach((r, i) => { const t = i * Math.PI / 3 + 0.2 + Math.PI / 6; a.push([0.79 * Math.cos(t), 0.79 * Math.sin(t), r]); });
    return a;
  })();
  function sweetBall(pal, o) {
    o = o || {};
    const bub = o.bubble == null ? 0.3 : o.bubble, sk = o.skin == null ? 0.5 : o.skin, hol = o.hollow || 0;
    const R = 60 * (1 + 0.5 * Math.max(0, Math.min(1, bub)));
    if (!o.cut) {
      let s = circ(0, 0, R, 'hsl(36 85% 52%)');
      [[-0.45, -0.35, 0.1], [0.3, -0.5, 0.08], [0.55, 0.1, 0.11], [-0.2, 0.3, 0.1], [0.15, 0.62, 0.07], [-0.62, 0.2, 0.07], [0.05, -0.1, 0.08]].forEach((c) => { s += circN(c[0] * R, c[1] * R, c[2] * R, 'hsl(32 75% 42%)'); });
      return s + ellN(-0.4 * R, -0.5 * R, 0.16 * R, 0.1 * R, 'hsl(44 92% 72%)');
    }
    const ri = R - R * (0.08 + 0.30 * Math.max(0, Math.min(1, sk))), sc = 0.25 + 1.25 * Math.max(0, Math.min(1, bub));
    let s = circ(0, 0, R, 'hsl(32 80% 46%)') + circN(0, 0, ri, 'hsl(46 85% 82%)');
    // 氣泡半徑上限 0.27 ri,且與皮、相鄰氣泡保留 ≥ 4 單位間距;裁到太小就不畫
    const gap = 4 / ri, put = [];
    BUB.forEach((b) => {
      let r = Math.min(b[2] * sc, 0.27, 1 - Math.hypot(b[0], b[1]) - gap);
      put.forEach((q) => { r = Math.min(r, Math.hypot(b[0] - q[0], b[1] - q[1]) - q[2] - gap); });
      if (r < 0.04) return;
      put.push([b[0], b[1], r]);
      s += circN(b[0] * ri, b[1] * ri, r * ri, 'hsl(40 70% 70%)');
    });
    if (hol > 0) s += circN(0, 0, ri * Math.min(1, hol), 'hsl(40 70% 70%)');
    return s;
  }

  // 夜市牛排鐵板(黑鐵板加木托盤、牛排帶烤紋)。o: {side:'potato'|'noodle', egg:false}
  function steakPlate(pal, o) {
    o = o || {};
    let s = rect(-140, -78, 280, 156, C.wood, 18) + ell(0, 0, 118, 64, 'hsl(20 10% 14%)') + ellN(0, 0, 104, 54, 'hsl(20 8% 22%)');
    s += polyN([[-80, -30], [-30, -42], [18, -34], [34, -8], [20, 26], [-30, 34], [-78, 20]], 'hsl(18 55% 30%)');
    [-62, -40, -18].forEach((x) => { s += g(`translate(${x} -4) rotate(-35)`, rectN(-22, -3, 44, 6, 'hsl(15 50% 17%)', 3)); });
    if (o.side === 'noodle') {
      s += ellN(70, -12, 32, 22, 'hsl(46 85% 76%)');
      [['M 46 -16 C 56 -30, 66 -4, 78 -18 S 92 -8, 98 -14'], ['M 44 -8 C 56 -20, 64 4, 78 -8 S 94 2, 96 -4'], ['M 50 0 C 60 -10, 70 10, 82 0'], ['M 52 -24 C 62 -34, 72 -14, 84 -26']]
        .forEach((d) => { s += `<path d="${d[0]}" fill="none" stroke="hsl(42 80% 60%)" stroke-width="4" stroke-linecap="round"/>`; });
    } else {
      [[62, -30, 20], [88, -8, -14], [58, -6, 36]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, rectN(-15, -12, 30, 24, 'hsl(42 75% 62%)', 7) + rectN(-9, -7, 14, 7, 'hsl(46 85% 74%)', 3)); });
    }
    if (o.egg) s += pathN('M 44 30 C 40 14, 66 10, 82 18 C 98 26, 90 46, 66 47 C 54 47, 46 42, 44 30 Z', 'hsl(50 30% 98%)') + circN(66, 30, 10, 'hsl(40 95% 55%)') + circN(63, 27, 3, 'hsl(48 100% 75%)');
    return s;
  }

  // ================= 台灣四城 =================
  // 台灣輪廓加四個城市點。o: {on:[1,1,1,1], greyRest:true}。城市:臺北、新北、臺中、高雄。城市名不在圖內
  const PT = () => (typeof window !== 'undefined' && window.PropsTurtle) || require('./props_turtle.js');
  const CITY_COL = ['hsl(210 75% 52%)', 'hsl(135 55% 42%)', 'hsl(24 90% 52%)', 'hsl(280 55% 52%)'];
  // 回傳各點座標(同圖解座標系);新北畫在臺北西南側避免重疊,高雄略往內陸
  function taiwan4Pos() {
    const xy = PT().twXY, p = [xy(121.56, 25.04), xy(121.46, 25.01), xy(120.68, 24.14), xy(120.31, 22.63)];
    return [{ name: '臺北', x: p[0][0] + 4, y: p[0][1] - 2 }, { name: '新北', x: p[1][0] - 12, y: p[1][1] + 14 }, { name: '臺中', x: p[2][0], y: p[2][1] },
      { name: '高雄', x: p[3][0] + 7, y: p[3][1] }];
  }
  function taiwan4(pal, o) {
    o = o || {};
    const on = o.on || [1, 1, 1, 1], grey = o.greyRest !== false;
    let s = PT().taiwan(pal, { fill: pal.pad });
    taiwan4Pos().forEach((c, i) => {
      if (on[i]) s += circ(c.x, c.y, 10, CITY_COL[i]);
      else if (grey) s += circ(c.x, c.y, 10, C.grey);
    });
    return s;
  }

  // ================= 第二批:食物 =================
  const CER = 'hsl(200 55% 88%)', PLATE = 'hsl(205 40% 90%)', PLATE_IN = 'hsl(205 35% 80%)';
  const line = (d, w, col) => `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  // 碗身路徑:上緣在 y0、半寬 rx、深 dep
  const bowlD = (rx, y0, dep) => `M ${f(-rx)} ${f(y0)} L ${f(rx)} ${f(y0)} C ${f(rx)} ${f(y0 + dep * 0.7)} ${f(rx * 0.55)} ${f(y0 + dep)} 0 ${f(y0 + dep)} C ${f(-rx * 0.55)} ${f(y0 + dep)} ${f(-rx)} ${f(y0 + dep * 0.7)} ${f(-rx)} ${f(y0)} Z`;
  // 麵條(幾條波浪線),中心 (cx,cy),寬 w
  const noodles = (cx, cy, w, col) => [0, 1, 2, 3].map((k) => line(`M ${f(cx - w / 2)} ${f(cy + k * 6 - 9)} q ${f(w / 8)} -9 ${f(w / 4)} 0 t ${f(w / 4)} 0 t ${f(w / 4)} 0 t ${f(w / 4)} 0`, 3.5, col)).join('');
  const eggShape = (x, y, col) => g(`translate(${x} ${y})`, path('M 0 -32 C 20 -32 26 -4 26 10 C 26 26 14 32 0 32 C -14 32 -26 26 -26 10 C -26 -4 -20 -32 0 -32 Z', col) + ellN(-9, -8, 5, 9, 'hsl(40 60% 98%)'));

  // 水餃(盤上 5 顆)
  function dumplings() {
    const one = (x, y, a) => g(`translate(${x} ${y}) rotate(${a})`, path('M -28 10 C -32 -22 32 -22 28 10 C 14 20 -14 20 -28 10 Z', 'hsl(40 60% 92%)') +
      [[-16, -8], [-5, -12], [6, -12], [17, -8]].map((p) => ellN(p[0], p[1], 3.5, 2.2, 'hsl(38 40% 76%)')).join(''));
    let s = ell(0, 0, 122, 78, PLATE) + ellN(0, 0, 104, 62, PLATE_IN);
    [[-52, -14, -8], [0, -22, 3], [52, -14, 9], [-26, 20, 5], [26, 20, -5]].forEach((d) => { s += one(d[0], d[1], d[2]); });
    return s;
  }

  // 牛肉麵(碗、紅褐湯、麵、3 塊牛肉、蔥花)
  function beefNoodle() {
    let s = rect(-34, 84, 68, 14, CER, 4) + path(bowlD(100, -20, 108), CER) + rectN(-90, 14, 180, 9, 'hsl(2 68% 52%)') + rectN(-70, 36, 140, 5, 'hsl(2 68% 62%)');
    s += ell(0, -20, 100, 30, CER) + ellN(0, -20, 90, 24, 'hsl(14 62% 30%)') + ellN(-6, -24, 56, 14, 'hsl(44 85% 70%)') + noodles(-6, -20, 90, 'hsl(40 80% 58%)');
    [[-52, -18, -10], [48, -14, 12], [-4, -30, 4]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, rect(-18, -10, 36, 20, 'hsl(18 52% 28%)', 5) + rectN(-12, -6, 24, 6, 'hsl(22 55% 42%)', 3)); });
    [[-30, -26], [26, -28], [60, -20], [-70, -18], [8, -12], [-18, -12]].forEach((p) => { s += circN(p[0], p[1], 4, 'hsl(110 55% 45%)'); });
    return s;
  }

  // 肉圓(小碗裡三顆半透明圓球淋紅醬)
  function meatball() {
    const ball = (x, y, r) => circ(x, y, r, 'hsl(32 30% 82%)') + ellN(x - r * 0.4, y - r * 0.5, r * 0.26, r * 0.14, 'hsl(40 45% 95%)') + ellN(x, y - r * 0.32, r * 0.84, r * 0.5, 'hsl(6 70% 46%)') + ellN(x - r * 0.3, y - r * 0.5, r * 0.22, r * 0.11, 'hsl(8 78% 64%)');
    let s = ball(0, -52, 34) + ball(-42, -26, 34) + ball(42, -26, 34);
    s += path(bowlD(94, -6, 78), CER) + rectN(-86, 24, 172, 8, 'hsl(210 60% 52%)') + ell(0, -6, 94, 12, CER) + ellN(0, -6, 86, 8, 'hsl(6 70% 46%)');
    [[-58, -6], [-8, -4], [40, -8], [66, -5]].forEach((p) => { s += circN(p[0], p[1], 3.5, 'hsl(110 55% 45%)'); });
    return s;
  }

  // 蚵仔煎(盤上不規則黃白煎片、綠葉、粉紅醬)
  function oysterOmelet() {
    let s = ell(0, 0, 130, 80, PLATE) + ellN(0, 0, 114, 66, PLATE_IN);
    s += g('translate(-92 -36) rotate(-30)', ell(0, 0, 26, 12, 'hsl(120 45% 40%)')) + g('translate(-70 -54) rotate(25)', ell(0, 0, 24, 11, 'hsl(110 50% 48%)'));
    s += poly([[-92, -5], [-76, -35], [-40, -46], [0, -40], [40, -48], [80, -30], [92, 0], [78, 32], [30, 42], [-20, 38], [-60, 44], [-88, 25]], 'hsl(44 85% 70%)');
    [[-50, 10, 20], [30, 28, -15], [70, -8, 30], [-20, -28, 10]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, ellN(0, 0, 26, 12, 'hsl(40 45% 94%)')); });
    [[-72, -4, 6], [-30, 34, 5], [60, 26, 6], [44, -36, 5]].forEach((c) => { s += circN(c[0], c[1], c[2], 'hsl(32 70% 52%)'); });
    [[-62, -24, 7], [14, 32, 7], [78, 12, 6]].forEach((c) => { s += circN(c[0], c[1], c[2], 'hsl(30 12% 68%)'); });
    s += pathN('M -50 -8 C -40 -30 20 -34 52 -14 C 70 4 40 24 0 20 C -30 26 -64 12 -50 -8 Z', 'hsl(350 70% 64%)') + ellN(-6, -10, 30, 7, 'hsl(350 75% 74%)');
    return s;
  }

  // 荷包蛋
  function friedEgg() {
    const D = 'M -82 -8 C -88 -50 -30 -76 8 -62 C 48 -78 92 -46 84 -6 C 96 30 58 68 14 56 C -22 76 -86 56 -82 -8 Z';
    return path(D, 'hsl(36 75% 62%)') + g('scale(0.93)', pathN(D, 'hsl(48 30% 98%)')) + circN(4, -4, 28, 'hsl(42 98% 55%)') + ellN(-6, -15, 9, 5, 'hsl(48 100% 78%)');
  }

  // 蛋餅(切成 4 段的黃色捲、盤子)
  function eggPancake() {
    const pc = (x, y, a) => g(`translate(${x} ${y}) rotate(${a})`, path('M -27 0 L -27 40 A 27 12 0 0 0 27 40 L 27 0 Z', 'hsl(42 88% 58%)') + circN(-12, 26, 4, 'hsl(32 70% 46%)') + circN(14, 32, 3.5, 'hsl(32 70% 46%)') +
      ell(0, 0, 27, 13, 'hsl(46 95% 78%)') + ellN(0, 0, 19, 9, 'hsl(42 85% 62%)') + ellN(0, 0, 11, 5, 'hsl(46 95% 78%)') + ellN(0, 0, 4, 2, 'hsl(42 85% 62%)'));
    let s = ell(0, 6, 146, 72, PLATE) + ellN(0, 6, 128, 60, PLATE_IN);
    [[-78, -8, -4], [-26, -14, 3], [26, -10, -3], [78, -14, 4]].forEach((c) => { s += pc(c[0], c[1], c[2]); });
    return s;
  }

  // 臭豆腐(紙盤、4 塊金黃方塊加一撮泡菜)
  function stinkyTofu() {
    let s = rect(-125, -60, 250, 120, 'hsl(40 45% 86%)', 12) + rectN(-112, -48, 224, 96, 'hsl(40 40% 94%)', 8);
    [[-82, -22, -4], [-28, -26, 4], [-78, 28, 3], [-24, 26, -4]].forEach((c) => {
      s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, rect(-25, -25, 50, 50, 'hsl(38 85% 50%)', 8) + rectN(-19, -19, 38, 38, 'hsl(42 90% 62%)', 6) +
        circN(-8, -6, 3, 'hsl(30 70% 36%)') + circN(9, 4, 3, 'hsl(30 70% 36%)') + circN(-4, 11, 2.5, 'hsl(30 70% 36%)') + circN(10, -12, 2.5, 'hsl(30 70% 36%)'));
    });
    s += ellN(70, 2, 36, 28, 'hsl(78 55% 62%)') + ellN(60, -12, 24, 14, 'hsl(86 50% 72%)') + ellN(86, 14, 20, 14, 'hsl(80 55% 54%)');
    [[52, 12, 30], [84, -10, -20], [74, 24, 60]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, rectN(-12, -3, 24, 6, 'hsl(22 90% 56%)', 3)); });
    [[66, 0], [94, 6], [48, -4]].forEach((p) => { s += circN(p[0], p[1], 3.5, 'hsl(6 78% 50%)'); });
    return s;
  }

  // 鹽酥雞(紙袋露出小塊炸物與九層塔、兩支竹籤)
  function popcornChicken() {
    const chunk = (x, y, r, i) => {
      const o = [[1, 0], [0.7, 0.75], [0, 1], [-0.8, 0.7], [-1, -0.1], [-0.6, -0.8], [0.2, -1], [0.85, -0.6]];
      return poly(o.map((p, k) => [x + p[0] * r * (1 + 0.14 * ((i + k) % 3 - 1)), y + p[1] * r * (1 + 0.14 * ((i * 2 + k) % 3 - 1))]), 'hsl(36 88% 56%)') +
        circN(x - r * 0.3, y - r * 0.2, r * 0.18, 'hsl(30 78% 40%)') + circN(x + r * 0.35, y + r * 0.3, r * 0.14, 'hsl(44 92% 72%)');
    };
    const bamboo = 'hsl(40 55% 62%)';
    let s = poly([[-14, -22], [-6, -24], [-40, -134], [-48, -132]], bamboo) + poly([[18, -22], [26, -20], [66, -122], [58, -126]], bamboo);
    [[-50, -34, 18], [-16, -50, 20], [22, -42, 19], [52, -28, 17], [-30, -18, 15], [6, -22, 17], [38, -8, 13]].forEach((c, i) => { s += chunk(c[0], c[1], c[2], i); });
    [[-62, -24, -30], [34, -58, 40], [-4, -34, 10], [64, -44, -20]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, ell(0, 0, 14, 7, 'hsl(125 48% 32%)') + rectN(-9, -0.8, 18, 1.6, 'hsl(120 40% 46%)')); });
    s += poly([[-70, -10], [70, -10], [84, 100], [-84, 100]], C.kraft) + rect(-78, -20, 156, 12, C.kraftD, 3) + rectN(-76, 44, 152, 24, C.red) + rectN(-70, 80, 140, 4, C.kraftD, 2);
    return s;
  }

  // 漢堡
  function burger() {
    let s = rect(-92, 56, 184, 26, 'hsl(30 72% 52%)', 13) + rect(-98, 34, 196, 26, 'hsl(20 50% 24%)', 13) +
      poly([[-94, 26], [94, 26], [84, 46], [44, 34], [0, 52], [-44, 34], [-84, 46]], 'hsl(46 95% 58%)') + rect(-88, 14, 176, 16, 'hsl(6 75% 50%)', 8);
    let d = 'M -100 6'; const n = 7, st = 200 / n;
    for (let i = 0; i < n; i++) d += ` Q ${f(-100 + st * (i + 0.5))} ${i % 2 ? 20 : -8} ${f(-100 + st * (i + 1))} 6`;
    s += path(d + ' L 100 16 L -100 16 Z', 'hsl(98 55% 46%)') + path('M -100 2 C -100 -76 100 -76 100 2 Z', 'hsl(30 78% 50%)');
    [[-40, -30, -20], [-10, -44, 10], [24, -34, 30], [52, -18, -15], [-62, -12, 20], [0, -20, 0]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, ellN(0, 0, 5, 2.8, PAPER)); });
    return g('translate(0 -12)', s);
  }

  // 小火鍋(鍋、紅湯、幾樣料、底下爐火)
  function hotpot() {
    let s = rect(112, -34, 24, 12, C.greyD, 5) + rect(-136, -34, 24, 12, C.greyD, 5) + path(bowlD(112, -22, 90), 'hsl(200 10% 32%)');
    [-38, 0, 38].forEach((x) => { s += g(`translate(${x} 100)`, path('M 0 -28 C 12 -14 16 -4 0 0 C -16 -4 -12 -14 0 -28 Z', 'hsl(22 92% 52%)') + pathN('M 0 -14 C 6 -8 8 -3 0 0 C -8 -3 -6 -8 0 -14 Z', 'hsl(48 98% 62%)')); });
    s += rect(-74, 100, 148, 14, C.greyD, 5) + ell(0, -22, 112, 34, 'hsl(200 10% 42%)') + ellN(0, -22, 100, 27, 'hsl(4 74% 40%)');
    s += ellN(-8, -28, 26, 12, 'hsl(95 50% 62%)') + ellN(-14, -30, 12, 6, 'hsl(90 55% 74%)');
    [[22, -16, 20], [-60, -14, -15]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, ellN(0, 0, 22, 9, 'hsl(352 60% 78%)')); });
    s += circN(-46, -30, 13, 'hsl(40 25% 94%)') + circN(40, -34, 12, 'hsl(40 25% 94%)') + circN(60, -24, 9, 'hsl(8 75% 52%)') + ellN(-70, -26, 9, 4, 'hsl(120 50% 40%)');
    [[-30, -14, 4], [50, -8, 3], [-4, -8, 3.5]].forEach((c) => { s += circN(c[0], c[1], c[2], 'hsl(8 75% 55%)'); });
    return s;
  }

  // 豆漿(封膜紙杯、白色飲料)
  function soyMilk(pal) {
    let s = poly([[-48, -40], [48, -40], [36, 100], [-36, 100]], 'hsl(195 40% 88%)') + polyN([[-44, -26], [44, -26], [33, 96], [-33, 96]], 'hsl(45 45% 97%)') +
      polyN([[-43.7, 10], [43.7, 10], [39.9, 54], [-39.9, 54]], pal.main) + g('translate(0 32) rotate(-20)', ellN(0, 0, 11, 6, PAPER));
    s += path('M -48 -42 Q 0 -78 48 -42 Z', 'hsl(195 35% 92%)') + rect(-52, -50, 104, 14, 'hsl(195 30% 76%)', 6);
    return s;
  }

  // 飯糰(塑膠袋包的橢圓白飯糰露出餡)
  function riceBall() {
    const bagC = 'hsl(195 45% 88%)', bagD = 'hsl(195 40% 82%)';
    let s = poly([[-90, -16], [-132, -32], [-122, -10], [-136, 6], [-120, 16], [-134, 34], [-90, 18]], bagD) + poly([[90, -16], [132, -32], [122, -10], [136, 6], [120, 16], [134, 34], [90, 18]], bagD);
    s += ell(0, 0, 98, 72, bagC) + ell(0, 2, 84, 60, 'hsl(44 40% 96%)');
    [[-60, 30], [-30, 40], [10, 42], [46, 34], [66, 16], [-64, -22], [-40, -42], [30, -44], [60, -26]].forEach((p) => { s += g(`translate(${p[0]} ${p[1]}) rotate(${p[0]})`, ellN(0, 0, 4, 2, 'hsl(40 30% 84%)')); });
    s += ellN(0, -2, 56, 22, 'hsl(26 55% 34%)');
    [[-36, -6], [-12, -14], [14, -10], [36, -4], [0, 4]].forEach((p) => { s += circN(p[0], p[1], 6, 'hsl(30 60% 48%)'); });
    s += g('translate(-22 2) rotate(20)', rectN(-13, -3.5, 26, 7, 'hsl(50 95% 62%)', 3)) + g('translate(22 2) rotate(-15)', rectN(-13, -3.5, 26, 7, 'hsl(50 95% 62%)', 3)) + g('translate(0 -10) rotate(8)', rectN(-11, -3, 22, 6, 'hsl(100 55% 42%)', 3));
    s += g('translate(-56 -38) rotate(-25)', ellN(0, 0, 18, 7, 'hsl(195 60% 98%)'));
    return s;
  }

  // 便當(方盒分格:白飯加滷肉、青菜、半顆蛋)
  function bento() {
    let s = rect(-132, -92, 264, 184, 'hsl(8 45% 30%)', 18) + rectN(-120, -80, 240, 160, 'hsl(8 40% 20%)', 12);
    s += rectN(-112, -72, 112, 144, 'hsl(45 40% 96%)', 22);
    [[-90, -40], [-60, -10], [-84, 20], [-40, 40], [-30, -50], [-70, 52], [-20, 0]].forEach((p) => { s += circN(p[0], p[1], 2.6, 'hsl(20 20% 22%)'); });
    s += rectN(10, -72, 104, 66, 'hsl(22 60% 28%)', 12) + ellN(44, -40, 22, 14, 'hsl(24 55% 40%)') + ellN(84, -36, 17, 12, 'hsl(24 55% 40%)') + ellN(66, -58, 14, 7, 'hsl(28 65% 52%)');
    s += rectN(10, 2, 56, 70, 'hsl(110 40% 26%)', 12);
    [[28, 30, 13], [46, 22, 12], [36, 52, 14], [52, 46, 10], [24, 10, 8]].forEach((c) => { s += circN(c[0], c[1], c[2], 'hsl(112 52% 40%)'); });
    s += rectN(74, 2, 40, 70, 'hsl(8 35% 16%)', 10) + ellN(94, 38, 19, 29, 'hsl(48 35% 97%)') + circN(94, 40, 10, 'hsl(40 95% 55%)') + circN(91, 36, 3, 'hsl(48 100% 78%)');
    return s;
  }

  // 羹碗(濃稠湯、橘紅蟹肉塊)
  function soupBowl() {
    let s = rect(-32, 62, 64, 12, CER, 4) + path(bowlD(108, -18, 84), CER) + rectN(-96, 8, 192, 9, 'hsl(205 55% 50%)');
    s += ell(0, -18, 108, 30, CER) + ellN(0, -18, 96, 24, 'hsl(36 78% 56%)');
    [[-60, -22, 20, 6], [20, -10, 24, 6], [-20, -26, 16, 5], [64, -20, 14, 5]].forEach((c) => { s += ellN(c[0], c[1], c[2], c[3], 'hsl(40 85% 70%)'); });
    ['M -62 -14 q 10 -8 20 0 t 20 0', 'M 8 -24 q 10 -8 20 0 t 20 0', 'M -30 -6 q 8 -6 16 0 t 16 0'].forEach((d) => { s += line(d, 3.5, 'hsl(46 95% 84%)'); });
    [[-50, -20, 15], [-14, -26, -20], [30, -16, 30], [56, -24, -10], [-30, -8, 40], [8, -4, -25]].forEach((c) => { s += g(`translate(${c[0]} ${c[1]}) rotate(${c[2]})`, rectN(-9, -5, 18, 10, 'hsl(10 78% 52%)', 3)); });
    [[-76, -16], [70, -10], [-2, -16]].forEach((p) => { s += circN(p[0], p[1], 3.2, 'hsl(110 55% 42%)'); });
    return s;
  }

  // 雞蛋糕(一顆金黃橢圓)
  function eggCake() {
    let s = ell(0, 0, 68, 54, 'hsl(38 85% 54%)');
    [[-24, -16, 18, 12], [14, -24, 16, 11], [36, 0, 14, 10], [-8, 6, 18, 11], [-40, 10, 13, 9], [10, 26, 16, 9]].forEach((c) => { s += ellN(c[0], c[1], c[2], c[3], 'hsl(42 92% 66%)'); });
    [[-50, -2, 4], [26, 18, 4], [52, -18, 3.5], [-14, -34, 3.5], [-30, 32, 3.5]].forEach((c) => { s += circN(c[0], c[1], c[2], 'hsl(30 72% 38%)'); });
    return s;
  }

  // 拉麵(深色碗、叉燒、海苔、蛋)
  function ramen() {
    let s = rect(-34, 80, 68, 14, 'hsl(0 6% 24%)', 4) + path(bowlD(104, -16, 100), 'hsl(0 6% 20%)') + rectN(-96, 10, 192, 10, 'hsl(2 68% 46%)');
    s += ell(0, -16, 104, 32, 'hsl(0 6% 28%)') + ellN(0, -16, 94, 26, 'hsl(34 60% 56%)');
    s += g('translate(56 -34) rotate(12)', rect(-18, -34, 36, 52, 'hsl(160 30% 14%)', 2) + rectN(-12, -26, 24, 3, 'hsl(160 25% 26%)', 1) + rectN(-12, -14, 24, 3, 'hsl(160 25% 26%)', 1));
    s += ellN(-4, -26, 46, 14, 'hsl(46 85% 74%)') + noodles(-4, -22, 70, 'hsl(42 80% 58%)');
    s += ell(-54, -18, 28, 13, 'hsl(16 50% 64%)') + ellN(-54, -18, 18, 8, 'hsl(14 45% 72%)') + ellN(-54, -18, 8, 3.5, 'hsl(16 50% 64%)');
    s += ell(34, -6, 22, 13, 'hsl(48 35% 97%)') + circN(34, -6, 8, 'hsl(32 90% 55%)');
    [[-2, -12], [14, -16], [-14, -14], [-24, -2]].forEach((p) => { s += circN(p[0], p[1], 3.5, 'hsl(110 55% 45%)'); });
    return s;
  }

  // 紫菜飯捲(一排 5 片切面)
  function kimbap() {
    let s = '';
    [-140, -70, 0, 70, 140].forEach((x, i) => {
      s += g(`translate(${x} ${i % 2 ? 3 : -3}) rotate(${i * 72})`, circ(0, 0, 32, 'hsl(160 25% 14%)') + circN(0, 0, 27, 'hsl(45 40% 96%)') + circN(-8, -7, 6, 'hsl(48 95% 60%)') + circN(8, -5, 5.5, 'hsl(22 85% 55%)') +
        circN(0, 8, 6, 'hsl(100 50% 42%)') + ellN(-11, 7, 4, 6, 'hsl(350 60% 62%)'));
    });
    return s;
  }

  // 生肉塊(紅肉帶白色油花)
  function meatChunk() {
    const mb = (x, y, rx, ry, a) => g(`translate(${x} ${y}) rotate(${a})`, ellN(0, 0, rx, ry, 'hsl(32 40% 92%)'));
    let s = poly([[-90, -20], [-64, -60], [-10, -72], [50, -60], [92, -26], [90, 20], [56, 56], [-10, 64], [-70, 50], [-96, 14]], 'hsl(354 62% 44%)');
    s += ellN(-20, -30, 44, 14, 'hsl(352 56% 54%)') + ellN(30, 20, 40, 14, 'hsl(352 56% 54%)');
    [[-40, -14, 34, 3.5, 20], [10, -36, 30, 3, -15], [48, -4, 26, 3.5, 35], [-20, 30, 36, 3, -10], [60, 34, 18, 3, 40], [-66, 10, 18, 3, -35], [4, 6, 22, 3, 10]].forEach((m) => { s += mb(m[0], m[1], m[2], m[3], m[4]); });
    s += poly([[-70, 50], [-10, 64], [56, 56], [40, 40], [-10, 46], [-60, 36]], 'hsl(34 35% 90%)');
    return s;
  }

  // ================= 第二批:器具與物件 =================
  // 撈網(長柄圓網)
  function skimmer() {
    let s = g('translate(-90 -60) rotate(37)', rect(56, -5, 60, 10, C.greyD, 4) + rect(112, -9, 120, 18, C.wood, 9) + circN(222, 0, 4, C.woodD));
    s = '<g transform="translate(25 17)">' + s + g('translate(-90 -60)', circ(0, 0, 62, C.greyD) + circN(0, 0, 52, 'hsl(200 14% 80%)') +
      [-44, -33, -22, -11, 0, 11, 22, 33, 44].map((v) => { const h = Math.sqrt(52 * 52 - v * v); return rectN(-h, v - 1.2, 2 * h, 2.4, 'hsl(200 10% 52%)') + rectN(v - 1.2, -h, 2.4, 2 * h, 'hsl(200 10% 52%)'); }).join('')) + '</g>';
    return s;
  }

  // 油鍋(寬口鍋裝金黃色油)
  function fryPot() {
    let s = rect(118, -22, 64, 16, C.wood, 7) + rect(-142, -22, 26, 12, C.greyD, 5) + path(bowlD(120, -10, 90), 'hsl(200 8% 24%)') + ell(0, -10, 120, 34, 'hsl(200 8% 36%)') + ellN(0, -10, 108, 27, 'hsl(42 90% 52%)');
    s += ellN(-40, -16, 26, 6, 'hsl(46 95% 72%)') + circN(34, -8, 6, 'hsl(46 95% 72%)') + circN(58, -14, 4, 'hsl(46 95% 72%)') + circN(-70, -6, 5, 'hsl(46 95% 72%)') + circN(8, 2, 4, 'hsl(46 95% 72%)');
    return g('translate(-20 -18)', s);
  }

  // 空紙袋(牛皮紙袋)
  function paperBag() {
    return polyN([[70, -80], [88, -70], [94, 92], [76, 100]], C.kraftD) + poly([[-70, -80], [70, -80], [76, 100], [-76, 100]], C.kraft) + ell(0, -82, 70, 16, 'hsl(34 45% 44%)') +
      polyN([[-70, -80], [70, -80], [72, -66], [-72, -66]], 'hsl(38 55% 76%)') + rectN(-76, 70, 152, 30, C.kraftD, 2) + rectN(-64, -40, 6, 100, 'hsl(38 55% 60%)', 2);
  }

  // 瓦斯桶
  function gasTank() {
    return rect(-12, -112, 24, 20, 'hsl(48 90% 55%)', 4) +
      path('M -62 84 L -62 -36 C -62 -96 62 -96 62 -36 L 62 84 Q 62 98 48 98 L -48 98 Q -62 98 -62 84 Z', 'hsl(14 75% 52%)') + rectN(-62, -8, 124, 28, 'hsl(8 60% 38%)') + rectN(-34, -2, 68, 16, PAPER, 3) +
      rectN(-50, -52, 10, 90, 'hsl(18 85% 70%)', 5) + rect(-44, -90, 88, 14, C.greyD, 5) + rect(-54, 92, 108, 10, C.greyD, 3);
  }

  // 鍋鏟(炒菜鍋鏟:木柄、金屬鏟面)
  function spatula() {
    return g('translate(29 -10) rotate(-30)', rect(-170, -9, 112, 18, C.wood, 9) + circN(-158, 0, 4, C.woodD) + rect(-62, -5, 66, 10, C.greyD, 4) +
      path('M 0 -20 L 72 -34 Q 88 -34 88 -18 L 88 18 Q 88 34 72 34 L 0 20 Z', C.greyL) + rectN(12, -8, 60, 5, PAPER, 2));
  }

  // 手提塑膠袋裝早餐(半透明袋、飲料、三明治)
  function breakfastBag(pal) {
    const bag = 'hsl(195 25% 90%)';
    let s = rope('M -50 -40 C -50 -110 -4 -110 -4 -40', 7, bag) + rope('M 4 -40 C 4 -110 50 -110 50 -40', 7, bag);
    s += poly([[-70, -40], [70, -40], [84, 100], [-84, 100]], bag);
    s += poly([[-50, -10], [-18, -10], [-22, 64], [-46, 64]], 'hsl(28 55% 62%)') + rectN(-52, -18, 36, 8, 'hsl(195 30% 76%)', 3) + g('translate(-32 -40) rotate(8)', rectN(-2.5, -18, 5, 50, pal.main, 2));
    s += polyN([[4, 70], [58, 70], [58, 16]], 'hsl(38 70% 72%)') + polyN([[12, 66], [54, 66], [54, 30]], 'hsl(44 80% 88%)') + rectN(18, 56, 36, 8, 'hsl(100 55% 50%)', 2) + rectN(26, 46, 28, 6, 'hsl(352 60% 70%)', 2);
    s += ellN(-52, 6, 5, 40, 'hsl(195 60% 99%)');
    return g('translate(0 0)', s);
  }

  // 磅秤(平台加圓形指針面)
  function scale() {
    let s = rect(-110, -70, 220, 18, C.greyL, 9) + rect(-14, -52, 28, 24, C.greyD, 3) + rect(-130, -30, 260, 120, 'hsl(205 14% 34%)', 22) + circ(0, 30, 46, PAPER);
    for (let i = 0; i < 10; i++) s += g(`translate(0 30) rotate(${-135 + i * 30})`, rectN(-2, -42, 4, i % 3 === 0 ? 11 : 7, INK, 1.5));
    return s + g('translate(0 30) rotate(40)', rectN(-3, -34, 6, 38, C.red, 3)) + circN(0, 30, 7, INK);
  }

  // 一籃蛋(約 9 顆)
  function eggCrate() {
    let s = '';
    [-96, -48, 0, 48, 96].forEach((x, i) => { s += eggShape(x, -26, i % 2 ? 'hsl(26 55% 72%)' : 'hsl(38 45% 94%)'); });
    [-72, -24, 24, 72].forEach((x, i) => { s += eggShape(x, 4, i % 2 ? 'hsl(38 45% 94%)' : 'hsl(26 55% 72%)'); });
    s += rect(-118, 6, 236, 86, 'hsl(34 62% 50%)', 14);
    [34, 56, 78].forEach((y) => { s += rectN(-110, y, 220, 4, 'hsl(30 55% 36%)', 2); });
    for (let r = 0; r < 3; r++) for (let x = -98 + r * 14; x < 100; x += 28) s += rectN(x, 38 + r * 22, 4, 16, 'hsl(30 55% 36%)', 2);
    return s + rect(-124, -2, 248, 18, 'hsl(30 58% 38%)', 8);
  }

  // 行李箱
  function suitcase(pal) {
    let s = rope('M -28 -66 L -28 -88 L 28 -88 L 28 -66', 9, C.greyD) + rect(-66, 80, 22, 14, INK, 4) + rect(44, 80, 22, 14, INK, 4) + rect(-90, -70, 180, 150, pal.main, 16);
    [-52, -18, 16, 50].forEach((x) => { s += rect(x - 3, -58, 6, 126, INK, 3, ' fill-opacity="0.2"' + NS); });
    return s + rectN(-18, -8, 36, 16, C.greyL, 4) + rectN(-84, -64, 14, 14, C.greyL, 4) + rectN(70, -64, 14, 14, C.greyL, 4) + rectN(-84, 54, 14, 14, C.greyL, 4) + rectN(70, 54, 14, 14, C.greyL, 4);
  }

  // 法槌(槌頭加槌座)
  function gavel() {
    return g('translate(0 -6)', rect(-60, 80, 150, 24, C.woodD, 8) + g('rotate(-22)', rect(-9, -18, 18, 100, C.wood, 8) + rect(-58, -70, 116, 52, C.wood, 10) + rect(-64, -74, 16, 60, C.woodD, 6) + rect(48, -74, 16, 60, C.woodD, 6) + rectN(-36, -62, 70, 8, 'hsl(26 50% 54%)', 4)));
  }

  // 天平。o: {tilt:0}:-1..1,正值右邊較低、0 等高
  function balance(pal, o) {
    const t = Math.max(-1, Math.min(1, (o && o.tilt) || 0)), a = t * 16, rad = a * Math.PI / 180, L = 124, py = -90;
    const ex = L * Math.cos(rad), ey = L * Math.sin(rad), GD = 'hsl(38 70% 38%)';
    let s = poly([[-84, 106], [84, 106], [60, 84], [-60, 84]], C.woodD) + rect(-9, -92, 18, 184, GD, 6);
    [[-ex, py - ey], [ex, py + ey]].forEach((e) => {
      const x = e[0], y = e[1];
      s += line(`M ${f(x)} ${f(y)} L ${f(x - 50)} ${f(y + 88)} M ${f(x)} ${f(y)} L ${f(x + 50)} ${f(y + 88)}`, 3, GD) +
        g(`translate(${f(x)} ${f(y + 88)})`, path('M -56 0 L 56 0 C 48 28 -48 28 -56 0 Z', C.gold) + ellN(-26, 7, 16, 3.5, C.goldL));
    });
    s += g(`translate(0 ${py}) rotate(${f(a)})`, rect(-L - 6, -7, 2 * L + 12, 14, C.gold, 7)) + circ(-ex, py - ey, 9, C.goldL) + circ(ex, py + ey, 9, C.goldL) + circ(0, py, 13, C.goldL) + circ(0, py - 18, 8, C.gold);
    return s;
  }

  // 磚牆。o: {text:''}:中間留白區可疊字(wall.labelBox)
  const WALL_LABEL = { x: -112, y: -38, w: 224, h: 76 };
  function wall(pal, o) {
    const text = o && o.text ? String(o.text) : '';
    let s = rect(-150, -110, 300, 220, 'hsl(30 18% 76%)', 6);
    for (let r = 0; r < 5; r++) {
      const off = r % 2 ? 35 : 0;
      for (let x = -150 - off; x < 150; x += 70) {
        const xl = Math.max(x, -150), xr = Math.min(x + 70, 150), k = (r * 3 + Math.round((x + 150) / 35)) % 4;
        s += rectN(xl + 2, -110 + r * 44 + 2, xr - xl - 4, 40, `hsl(${10 + k * 2} ${50 - k * 2}% ${38 + k * 3}%)`, 4);
      }
    }
    s += rectN(WALL_LABEL.x, WALL_LABEL.y, WALL_LABEL.w, WALL_LABEL.h, PAPER, 8);
    if (text) {
      const est = [...text].reduce((a, c) => a + (c.charCodeAt(0) < 256 ? (c === ' ' ? 0.3 : 0.58) : 1), 0);
      s += txt(text, 0, 2, Math.min(52, Math.floor(200 / Math.max(1, est))), INK);
    }
    return s;
  }

  // 大腦(粉色紙片)
  function brain() {
    const N = 12, P = [];
    for (let i = 0; i < N; i++) { const a = -Math.PI / 2 + 2 * Math.PI * i / N; P.push([112 * Math.cos(a), 74 * Math.sin(a) - 4]); }
    let d = `M ${f(P[0][0])} ${f(P[0][1])}`;
    for (let i = 1; i <= N; i++) d += ` A 32 32 0 0 1 ${f(P[i % N][0])} ${f(P[i % N][1])}`;
    const fold = (k) => line(`M ${k * 86} -24 C ${k * 66} -48 ${k * 48} -20 ${k * 28} -42`, 6, 'hsl(344 50% 62%)') + line(`M ${k * 96} 14 C ${k * 72} -6 ${k * 56} 24 ${k * 32} 4`, 6, 'hsl(344 50% 62%)') +
      line(`M ${k * 60} 44 C ${k * 40} 28 ${k * 28} 54 ${k * 8} 38`, 6, 'hsl(344 50% 62%)') + line(`M ${k * 56} -64 C ${k * 44} -52 ${k * 32} -64 ${k * 20} -54`, 6, 'hsl(344 50% 62%)');
    return poly([[-12, 60], [14, 60], [18, 100], [-8, 100]], 'hsl(340 55% 72%)') + path(d + ' Z', 'hsl(344 70% 78%)') + line('M 0 -72 C -10 -40 8 -20 -2 12', 6, 'hsl(344 50% 62%)') + fold(1) + fold(-1);
  }

  // 皇冠
  function crown() {
    return poly([[-100, 60], [-110, -50], [-55, 0], [0, -70], [55, 0], [110, -50], [100, 60]], C.gold) + rect(-102, 34, 204, 34, 'hsl(38 85% 42%)', 6) +
      circ(-110, -58, 12, C.goldL) + circ(0, -78, 13, C.goldL) + circ(110, -58, 12, C.goldL) +
      circN(-60, 51, 9, C.red) + circN(0, 51, 11, 'hsl(210 70% 55%)') + circN(60, 51, 9, C.red) + polyN([[-40, 4], [-26, -18], [-18, 6]], C.goldL) + polyN([[40, 4], [26, -18], [18, 6]], C.goldL);
  }

  // 放大鏡
  function magnifier() {
    return g('translate(4 4)', g('translate(-30 -30) rotate(45)', rect(66, -11, 100, 22, C.wood, 10) + rect(58, -14, 16, 28, C.greyD, 4)) +
      circ(-30, -30, 70, C.gold) + circN(-30, -30, 56, 'hsl(195 60% 90%)') + g('translate(-52 -52) rotate(-45)', ellN(0, 0, 20, 7, 'hsl(195 70% 99%)')));
  }

  // 極簡小人(圓頭加梯形身體,無臉)。o: {grey:false}
  function person(pal, o) {
    const grey = !!(o && o.grey);
    return path('M -50 96 L -42 -24 Q -40 -36 -26 -36 L 26 -36 Q 40 -36 42 -24 L 50 96 Z', grey ? C.grey : pal.main) + circ(0, -66, 28, grey ? 'hsl(200 8% 74%)' : 'hsl(28 60% 80%)');
  }

  // 廟(翹脊屋頂、紅柱、門、匾額)。o: {plaque:''}
  function temple(pal, o) {
    const pl = o && o.plaque ? String(o.plaque) : '', RED = 'hsl(4 68% 42%)';
    let s = rect(-110, -20, 220, 122, 'hsl(38 55% 86%)', 0) + rect(-112, -20, 22, 122, RED, 0) + rect(90, -20, 22, 122, RED, 0) + rect(-62, -20, 16, 122, RED, 0) + rect(46, -20, 16, 122, RED, 0);
    s += rect(-36, 26, 72, 76, 'hsl(4 60% 34%)', 4) + rectN(-1.5, 26, 3, 76, INK);
    [-24, -12, 12, 24].forEach((x) => { [44, 70].forEach((y) => { s += circN(x, y, 3.5, C.gold); }); });
    s += rect(-52, -14, 104, 34, 'hsl(24 45% 20%)', 4);
    if (pl) s += txt(pl, 0, 4, Math.min(30, Math.floor(88 / pl.length)), 'hsl(44 90% 60%)');
    s += poly([[-64, -112], [-44, -132], [44, -132], [64, -112]], 'hsl(36 90% 38%)') + circ(0, -138, 8, RED);
    s += poly([[-160, -80], [-136, -52], [-110, -36], [110, -36], [136, -52], [160, -80], [140, -82], [118, -98], [60, -112], [-60, -112], [-118, -98], [-140, -82]], 'hsl(38 88% 46%)');
    for (let x = -96; x <= 96; x += 20) s += rectN(x, -96, 5, 56, 'hsl(32 80% 36%)', 2);
    s += rect(-112, -36, 224, 18, 'hsl(150 35% 30%)', 3) + rect(-120, 102, 240, 12, C.greyD, 3) + rect(-132, 114, 264, 10, C.grey, 3);
    return s;
  }

  // 名稱 → {fn, w, h(建議外框,單位), zh(總表上的名稱), wide}
  const LIST = {
    stall: { fn: stall, w: 340, h: 312, zh: '夜市攤車', signBox: STALL_SIGN }, bulbString: { fn: bulbString, w: 940, h: 84, zh: '一串燈泡', wide: true },
    bill100: { fn: bill100, w: 304, h: 144, zh: '百元鈔', wide: true }, coin50: { fn: coin50, w: 104, h: 104, zh: '50元硬幣' }, coin10: { fn: coin10, w: 88, h: 88, zh: '10元硬幣' },
    diceBeef: { fn: diceBeef, w: 224, h: 202, zh: '骰子牛' }, folder: { fn: folder, w: 248, h: 176, zh: '資料夾' }, alarm: { fn: alarm, w: 164, h: 192, zh: '鬧鐘' },
    clipboard: { fn: clipboard, w: 144, h: 208, zh: '記錄板' }, chickenCutlet: { fn: chickenCutlet, w: 232, h: 212, zh: '雞排' },
    bobaCup: { fn: bobaCup, w: 116, h: 242, zh: '珍珠奶茶' }, braisedPorkRice: { fn: braisedPorkRice, w: 208, h: 196, zh: '滷肉飯' },
    sweetBall: { fn: sweetBall, w: 184, h: 184, zh: '地瓜球' }, steakPlate: { fn: steakPlate, w: 284, h: 160, zh: '夜市牛排' },
    taiwan4: { fn: taiwan4, w: 160, h: 290, zh: '台灣四城' }, payEnvelope: { fn: payEnvelope, w: 224, h: 144, zh: '薪資袋', labelBox: ENV_LABEL },
    calculator: { fn: calculator, w: 124, h: 184, zh: '計算機' },
    // 第二批
    dumplings: { fn: dumplings, w: 248, h: 160, zh: '水餃' }, beefNoodle: { fn: beefNoodle, w: 204, h: 152, zh: '牛肉麵' }, meatball: { fn: meatball, w: 192, h: 164, zh: '肉圓' },
    oysterOmelet: { fn: oysterOmelet, w: 264, h: 164, zh: '蚵仔煎' }, friedEgg: { fn: friedEgg, w: 188, h: 148, zh: '荷包蛋' }, eggPancake: { fn: eggPancake, w: 294, h: 146, zh: '蛋餅' },
    stinkyTofu: { fn: stinkyTofu, w: 254, h: 124, zh: '臭豆腐' }, popcornChicken: { fn: popcornChicken, w: 176, h: 238, zh: '鹽酥雞' }, burger: { fn: burger, w: 204, h: 142, zh: '漢堡' },
    hotpot: { fn: hotpot, w: 274, h: 172, zh: '小火鍋' }, soyMilk: { fn: soyMilk, w: 108, h: 164, zh: '豆漿' }, riceBall: { fn: riceBall, w: 276, h: 148, zh: '飯糰' },
    bento: { fn: bento, w: 266, h: 186, zh: '便當' }, soupBowl: { fn: soupBowl, w: 218, h: 124, zh: '羹碗' }, eggCake: { fn: eggCake, w: 140, h: 112, zh: '雞蛋糕' },
    ramen: { fn: ramen, w: 210, h: 162, zh: '拉麵' }, kimbap: { fn: kimbap, w: 312, h: 72, zh: '紫菜飯捲', wide: true }, meatChunk: { fn: meatChunk, w: 194, h: 140, zh: '生肉塊' },
    skimmer: { fn: skimmer, w: 262, h: 218, zh: '撈網' }, fryPot: { fn: fryPot, w: 328, h: 128, zh: '油鍋', wide: true }, paperBag: { fn: paperBag, w: 190, h: 200, zh: '空紙袋' },
    gasTank: { fn: gasTank, w: 132, h: 216, zh: '瓦斯桶' }, spatula: { fn: spatula, w: 250, h: 176, zh: '鍋鏟' }, breakfastBag: { fn: breakfastBag, w: 172, h: 212, zh: '早餐袋' },
    scale: { fn: scale, w: 264, h: 164, zh: '磅秤' }, eggCrate: { fn: eggCrate, w: 250, h: 152, zh: '一籃蛋' }, suitcase: { fn: suitcase, w: 184, h: 200, zh: '行李箱' },
    gavel: { fn: gavel, w: 196, h: 204, zh: '法槌' }, balance: { fn: balance, w: 372, h: 226, zh: '天平', wide: true }, wall: { fn: wall, w: 304, h: 224, zh: '磚牆', labelBox: WALL_LABEL },
    brain: { fn: brain, w: 248, h: 204, zh: '大腦' }, crown: { fn: crown, w: 250, h: 168, zh: '皇冠' }, magnifier: { fn: magnifier, w: 196, h: 196, zh: '放大鏡' },
    person: { fn: person, w: 112, h: 196, zh: '小人' }, temple: { fn: temple, w: 324, h: 272, zh: '廟', plaqueBox: { x: -52, y: -14, w: 104, h: 34 } },
  };

  const API = { C, LIST, taiwan4Pos };
  Object.keys(LIST).forEach((n) => { API[n] = LIST[n].fn; });
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.PropsSnack = API;
})();
