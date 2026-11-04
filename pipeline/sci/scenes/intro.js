/* 片頭 3.0 秒(固定鏡頭)。render(t, params) 回傳完整 <svg> 內容;params: {hue}。
 * 0.0–0.5 五張字牌逐張彈入(兩列放左側)→ 0.6「?」牌掉下(0.9 落定)→ 0.8–1.4 鴿子從右走進站定
 * → 1.4 歪頭加 doubt → 1.8 副標(字牌下方)→ 2.1–2.7 shrug → 2.7 回基準站姿靜止。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const U = 2;                                   // 鴿子倍率(高約 458px);全場紙片共用
  const WM = { cx: 690, cy: 410, size: 280, gap: 6, u: U, rows: 2, q: 'drop', qAt: 0.6, dropSeq: [0, 2, 3, 5] };
  const PIGEON = { x: 1621, y: 800 };            // 腳底落點
  const STEP_PX = 80;                            // 走路每格位移
  const K_WALK = 8, K_TILT = 14, K_SUB = 18, K_SHRUG = 21, K_HOLD = 27;

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t);
    let s = k >= K_TILT ? K.ground({ x: 1603, y: 806, w: 440, h: 40, u: U, pal }) : '';   // 鴿子站定後才出現
    s += K.wordmark(t, Object.assign({ pal }, WM));
    if (k >= K_SUB) s += K.label('沒用的知識,快樂就好。', { x: WM.cx, y: 768, fs: 60, u: U, rot: -1.5, id: 'sub' });
    if (k >= K_WALK) {
      let pose, dx = 0;
      if (k < K_TILT) { pose = K.clip('walk', k - K_WALK); dx = (K_TILT - k) * STEP_PX; }
      else if (k < K_SHRUG) pose = K.expr(K.clip('tilt', k - K_TILT), 'doubt');   // 歪頭 6 格後留在 doubt 站姿
      else if (k < K_HOLD) pose = K.clip('shrug', k - K_SHRUG + 1);
      else pose = K.clip('shrug', 7);            // 回基準站姿,靜止
      s += K.pigeon(pose, { x: PIGEON.x + dx, y: PIGEON.y, scale: U, enter: dx > 0 });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 'intro', dur: 3, render, meta: () => ({ noOverlapFrom: 0.8, clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
