/* salary 圖解總表(審圖用,不進正片)。render(t, params) 回傳完整 <svg> 內容;params: {hue}。
 * 第 n 頁在 t∈[n, n+1) 顯示,共 5 頁:前三頁是 props_salary.js 的圖解(每頁 ≤8 個,4 欄 × 2 列,下方標名稱,含各參數變化),
 * 第 4 頁 decileRow 示範(主計總處 113 年十分位數 D1–D9,marker 標 100 萬、D8 D9 黃柱),
 * 第 5 頁千元鈔排在足球場上的比例驗證(160mm vs 105m:一排 656 張,1000 張 = 160 m,約 1.5 個球場長)。
 * 每頁前 5 格靜止(看圖用),後 5 格讓圖表元件重新逐一彈入(只為跑過進場路徑);圖解頁全部靜止。
 * 總表不遵守字幕帶(render_clip 的字幕帶檢查可忽略);邊距 ≥80 的檢查仍適用於圖表頁。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), Ch = W.Charts || require('../charts.js'), PS = W.PropsSalary || require('../props_salary.js');
  const COLS = 4, CELL_H = 540, BOX_H = 340, U_MAX = 1.9, PAGES = 5;
  // [圖解名, 參數, 標名]
  const P1 = [['bill', {}, '千元鈔 160:70'], ['payslip', {}], ['gradcap', {}], ['gate', {}, '校門(無校名)'], ['briefcase', {}], ['bank', {}], ['survey', {}], ['stele', {}, '石碑 5 行']];
  const P2 = [['scale', { tilt: -1 }, '天秤 左沉'], ['scale', {}, '天秤 平衡'], ['scale', { tilt: 1 }, '天秤 右沉'], ['globe', {}, '地球 無牌'],
    ['globe', { sign: '世界一' }, '地球 世界一'], ['globe', { sign: '世界二', v: 2 }, '地球 世界二'], ['meter', { v: 0 }, '計量表 0'], ['meter', { v: 0.5 }, '計量表 0.5']];
  const P3 = [['meter', { v: 1 }, '計量表 1'], ['helmet', {}], ['saltbag', {}], ['shaker', {}], ['dict', {}, '厚辭典 辭典'], ['dict', { text: '韋氏字典' }, '厚辭典 韋氏字典'],
    ['tape', {}, '捲尺 拉出'], ['tape', { out: 0.4 }, '捲尺 拉出 0.4']];
  const PAGE_LISTS = [P1, P2, P3];

  function gridPage(p, list, pal) {
    let s = '';
    const cw = 1920 / COLS, bw = cw - 100;
    list.forEach((it, i) => {
      const e = PS.LIST[it[0]], cx = (i % COLS) * cw + cw / 2, top = Math.floor(i / COLS) * CELL_H;
      const u = Math.min(bw / e.w, BOX_H / e.h, U_MAX);
      s += K.paper(e.fn(pal, Object.assign({ u }, it[1])), { x: cx, y: top + 220, scale: u, k: 'prop', id: `${it[0]}${p}${i}`, wide: e.wide }) +
        K.label(it[2] || e.zh, { x: cx, y: top + 470, fs: 36, u: 1, id: `${it[0]}${p}${i}` });
    });
    return s;
  }

  // 第 4 頁:十分位數階梯(D1–D9,單位萬元;100 萬在 D8 與 D9 之間)
  const DECILE = [33.0, 38.1, 43.2, 48.7, 54.6, 62.8, 75.3, 95.9, 133.6];
  function decilePage(pal, kOf) {
    return Ch.decileRow({ x: 120, y: 220, w: 1680, h: 560, pal, id: 'dr', vals: DECILE, hiIdx: [7, 8], title: '年薪 十分位數 單位 萬元', k: kOf(0), kStep: 0,
      marker: { value: 100, label: '100 萬', k: kOf(1) } }) +
      Ch.srcTag('主計總處 113 年 全年總薪資(含獎金 稅前) 附表 2', { x: 120, y: 960, anchor: 'left', pal, k: kOf(2) });
  }

  // 第 5 頁:千元鈔排足球場(比例照真實:u px = 1 公尺;鈔票長 0.16 m)
  function fieldPage(pal, kOf) {
    const U = 10.5, PSC = 1.8, fx = 680, fy = 480, F = PS.FIELD;     // PSC:paper 的 scale(陰影偏移 = 5·PSC、6·PSC px)
    let s = K.paper(PS.field(pal, { u: U, ps: PSC, bills: 1000 }), { x: fx, y: fy, scale: PSC, k: 'prop', id: 'field', wide: true });
    const row1Y = fy - 10 * U, row2Y = fy + 10 * U, x0 = fx - F.len / 2 * U;
    // 場上標示(第一排、第二排張數)
    const tag = (t, x, y, id, k) => Ch.sheet(Ch.plate(t, 56).svg, { x, y, u: 1.4, k, kind: 'tag', id, wide: true });
    s += tag('第一排 656 張', fx, row1Y - 70, 'r1', kOf(0)) + tag('第二排 344 張', x0 + (55 + 26) * U, row2Y + 8, 'r2', kOf(0));
    // 右欄換算
    [['千元鈔 長160mm', 1], ['球場 長105m', 2], ['一排 656 張', 3], ['1000 張=160m', 4], ['約 1.5 個球場', 5]].forEach((r, i) => {
      s += tag(r[0], 1580, 190 + i * 140, 'c' + i, kOf(i + 1));
    });
    // 放大示意:8 張千元鈔(160:70)
    let z = '';
    for (let i = 0; i < 8; i++) z += K.paper(PS.bill(pal, {}), { x: 110 + 62 + i * 124, y: 905, scale: 120 / 320, k: 'prop', id: 'zb' + i, wide: true });
    s += z + tag('放大示意', 1300, 905, 'zl', kOf(0));
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue);
    const page = Math.max(0, Math.min(PAGES - 1, Math.floor(t + 1e-6))), kp = K.frame(t - page);
    const kOf = (i) => (kp < 5 ? 99 : kp - 5 - i);
    if (page < 3) return K.wrap(pal, gridPage(page, PAGE_LISTS[page], pal));
    return K.wrap(pal, page === 3 ? decilePage(pal, kOf) : fieldPage(pal, kOf));
  }

  const Scene = { name: 'salary_props_sheet', dur: PAGES, pages: PAGES, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
