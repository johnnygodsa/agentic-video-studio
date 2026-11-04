/* pearl 圖解總表(審圖用,不進正片)。render(t, params) 回傳完整 <svg> 內容;params: {hue}。
 * 第 n 頁在 t∈[n, n+1) 顯示,共 5 頁,每頁 8 個圖解(4 欄 × 2 列,下方標名稱),含各參數變化。全部靜止、無進場動畫。
 * 總表不遵守字幕帶與安全邊界(render_clip 的這兩項檢查可忽略)。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), PP = W.PropsPearl || require('../props_pearl.js');
  const COLS = 4, CELL_H = 540, BOX_H = 340, U_MAX = 1.9, PAGES = 5;
  // [圖解名, 參數, 標名]
  const P1 = [['cup', {}, '手搖杯'], ['cup', { ice: true }, '手搖杯 加冰'], ['pearl', {}, '黑珍珠 軟'], ['pearl', { hard: true }, '黑珍珠 硬'],
    ['vinegar', {}], ['wifecake', {}], ['lock', {}], ['bag', {}, '原料袋(澱粉)']];
  const P2 = [['chain', {}, '澱粉鏈 0 零件'], ['chain', { tags: 3 }, '澱粉鏈 3 零件'], ['chain', { tags: 6 }, '澱粉鏈 6 零件'], ['chain', { tags: 8 }, '澱粉鏈 8 零件'],
    ['chain', { bend: 0.5 }, '澱粉鏈 彎0.5'], ['chain', { bend: 1 }, '澱粉鏈 彎1'], ['chain', { bend: 1, tags: 3 }, '彎1 加3零件'], ['bag', { text: '粉圓' }, '原料袋(粉圓)']];
  const P3 = [['pot', {}, '大鍋 熱氣'], ['pot', { steam: false }, '大鍋 無熱氣'], ['rice', {}, '白飯 軟'], ['rice', { hard: true }, '白飯 硬'],
    ['clock', { h: 3 }, '時鐘 3 時'], ['clock', { h: 6.5 }, '時鐘 6:30'], ['germ', {}], ['germ', { full: true }, '細菌小人 肚子鼓']];
  const P4 = [['thermo', {}], ['factory', {}], ['noodle', {}], ['frozen', {}], ['sausage', {}], ['fishball', {}], ['dumpling', {}], ['lens', {}]];
  const P5 = [['phone', {}], ['tongue', {}], ['tongue', { ang: 25 }, '舌頭 旋轉 25'], ['factory', { water: false }, '小工廠 無水']];
  const PAGE_LISTS = [P1, P2, P3, P4, P5];

  function gridPage(p, list, pal) {
    let s = '';
    const cw = 1920 / COLS, bw = cw - 100;
    list.forEach((it, i) => {
      const e = PP.LIST[it[0]], cx = (i % COLS) * cw + cw / 2, top = Math.floor(i / COLS) * CELL_H;
      const u = Math.min(bw / e.w, BOX_H / e.h, U_MAX);
      s += K.paper(e.fn(pal, it[1]), { x: cx, y: top + 220, scale: u, k: 'prop', id: `${it[0]}${p}${i}`, wide: e.wide }) +
        K.label(it[2] || e.zh, { x: cx, y: top + 470, fs: 36, u: 1, id: `${it[0]}${p}${i}` });
    });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue);
    const page = Math.max(0, Math.min(PAGES - 1, Math.floor(t + 1e-6)));
    return K.wrap(pal, gridPage(page, PAGE_LISTS[page], pal));
  }

  const Scene = { name: 'p_props_sheet', dur: PAGES, pages: PAGES, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
