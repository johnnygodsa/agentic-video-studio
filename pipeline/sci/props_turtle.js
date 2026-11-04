/* ChannelC:turtle 片的圖解(扁平色塊剪紙)。純函式,不依賴 DOM 與 kit.js。
 * 每個函式 fn(pal, o) 回傳「以單位繪製、中心在原點」的紙片內容,由呼叫端包成紙片:
 *   K.paper(PT.turtle(pal, {expr:'speechless'}), {x, y, scale: u, k: 'prop', id: 'turtle', wide: PT.LIST.turtle.wide})
 * LIST[名] = {fn, w, h, zh, wide}:w/h 為建議外框(單位),wide = 扁長(紙片濾鏡要放寬)。
 * 外形片繼承紙片的紙白描邊;細節(N 結尾的函式)不描邊。只用 polygon/path/rect/circle(舞台量外框只認這些)。
 * 顏色:pal(K.palette(170))加固定色(品牌黃、墨、紙白)與 C 的輔助色。不用漸層、亂數、時鐘。 */
(function () {
  const Y = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7';
  const C = {
    brown: 'hsl(28 45% 36%)', brownD: 'hsl(26 48% 25%)', tan: 'hsl(38 55% 70%)', grey: 'hsl(200 8% 62%)', greyD: 'hsl(200 10% 38%)',
    greyL: 'hsl(200 14% 82%)', white: 'hsl(40 20% 96%)', red: 'hsl(6 75% 55%)', blue: 'hsl(205 70% 52%)', sky: 'hsl(195 70% 84%)',
    night: 'hsl(170 45% 14%)', pink: 'hsl(330 55% 82%)', orange: 'hsl(25 90% 58%)', green: 'hsl(130 45% 45%)',
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
  // 粗線(紙白襯底加色線):繩、線、鉤
  const rope = (d, w, col) => `<path d="${d}" fill="none" stroke="${PAPER}" stroke-width="${f(w + 7)}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  const g = (tr, s) => `<g transform="${tr}">${s}</g>`;

  // ================= 動物 =================
  // 成年海龜(側面,面向右;殼褐色)。o: {expr:'normal'|'speechless', headUp:true|角度(度)}
  function turtle(pal, o) {
    o = o || {};
    const skin = 'hsl(85 28% 44%)', skinD = 'hsl(85 30% 31%)', shell = C.brownD, scute = 'hsl(30 52% 42%)', belly = 'hsl(48 55% 78%)';
    const up = o.headUp === true ? 28 : +o.headUp || 0, sp = o.expr === 'speechless';
    const eye = sp ? circN(146, -3, 6.5, INK) + rectN(137, -11, 18, 7, skin) + rectN(137, -4.5, 18, 3.5, INK)      // 半閉眼
      : circN(146, -3, 6.5, INK) + circN(148, -5.2, 2.2, PAPER);
    const mouth = sp ? rectN(146, 11.5, 22, 3.5, INK) : pathN('M 146 11 Q 158 17 169 10 L 169 13.5 Q 158 21 146 14.5 Z', INK);
    const head = poly([[70, -6], [122, -13], [122, 25], [74, 38]], skin) +
      path('M 108 -15 C 128 -24, 160 -18, 171 -1 C 176 10, 167 23, 151 25 L 110 27 Z', skin) +
      polyN([[100, -9], [124, -12], [124, 23], [100, 26]], skin) + circN(118, 14, 4, skinD) + circN(128, -8, 3.5, skinD) + eye + mouth;
    let s = path('M -92 28 C -108 50, -134 64, -152 60 C -142 44, -126 28, -108 16 Z', skin) +                   // 後鰭
      poly([[-118, 16], [-146, 24], [-120, 30]], skin) +                                                          // 尾
      g(`rotate(${f(-up)} 78 14)`, head) +
      path('M -116 20 L 92 20 C 82 48, 40 54, -20 54 C -72 54, -106 46, -116 20 Z', belly) +                      // 腹甲
      path('M -125 25 C -120 -30, -70 -72, -15 -72 C 45 -72, 85 -35, 95 25 Z', shell);                            // 背甲
    [[[-98, 8], [-92, -22], [-66, -44], [-50, -8], [-62, 10]], [[-56, -52], [-18, -60], [-4, -14], [-38, -4]],
      [[-8, -60], [30, -54], [44, -12], [6, -12]], [[40, -48], [64, -30], [80, 6], [54, -10]]].forEach((a) => { s += polyN(a, scute); });
    s += polyN([[-116, 16], [88, 16], [92, 23], [-122, 23]], scute);
    s += path('M 72 26 C 62 60, 22 96, -34 100 C -18 78, 12 52, 34 22 Z', skin) +                                // 前鰭(最上層)
      circN(38, 48, 6, skinD) + circN(17, 69, 5.5, skinD) + circN(-6, 87, 4.5, skinD);
    return g('translate(-10 -14)', s);
  }

  // 小海龜(俯視,深灰)。o: {ang:朝向角度,0 = 朝上,順時針}
  function hatchling(pal, o) {
    const dark = 'hsl(200 15% 24%)', mid = 'hsl(200 12% 40%)';
    let s = '';
    [-1, 1].forEach((d) => {
      s += poly([[d * 18, -12], [d * 56, -32], [d * 62, -18], [d * 28, 6]], dark) + poly([[d * 16, 32], [d * 36, 54], [d * 28, 60], [d * 8, 44]], dark);
    });
    s += circ(0, -38, 15, dark) + ell(0, 8, 28, 36, dark) + ellN(0, 8, 13, 20, mid) + circN(-7, -43, 2.6, PAPER) + circN(7, -43, 2.6, PAPER);
    return g(`rotate(${f((o && o.ang) || 0)})`, s);
  }

  // 野豬(側面,面向右)。o: {bald:true 脖子缺一撮毛(露出粉色皮)}
  function boar(pal, o) {
    const fur = 'hsl(24 30% 31%)', furD = 'hsl(24 32% 17%)', skin = 'hsl(14 50% 70%)', bald = !!(o && o.bald);
    const backY = (x) => -70 + 0.004 * (x + 10) * (x + 10);
    const top = [], bot = [], x1 = bald ? 26 : 62;
    for (let x = -70, i = 0; x <= x1 + 0.1; x += 12, i++) {                    // 鬃毛:沿背脊的鋸齒
      top.push(i % 2 ? [x - 5, backY(x) - 21] : [x, backY(x) - 3]);
      bot.unshift([x, backY(x) + 11]);
    }
    let s = rect(-88, 36, 17, 54, furD) + rect(52, 36, 17, 54, furD) +                                           // 遠側的腿
      rope('M -121 -8 q -22 -4 -24 18', 6, fur) + poly([[-151, 8], [-140, 7], [-146, 27]], furD) +                // 尾巴
      path('M -122 8 C -126 -46, -72 -74, -10 -70 C 30 -68, 60 -56, 76 -36 L 82 38 C 60 60, -82 62, -112 44 Z', fur) +
      path('M 50 -54 C 80 -60, 100 -46, 112 -26 L 152 6 L 152 30 L 112 38 C 92 50, 66 46, 54 30 Z', fur) +       // 頭(楔形長吻)
      polyN([[44, -50], [64, -52], [66, 30], [46, 32]], fur) +
      poly(top.concat(bot), furD) + poly([[64, -50], [70, -90], [90, -48]], furD) +                                // 鬃毛、耳
      rect(-108, 34, 19, 58, fur) + rectN(-106, 30, 15, 12, fur) + rect(30, 36, 19, 56, fur) + rectN(32, 32, 15, 12, fur) +
      rectN(-108, 82, 19, 10, INK) + rectN(30, 82, 19, 10, INK) + rectN(-88, 81, 17, 9, INK) + rectN(52, 81, 17, 9, INK) +
      ell(152, 18, 7, 13, skin) + circN(153, 14, 2, furD) + circN(153, 22, 2, furD) +                              // 吻端
      poly([[116, 34], [124, 12], [130, 34]], PAPER) + circN(100, -14, 6, PAPER) + circN(101.5, -14, 3.4, INK);    // 獠牙、眼
    if (bald) s += polyN([[26, -62], [42, -59], [58, -51], [58, -36], [40, -32], [28, -40]], skin) + rectN(33, -52, 4, 9, furD) + rectN(46, -47, 4, 8, furD);
    return g('translate(-4 -1)', s);
  }

  // 水母
  function jellyfish(pal, o) {
    const bell = (o && o.col) || C.pink, arm = 'hsl(330 45% 68%)';
    let s = '';
    [-36, -12, 12, 36].forEach((x, i) => { s += rope(`M ${x} -6 q ${i % 2 ? -10 : 10} 20 0 40 q ${i % 2 ? 10 : -10} 20 0 40 q ${i % 2 ? -8 : 8} 14 0 ${i % 3 ? 28 : 18}`, 7, arm); });
    s += path('M -55 -10 C -55 -84, 55 -84, 55 -10 Q 41 2 27 -8 Q 14 2 0 -8 Q -14 2 -27 -8 Q -41 2 -55 -10 Z', bell) + ellN(-22, -42, 9, 14, PAPER);
    return g('translate(0 -19)', s);
  }

  // ================= 建築與設施 =================
  // 飯店(4 欄 × 5 列共 20 扇窗,由上而下、由左而右)。o.lit:每扇窗的亮度陣列(0–1 或布林)或單一亮度;≥0.67 亮、≥0.34 半亮、其餘暗
  function hotel(pal, o) {
    const lit = o && o.lit, wall = 'hsl(205 28% 46%)', dark = 'hsl(205 35% 20%)', dim = 'hsl(46 55% 42%)';
    const lv = (i) => { const v = Array.isArray(lit) ? lit[i] : lit; return v == null || v === true ? 1 : +v; };
    let s = rect(-110, -128, 220, 268, wall) + rect(-120, -144, 240, 20, 'hsl(205 30% 32%)');
    for (let i = 0; i < 20; i++) {
      const v = lv(i);
      s += rectN(-92 + (i % 4) * 50, -112 + Math.floor(i / 4) * 42, 34, 28, v >= 0.67 ? Y : v >= 0.34 ? dim : dark);
    }
    return s + rectN(-20, 100, 40, 40, dark) + rect(-34, 88, 68, 14, C.red);
  }

  // 焚化爐加煙囪加旋轉餐廳(底邊固定在 y=+200)。o: {tall:煙囪高度比例 0–1, rot:餐廳旋轉格數(暗窗的位置), restaurant:false 不畫餐廳}
  function incinerator(pal, o) {
    o = o || {};
    const tall = o.tall == null ? 1 : Math.max(0, Math.min(1, o.tall)), rot = ((Math.round(o.rot || 0) % 6) + 6) % 6;
    const top = 200 - (130 + 262 * tall), cx = 85;
    let s = poly([[-140, 200], [-140, 112], [-92, 82], [40, 82], [40, 200]], C.greyL) + rectN(-122, 134, 52, 66, C.greyD) +
      rectN(-52, 122, 74, 26, C.sky) + rect(cx - 24, top, 48, 200 - top, C.white);
    for (let y = top + 104; y + 22 < 196; y += 60) s += rectN(cx - 22, y, 44, 22, pal.main);
    s += rect(cx - 29, top - 8, 58, 12, C.greyD);
    if (o.restaurant !== false) {
      const ry = top + 44;
      s += rect(cx - 50, ry - 9, 100, 12, C.greyD, 5) + rect(cx - 62, ry, 124, 36, C.red, 12);
      for (let i = 0; i < 6; i++) s += rectN(cx - 51 + i * 18, ry + 11, 12, 14, i === rot ? INK : Y);
    }
    return g('translate(-4 0)', s);
  }

  // 小房子。o: {lit:窗亮}
  function house(pal, o) {
    return rect(-60, -10, 120, 85, 'hsl(35 60% 80%)') + poly([[-78, -8], [0, -72], [78, -8]], C.red) + rectN(-38, 30, 28, 45, C.brown) +
      rectN(8, 12, 30, 28, o && o.lit ? Y : C.sky);
  }

  // 櫃檯(桌面、服務鈴、立牌)
  function counter(pal) {
    return rect(-124, -74, 62, 36, PAPER) + rectN(-114, -64, 42, 6, INK) + rectN(-114, -52, 28, 6, C.grey) +
      path('M 62 -40 A 22 22 0 0 1 106 -40 Z', Y) + circ(84, -66, 5, INK) +
      rect(-135, -22, 270, 96, C.brown) + rectN(-118, -4, 236, 14, 'hsl(28 45% 46%)') + rectN(-118, 44, 236, 14, 'hsl(28 45% 46%)') +
      rect(-146, -42, 292, 22, C.brownD);
  }

  // 走廊告示(告示板:禁止記號加幾行字的示意條)
  function notice(pal) {
    return rect(-76, -100, 152, 200, pal.text) + rectN(-66, -90, 132, 180, PAPER) + rectN(-66, -90, 132, 26, pal.main) +
      circN(0, -18, 36, C.red) + circN(0, -18, 25, PAPER) + rectN(-17, -22, 34, 8, INK) + g('rotate(45 0 -18)', rectN(-33, -23, 66, 10, C.red)) +
      rectN(-48, 32, 96, 9, INK) + rectN(-48, 50, 96, 9, C.grey) + rectN(-48, 68, 62, 9, C.grey) + circ(0, -100, 8, C.red);
  }

  // ================= 垃圾處理 =================
  function bin(pal) {
    let s = rect(-15, -80, 30, 16, C.greyD, 5) + poly([[-48, -50], [48, -50], [38, 80], [-38, 80]], C.grey);
    [-22, 0, 22].forEach((x) => { s += rectN(x - 4, -34, 8, 98, C.greyD, 4); });
    return s + rect(-56, -66, 112, 18, C.greyD, 5);
  }

  // 垃圾車(台灣的黃色垃圾車,面向右)。o: {spin:輪子轉角(度)}
  function truck(pal, o) {
    const spin = (o && o.spin) || 0;
    const wheel = (x) => circ(x, 56, 27, INK) + circN(x, 56, 11, C.greyL) + g(`rotate(${f(spin)} ${x} 56)`, rectN(x - 2.5, 34, 5, 44, C.greyL));
    return rect(-150, 44, 292, 14, C.greyD) + poly([[-150, -36], [-118, -78], [40, -78], [40, 46], [-150, 46]], Y) +
      rectN(-112, -40, 140, 16, pal.text) + polyN([[-150, -36], [-132, -60], [-132, 46], [-150, 46]], 'hsl(42 85% 46%)') +
      poly([[50, -42], [108, -42], [142, -4], [142, 46], [50, 46]], Y) + polyN([[62, -31], [103, -31], [125, -5], [62, -5]], C.sky) +
      rectN(128, 18, 14, 12, C.red) + wheel(-88) + wheel(94);
  }

  // 灰渣堆
  function ashPile(pal) {
    let s = path('M -110 45 C -80 12, -52 -30, -22 -40 C 0 -48, 20 -22, 40 -26 C 70 -30, 94 20, 110 45 Z', C.greyD);
    [[-50, 10, 6], [-18, -14, 5], [14, 6, 7], [48, -2, 5], [72, 24, 6], [-78, 30, 5], [-14, 26, 5]].forEach((c, i) => { s += circN(c[0], c[1], c[2], i % 2 ? C.grey : C.greyL); });
    return s;
  }

  // 淨灘記錄表(夾板上 19 格,4 欄由左而右、由上而下)。o: {hi:高亮格(索引或陣列,0 起), tally:各格正字筆畫數(陣列或 {索引:數},每格最多 10), n:出現幾格}
  const ZHENG = [[0, 0, 18, 3], [7.5, 0, 3, 18], [9, 8, 8, 3], [2, 8, 3, 10], [0, 15, 18, 3]];
  function tallySheet(pal, o) {
    o = o || {};
    const n = Math.min(19, o.n == null ? 19 : o.n), hi = [].concat(o.hi == null ? [] : o.hi), tally = o.tally || [];
    const cw = 70, ch = 46, gp = 4, x0 = -(4 * cw + 3 * gp) / 2, y0 = -114;
    let s = rect(-170, -144, 340, 300, C.brown, 8) + rectN(-158, -126, 316, 270, PAPER) + rect(-42, -158, 84, 28, C.greyD, 6);
    for (let i = 0; i < n; i++) {
      const x = x0 + (i % 4) * (cw + gp), y = y0 + Math.floor(i / 4) * (ch + gp), on = hi.indexOf(i) >= 0, t = Math.min(10, tally[i] || 0);
      s += rectN(x, y, cw, ch, on ? Y : `hsl(${pal.h} 22% 88%)`, 3) + rectN(x + 5, y + ch / 2 - 4, 13, 8, on ? INK : C.grey, 2);
      for (let j = 0; j < t; j++) {
        const z = ZHENG[j % 5];
        s += rectN(x + 23 + Math.floor(j / 5) * 23 + z[0], y + 14 + z[1], z[2], z[3], INK);
      }
    }
    return g('translate(0 1)', s);
  }

  // ================= 海洋垃圾 =================
  function straw(pal, o) {
    const col = (o && o.col) || C.red;
    return g('translate(-16 0)', rect(-8, -62, 16, 172, col, 4) + poly([[-8, -58], [8, -62], [40, -104], [27, -113]], col) +
      rectN(-8, -44, 16, 5, PAPER) + rectN(-8, -34, 16, 5, PAPER) + rectN(-8, -24, 16, 5, PAPER));
  }

  // 寶特瓶。o: {cap:false 不畫瓶蓋}
  function bottle(pal, o) {
    return (o && o.cap === false ? '' : rect(-15, -110, 30, 20, C.blue, 3)) + rect(-11, -92, 22, 16, C.sky) +
      path('M -11 -80 C -36 -70 -38 -50 -38 -30 L -38 96 Q -38 106 -28 106 L 28 106 Q 38 106 38 96 L 38 -30 C 38 -50 36 -70 11 -80 Z', C.sky) +
      rectN(-38, -8, 76, 52, pal.main) + rectN(-27, -54, 8, 32, PAPER) + rectN(-27, 58, 8, 30, PAPER);
  }

  function cap(pal, o) {
    let s = rect(-36, -20, 72, 40, (o && o.col) || C.blue, 6);
    for (let x = -26; x <= 26; x += 13) s += rectN(x - 2.5, -4, 5, 20, 'hsl(205 70% 36%)', 2);
    return s;
  }

  // 針筒(針頭朝右)
  function syringe(pal) {
    let s = rect(-122, -5, 54, 10, C.greyD) + rect(-130, -23, 11, 46, C.greyD, 3) + poly([[66, -3.5], [126, 0], [66, 3.5]], C.greyD) +
      rect(50, -8, 18, 16, C.grey) + rect(-70, -18, 122, 36, C.white, 4) + rectN(-22, -14, 70, 28, C.sky) + rectN(-30, -16, 9, 32, INK) +
      rect(-78, -30, 10, 60, C.greyD, 3);
    for (let x = -10; x <= 40; x += 12.5) s += rectN(x, -14, 3, 11, INK);
    return s;
  }

  // 漁網(菱形網格加浮球)
  function net(pal) {
    let d = '';
    [1, -1].forEach((sg) => {
      for (let c = -6; c <= 6; c++) {
        const lo = Math.max(-60, sg > 0 ? -100 - c * 40 : c * 40 - 100), hi = Math.min(80, sg > 0 ? 120 - c * 40 : c * 40 + 120);
        if (hi - lo > 5) d += `M ${f(c * 40 + sg * (lo - 10))} ${f(lo)} L ${f(c * 40 + sg * (hi - 10))} ${f(hi)} `;
      }
    });
    let s = rope(d.trim(), 4.5, 'hsl(190 32% 30%)') + rope('M -110 -60 L 110 -60', 8, C.brownD);
    [-88, -44, 0, 44, 88].forEach((x) => { s += circ(x, -60, 11, C.orange); });
    return g('translate(0 -5)', s);
  }

  // 魚鉤
  function hook(pal) {
    return rope('M 31 -49 L 31 37 A 30 30 0 0 1 -29 37 L -29 21', 9, C.greyD) + poly([[-41, 23], [-29, -3], [-19, 25]], C.greyD) +
      circ(31, -59, 10, C.greyD) + circN(31, -59, 4.2, PAPER);
  }

  // 釣魚線(纏成一團)
  function fishline(pal) {
    return rope('M -90 40 C -60 -60, 20 -70, 30 -10 C 40 50, -50 60, -40 0 C -30 -50, 60 -60, 70 0 C 78 40, 30 60, 10 30 C -10 0, 60 -20, 92 30', 5, 'hsl(200 55% 42%)');
  }

  // 塑膠袋(紅白條背心袋)。o: {col:給顏色就畫成單色素面袋}
  function bag(pal, o) {
    const col = o && o.col;
    let s = poly([[-58, -92], [-30, -92], [-24, -40], [24, -40], [30, -92], [58, -92], [62, -20], [66, 88], [-66, 88], [-62, -20]], col || C.white);
    if (!col) {
      s += rectN(-50, -90, 9, 176, C.red) + rectN(41, -90, 9, 176, C.red);
      [-30, -10, 10, 30].forEach((x) => { s += rectN(x - 4.5, -38, 9, 124, C.red); });
    }
    return s;
  }

  // 塑膠碎片。o: {n:出現幾片(最多 8)}
  const FRAG_T = [[[-12, -8], [10, -12], [14, 6], [-8, 10]], [[-11, -10], [13, -4], [-2, 13]], [[-14, -4], [0, -12], [14, -2], [6, 10], [-10, 8]]];
  const FRAG_P = [[-68, -22], [-36, 18], [-4, -26], [30, 14], [62, -18], [78, 24], [-80, 24], [0, 30]];
  function fragments(pal, o) {
    const cols = [C.red, C.blue, Y, pal.main, C.white, C.green, C.orange, C.blue], n = Math.min(8, o && o.n != null ? o.n : 8);
    let s = '';
    for (let i = 0; i < n; i++) s += g(`translate(${FRAG_P[i][0]} ${FRAG_P[i][1]}) rotate(${i * 47})`, poly(FRAG_T[i % 3], cols[i]));
    return s;
  }

  // 飲料杯(透明杯、吸管、珍珠)
  function cup(pal) {
    let s = poly([[4, -104], [18, -104], [10, -40], [-4, -40]], C.red) + poly([[-40, -42], [40, -42], [30, 96], [-30, 96]], C.sky) +
      polyN([[-37.5, -8], [37.5, -8], [28, 92], [-28, 92]], 'hsl(28 50% 58%)');
    [[-16, 80], [-2, 84], [13, 79], [-8, 68], [7, 66]].forEach((c) => { s += circN(c[0], c[1], 5.5, INK); });
    return s + rect(-45, -54, 90, 13, C.greyL, 4);
  }

  // 免洗餐具(免洗筷一雙加塑膠湯匙)
  function cutlery(pal) {
    return g('translate(-4 0)', poly([[-50, -100], [-40, -100], [-36, 100], [-44, 100]], C.tan) + poly([[-28, -100], [-18, -100], [-18, 100], [-26, 100]], C.tan) +
      rect(34, -52, 12, 150, C.white, 6) + ell(40, -72, 18, 27, C.white) + ellN(40, -72, 10, 18, C.greyL));
  }

  // ================= 備品 =================
  function toothbrush(pal, o) {
    const col = (o && o.col) || pal.main;
    let s = rect(56, -26, 46, 28, C.white, 3);
    [67, 79, 91].forEach((x) => { s += rectN(x - 1.5, -24, 3, 22, C.greyL); });
    return s + rect(-110, 2, 176, 18, col, 9) + rect(48, 0, 62, 22, col, 8) + rectN(40, 4, 20, 14, col);
  }

  function toothpaste(pal) {
    return poly([[-100, -34], [-88, -34], [60, -22], [60, 22], [-88, 34], [-100, 34]], C.white) + polyN([[-42, -30], [22, -25], [22, 25], [-42, 30]], pal.main) +
      rectN(-100, -34, 11, 68, C.greyL) + poly([[60, -22], [78, -10], [78, 10], [60, 22]], C.greyL) + rect(78, -13, 26, 26, C.red, 4);
  }

  function comb(pal, o) {
    const a = [[-100, -30], [100, -30], [100, -6]];
    for (let i = 0; i < 13; i++) { const xr = 94 - i * 15; a.push([xr, -6], [xr, 30], [xr - 8, 30], [xr - 8, -6]); }
    a.push([-100, -6]);
    return poly(a, (o && o.col) || C.brown);
  }

  function razor(pal) {
    let s = poly([[-10, -68], [10, -68], [8, -40], [-8, -40]], C.greyD) + rect(-11, -46, 22, 152, C.blue, 10);
    [0, 14, 28, 42].forEach((y) => { s += rectN(-7, 30 + y, 14, 6, 'hsl(205 70% 36%)', 3); });
    return s + rect(-46, -102, 92, 36, C.blue, 6) + rectN(-38, -92, 76, 5, C.greyL) + rectN(-38, -82, 76, 5, C.greyL);
  }

  // 刮鬍泡(噴罐加一坨泡)
  function foam(pal) {
    return g('translate(0 6)', circ(-18, -88, 12, C.white) + circ(14, -90, 13, C.white) + circ(-3, -98, 17, C.white) + rect(-9, -80, 22, 18, C.greyD, 3) +
      rect(-26, -64, 52, 16, C.greyL, 6) + rect(-32, -50, 64, 150, C.blue, 6) + rectN(-32, -10, 64, 56, PAPER) + rectN(-22, 2, 44, 9, C.red) +
      rectN(-22, 20, 30, 9, C.grey));
  }

  // 浴帽(圓頂、鬆緊帶皺邊、圓點)
  function showerCap(pal) {
    let s = path('M -80 20 C -86 -72, 86 -72, 80 20 Z', C.sky);
    for (let x = -78; x <= 78; x += 26) s += circ(x, 24, 14, C.sky);
    s += rectN(-78, 14, 156, 14, C.sky);
    [[-40, -18], [0, -34], [40, -18], [-20, 4], [22, 2], [-56, 4], [58, 2]].forEach((c) => { s += circN(c[0], c[1], 6, PAPER); });
    return g('translate(0 6)', s);
  }

  function slipper(pal) {
    return path('M -34 -70 C -34 -106, 34 -106, 36 -66 L 30 80 C 28 104, -28 104, -30 80 Z', C.greyL) + ellN(0, 52, 20, 30, C.white) +
      poly([[-40, -62], [40, -58], [38, -6], [-38, -10]], pal.main);
  }

  // 小瓶(旅行用小包裝)
  function miniBottle(pal, o) {
    return rect(-14, -62, 28, 22, C.greyD, 3) + rect(-26, -42, 52, 104, (o && o.col) || 'hsl(40 75% 62%)', 10) + rectN(-18, -12, 36, 42, PAPER) +
      rectN(-12, -2, 24, 6, INK) + rectN(-12, 12, 16, 6, C.grey);
  }

  // 大瓶(壓頭式補充瓶)
  function pumpBottle(pal, o) {
    return g('translate(0 -8)', poly([[-10, -94], [42, -94], [42, -68], [30, -68], [30, -80], [-10, -80]], C.greyD) + rect(-5, -82, 10, 34, C.greyD) +
      rect(-13, -52, 26, 24, C.greyD, 3) + rect(-42, -30, 84, 140, (o && o.col) || pal.text, 12) + rectN(-28, 6, 56, 64, PAPER) +
      rectN(-18, 20, 36, 8, INK) + rectN(-18, 38, 24, 8, C.grey));
  }

  // ================= 其他 =================
  // 電風扇。o: {ang:葉片角度(度)}
  function fan(pal, o) {
    const ang = (o && o.ang) || 0;
    let blades = '';
    for (let i = 0; i < 3; i++) blades += g(`rotate(${i * 120})`, path('M 0 0 C 22 -18, 42 -58, 12 -68 C -16 -72, -12 -30, 0 0 Z', pal.main));
    return rect(-7, 40, 14, 70, C.greyD) + rect(-48, 104, 96, 16, C.greyD, 8) + circ(0, -38, 80, C.greyD) + circN(0, -38, 71, C.white) +
      g(`translate(0 -38) rotate(${f(ang)})`, blades) + circ(0, -38, 13, C.greyD);
  }

  // 手機(直立)。o: {screen:螢幕顏色}
  function phone(pal, o) {
    return rect(-48, -95, 96, 190, INK, 14) + rectN(-40, -80, 80, 152, (o && o.screen) || pal.pad, 4) + circN(0, 83, 5, C.grey) + rectN(-12, -89, 24, 4, C.grey, 2);
  }

  function coin(pal) {
    return circ(0, 0, 50, 'hsl(40 90% 48%)') + circN(0, 0, 40, Y) +
      `<text x="0" y="2" font-family="GenSen" font-size="54" text-anchor="middle" dominant-baseline="central" fill="${INK}" stroke="none">$</text>`;
  }

  // 燈泡。o: {on:false 熄(灰), rays:true 加光芒}
  function bulb(pal, o) {
    const on = !(o && o.on === false);
    let s = '';
    if (on && o && o.rays) [-60, -30, 0, 30, 60].forEach((a) => { s += g(`rotate(${a} 0 -28)`, rect(-5, -104, 10, 26, Y, 5)); });
    s += rect(-9, 68, 18, 9, INK, 3) + rect(-20, 38, 40, 31, C.greyD, 4) + rectN(-20, 46, 40, 5, C.greyL) + rectN(-20, 58, 40, 5, C.greyL) +
      path('M -45 -28 A 45 45 0 1 1 45 -28 C 45 -2, 24 10, 22 40 L -22 40 C -24 10, -45 -2, -45 -28 Z', on ? Y : C.greyL) + ellN(-18, -42, 8, 13, PAPER);
    return s;
  }

  // 月亮(弦月)
  function moon(pal) {
    return path('M 38 -55 A 58 58 0 1 0 38 55 A 62 62 0 0 1 38 -55 Z', Y);
  }

  // 台灣輪廓(簡化 28 點,經緯度等距投影)。twXY(lon, lat) 回傳同一座標系的 [x, y],供場景在圖上標位置。o: {fill}
  const TW = [[121.54, 25.30], [121.75, 25.15], [122.00, 25.01], [121.88, 24.85], [121.85, 24.60], [121.77, 24.30], [121.62, 24.00],
    [121.52, 23.50], [121.40, 23.10], [121.18, 22.76], [121.00, 22.50], [120.90, 22.25], [120.86, 21.90], [120.74, 21.96], [120.70, 22.12],
    [120.60, 22.35], [120.45, 22.47], [120.28, 22.58], [120.18, 22.90], [120.06, 23.08], [120.12, 23.50], [120.20, 23.82], [120.42, 24.15],
    [120.60, 24.42], [120.78, 24.68], [120.98, 24.92], [121.15, 25.08], [121.38, 25.16]];
  const twXY = (lon, lat) => [(lon - 121.03) * 0.916 * 82, -(lat - 23.6) * 82];
  function taiwan(pal, o) {
    return poly(TW.map((p) => twXY(p[0], p[1])), (o && o.fill) || pal.main);
  }

  function car(pal, o) {
    const wheel = (x) => circ(x, 42, 20, INK) + circN(x, 42, 8, C.greyL);
    return g('translate(0 -12)', poly([[-56, 4], [-36, -38], [40, -38], [66, 4]], (o && o.col) || C.red) + rect(-100, 0, 200, 42, (o && o.col) || C.red, 12) +
      polyN([[-42, 0], [-28, -29], [0, -29], [0, 0]], C.sky) + polyN([[8, 0], [8, -29], [35, -29], [52, 0]], C.sky) + rectN(86, 10, 14, 10, Y) +
      wheel(-58) + wheel(58));
  }

  function computer(pal) {
    return rect(-10, 35, 20, 26, C.greyD) + rect(-46, 58, 92, 13, C.greyD, 6) + rect(-85, -75, 170, 112, INK, 8) + rectN(-75, -65, 150, 92, pal.pad, 3) +
      rectN(-58, -48, 70, 9, pal.text) + rectN(-58, -30, 100, 9, PAPER) + rectN(-58, -12, 84, 9, PAPER);
  }

  function microwave(pal) {
    return rect(-88, 56, 20, 9, INK) + rect(68, 56, 20, 9, INK) + rect(-100, -60, 200, 118, C.greyL, 8) + rectN(-88, -47, 128, 92, INK, 4) +
      rectN(-78, -37, 108, 72, 'hsl(200 12% 30%)', 3) + circN(70, -24, 13, C.greyD) + rectN(56, 4, 28, 9, C.greyD, 3) + rectN(56, 22, 28, 9, C.greyD, 3);
  }

  // 名稱 → {fn, w, h(建議外框,單位), zh(總表上的名稱), wide}
  const LIST = {
    turtle: { fn: turtle, w: 330, h: 180, zh: '成年海龜' }, hatchling: { fn: hatchling, w: 130, h: 130, zh: '小海龜' },
    boar: { fn: boar, w: 316, h: 190, zh: '野豬' }, jellyfish: { fn: jellyfish, w: 124, h: 180, zh: '水母' },
    hotel: { fn: hotel, w: 250, h: 290, zh: '飯店' }, incinerator: { fn: incinerator, w: 296, h: 416, zh: '焚化爐' },
    house: { fn: house, w: 160, h: 150, zh: '小房子' }, counter: { fn: counter, w: 296, h: 150, zh: '櫃檯' },
    notice: { fn: notice, w: 156, h: 212, zh: '走廊告示' }, bin: { fn: bin, w: 116, h: 164, zh: '垃圾桶' },
    truck: { fn: truck, w: 300, h: 166, zh: '垃圾車' }, ashPile: { fn: ashPile, w: 224, h: 96, zh: '灰渣堆' },
    tallySheet: { fn: tallySheet, w: 344, h: 318, zh: '淨灘記錄表' }, straw: { fn: straw, w: 52, h: 226, zh: '吸管' },
    bottle: { fn: bottle, w: 80, h: 220, zh: '寶特瓶' }, cap: { fn: cap, w: 76, h: 44, zh: '瓶蓋' },
    syringe: { fn: syringe, w: 260, h: 64, zh: '針筒', wide: true }, net: { fn: net, w: 240, h: 160, zh: '漁網' },
    hook: { fn: hook, w: 92, h: 142, zh: '魚鉤' }, fishline: { fn: fishline, w: 190, h: 110, zh: '釣魚線' },
    bag: { fn: bag, w: 136, h: 184, zh: '塑膠袋' }, fragments: { fn: fragments, w: 190, h: 90, zh: '塑膠碎片' },
    cup: { fn: cup, w: 94, h: 204, zh: '飲料杯' }, cutlery: { fn: cutlery, w: 116, h: 204, zh: '免洗餐具' },
    toothbrush: { fn: toothbrush, w: 224, h: 52, zh: '牙刷', wide: true }, toothpaste: { fn: toothpaste, w: 208, h: 72, zh: '牙膏' },
    comb: { fn: comb, w: 204, h: 64, zh: '梳子', wide: true }, razor: { fn: razor, w: 96, h: 212, zh: '刮鬍刀' },
    foam: { fn: foam, w: 70, h: 216, zh: '刮鬍泡' }, showerCap: { fn: showerCap, w: 190, h: 110, zh: '浴帽' },
    slipper: { fn: slipper, w: 84, h: 200, zh: '拖鞋' }, miniBottle: { fn: miniBottle, w: 56, h: 128, zh: '小瓶' },
    pumpBottle: { fn: pumpBottle, w: 88, h: 208, zh: '大瓶' }, fan: { fn: fan, w: 164, h: 242, zh: '電風扇' },
    phone: { fn: phone, w: 100, h: 194, zh: '手機' }, coin: { fn: coin, w: 104, h: 104, zh: '硬幣' },
    bulb: { fn: bulb, w: 150, h: 190, zh: '燈泡' }, moon: { fn: moon, w: 96, h: 120, zh: '月亮' },
    taiwan: { fn: taiwan, w: 150, h: 284, zh: '台灣輪廓' }, car: { fn: car, w: 204, h: 104, zh: '汽車' },
    computer: { fn: computer, w: 174, h: 150, zh: '電腦' }, microwave: { fn: microwave, w: 204, h: 128, zh: '微波爐' },
  };

  const API = { C, LIST, twXY };
  Object.keys(LIST).forEach((n) => { API[n] = LIST[n].fn; });
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.PropsTurtle = API;
})();
