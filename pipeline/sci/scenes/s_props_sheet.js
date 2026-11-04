/* snack 圖解總表(審圖用,不進正片)。render(t, params) 回傳完整 <svg> 內容;params: {hue}。
 * 第 n 頁在 t∈[n, n+1) 顯示,共 11 頁:前三頁各 6 個圖解(3 欄 × 2 列,下方標名稱),第 4 頁是地瓜球五種加台灣四城兩種,
 * 第 5 頁是深色夜空底上的燈泡串與攤車;第 6–9 頁是第二批圖解(各 8 個,4 欄 × 2 列),第 10 頁地瓜球五種加天平三種傾斜,
 * 第 11 頁廟、磚牆、小人。全部靜止、無進場動畫。
 * 總表不遵守字幕帶與安全邊界(render_clip 的這兩項檢查可忽略)。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), PS = W.PropsSnack || require('../props_snack.js');
  const COLS = 3, CELL_W = 640, CELL_H = 540, BOX_W = 540, BOX_H = 340, U_MAX = 1.9, PAGES = 11;
  // [圖解名, 參數, 標名]
  const P1 = [['stall', { sign: '骰子牛' }], ['bulbString', {}], ['bill100', {}], ['coin50', {}], ['coin10', {}], ['diceBeef', {}]];
  const P2 = [['folder', { open: false, label: '帳本' }, '資料夾(關)'], ['folder', { open: true, label: '帳本' }, '資料夾(開)'], ['alarm', {}], ['clipboard', {}],
    ['payEnvelope', {}], ['calculator', {}]];
  const P3 = [['chickenCutlet', {}], ['bobaCup', {}], ['braisedPorkRice', {}], ['steakPlate', { side: 'potato' }, '牛排 馬鈴薯'],
    ['steakPlate', { side: 'noodle' }, '牛排 麵'], ['steakPlate', { side: 'noodle', egg: true }, '牛排 麵加蛋']];
  const P4A = [['sweetBall', {}, '地瓜球'], ['sweetBall', { cut: true, bubble: 0.2, skin: 0.8 }, '剖面 小泡厚皮'], ['sweetBall', { cut: true, bubble: 0.6, skin: 0.5 }, '剖面 中泡'],
    ['sweetBall', { cut: true, bubble: 1, skin: 0.25 }, '剖面 大泡薄皮'], ['sweetBall', { cut: true, hollow: 1, skin: 0.2 }, '剖面 全空']];
  const P4B = [['taiwan4', { on: [1, 1, 1, 1] }, '台灣四城 全亮'], ['taiwan4', { on: [1, 0, 0, 1] }, '只亮臺北高雄']];

  const L = (names) => names.map((n) => [n, {}]);
  const P6 = L(['dumplings', 'beefNoodle', 'meatball', 'oysterOmelet', 'friedEgg', 'eggPancake', 'stinkyTofu', 'popcornChicken']);
  const P7 = L(['burger', 'hotpot', 'soyMilk', 'riceBall', 'bento', 'soupBowl', 'eggCake', 'ramen']);
  const P8 = L(['kimbap', 'meatChunk', 'skimmer', 'fryPot', 'paperBag', 'gasTank', 'spatula', 'breakfastBag']);
  const P9 = L(['scale', 'eggCrate', 'suitcase', 'gavel', 'brain', 'crown', 'magnifier']).concat([['folder', { open: true, noLabel: true }, '資料夾(無標籤)']]);
  const P10 = P4A.concat([-1, 0, 1].map((t) => ['balance', { tilt: t }, `天平 tilt ${t}`]));
  const P11 = [['temple', { plaque: '天后宮' }, '廟(天后宮)'], ['wall', { text: '1000 円' }, '磚牆(1000 円)'], ['person', { grey: false }, '小人'], ['person', { grey: true }, '小人(灰)']];

  const item = (pal, [name, opts, zh], cx, cy, u, ly, i, p) => {
    const e = PS.LIST[name];
    return K.paper(e.fn(pal, opts), { x: cx, y: cy, scale: u, k: 'prop', id: `${name}${p}${i}`, wide: e.wide }) +
      K.label(zh || e.zh, { x: cx, y: ly, fs: 36, u: 1, id: `${name}${p}${i}` });
  };

  function gridPage(p, list, pal, cols) {
    let s = '';
    const cw = 1920 / (cols || COLS), bw = cw - 100;
    list.forEach((it, i) => {
      const e = PS.LIST[it[0]], cx = (i % (cols || COLS)) * cw + cw / 2, top = Math.floor(i / (cols || COLS)) * CELL_H;
      const u = Math.min(bw / e.w, BOX_H / e.h, U_MAX);
      s += item(pal, [it[0], it[1], it[2] || e.zh], cx, top + 220, u, top + 470, i, p);
    });
    return s;
  }

  function page4(pal) {
    let s = '';
    P4A.forEach((it, i) => {
      const e = PS.LIST[it[0]], u = Math.min(340 / e.w, 300 / e.h, 1.6);
      s += item(pal, it, i * 384 + 192, 170, u, 345, i, 3);
    });
    P4B.forEach((it, i) => {
      const e = PS.LIST[it[0]], u = 1.8;
      s += item(pal, it, i * 960 + 480, 725, u, 1030, i, 4);
    });
    return s;
  }

  function nightPage(pal) {
    const night = K.paper(`<rect x="-940" y="-520" width="1880" height="1040" fill="${PS.C.night}"/>`, { x: 960, y: 540, k: 'ground', id: 'night', wide: true });
    const bs = PS.LIST.bulbString, st = PS.LIST.stall;
    return night + K.paper(bs.fn(pal, { n: 12, w: 1500, sag: 70 }), { x: 960, y: 170, scale: 1, k: 'prop', id: 'bulbNight', wide: true }) +
      K.paper(st.fn(pal, { sign: '骰子牛', lit: true }), { x: 960, y: 640, scale: 2, k: 'prop', id: 'stallNight', wide: st.wide });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue);
    const page = Math.max(0, Math.min(PAGES - 1, Math.floor(t + 1e-6)));
    const s = [() => gridPage(0, P1, pal), () => gridPage(1, P2, pal), () => gridPage(2, P3, pal), () => page4(pal), () => nightPage(pal),
      () => gridPage(5, P6, pal, 4), () => gridPage(6, P7, pal, 4), () => gridPage(7, P8, pal, 4), () => gridPage(8, P9, pal, 4), () => gridPage(9, P10, pal, 4), () => gridPage(10, P11, pal, 4)][page]();
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_props_sheet', dur: PAGES, pages: PAGES, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
