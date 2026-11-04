/* 版面常數示範(F2-4):依 Kit.L(橫/直式 LAYOUT)擺字標、副標、鴿子,用來驗直式安全邊界;不屬於任何影片。
 * render(t, params);params: {hue, portrait}。全部由 Kit.L 取值,橫式與直式共用同一份程式。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const L = K.L, M = L.margin, T = L.title, PG = L.pigeon;
  const CX = K.portrait ? (M[0] + L.W - M[2]) / 2 : 690, CY = K.portrait ? 360 : 410;   // 字標第二列的水平中心、兩列合計的垂直中心
  const U = PG.u;

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t);
    let s = K.ground({ x: PG.x - 18, y: PG.y + 6, w: 440, h: 40, u: U, pal });
    s += K.wordmark(t, { pal, cx: CX, cy: CY, size: T.tile, gap: 6, u: U, rows: 2, q: 'drop', qAt: 0.6, dropSeq: [0, 2, 3, 5] });
    if (k >= 18) s += K.label('快樂就好', { x: CX, y: K.portrait ? 620 : 768, fs: T.labelFs, u: U, rot: -1.5, id: 'sub' });
    s += K.pigeon(K.expr(K.clip('idle', k), 'normal'), { x: PG.x, y: PG.y, scale: U });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'layout_demo', dur: 3, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
