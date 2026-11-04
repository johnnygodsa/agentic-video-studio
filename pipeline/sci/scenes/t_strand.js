/* turtle 場景 §21 t_strand(句 77–79,17.9 秒)擱淺數字。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句77:大數字「325 隻 擱淺通報」加整條比例條(325)加小牌「2024 報導引用海洋保育署」;35% 處「237 隻 死亡」彈入,比例條切成 237/其餘。
 * 句78:死因欄:標題「237 隻死亡的死因」,一排五張「?」逐張彈入,下方牌「發現時已腐爛 無法解剖」(不畫腐爛)。
 * 句79:排行榜板子,三列名次全是「?」;鴿子左下彈入,約 55% 處聳肩。
 * 77–78 純圖表不放鴿子;句與句之間硬切。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 330, y: 800 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.09, end: 8.245 }, { start: 8.365, end: 13.205 }, { start: 13.325, end: 17.855 }];
  const RED = 'hsl(6 75% 55%)';

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));

  // ---------- 句77 ----------
  function s77(pal, L, k) {
    const grey = `hsl(${pal.h} 8% 72%)`, k2 = k - at(L[0], 0.35), split = k2 >= 0;
    let s = Ch.bigNum({ x: 520, y: 225, num: '325', unit: '隻', note: '擱淺通報', fs: 200, u: U, id: 'n325' });
    s += Ch.bigNum({ x: 1340, y: 225, num: '237', unit: '隻', note: '死亡', fs: 200, fill: RED, ink: K.PAPER, u: U, k: k2, kNote: k2 - 2, id: 'n237' });
    const bar = { pal, u: U, x: 960, y: 650, w: 1500, h: 100, fs: 56, id: 'rb' };
    s += Ch.ratioBar(Object.assign(bar, { segs: split
      ? [{ value: 237, label: '死亡', text: '237 隻', color: RED, side: 'up' }, { value: 88, label: '其餘', color: grey, side: 'down' }]
      : [{ value: 325, label: '擱淺通報', text: '325 隻', color: grey, side: 'down' }] }));
    return s + Ch.srcTag('2024 報導引用海洋保育署', { x: 100, y: 800, anchor: 'left', pal, u: U, id: 'src77' });
  }

  // ---------- 句78 ----------
  const TILE_X = [360, 660, 960, 1260, 1560];
  function s78(pal, L, k) {
    const hd = Ch.plate('237 隻死亡的死因', 120, { fill: K.PAPER });
    let s = Ch.sheet(hd.svg, { x: 960, y: 190, rot: -1, u: U, kind: 'note', id: 'h78', wide: true });
    TILE_X.forEach((x, i) => {
      s += K.tile('', { x, y: 470, size: 190, rot: (i % 2 ? 2 : -2), u: U, fill: pal.pad, id: 'slot' + i });
      const kq = k - at(L[1], 0.06 + 0.1 * i);
      if (kq >= 0) s += K.tile('?', { x, y: 470, size: 190, rot: (i % 2 ? 2 : -2), u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(kq), sy: K.pop(kq), id: 'q' + i, enter: kq < 2 });
    });
    const pl = Ch.plate('發現時已腐爛 無法解剖', 76, { fill: K.YELLOW });
    return s + Ch.sheet(pl.svg, { x: 960, y: 690, rot: 1, u: U, k: k - at(L[1], 0.62), kind: 'note', id: 'why', wide: true });
  }

  // ---------- 句79 ----------
  const BOARD = { x: 1205, y: 441, w: 1210, h: 698 }, ROW_Y = [340, 520, 700];
  function s79(pal, L, k) {
    let s = Ch.sheet(`<rect x="${-BOARD.w / 2}" y="${-BOARD.h / 2}" width="${BOARD.w}" height="${BOARD.h}" fill="${pal.pad}" stroke-linejoin="miter"/>`,
      { x: BOARD.x, y: BOARD.y, u: U, kind: 'prop', id: 'board' });
    const ti = Ch.plate('死因排行榜', 90, { fill: K.YELLOW });
    s += Ch.sheet(ti.svg, { x: BOARD.x, y: 185, rot: -1, u: U, kind: 'note', id: 'title', wide: true });
    ROW_Y.forEach((y, i) => {
      const kr = k - at(L[2], 0.08 + 0.12 * i);
      const bw = 780, bh = 130, bar = `<rect x="${-bw / 2}" y="${-bh / 2}" width="${bw}" height="${bh}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
        `<text x="0" y="0" font-family="GenSen" font-size="90" text-anchor="middle" dominant-baseline="central" fill="hsl(${pal.h} 8% 58%)" stroke="none">？？？</text>`;
      s += Ch.sheet(bar, { x: 1330, y, u: U, k: kr, kind: 'note', id: 'name' + i, wide: true });
      if (kr >= 0) s += K.tile('?', { x: 720, y, size: 150, rot: (i % 2 ? 3 : -3), u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(kr), sy: K.pop(kr), id: 'rank' + i, enter: kr < 2 });
    });
    return s;
  }

  function pigeonPose(k, kShrug) {
    const n = K.P.CLIPS.shrug.frames.length;
    const p = k >= kShrug && k < kShrug + n ? K.expr(K.clip('shrug', k - kShrug), 'doubt') : K.expr(K.clip('idle', k), k >= kShrug ? 'doubt' : 'look');
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    let s = '';
    if (k < F[1]) s = s77(pal, L, k);
    else if (k < F[2]) s = s78(pal, L, k);
    else {
      s = s79(pal, L, k);
      const kp = k - F[2], p = K.pop(kp);
      s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
      s += K.pigeon(pigeonPose(k, at(L[2], 0.55)), { x: FOOT.x, y: FOOT.y, scale: U * p, id: 'main', enter: kp < 3 });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_strand', dur: 17.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
