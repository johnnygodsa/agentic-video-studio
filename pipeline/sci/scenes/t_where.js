/* turtle 場景 §13 t_where(句 45–49,22.7 秒)差在哪裡被用掉。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 鴿子在左下(高約 305px,x 100–410),內容在 x 440–1840。
 * 句45:牙刷(直放,長 650)與吸管(直放,長 650)往中間靠並排,中間「?」,外側下方各一張名牌。
 * 句46:「?」換成黃色小牌「我的理解」,地點圖釘彈入。
 * 句47:兩欄板「浴室」「戶外」;浴室:垃圾桶,牙刷平放在旁,過一會兒一格跳進桶(桶在前)。
 * 句48:浴室欄收掉,「戶外」佔 x 445–1835:三張小景橫向並排(馬路、機車、海邊,各 436×560),各有一根粗吸管:
 *       前兩根逐格進桶,海邊那根逐格被吹到沙灘上躺平。
 * 句49:牙刷與吸管加「材質」縮小退到左側變淡(仍高 320),圖釘放大到中間(高 520),加「在哪裡被丟掉」;鴿子點頭。
 * 同時在動的非文字元素 ≤ 2 組(鴿子 + 一組)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.33;                                  // 鴿子倍率(高約 305px:戶外三景要佔到 x 445,鴿子縮到規定下限);全場紙片共用
  const FOOT = { x: 240, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.08, end: 3.22 }, { start: 3.34, end: 6.71 }, { start: 6.83, end: 11.33 }, { start: 11.45, end: 17.82 }, { start: 17.93, end: 22.65 }];
  const RED = 'hsl(6 75% 55%)';
  const BRUSH = { x: 820, y: 420, box: 650 }, STRAW = { x: 1540, y: 420, box: 650 }, MID = { x: 1180, y: 400 };   // 句45–46 的並排
  const TC = { x: 1137.5, y: 460, w: 1395, h: 740, gap: 24, fs: 72 };    // 兩欄板(x 440–1835)
  const LX = Ch.twoColPos(TC)[0].x;                                        // 左欄中心 x
  const PANEL = { w: 436, h: 560, y: 546, xs: [663, 1139, 1615] };        // 句48 三張小景(x 445–1833、y 266–826)
  const SCENES = ['馬路', '機車', '海邊'];
  const f = (x) => +(+x).toFixed(2);
  const lerp = (a, b, p) => a + (b - a) * p;
  const np = (k) => (k < 0 ? -1 : k === 0 ? 2 : 3);   // 大塊紙片不過衝(過衝會壓到字幕帶):第 0 格 0.95 倍,之後原大

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (L, i, frac) => K.frame(L[i].start + frac * (L[i].end - L[i].start));

  function pigeonPose(k, reacts, expr) {
    for (const r of reacts) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (k >= r.k0 && k < r.k0 + n) return K.expr(K.clip(r.clip, k - r.k0), r.expr || expr);
    }
    return K.expr(K.clip('idle', k), expr);
  }

  // 地點圖釘(px 繪製,中心在原點,約 160×210)
  const PIN = { w: 160, h: 210, svg: `<g transform="translate(0 -5)"><path d="M 0 110 C -30 60 -80 30 -80 -20 A 80 80 0 1 1 80 -20 C 80 30 30 60 0 110 Z" fill="${RED}"/>` +
    `<circle cx="0" cy="-20" r="30" fill="${K.PAPER}" stroke="none"/></g>` };

  // 粗吸管(px,中心在原點,直立,長 318、管粗 46):PT.straw 的管粗只有長度的 7%,縮到小景裡看不清,這裡照同樣造型自己畫
  const FAT = `<g transform="translate(-20 9)"><rect x="-23" y="-70" width="46" height="90" rx="8" fill="${RED}" transform="translate(0 -100) rotate(40)"/>` +
    `<rect x="-23" y="-104" width="46" height="254" rx="10" fill="${RED}"/>` +
    [0, 1, 2].map((i) => `<rect x="-23" y="${-66 + i * 24}" width="46" height="11" fill="${K.PAPER}" stroke="none"/>`).join('') + '</g>';

  // 句48 小景(px,中心在原點,436×560):紙白底板加場景圖;wind = 風的短線位置(海邊那張吹走時)
  function panelSvg(kind, pal, wind) {
    const R = (x, y, w, h, fill, rx) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"${rx ? ` rx="${rx}"` : ''} fill="${fill}"/>`;
    const N = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${w}" height="${h}" fill="${fill}" stroke="none"/>`;
    const C = (x, y, r, fill, ns) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"${ns ? ' stroke="none"' : ''}/>`;
    const road = 'hsl(215 8% 52%)';
    let s = `<rect x="${-PANEL.w / 2}" y="${-PANEL.h / 2}" width="${PANEL.w}" height="${PANEL.h}" fill="${K.PAPER}" stroke-linejoin="miter"/>`;
    if (kind === '馬路') {
      s += R(-202, 150, 404, 114, road) + [-180, -78, 24, 126].map((x) => N(x, 200, 58, 14, K.PAPER)).join('');
    } else if (kind === '機車') {
      s += R(-202, 238, 404, 26, road) + '<g transform="translate(-85 150) scale(1.8)" stroke-width="3">' +
        R(-58, -14, 74, 34, pal.main, 12) + R(-52, -28, 52, 14, K.INK, 5) + R(16, -52, 9, 66, K.INK, 3) + R(8, -58, 34, 9, K.INK, 3) +
        C(-38, 32, 20, K.INK) + C(40, 32, 20, K.INK) + C(-38, 32, 7, K.PAPER, 1) + C(40, 32, 7, K.PAPER, 1) + '</g>';
    } else {
      s += R(-202, -200, 404, 270, 'hsl(200 65% 62%)') + R(-202, 70, 404, 194, 'hsl(42 60% 78%)') +
        N(-160, -120, 84, 12, K.PAPER) + N(40, -70, 110, 12, K.PAPER) + N(-90, 10, 96, 12, K.PAPER);
      if (wind) s += [0, 1, 2].map((i) => N(Math.max(-200, wind[0] - 168 + i * 14), wind[1] - 40 + i * 38, 76, 11, K.INK)).join('');
    }
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : 4;
    const q = k - F[ph];
    const icn = (name, opts, x, y, box, o) => Ch.sheet(Ch.icon({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h }, 0, 0, box, o && o.dim),
      Object.assign({ x, y, u: U, kind: 'prop', id: name, wide: PT.LIST[name].wide }, o));
    const pin = (x, y, box, o) => Ch.sheet(Ch.icon(PIN, 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: 'pin' }, o));

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 300, h: 36, u: U, pal });
    const reacts = [{ k0: F[0] + 3, clip: 'tilt', expr: 'doubt' }, { k0: at(L, 4, 0.62) + 2, clip: 'nod', expr: 'look' }];
    s += K.pigeon(Object.assign({}, pigeonPose(k, reacts, 'look'), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (ph <= 1) {                                 // 句45–46:牙刷 ? 吸管;46 換成「我的理解」加圖釘
      const kb = ph === 0 ? q : 99, ks = ph === 0 ? q - (at(L, 0, 0.3) - F[0]) : 99;
      s += icn('toothbrush', {}, BRUSH.x, BRUSH.y, BRUSH.box, { rot: 90, k: kb, id: 'brush' });
      s += icn('straw', {}, STRAW.x, STRAW.y, STRAW.box, { k: ks, id: 'straw' });
      const pb = Ch.plate('牙刷', 64), ps = Ch.plate('吸管', 64);       // 名牌放外側下方(直放的圖已佔滿 y 95–745)
      s += Ch.sheet(pb.svg, { x: BRUSH.x - 205, y: 775, rot: -1.5, u: U, k: kb, kind: 'note', id: 'lb', wide: true });
      s += Ch.sheet(ps.svg, { x: STRAW.x + 190, y: 775, rot: 1.5, u: U, k: ks, kind: 'note', id: 'ls', wide: true });
      if (ph === 0) {
        const kq = k - at(L, 0, 0.55);
        s += K.tile('?', { x: MID.x, y: MID.y, size: 260, rot: 6, u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(kq), sy: K.pop(kq), id: 'q', enter: kq < 2 });
      } else {
        const pl = Ch.plate('我的理解', 84, { fill: K.YELLOW });
        s += Ch.sheet(pl.svg, { x: MID.x, y: 700, rot: -2, u: U, k: q, kind: 'note', id: 'mine', wide: true });
        s += pin(MID.x, 380, 440, { k: q - 10 });
      }
    } else if (ph === 2) {                         // 句47:兩欄板;浴室:牙刷平放,一格跳進桶
      s += Ch.twoCol({ pal, u: U, x: TC.x, y: TC.y, w: TC.w, h: TC.h, gap: TC.gap, fs: TC.fs, id: 'tc',
        left: { title: '浴室', k: np(q) }, right: { title: '戶外', k: np(q) } });
      const kj = at(L, 2, 0.42) - F[2], j = q - kj;
      const J = [[LX - 10, 380, 0], [LX + 10, 340, -15], [LX + 60, 420, -45], [LX + 100, 520, -60]];
      const p = j < 0 ? J[0] : J[Math.min(j, 3)];
      s += icn('toothbrush', {}, p[0], p[1], 600, { rot: p[2], k: q - 3, id: 'brush' });
      s += icn('bin', {}, LX + 40, 660, 320, { k: np(q) });
    } else if (ph === 3) {                         // 句48:浴室欄收掉,「戶外」三張小景橫向並排
      const ph48 = Ch.plate('戶外', 64, { fill: K.INK, ink: K.PAPER });
      s += Ch.sheet(ph48.svg, { x: 1140, y: 142, rot: 1.5, u: U, k: q, kind: 'colT', id: 'out', wide: true });
      const st = [0, at(L, 3, 0.08) - F[3], at(L, 3, 0.16) - F[3]];
      const mv = [at(L, 3, 0.27) - F[3], at(L, 3, 0.40) - F[3], at(L, 3, 0.53) - F[3]];
      // 位置為小景中心起算的 [x, y, 轉角]。前兩根進桶(每 2 格一步,4 步)、第三根被吹到沙灘上躺平(每 3 格一步,5 步)
      const IN = [[-110, -30, -8], [-40, -50, 5], [60, -50, 12], [115, -40, 14], [115, 5, 14]];
      const OUT = [[-110, -40, -8], [-80, -30, -25], [-40, 10, -45], [0, 70, -62], [30, 130, -78], [40, 170, -90]];
      for (let i = 0; i < 3; i++) {
        const kp = q - st[i], cx = PANEL.xs[i], cy = PANEL.y;
        if (kp < 0) continue;
        const seq = i < 2 ? IN : OUT, m = q - mv[i], n = m < 0 ? 0 : Math.min(Math.floor(m / (i < 2 ? 2 : 3)), seq.length - 1), pos = seq[n];
        s += Ch.sheet(panelSvg(SCENES[i], pal, i === 2 && n > 0 && n < seq.length - 1 ? pos : null), { x: cx, y: cy, u: U, k: np(kp), kind: 'panel', id: 'p' + i });
        s += Ch.sheet(FAT, { x: cx + pos[0], y: cy + pos[1], rot: pos[2], u: U, k: kp - 1, kind: 'prop', id: 'straw' + i });
        if (i < 2) s += icn('bin', {}, cx + 115, cy + 130, 230, { k: kp, id: 'bin' + i });
        const pl = Ch.plate(SCENES[i], 60, { fill: K.YELLOW });
        s += Ch.sheet(pl.svg, { x: cx, y: cy - PANEL.h / 2 + 6, rot: -1.5, u: U, k: kp, kind: 'note', id: 'pl' + i, wide: true });
      }
    } else {                                       // 句49:材質退到左側、圖釘放大到中間
      const ks = at(L, 4, 0.38) - F[4], kt = q - ks;
      const P = [0, 0.3, 0.6, 0.85, 1], p = kt < 0 ? 0 : P[Math.min(kt, 4)];
      const PIN_P = [0, 0.5, 0.8, 0.95, 1], kp = kt - 3, pp = kp < 0 ? 0 : PIN_P[Math.min(kp, 4)];   // 吸管退到左側後圖釘才出來(不交錯)
      const dim = p > 0.5;
      const bx = lerp(BRUSH.x, 580, p), sx = lerp(STRAW.x, 720, p), gy = lerp(BRUSH.y, 300, p), box = lerp(BRUSH.box, 320, p);
      s += icn('toothbrush', {}, bx, gy, box, { rot: 90, id: 'brush', dim });
      s += icn('straw', {}, sx, gy, box, { id: 'straw', dim });
      if (kt < 0) {                                // 退後前沿用句45 的名牌(畫面不留空)
        const pb = Ch.plate('牙刷', 64), ps = Ch.plate('吸管', 64);
        s += Ch.sheet(pb.svg, { x: BRUSH.x - 205, y: 775, rot: -1.5, u: U, k: 99, kind: 'note', id: 'lb', wide: true });
        s += Ch.sheet(ps.svg, { x: STRAW.x + 190, y: 775, rot: 1.5, u: U, k: 99, kind: 'note', id: 'ls', wide: true });
      }
      const pm = Ch.plate('材質', lerp(100, 72, p), { fill: K.YELLOW });
      s += Ch.sheet(pm.svg, { x: lerp(MID.x, 650, p), y: lerp(MID.y, 545, p), rot: -2, u: U, k: 99, kind: 'note', id: 'mat', wide: true });
      if (kp >= 0) s += pin(1240, 355, lerp(190, 520, pp), { id: 'pin' });
      const pw = Ch.plate('在哪裡被丟掉', 110, { fill: K.YELLOW });
      s += Ch.sheet(pw.svg, { x: 1240, y: 728, rot: -1.5, u: U, k: np(q - (at(L, 4, 0.62) - F[4])), kind: 'note', id: 'where', wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_where', dur: 22.7, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
