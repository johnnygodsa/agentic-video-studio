/* 固定結語(全片最大的一鏡)。render(t, params) 回傳完整 <svg> 內容;
 * params: {hue, dur(預設 8), tQuestion(旁白說「ChannelC?」的秒數,預設 5), lines([{idx,text,start,end}] 秒,相對場景起點)}。
 * 有 lines 且沒給 tQuestion 時,以最後一句的 start 當 tQuestion。
 * 0 寫字循環 → tQuestion-1.2 收板看鏡頭 → tQuestion 字牌逐張彈入、鴿子 shrug → speechless 待機到結束。
 * 右下 x 1000–1840、y 520–820 淨空給 YouTube 片尾推薦;字幕帶 y 850–1000 不放東西。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const U = 2.6;                                 // 鴿子倍率(高約 595px);全場紙片共用
  const WM = { cx: 1420, cy: 293, size: 186, gap: 6, u: U, rows: 2, soft: 0.2, q: 'pop' };   // 兩列(含彈入 1.15)落在 x 1000–1840、y 80–500
  const PIGEON = { x: 368, y: 800 };             // 腳底落點;鴿子朝右
  const CLEAR = [1000, 520, 1840, 820];
  const tQof = (p) => {
    p = p || {};
    if (p.tQuestion != null) return +p.tQuestion;
    if (Array.isArray(p.lines) && p.lines.length) return +p.lines[p.lines.length - 1].start;
    return 5;
  };
  const kQof = (params) => Math.round(tQof(params) * K.FPS);

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), kQ = kQof(params), kOut = kQ - 12;
    let pose;
    if (k < kOut) pose = K.clip('write', k);
    else if (k < kOut + 3) pose = K.clip('write_out', k - kOut);
    else if (k < kQ) pose = K.P.mk({ expr: 'look' });
    else if (k < kQ + 8) pose = K.clip('shrug', k - kQ);
    else pose = K.expr(K.clip('idle', k - kQ - 8), 'speechless');
    let s = K.ground({ x: 368, y: 806, w: 520, h: 40, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: PIGEON.x, y: PIGEON.y, scale: U });
    s += K.wordmark((k - kQ) / K.FPS, Object.assign({ pal }, WM));
    return K.wrap(pal, s);
  }

  const meta = (params) => ({ noOverlapFrom: kQof(params) / K.FPS, clear: [CLEAR] });
  const Scene = { name: 'outro', dur: 8, render, meta };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
