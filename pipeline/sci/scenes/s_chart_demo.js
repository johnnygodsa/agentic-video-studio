/* charts.js 新元件示範(審圖用,不進正片):priceFlip、lineChart。render(t, params) 回傳完整 <svg> 內容;params: {hue}。
 * 0–2 秒:三張價牌(100→150 元;'80–90'→100 元;只有舊價的「? 元」),第 1 秒起翻牌;
 * 2–4 秒:折線圖「蛋類指數(2021=100)」五點,每 3 格出一點,第 3 點(索引 2)用黃牌。數字為示範。
 * 不遵守字幕帶與安全邊界(render_clip 的這兩項檢查可忽略)。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), Ch = W.Charts || require('../charts.js');
  const DUR = 4;

  function prices(pal, t) {
    const kf = K.frame(t - 1);                                   // 第 1 秒起翻牌(<0 = 尚未)
    return Ch.priceFlip({ x: 330, y: 540, from: 100, to: 150, unit: '元', pal, rot: -2, id: 'p1', kFlip: kf }) +
      Ch.priceFlip({ x: 960, y: 540, from: '80–90', to: 100, unit: '元', pal, rot: 1.5, id: 'p2', kFlip: kf }) +
      Ch.priceFlip({ x: 1580, y: 540, from: '?', unit: '元', pal, rot: -1, id: 'p3', kFlip: kf });
  }

  function chart(pal, t) {
    const kp = K.frame(t - 2), kOf = (i) => kp - 3 * i;           // 每 3 格出一點
    const D = [['2021', 100], ['2022', 126.4], ['2023', 139.9], ['2024', 120.9], ['2025', 114.9]];
    return Ch.lineChart({ x: 160, y: 200, w: 1600, h: 600, pal, id: 'lc', hi: 2, title: '蛋類指數(2021=100)',
      pts: D.map((d, i) => ({ label: d[0], value: d[1], k: kOf(i) })) });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue);
    return K.wrap(pal, t < 2 - 1e-6 ? prices(pal, t) : chart(pal, t));
  }

  const Scene = { name: 's_chart_demo', dur: DUR, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
