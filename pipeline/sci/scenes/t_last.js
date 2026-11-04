/* turtle 場景 §31 t_last(句 125–127,10.5 秒)最後一鏡,直接接 outro。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 鴿子位置、倍率與 outro.js 完全相同(腳底 x368 y800、U=2.6、朝右 flip:1,高約 595px,不受 300–345px 限制);最後 1.2 秒是 outro 的站姿 mk({expr:'look'})。
 * 右側焚化爐(高 ≥560px)句125 起固定在 (1620,480);句127 頂端出現旋轉餐廳並逐格旋轉。
 * 句125:右側一條路線(飯店 → 垃圾車 → 焚化爐)逐站出現;句126:路線退場,鴿子嘴邊出現牙刷,在嘴前 3 格循環左右移動(刷牙);
 * 句127:餐廳開始旋轉,小牌「旋轉餐廳」彈入;結束前 1.2 秒(含 2 格退場縮小)牙刷、焚化爐與小牌全部退場,右下 x1000–1840、y520–820 清空。
 * 大紙片(焚化爐、牙刷)以原尺寸直接出現,不過衝。同時在動的非文字元素 ≤ 2 組(鴿子、牙刷或餐廳)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 2.6;                                   // 鴿子倍率(與 outro 相同);全場紙片共用
  const PIGEON = { x: 368, y: 800 };               // 腳底落點(與 outro 相同);朝右
  const DUR = 10.5;
  const DEF = [{ start: 0.1, end: 2.85 }, { start: 2.96, end: 6.02 }, { start: 6.14, end: 10.44 }];
  const CLEAR = [1000, 520, 1840, 820];
  const INC = { x: 1620, y: 480, box: 590 };       // 焚化爐(全高約 567px)
  const BRUSH = { x: 1000, y: 360, box: 560 };     // 牙刷中心(長 560、粗約 130);頭朝左對著喙(喙尖約 x690、y353)
  const SWAY = [0, 70, 35];                        // 刷牙 3 格循環的水平位移
  const HEAD_DX = [0, 4, 2];                       // 鴿子頭部跟著(朝左 = 遠離牙刷)
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const TAG = { x: 1200, y: 190, fs: 72 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const now = (k) => (k < 0 ? -1 : 3);
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  // 退場:kOut 起縮小兩格,之後 null
  function shrink(k, kOut, cx, cy) {
    if (k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  const wrapOut = (k, kOut, cx, cy, s) => { const o = shrink(k, kOut, cx, cy); return o ? o(s) : ''; };

  function incinerator(pal, k, kk, rest, rot) {
    return Ch.sheet(Ch.icon(ic(pal, 'incinerator', { tall: 1, restaurant: rest, rot }), 0, 0, INC.box), { x: INC.x, y: INC.y, u: U, k: now(kk), kind: 'prop', id: 'burner' });
  }
  function brush(pal, dx, kk) {
    const g = Ch.icon(ic(pal, 'toothbrush', {}), 0, 0, BRUSH.box);
    return Ch.sheet(`<g transform="scale(-1 1)">${g}</g>`, { x: BRUSH.x + dx, y: BRUSH.y, u: U, k: now(kk), kind: 'prop', id: 'brush', wide: true });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), P = params || {};
    const F = L.map((l) => K.frame(l.start));
    const kEnd = Math.round((P.dur != null && isFinite(P.dur) ? +P.dur : DUR) * K.FPS);
    const kOut = kEnd - 14;                        // 退場縮小 2 格,kEnd-12 起右側全空
    const still = K.P.mk({ expr: 'look' });

    // 鴿子:句125 站著看;句126–127 刷牙(頭部 3 格循環);最後與 outro 相同的站姿
    let pose;
    if (k >= kOut) pose = still;
    else if (k >= F[1]) { const i = (k - F[1]) % 3; pose = Object.assign(K.expr(K.clip('idle', 0), 'look'), { headDx: HEAD_DX[i], beak: i === 1 ? 0.3 : 0 }); }
    else pose = K.expr(K.clip('idle', k), 'look');
    let s = K.ground({ x: PIGEON.x, y: PIGEON.y + 6, w: 520, h: 40, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: PIGEON.x, y: PIGEON.y, scale: U });

    // 焚化爐(句125 起;句127 起有旋轉餐廳)
    const rest = k >= F[2], rot = rest ? (k - F[2]) % 6 : 0;
    s += wrapOut(k, kOut, INC.x, INC.y, incinerator(pal, k, k - F[0], rest, rot));

    // 句125:路線(飯店 → 垃圾車 → 焚化爐),句126 開頭退場
    if (k < F[1] + OUT.length) {
      const kr = [F[0], at(L[0], 0.15), at(L[0], 0.35), at(L[0], 0.55)].map((x) => k - x);
      const route = Ch.route({ pal, u: U, fs: 56, r: 28, th: 18, id: 'rt', stops: [
        { x: 800, y: 650, label: '飯店', labelSide: 'down', k: kr[0] }, { x: 1000, y: 430, k: kr[1] },
        { x: 1190, y: 620, label: '垃圾車', labelSide: 'down', k: kr[2] }, { x: 1395, y: 650, k: kr[3] }] });
      const o = shrink(k, F[1], 1100, 540);
      if (o) s += o(route);
    }

    // 句126–127:牙刷在嘴前左右移動(3 格循環)
    if (k >= F[1]) s += wrapOut(k, kOut, BRUSH.x + 35, BRUSH.y, brush(pal, SWAY[(k - F[1]) % 3], k - F[1]));

    // 句127:小牌「旋轉餐廳」
    const kT = k - at(L[2], 0.25);
    if (kT >= 0) {
      const tag = Ch.sheet(Ch.plate('旋轉餐廳', TAG.fs, { fill: K.YELLOW }).svg, { x: TAG.x, y: TAG.y, rot: -2, u: U, k: kT, kind: 'tag', id: 'rest', wide: true });
      s += wrapOut(k, kOut, TAG.x, TAG.y, tag);
    }
    return K.wrap(pal, s);
  }

  // checkClear:驗證用,檢查最後 1.2 秒右下淨空區(平常不開,因為前面右側本來就有物件)
  const meta = (p) => ({ clear: p && p.checkClear ? [CLEAR] : [] });
  const Scene = { name: 't_last', dur: DUR, render, meta };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
