/* turtle 場景 §4 t_rule_a(句 11–13)規定內容,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句11:日曆牌「2025 年 1 月」加台灣輪廓彈入;15–55% 全島 8 間小房子逐一彈入、3 格後窗亮起;62% 墾丁紅點、68% 字牌。
 * 句12:公告紙「第一條」彈入;10% 小瓶、25% 「180 毫升以下」字牌、40% 紅叉(鴿子點頭)、60% 大瓶、68% 打勾。
 * 句13:公告紙換「第二條」,「房間」托盤彈入;六樣備品在 6%–48.5% 之間等間隔逐一彈入(各帶名稱牌);58% 名稱牌收掉、整排連托盤分 3 格下移,
 *      櫃檯同格彈入蓋在前面(東西在櫃檯後面),3 格後「櫃檯」字牌彈入。
 * 同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PT = (typeof window !== 'undefined' && window.PropsTurtle) || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 800 };                  // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0.06, end: 6.14 }, { start: 6.26, end: 11.425 }, { start: 11.545, end: 17.145 }];
  const TW = { x: 1480, y: 440, box: 700 };         // 台灣輪廓(中心與見方框)
  const TAG = { x: 700, y: 290, size: 340 };        // 日曆牌
  const HOUSES = [[121.5, 25.1], [121.82, 24.62], [120.97, 24.8], [120.7, 24.15], [121.55, 23.98], [120.5, 23.2], [120.4, 22.65], [121.1, 22.8]];
  const KENTING = [120.8, 21.95];
  const PANEL = { x: 1160, y: 440, w: 1340, h: 680 };   // 左緣 490,鴿子右緣約 470
  // 六樣備品:細長的轉直立(rot -90)、box = 長邊;vh = 實際視覺高(px)
  const ITEMS = [['牙刷', 'toothbrush', -90, 340, 340], ['牙膏', 'toothpaste', -90, 340, 340], ['梳子', 'comb', -90, 340, 340],
    ['刮鬍刀', 'razor', 0, 320, 320], ['刮鬍泡', 'foam', 0, 320, 320], ["浴帽", "showerCap", 0, 316, 152]];
  const YB = 560, TRAY_H = 90, TRAY_W = 1280, PITCH = 205, PLATE_Y = 700, DY = [15, 35, 50];   // YB:備品腳底線;移到櫃檯後下移 50
  const COUNTER = { x: 1160, w: 1280, topH: 40, frontH: 150 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (L, i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const txt = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="${anchor || 'middle'}"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const sheet = (c, o, k) => Ch.sheet(c, Object.assign({ u: U, k }, o));

  // 台灣上的座標(px):twXY 單位 × 倍率
  const twScale = TW.box / PT.LIST.taiwan.h;
  const twPos = (ll) => { const p = PT.twXY(ll[0], ll[1]); return [TW.x + p[0] * twScale, TW.y + p[1] * twScale]; };

  function panel(pal, title, k) {
    const w = PANEL.w, h = PANEL.h;
    const c = `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="110" fill="${pal.main}" stroke="none"/>` + txt(title, 0, -h / 2 + 55, 84, pal.onMain);
    return sheet(c, { x: PANEL.x, y: PANEL.y, kind: 'panel', id: 'panel' }, k);
  }
  const redX = (size) => [45, -45].map((a) => `<rect x="${-size / 2}" y="-13" width="${size}" height="26" fill="${PT.C.red}" transform="rotate(${a})"/>`).join('');
  const CHECK = [[-55, 5], [-35, -15], [-15, 10], [45, -50], [65, -30], [-15, 50]];

  function scene11(pal, k, L, F) {
    let s = '';
    s += sheet(Ch.icon(ic(pal, 'taiwan', {}), 0, 0, TW.box), { x: TW.x, y: TW.y, kind: 'map', id: 'taiwan' }, k - F[0]);
    s += Ch.dateTag({ x: TAG.x, y: TAG.y, top: '2025 年', main: '1 月', size: TAG.size, u: U, k: k - F[0] });
    HOUSES.forEach((ll, i) => {
      const kh = k - at(L, 0, 0.15 + 0.4 * i / (HOUSES.length - 1));
      if (kh < 0) return;
      const p = twPos(ll);
      s += sheet(Ch.icon(ic(pal, 'house', { lit: kh >= 3 }), 0, 0, 84), { x: p[0], y: p[1], kind: 'house', id: 'house' + i }, kh);
    });
    const kd = k - at(L, 0, 0.62), kl = k - at(L, 0, 0.68);
    if (kd >= 0) { const p = twPos(KENTING); s += sheet(`<circle r="22" fill="${PT.C.red}"/>`, { x: p[0], y: p[1], kind: 'dot', id: 'kenting' }, kd); }
    if (kl >= 0) { const p = twPos(KENTING); s += sheet(Ch.plate('墾丁', 64, {}).svg, { x: p[0] - 190, y: p[1] - 4, kind: 'label', id: 'kentingL', wide: true }, kl); }
    return s;
  }

  function scene12(pal, k, L, F) {
    let s = panel(pal, '第一條', k - F[1]);
    const kb = k - at(L, 1, 0.1), kl = k - at(L, 1, 0.25), kx = k - at(L, 1, 0.4), kB = k - at(L, 1, 0.6), kc = k - at(L, 1, 0.68);
    if (kb >= 0) s += sheet(Ch.icon(ic(pal, 'miniBottle', {}), 0, 0, 300), { x: 830, y: 420, kind: 'prop', id: 'mini' }, kb);
    if (kl >= 0) {
      const p = Ch.plate('180 毫升以下', 60, {});
      s += sheet(p.svg, { x: 830, y: 665, kind: 'label', id: 'miniL', wide: true }, kl);
    }
    if (kx >= 0) s += sheet(redX(240), { x: 830, y: 420, kind: 'cross', id: 'cross', wide: true }, kx);
    if (kB >= 0) s += sheet(Ch.icon(ic(pal, 'pumpBottle', {}), 0, 0, 320), { x: 1400, y: 420, kind: 'prop', id: 'pump' }, kB);
    if (kc >= 0) s += sheet(`<polygon points="${CHECK.map((p) => p.join(',')).join(' ')}" fill="${pal.text}"/>`, { x: 1610, y: 380, kind: 'check', id: 'check' }, kc);
    return s;
  }

  // 櫃檯(自畫):台面加正面,字牌放在正面;備品站在台面上,不被遮
  function counterSvg(w, topH, frontH) {
    return `<rect x="${-w / 2}" y="0" width="${w}" height="${topH}" fill="hsl(30 45% 40%)" stroke-linejoin="miter"/>` +
      `<rect x="${-w / 2 + 20}" y="${topH}" width="${w - 40}" height="${frontH}" fill="hsl(36 55% 62%)" stroke-linejoin="miter"/>`;
  }

  function scene13(pal, k, L, F) {
    let s = panel(pal, '第二條', k - F[2]);
    const kMove = at(L, 2, 0.58), moved = k >= kMove, dy = moved ? DY[Math.min(k - kMove, DY.length - 1)] : 0;
    // 托盤(移到櫃檯後換成櫃檯)
    if (!moved) {
      const tray = `<rect x="${-TRAY_W / 2}" y="-${TRAY_H / 2}" width="${TRAY_W}" height="${TRAY_H}" fill="hsl(36 55% 62%)" stroke-linejoin="miter"/>` +
        `<rect x="${-TRAY_W / 2}" y="-${TRAY_H / 2}" width="${TRAY_W}" height="14" fill="hsl(30 45% 48%)" stroke="none"/>` + txt('房間', TRAY_W / 2 - 100, 8, 64, K.INK);
      s += sheet(tray, { x: PANEL.x, y: YB + TRAY_H / 2, kind: 'tray', id: 'tray', wide: true }, k - F[2]);
    }
    ITEMS.forEach(([zh, name, rot, box, vh], i) => {
      const ki = k - at(L, 2, 0.06 + 0.085 * i);
      if (ki < 0) return;
      const cy = YB + dy - vh / 2;
      let c = `<g transform="rotate(${rot})">${Ch.icon(ic(pal, name, {}), 0, 0, box)}</g>`;
      if (!moved) c += `<g transform="translate(0 ${PLATE_Y - cy})">${Ch.plate(zh, 56, { padX: 0.4 }).svg}</g>`;
      s += sheet(c, { x: PANEL.x - 12 + (i - 2.5) * PITCH, y: cy, kind: 'item', id: 'item' + i, wide: !moved }, ki);
    });
    if (moved) {
      const top = YB + DY[DY.length - 1], ch = COUNTER.topH + COUNTER.frontH;
      s += sheet(counterSvg(COUNTER.w, COUNTER.topH, COUNTER.frontH), { x: COUNTER.x, y: top, kind: 'counter', id: 'counter', wide: true }, k - kMove);
      const kl = k - (kMove + 3);
      if (kl >= 0) s += sheet(Ch.plate('櫃檯', 64, {}).svg, { x: COUNTER.x, y: top + COUNTER.topH + COUNTER.frontH / 2, kind: 'label', id: 'counterL', wide: true }, kl);
    }
    return s;
  }

  function pigeonPose(k, kNod) {
    const p = k >= kNod && k < kNod + 6 ? K.expr(K.clip('nod', k - kNod), 'look') : K.expr(K.clip('idle', k), 'look');
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = k < F[1] ? scene11(pal, k, L, F) : k < F[2] ? scene12(pal, k, L, F) : scene13(pal, k, L, F);
    s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 380, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, at(L, 1, 0.4)), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_rule_a', dur: 17.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
