/* turtle 圖解總表(審圖用,不進正片)。render(t, params) 回傳完整 <svg> 內容;params: {hue}。
 * 第 n 頁在 t∈[n, n+1) 顯示:前幾頁是 props_turtle.js 的圖解(每頁 4 欄 × 3 列共 12 個,下方標名稱;最後接幾個狀態變體),
 * 末兩頁是 charts.js 的元件示範。每頁前 5 格靜止(看圖用),後 5 格讓圖表元件重新逐一彈入(只為跑過進場路徑)。
 * 總表不遵守字幕帶與安全邊界(render_clip 的這兩項檢查可忽略)。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), Ch = W.Charts || require('../charts.js'), PT = W.PropsTurtle || require('../props_turtle.js');
  const PER = 12, COLS = 4, CELL_W = 480, CELL_H = 360, BOX_W = 400, BOX_H = 240, U_MAX = 1.6;
  // 總表上的示範狀態
  const DEMO = {
    hotel: { lit: [1, 1, 0, 1, 0, 1, 1, 0.5, 1, 0, 0.5, 1, 1, 1, 0, 0, 0.5, 1, 1, 0] }, incinerator: { tall: 1, rot: 2 }, fan: { ang: 20 },
    tallySheet: { hi: [2], tally: [5, 3, 7, 2, 10, 1, 4, 0, 6, 3, 2, 8, 1, 5, 0, 3, 2, 4, 1] }, house: { lit: true }, bulb: { rays: true },
    hatchling: { ang: 30 },
  };
  const EXTRA = [['turtle', { expr: 'speechless', headUp: true }, '海龜無言抬頭'], ['boar', { bald: true }, '野豬缺毛'],
    ['hotel', { lit: 0 }, '飯店全暗'], ['incinerator', { tall: 0.4, rot: 5 }, '煙囪矮'], ['bulb', { on: false }, '燈泡熄'],
    ['tallySheet', { n: 7, hi: [0, 5], tally: { 0: 9, 5: 4 } }, '記錄表七格']];
  const ENTRIES = Object.keys(PT.LIST).map((n) => [n, DEMO[n] || {}, PT.LIST[n].zh]).concat(EXTRA);
  const PROP_PAGES = Math.ceil(ENTRIES.length / PER), PAGES = PROP_PAGES + 2;

  function propPage(p, pal) {
    let s = '';
    ENTRIES.slice(p * PER, (p + 1) * PER).forEach(([name, opts, zh], i) => {
      const e = PT.LIST[name], cx = (i % COLS) * CELL_W + CELL_W / 2, top = Math.floor(i / COLS) * CELL_H;
      const u = Math.min(BOX_W / e.w, BOX_H / e.h, U_MAX);
      s += K.paper(e.fn(pal, opts), { x: cx, y: top + 145, scale: u, k: 'prop', id: name + i, wide: e.wide });
      s += K.label(zh, { x: cx, y: top + 315, fs: 36, u: 1, id: name + i });
    });
    return s;
  }

  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });

  // 圖表示範一:hbars 五條(一條高亮、一條灰)、ratioBar 三段、bigNum、iconRow(數字皆為示範,非查證數字)
  function chartsA(pal, kOf) {
    return Ch.hbars({ x: 80, y: 70, w: 1040, rowH: 96, gap: 22, pal, id: 'hb', bars: [
      { label: '塑膠袋', value: 310, icon: ic(pal, 'bag'), k: kOf(0) }, { label: '寶特瓶', value: 240, icon: ic(pal, 'bottle'), k: kOf(1) },
      { label: '吸管', value: 180, icon: ic(pal, 'straw'), hi: true, k: kOf(2) }, { label: '瓶蓋', value: 90, icon: ic(pal, 'cap'), k: kOf(3) },
      { label: '漁網', value: 40, icon: ic(pal, 'net'), grey: true, k: kOf(4) }] }) +
      Ch.ratioBar({ x: 600, y: 860, w: 1000, h: 90, pal, segs: [{ value: 50, label: '焚化', k: kOf(1) }, { value: 35, label: '回收', k: kOf(2) },
        { value: 15, label: '其他', k: kOf(3) }] }) +
      Ch.bigNum({ x: 1510, y: 230, num: '150', unit: '公尺', note: '大數字示範', pal, k: kOf(0), kNote: kOf(1) }) +
      Ch.iconRow({ x: 1510, y: 660, pitch: 220, size: 150, pal, items: [{ icon: ic(pal, 'bottle'), label: '瓶子', k: kOf(2) },
        { icon: ic(pal, 'cap'), label: '瓶蓋', k: kOf(3) }, { icon: ic(pal, 'straw'), label: '吸管', dim: true, k: kOf(4) }] });
  }

  // 圖表示範二:checklist 三種狀態、dotGrid 12/100、podium、srcTag、triviaMark、bubble 實線與虛線、dateTag、route 三站、twoCol
  function chartsB(pal, kOf) {
    return Ch.checklist({ x: 80, y: 70, w: 640, rowH: 100, gap: 24, pal, items: [{ label: '不主動提供', state: 'check', k: kOf(0), kState: kOf(1) },
      { label: '住客可索取', state: 'empty', k: kOf(1) }, { label: '真的有效嗎', state: 'q', k: kOf(2), kState: kOf(3) }] }) +
      Ch.dotGrid({ x: 950, y: 250, size: 340, n: 12, pal, k: kOf(0), kFill: kOf(1), per: 4 }) +
      Ch.podium({ x: 1500, y: 470, w: 720, h: 260, pal, places: [{ label: '塑膠袋', k: kOf(2) }, { label: '菸蒂', k: kOf(1) }, { label: '瓶蓋', k: kOf(0) }] }) +
      Ch.srcTag('來源:環境部', { x: 80, y: 500, anchor: 'left', pal, k: kOf(2) }) + Ch.srcTag('自算', { x: 560, y: 500, anchor: 'left', pal, id: 'src2', k: kOf(3) }) +
      Ch.triviaMark({ x: 1780, y: 620, k: kOf(1) }) +
      Ch.bubble('這樣有用嗎', { x: 320, y: 700, fs: 64, tail: 'bl', id: 'b1', k: kOf(0) }) +
      Ch.bubble(['聽說', '會分解'], { x: 860, y: 690, fs: 60, tail: 'br', dashed: true, id: 'b2', k: kOf(1) }) +
      Ch.dateTag({ x: 1500, y: 650, top: '2025', main: '1/1', k: kOf(2) }) +
      Ch.route({ pal, stops: [{ x: 260, y: 900, label: '飯店', k: kOf(0) }, { x: 700, y: 900, label: '垃圾車', k: kOf(1) },
        { x: 1140, y: 900, label: '焚化爐', k: kOf(2), kOn: -1 }] }) +
      Ch.twoCol({ x: 1620, y: 910, w: 440, h: 250, pal, left: { title: '有用', k: kOf(3) }, right: { title: '沒用', k: kOf(4) } });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 170 : params.hue);
    const page = Math.max(0, Math.min(PAGES - 1, Math.floor(t + 1e-6))), kp = K.frame(t - page);
    const kOf = (i) => (kp < 5 ? 99 : kp - 5 - i);              // 前 5 格全部靜止;之後逐一重新彈入
    const s = page < PROP_PAGES ? propPage(page, pal) : page === PROP_PAGES ? chartsA(pal, kOf) : chartsB(pal, kOf);
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_props_sheet', dur: PAGES, pages: PAGES, propPages: PROP_PAGES, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
