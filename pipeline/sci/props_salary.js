/* ChannelC:salary 片(薪水、年薪百萬、快樂與鹽)的圖解(扁平色塊剪紙)。純函式,不依賴 DOM 與 kit.js。
 * 每個函式 fn(pal, o) 回傳「以單位繪製、中心在原點」的紙片內容,由呼叫端包成紙片:
 *   K.paper(PS.globe(pal, {sign:'世界一'}), {x, y, scale: u, k: 'prop', id: 'g1', wide: PS.LIST.globe.wide})
 * LIST[名] = {fn, w, h, zh, wide}:w/h 為建議外框(單位)。外形片繼承紙片的紙白描邊;細節(N 結尾的函式)不描邊。只用 polygon/path/rect/circle/text。
 * 參數:bill {n:數字字樣} / globe {sign, v:1|2} / meter {v:0–1} / scale {tilt:-1..1,正 = 右邊下沉} / dict {text:書背字,≤5 字} /
 *   stele {lines} / tape {out:0..1} / field {u:呼叫端的 px 每單位, bills:0–1000 張千元鈔}。不用漸層、亂數、時鐘。
 * 不畫真實人物臉(千元鈔只畫抽象徽記);校門沒有校名;不畫任何商標。
 * 比例:千元鈔 160×70 公釐(央行公告)= bill 的 320×140 單位;field 1 單位 = 1 公尺(105×68),所以一張千元鈔 = 0.16 單位長。
 * field 的描邊以 px 為準:呼叫端要把縮放倍率以 o.u 傳進來,K.paper 的 scale 用 o.ps(總表:u=10.5, ps=1.8 → 陰影約 9×11px)。 */
(function () {
  const Y = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7';
  const C = {
    brown: 'hsl(24 52% 32%)', wood: 'hsl(24 55% 40%)', woodD: 'hsl(24 55% 30%)', kraft: 'hsl(38 62% 68%)', kraftD: 'hsl(36 55% 54%)',
    tan: 'hsl(38 40% 78%)', grey: 'hsl(200 8% 62%)', greyD: 'hsl(200 10% 38%)', greyL: 'hsl(200 14% 82%)', red: 'hsl(4 68% 52%)',
    gold: 'hsl(42 88% 50%)', goldL: 'hsl(44 92% 62%)', goldD: 'hsl(38 80% 38%)', stone: 'hsl(40 8% 64%)', stoneD: 'hsl(40 8% 44%)',
    blue: 'hsl(205 55% 72%)', blueD: 'hsl(205 50% 42%)', glass: 'hsl(195 50% 90%)', salt: 'hsl(200 15% 97%)', navy: 'hsl(220 30% 22%)',
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
  const line = (d, w, col) => `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  const rope = (d, w, col) => line(d, w + 7, PAPER) + line(d, w, col);
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

  // ================= 錢與薪水 =================
  // 千元鈔(長寬比 160:70 = 320×140 單位;左側抽象徽記、右側大面額數字,不畫人像)。o: {n:字樣,預設 1000}
  function bill(pal, o) {
    o = o || {};
    const n = o.n == null ? '1000' : String(o.n);
    let s = rect(-160, -70, 320, 140, C.blue, 8) + rectN(-149, -59, 298, 118, 'hsl(205 60% 80%)', 4);
    s += line('M -149 -59 H 149 V 59 H -149 Z', 3, C.blueD);
    s += circN(-86, 0, 46, C.blueD) + circN(-86, 0, 36, 'hsl(205 60% 84%)') + circN(-86, 0, 24, C.blueD) + circN(-86, 0, 12, 'hsl(205 60% 84%)');
    s += line('M -30 -36 Q 20 -52 60 -36 T 140 -36', 3, C.blueD) + line('M -30 36 Q 20 20 60 36 T 140 36', 3, C.blueD);
    s += txt(n, 60, 0, 58, C.blueD);
    s += txt(n, -124, -46, 14, C.blueD) + txt(n, 124, 46, 14, C.blueD);
    return s;
  }

  // 薪資袋(牛皮紙袋、袋口露出一張鈔票)
  function payslip(pal) {
    let s = rect(-56, -102, 112, 56, C.blue, 4) + rectN(-46, -92, 92, 6, C.blueD) + rectN(-46, -78, 60, 6, C.blueD);
    s += rect(-80, -60, 160, 150, C.kraft, 6) + polyN([[-80, -60], [80, -60], [0, 8]], C.kraftD) + rectN(-80, -60, 160, 6, C.kraftD);
    s += rect(-50, 30, 100, 48, PAPER, 5) + rectN(-50, 30, 100, 8, pal.main, 3) + txt('薪資', 0, 58, 32, INK);
    return g('translate(0 6)', s);
  }

  // 學士帽(方帽、流蘇)
  function gradcap() {
    let s = poly([[-58, -4], [58, -4], [52, 52], [0, 66], [-52, 52]], C.navy);
    s += poly([[0, -62], [112, -22], [0, 18], [-112, -22]], 'hsl(220 30% 30%)') + polyN([[0, -62], [112, -22], [0, -18], [-112, -22]], 'hsl(220 30% 38%)');
    s += circ(0, -22, 8, C.gold) + line('M 0 -22 L 94 -8 L 94 40', 5, C.gold);
    s += rect(86, 38, 16, 32, C.gold, 4) + rectN(86, 38, 16, 8, C.goldD, 2);
    return g('translate(0 -4)', s);
  }

  // 校門(磚柱、鐵柵門、上方空白橫牌,不寫校名)
  function gate(pal) {
    let s = rect(-86, -110, 172, 46, pal.main, 5) + rectN(-76, -102, 152, 30, pal.pad, 3);
    s += rect(-92, -66, 8, 12, C.greyD, 2) + rect(84, -66, 8, 12, C.greyD, 2);
    for (let i = 0; i < 6; i++) s += rect(-70 + i * 28, -10, 10, 112, C.greyD, 4) + polyN([[-70 + i * 28, -10], [-65 + i * 28, -26], [-60 + i * 28, -10]], C.greyD);
    s += rect(-84, 6, 168, 10, C.greyD, 3) + rect(-84, 84, 168, 10, C.greyD, 3);
    [-1, 1].forEach((d) => {
      const x = d < 0 ? -128 : 88;
      s += rect(x, -40, 40, 160, 'hsl(14 52% 46%)', 3) + rect(x - 8, -58, 56, 20, C.tan, 4) + rectN(x - 8, -58, 56, 6, 'hsl(38 40% 88%)', 2);
      [-10, 20, 50, 80].forEach((y) => { s += rectN(x, y, 40, 3, 'hsl(14 40% 32%)') + rectN(x + 14, y + 3, 3, 27, 'hsl(14 40% 32%)'); });
    });
    return g('translate(0 -5)', s);
  }

  // 公事包
  function briefcase() {
    let s = rope('M -36 -34 L -36 -58 Q -36 -72 -22 -72 L 22 -72 Q 36 -72 36 -58 L 36 -34', 14, C.woodD);
    s += rect(-100, -36, 200, 130, C.brown, 14) + rectN(-100, -8, 200, 8, C.woodD) + rectN(-88, -30, 176, 6, 'hsl(24 45% 46%)', 3);
    s += rect(-20, -16, 40, 34, C.gold, 6) + circN(0, 0, 6, INK) + rectN(-3, 2, 6, 12, INK, 2);
    return g('translate(0 -7)', s);
  }

  // 銀行建築(三角楣飾、四柱、台階、楣飾上的「元」字金幣)
  function bank() {
    let s = poly([[-122, -70], [0, -132], [122, -70]], C.tan) + circ(0, -94, 20, C.gold) + txt('元', 0, -93, 24, C.goldD);
    s += rect(-122, -70, 244, 22, C.tan, 3);
    [-90, -30, 30, 90].forEach((x) => { s += rect(x - 15, -48, 30, 110, PAPER, 3) + rectN(x - 7, -44, 4, 102, C.greyL) + rectN(x + 3, -44, 4, 102, C.greyL); });
    s += rect(-132, 62, 264, 16, C.tan, 3) + rect(-142, 78, 284, 16, C.stone, 3);
    return g('translate(0 17)', s);
  }

  // 問卷板(木板、夾子、三題、第一題打勾)
  function survey() {
    let s = rect(-80, -100, 160, 200, C.wood, 10) + rectN(-64, -82, 128, 164, PAPER, 3);
    s += rect(-30, -114, 60, 28, C.grey, 6) + rectN(-22, -108, 44, 6, C.greyL, 3);
    [-44, 4, 52].forEach((y) => {
      s += rectN(-52, y - 13, 26, 26, INK, 3) + rectN(-49, y - 10, 20, 20, PAPER, 2) + rectN(-14, y - 8, 56, 8, C.greyL, 3) + rectN(-14, y + 6, 36, 6, C.greyL, 3);
    });
    s += line('M -48 -44 L -41 -35 L -28 -54', 6, 'hsl(140 60% 36%)');
    return g('translate(0 7)', s);
  }

  // 天秤。o: {tilt:-1..1,正 = 右盤下沉}
  function scale(pal, o) {
    o = o || {};
    const a = clamp(+o.tilt || 0, -1, 1) * 12, r = a * Math.PI / 180, L = 110, cy = -100;
    const ex = L * Math.cos(r), ey = L * Math.sin(r), pans = [[-ex, cy - ey], [ex, cy + ey]];
    let s = rect(-8, -112, 16, 196, C.greyD, 3) + rect(-70, 74, 140, 16, C.greyD, 5);
    pans.forEach((p) => {
      s += line(`M ${f(p[0])} ${f(p[1])} L ${f(p[0] - 52)} ${f(p[1] + 106)} M ${f(p[0])} ${f(p[1])} L ${f(p[0] + 52)} ${f(p[1] + 106)}`, 3.5, C.greyD);
      s += path(`M ${f(p[0] - 62)} ${f(p[1] + 106)} Q ${f(p[0])} ${f(p[1] + 152)} ${f(p[0] + 62)} ${f(p[1] + 106)} Z`, C.gold);
      s += rectN(p[0] - 56, p[1] + 106, 112, 6, C.goldL, 2);
    });
    s += g(`rotate(${f(a)} 0 ${cy})`, rect(-L - 8, cy - 6, 2 * L + 16, 12, C.gold, 6)) + circ(0, cy, 14, C.goldD) + circN(0, cy, 5, C.goldL);
    return g('translate(0 22)', s);
  }

  // ================= 世界、快樂、時間 =================
  // 地球。o: {sign:牌子字(留空 = 無牌), v:1|2(兩個世界:v1 藍海綠陸、v2 橘海紅褐陸)}
  function globe(pal, o) {
    o = o || {};
    const v2 = +o.v === 2, ocean = v2 ? 'hsl(34 88% 62%)' : 'hsl(205 70% 62%)', land = v2 ? 'hsl(10 58% 44%)' : 'hsl(125 42% 46%)';
    const sx = v2 ? -1 : 1, cy = -34;
    let s = rope('M -92 -34 Q -92 68 0 76 Q 92 68 92 -34', 9, C.greyD) + rect(-9, 70, 18, 30, C.greyD, 3) + rect(-56, 96, 112, 16, C.greyD, 5);
    s += circ(0, cy, 82, ocean);
    s += g(`translate(0 ${cy}) scale(${sx} 1)`, polyN([[-52, -34], [-22, -58], [4, -48], [-2, -22], [-24, -8], [-48, -14]], land) +
      polyN([[8, -2], [34, -14], [58, 4], [48, 36], [22, 56], [4, 30]], land) + polyN([[-44, 18], [-24, 14], [-18, 44], [-34, 62], [-48, 40]], land));
    s += ellN(-34, cy - 40, 18, 9, 'hsl(0 0% 100% / .35)');
    if (o.sign) {
      const t = String(o.sign), size = Math.min(46, 170 / Math.max(1, t.length));
      s += rect(-100, 118, 200, 66, PAPER, 5) + rectN(-100, 118, 200, 9, pal.main, 3) + txt(t, 0, 156, size, INK);
      return g('translate(0 -33)', s);
    }
    return g('translate(0 -2)', s);
  }

  // 笑臉計量表(半圓紅到綠五段、指針、下方笑臉隨 v 由哭變笑)。o: {v:0–1}
  function meter(pal, o) {
    o = o || {};
    const v = clamp(o.v == null ? 0.5 : +o.v, 0, 1), cy = 30, R1 = 110, R0 = 64;
    const P = (r, th) => `${f(r * Math.sin(th * Math.PI / 180))} ${f(cy - r * Math.cos(th * Math.PI / 180))}`;
    const cols = ['hsl(4 72% 52%)', 'hsl(24 85% 54%)', 'hsl(46 90% 54%)', 'hsl(90 55% 48%)', 'hsl(135 55% 40%)'];
    let s = path(`M -126 ${cy} A 126 126 0 0 1 126 ${cy} Z`, PAPER) + rect(-126, cy, 252, 14, PAPER, 4);
    cols.forEach((c, i) => {
      const a0 = -90 + i * 36, a1 = a0 + 34;
      s += pathN(`M ${P(R1, a0)} A ${R1} ${R1} 0 0 1 ${P(R1, a1)} L ${P(R0, a1)} A ${R0} ${R0} 0 0 0 ${P(R0, a0)} Z`, c);
    });
    s += g(`translate(0 ${cy}) rotate(${f(v * 180 - 90)})`, polyN([[-7, 0], [7, 0], [0, -102]], INK));
    s += circ(0, cy, 13, INK);
    const hue = Math.round(v * 120), fy = 104;
    s += circ(0, fy, 44, `hsl(${hue} 85% 60%)`) + circN(-15, fy - 10, 6, INK) + circN(15, fy - 10, 6, INK);
    s += line(`M -18 ${fy + 16} Q 0 ${f(fy + 16 + (v - 0.5) * 44)} 18 ${fy + 16}`, 5, INK);
    return g('translate(0 -26)', s);
  }

  // ================= 鹽與羅馬 =================
  // 羅馬軍團頭盔(正面開臉:銅色圓頂、頭頂紅色縱向刷狀羽冠、前額橫向眉沿、兩側下垂護頰、後方護頸)
  function helmet() {
    const RD = 'hsl(4 66% 36%)', SKIN = 'hsl(28 62% 80%)';
    let s = poly([[-82, 22], [82, 22], [98, 70], [-98, 70]], C.goldD) + rectN(-90, 46, 180, 5, C.gold, 2);     // 後方護頸(兩側外翻)
    s += rect(-50, 18, 100, 72, SKIN, 20) + circN(-20, 46, 4.5, INK) + circN(20, 46, 4.5, INK);                  // 臉(開口)
    s += line('M -26 36 L -12 34', 4, INK) + line('M 12 34 L 26 36', 4, INK) + line('M 0 48 L -3 62 L 4 62', 3, 'hsl(28 40% 55%)') + line('M -12 76 Q 0 82 12 76', 3.5, INK);
    s += path('M -86 20 A 86 86 0 0 1 86 20 Z', C.gold) + rectN(-66, -34, 40, 8, C.goldL, 4);                   // 圓頂
    s += rect(-30, -66, 60, 12, C.goldD, 4);                                                                     // 羽冠底座
    s += path('M -26 -62 Q -34 -96 -20 -106 Q 0 -114 20 -106 Q 34 -96 26 -62 Z', C.red);                         // 羽冠(刷狀)
    [-16, -8, 0, 8, 16].forEach((x) => { s += line(`M ${x} -64 L ${x * 1.15} -100`, 3.2, RD); });
    s += rect(-94, 8, 188, 16, C.goldD, 5);                                                                      // 前額眉沿
    [-70, -35, 0, 35, 70].forEach((x) => { s += circN(x, 16, 3.5, C.goldL); });
    s += poly([[-94, 24], [-50, 24], [-46, 92], [-62, 102], [-84, 86]], C.gold) + poly([[94, 24], [50, 24], [46, 92], [62, 102], [84, 86]], C.gold);   // 護頰
    [[-72, 50], [72, 50], [-66, 74], [66, 74]].forEach((p) => { s += circN(p[0], p[1], 3.2, C.goldD); });
    return g('translate(0 4)', s);
  }

  // 鹽袋(白布袋、口綁繩、「鹽」字標籤)
  function saltbag(pal) {
    let s = path('M -62 -70 L 62 -70 Q 80 0 72 84 Q 0 100 -72 84 Q -80 0 -62 -70 Z', 'hsl(40 20% 94%)');
    s += rect(-66, -88, 132, 22, 'hsl(40 15% 80%)', 5) + line('M -44 -66 Q 0 -54 44 -66', 5, C.greyD);
    s += rect(-54, -36, 108, 100, pal.main, 5) + txt('鹽', 0, 14, 90, pal.onMain || INK).replace('stroke="none"', `stroke="${pal.main}" stroke-width="2.4"`);   // 字放大、以底色描邊把重字削細,下半「皿」與上半不糊成一團
    s += pathN('M -68 62 Q 0 74 68 62', 'hsl(40 15% 82%)');
    return g('translate(0 -2)', s);
  }

  // 鹽罐(玻璃罐、白鹽、金屬蓋三個孔)
  function shaker() {
    let s = path('M -44 -50 L 44 -50 L 50 90 Q 50 100 40 100 L -40 100 Q -50 100 -50 90 Z', C.glass);
    s += pathN('M -46 -6 L 46 -6 L 49 90 Q 49 98 40 98 L -40 98 Q -49 98 -49 90 Z', C.salt);
    s += ellN(-34, 28, 4.5, 36, 'hsl(195 60% 99%)');
    s += rect(-48, -84, 96, 36, C.greyL, 14) + path('M -46 -84 Q 0 -114 46 -84 Z', C.grey);
    [-24, 0, 24].forEach((x) => { s += circN(x, -66, 4.5, INK); });
    return g('translate(0 7)', s);
  }

  // 厚辭典(書背朝前、金色橫帶、書名牌直排)。o: {text:書背字,≤5 字,預設「辭典」}
  function dict(pal, o) {
    o = o || {};
    const cs = Array.from(o.text == null ? '辭典' : String(o.text)).slice(0, 5), n = Math.max(1, cs.length), size = Math.min(52, 112 / n);
    let s = rect(-62, -120, 124, 240, 'hsl(8 50% 30%)', 8) + rectN(-50, -112, 8, 224, 'hsl(8 45% 40%)', 3);
    [[-100, 8], [-84, 4], [84, 4], [96, 8]].forEach((b) => { s += rectN(-62, b[0], 124, b[1], C.gold); });
    s += rect(-44, -58, 88, 116, 'hsl(40 50% 86%)', 5) + rectN(-44, -58, 88, 8, C.gold, 3) + rectN(-44, 50, 88, 8, C.gold, 3);
    cs.forEach((c, i) => { s += txt(c, 0, (i - (n - 1) / 2) * size * 1.04, size, 'hsl(8 50% 26%)'); });
    return s;
  }

  // 石碑(圓頂石板、日輪徽記、刻痕行、底座)。o: {lines:刻痕行數,預設 5}
  function stele(pal, o) {
    o = o || {};
    const nl = clamp(o.lines == null ? 5 : o.lines | 0, 0, 7);
    let s = rect(-86, 100, 172, 24, C.stoneD, 5) + path('M -64 100 L -64 -50 Q -64 -110 0 -110 Q 64 -110 64 -50 L 64 100 Z', C.stone);
    s += pathN('M -50 94 L -50 -48 Q -50 -96 0 -96 Q 50 -96 50 -48 L 50 94 Z', 'hsl(40 8% 70%)');
    s += circ(0, -62, 16, C.stoneD) + circN(0, -62, 8, 'hsl(40 8% 70%)');
    for (let i = 0; i < nl; i++) s += rectN(-36, -28 + i * 20, 72 - (i % 3 === 2 ? 26 : 0), 8, C.stoneD, 3);
    return g('translate(0 -7)', s);
  }

  // 捲尺(黃色圓角殼、拉出的帶尺、刻度、尾端鉤)。o: {out:0..1 拉出長度,預設 1}
  function tape(pal, o) {
    o = o || {};
    const L = 190 * clamp(o.out == null ? 1 : +o.out, 0, 1);
    let s = '';
    if (L > 0) {
      s += rect(70, 28, L, 30, 'hsl(48 90% 86%)', 2) + rect(70 + L, 20, 10, 46, C.greyD, 3);
      for (let x = 0; x < L - 4; x += 12) s += rectN(78 + x, 28, 3, x % 60 === 0 ? 20 : 11, INK, 1);
    }
    s += rect(-70, -60, 140, 120, C.gold, 34) + rectN(-56, -48, 112, 14, C.goldL, 7);
    s += circ(-6, -4, 34, INK) + circN(-6, -4, 22, C.grey) + circN(-6, -4, 8, INK);
    s += rect(36, -78, 26, 24, INK, 6) + rectN(60, 32, 14, 22, INK, 2);
    return g('translate(-100 6)', s);
  }

  // ================= 足球場(俯視) =================
  // 1 單位 = 1 公尺:105×68,一張千元鈔 160mm = 0.16 單位。
  // o: {u:呼叫端的縮放(px 每單位,決定描邊粗細,預設 15), ps:呼叫端傳給 K.paper 的 scale(預設 = u;給小一點的值,陰影偏移 = 5·ps、6·ps px 才不會被 u 放大成一大塊), bills:0–1000 張千元鈔沿長邊排列(第一排放滿 656 張,其餘排第二排;寬度放大成 9px 方便看)}
  const FIELD = { len: 105, wid: 68, billMM: 160, billWmm: 70, pitch: 0.16, perRow: 105 / 0.16 };
  function field(pal, o) {
    o = o || {};
    const u = +o.u > 0 ? +o.u : 15, ps = +o.ps > 0 ? +o.ps : u, lw = 3 / u, hw = FIELD.len / 2, hh = FIELD.wid / 2;
    let s = rectN(-hw, -hh, FIELD.len, FIELD.wid, 'hsl(130 42% 44%)');
    for (let i = 0; i < 10; i += 2) s += rectN(-hw + i * 10.5, -hh, 10.5, FIELD.wid, 'hsl(130 42% 49%)');
    const W = PAPER;
    s += `<g stroke-width="${f(lw)}">` + [
      `M ${-hw} ${-hh} H ${hw} V ${hh} H ${-hw} Z`, `M 0 ${-hh} V ${hh}`,
      `M ${-hw} -20.16 H ${-hw + 16.5} V 20.16 H ${-hw}`, `M ${hw} -20.16 H ${hw - 16.5} V 20.16 H ${hw}`,
      `M ${-hw} -9.16 H ${-hw + 5.5} V 9.16 H ${-hw}`, `M ${hw} -9.16 H ${hw - 5.5} V 9.16 H ${hw}`,
    ].map((d) => `<path d="${d}" fill="none" stroke="${W}"/>`).join('') + `</g>`;
    s += `<circle cx="0" cy="0" r="9.15" fill="none" stroke="${W}" stroke-width="${f(lw)}"/>` + circN(0, 0, 0.4, W) + circN(-hw + 11, 0, 0.35, W) + circN(hw - 11, 0, 0.35, W);
    s += rectN(-hw - 2, -3.66, 2, 7.32, W) + rectN(hw, -3.66, 2, 7.32, W);
    const nb = clamp(Math.round(+o.bills || 0), 0, 1000);
    if (nb > 0) {
      const per = Math.floor(FIELD.perRow), bh = 9 / u, rows = [[-hw, Math.min(nb, per), -10], [-hw, Math.max(0, nb - per), 10]];
      rows.forEach((r) => {
        if (r[1] <= 0) return;
        let odd = '';
        for (let i = 1; i < r[1]; i += 2) odd += `M ${f(r[0] + i * FIELD.pitch)} ${f(r[2] - bh / 2)} h ${FIELD.pitch} v ${f(bh)} h ${-FIELD.pitch} Z `;
        s += rectN(r[0], r[2] - bh / 2, r[1] * FIELD.pitch, bh, C.blue) + pathN(odd, C.blueD);
      });
    }
    return `<g transform="scale(${f(u / ps)})"><g stroke-width="${f(6 / u)}">${s}</g></g>`;
  }

  // 名稱 → {fn, w, h(建議外框,單位), zh(總表上的名稱), wide}
  const LIST = {
    bill: { fn: bill, w: 320, h: 140, zh: '千元鈔', wide: true }, payslip: { fn: payslip, w: 170, h: 196, zh: '薪資袋' }, gradcap: { fn: gradcap, w: 226, h: 140, zh: '學士帽' },
    gate: { fn: gate, w: 280, h: 236, zh: '校門' }, briefcase: { fn: briefcase, w: 210, h: 176, zh: '公事包' }, bank: { fn: bank, w: 290, h: 236, zh: '銀行' },
    survey: { fn: survey, w: 170, h: 222, zh: '問卷板' }, scale: { fn: scale, w: 350, h: 240, zh: '天秤' }, globe: { fn: globe, w: 210, h: 306, zh: '地球' },
    meter: { fn: meter, w: 262, h: 248, zh: '笑臉計量表' }, helmet: { fn: helmet, w: 210, h: 220, zh: '羅馬頭盔' }, saltbag: { fn: saltbag, w: 170, h: 196, zh: '鹽袋' },
    shaker: { fn: shaker, w: 110, h: 220, zh: '鹽罐' }, dict: { fn: dict, w: 130, h: 250, zh: '厚辭典' }, stele: { fn: stele, w: 176, h: 240, zh: '石碑' },
    field: { fn: field, w: 112, h: 72, zh: '足球場', wide: true }, tape: { fn: tape, w: 340, h: 146, zh: '捲尺', wide: true },
  };

  // s_rank_a / s_rank_b 共用的十等份階梯版面(px):chart = decileRow 的 x,y,w,h,max;左側 x 80–420 是鴿子欄(腳底 pigeon.x,y;倍率 scale)。
  // chart.h 讓 x 軸標籤(yBot+16 起、高約 91)與陰影落在字幕帶 y 850 以上;src = 薪資段固定來源牌(左上,fs 40)
  const RANK_LAYOUT = {
    chart: { x: 420, y: 190, w: 1380, h: 535, max: 133.6 },
    vals: [33.0, 38.1, 43.2, 48.7, 54.6, 62.8, 75.3, 95.9, 133.6],
    pigeon: { x: 245, y: 815, scale: 1.4 },
    src: { text: '主計總處 113 年 全年總薪資(含獎金 稅前 不含公部門與學校) 附表 2', x: 84, y: 118, fs: 40 },
  };

  const API = { C, LIST, FIELD, RANK_LAYOUT };
  Object.keys(LIST).forEach((n) => { API[n] = LIST[n].fn; });
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.PropsSalary = API;
})();
