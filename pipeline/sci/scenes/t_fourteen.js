/* turtle 場景 §18 t_fourteen(句 68–70,15.2 秒)吃下去會怎樣。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句68:海龜肚子剪影(深色輪廓,寬約 980px,不畫內臟),右上「?」。
 * 句69:牌「澳洲研究 246 隻」;塑膠片依句長平均分配逐片彈入到 14 片(前 70% 的句長),左邊計數牌 0→14,右側直式量表每片升一格,
 *      升到 14 片時剛好 50%;約 74% 處計數牌與研究牌退場,換大字「14 片 → 50%」。
 * 句70:四樣東西(塑膠袋、塑膠碎片、釣魚線、魚鉤)排一排,依序打勾;最後下方一條板子:牙刷灰階加空框「牙刷:沒看到」;上方小牌「我們查過的研究」。
 * 鴿子在左下當觀察者(每句最多一個反應);內容全在 x 508 以右。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 800 };                 // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0.085, end: 1.53 }, { start: 1.65, end: 9.025 }, { start: 9.145, end: 15.13 }];
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const BODY = { x: 1000, y: 570, s: 3.0 };        // 剪影中心(單位 (12,14))與倍率
  const WIN = { x: -14, y: -10 };                  // 肚子視窗中心(單位)
  const GAUGE = { x: 1760, y: 617, h: 390, w: 70 };
  const N = 14;
  const f = (x) => +(+x).toFixed(2);
  const now = (k) => (k < 0 ? -1 : 3);             // 大紙片直接以原尺寸出現(不過衝,免得蓋進字幕帶)
  const DARK = 'hsl(170 40% 17%)', BELLY = 'hsl(170 26% 33%)', RED = 'hsl(6 75% 55%)', GREEN = 'hsl(130 55% 40%)';

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const sh = (c, x, y, kk, kind, id, ex) => Ch.sheet(c, Object.assign({ x, y, u: U, k: kk, kind, id }, ex));
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  function tl(ch, x, y, size, kk, id, o) {
    const p = K.pop(kk);
    if (p <= 0) return '';
    return K.tile(ch, Object.assign({ x, y, size, u: U, sx: p, sy: p, id, enter: kk < 2 }, o));
  }
  function layer(k, kIn, kOut, cx, cy, draw) {
    if (k < kIn) return '';
    if (kOut != null && k >= kOut) {
      const j = k - kOut;
      if (j >= OUT.length) return '';
      return `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${draw(1e6)}</g>`;
    }
    return draw(k);
  }

  // ---------- 海龜剪影(單位 = 海龜原座標;外層依 BODY 縮放) ----------
  const PARTS = ['M -92 28 C -108 50, -134 64, -152 60 C -142 44, -126 28, -108 16 Z', 'M -118 16 L -146 24 L -120 30 Z',
    'M 70 -6 L 122 -13 L 122 25 L 74 38 Z', 'M 108 -15 C 128 -24, 160 -18, 171 -1 C 176 10, 167 23, 151 25 L 110 27 Z',
    'M -116 20 L 92 20 C 82 48, 40 54, -20 54 C -72 54, -106 46, -116 20 Z', 'M -125 25 C -120 -30, -70 -72, -15 -72 C 45 -72, 85 -35, 95 25 Z',
    'M 72 26 C 62 60, 22 96, -34 100 C -18 78, 12 52, 34 22 Z'];
  const PIECE = [[[-12, -8], [10, -12], [14, 6], [-8, 10]], [[-11, -10], [13, -4], [-2, 13]], [[-14, -4], [0, -12], [14, -2], [6, 10], [-10, 8]]];
  const PCOL = [PT.C.red, PT.C.blue, K.YELLOW, PT.C.white, PT.C.orange, PT.C.green];
  // 14 個位置:3 列 5、5、4 片
  const SLOTS = [];
  [[-27, [-54, -27, 0, 27, 54]], [0, [-54, -27, 0, 27, 54]], [27, [-40.5, -13.5, 13.5, 40.5]]].forEach(([dy, xs]) => xs.forEach((dx) => SLOTS.push([WIN.x + dx, WIN.y + dy])));
  const piecePoly = (i, sc) => {
    const pts = PIECE[i % 3].map((p) => `${f(p[0] * 0.8)},${f(p[1] * 0.8)}`).join(' ');
    return `<g transform="translate(${f(SLOTS[i][0])} ${f(SLOTS[i][1])}) rotate(${(i * 47) % 360}) scale(${sc})"><polygon points="${pts}" fill="${PCOL[i % 6]}"/></g>`;
  };
  // n 片:kp[i] = 第 i 片出現後第幾格
  function bodySvg(kp) {
    const lay = (stroke) => PARTS.map((d) => `<path d="${d}" fill="${DARK}" ${stroke}/>`).join('');
    let c = lay(`stroke="${K.PAPER}" stroke-width="${f(8 / BODY.s)}" stroke-linejoin="round"`) + lay('stroke="none"') +
      `<ellipse cx="${WIN.x}" cy="${WIN.y}" rx="88" ry="44" fill="${BELLY}" stroke="none"/><circle cx="146" cy="-3" r="5" fill="${K.PAPER}" stroke="none"/>`;
    for (let i = 0; i < N; i++) {
      const sc = K.pop(kp[i]);
      if (sc > 0) c += piecePoly(i, sc);
    }
    return `<g transform="scale(${BODY.s}) translate(-12 -14)" stroke-width="${f(4 / BODY.s)}">${c}</g>`;
  }
  // 量表:n 片 → 填到 n/14 × 50%
  function gaugeSvg(n) {
    const hi = GAUGE.h - 20, fill = hi * 0.5 * n / N;
    return `<rect x="${-GAUGE.w / 2}" y="${-GAUGE.h / 2}" width="${GAUGE.w}" height="${GAUGE.h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="-25" y="${-hi / 2}" width="50" height="${hi}" fill="hsl(200 15% 86%)" stroke="none"/>` +
      (fill > 0 ? `<rect x="-25" y="${f(hi / 2 - fill)}" width="50" height="${f(fill)}" fill="${RED}" stroke="none"/>` : '') +
      `<rect x="${-GAUGE.w / 2}" y="-3" width="${GAUGE.w}" height="6" fill="${K.INK}" stroke="none"/>`;
  }

  // ---------- 句70 的圖 ----------
  const checkSvg = () => `<g transform="scale(0.42)"><polygon points="-120,6 -76,-38 -34,6 84,-110 128,-66 -34,92" fill="${GREEN}"/></g>`;
  function fragIc(pal) {                           // 兩團塑膠碎片疊起來,高度夠大
    const fr = PT.LIST.fragments.fn(pal, {});
    return { svg: `<g transform="translate(0 -48)">${fr}</g><g transform="translate(0 48) rotate(180)">${fr}</g>`, w: 190, h: 190 };
  }
  const CARDS = [{ label: '塑膠袋', icn: (pal) => ic(pal, 'bag', {}), box: 180 }, { label: '塑膠碎片', icn: fragIc, box: 190 },
    { label: '釣魚線', icn: (pal) => ic(pal, 'fishline', {}), box: 250 }, { label: '魚鉤', icn: (pal) => ic(pal, 'hook', {}), box: 180 }];
  const CW = 306, CGAP = 24, CY = 380;
  const cardX = (i) => 540 + CW / 2 + i * (CW + CGAP);

  function pigeonPose(k, evs) {
    for (const e of evs) {
      const n = K.P.CLIPS[e.clip].frames.length;
      if (k >= e.k0 && k < e.k0 + n) return Object.assign({}, K.expr(K.clip(e.clip, k - e.k0), e.expr), { flip: 1 });
    }
    return Object.assign({}, K.expr(K.clip('idle', k), 'look'), { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const kP = [];                                  // 第 i 片出現的格(前 70% 句長平均分配)
    for (let i = 0; i < N; i++) kP.push(at(L[1], 0.03 + i * (0.67 / (N - 1))));
    const E = { big: at(L[1], 0.74), half: kP[N - 1] + 2, tick: [0.28, 0.4, 0.52, 0.63].map((p) => at(L[2], p)), strip: at(L[2], 0.74) };
    const evs = [{ k0: F[0] + 3, clip: 'tilt', expr: 'think' }, { k0: E.big, clip: 'shock', expr: 'surprised' }, { k0: E.strip, clip: 'shrug', expr: 'doubt' }];
    const nOf = (ke) => kP.filter((p) => ke >= p).length;

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, evs), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // ----- 句68–69:剪影、量表 -----
    s += layer(k, F[0], F[2], BODY.x, BODY.y, (ke) => sh(bodySvg(kP.map((p) => ke - p)), BODY.x, BODY.y, now(ke - F[0]), 'prop', 'body'));
    s += layer(k, F[0] + 1, F[1], 1700, 250, (ke) => tl('?', 1700, 250, 220, ke - F[0] - 1, 'q', { fill: K.INK, ink: K.YELLOW, rot: 6 }));
    s += layer(k, F[1] + 1, F[2], GAUGE.x, GAUGE.y, (ke) => sh(gaugeSvg(nOf(ke)), GAUGE.x, GAUGE.y, now(ke - F[1] - 1), 'prop', 'gauge', { wide: true }) +
      sh(Ch.plate('死亡機率', 56, {}).svg, 1690, 365, ke - F[1] - 1, 'tag', 'gaugeT', { rot: -2, wide: true }) +
      sh(Ch.plate('50%', 56, { fill: K.YELLOW }).svg, 1612, GAUGE.y, ke - E.half, 'tag', 'half', { rot: -2, wide: true }));
    s += layer(k, F[1], E.big, 800, 220, (ke) => sh(Ch.plate('澳洲研究 246 隻', 64, { fill: K.YELLOW }).svg, 800, 150, ke - F[1], 'tag', 'study', { rot: -1.5, wide: true }) +
      sh(Ch.plate(nOf(ke) + ' 片', 72, {}).svg, 640, 270, ke - F[1], 'tag', 'count', { rot: 1.5, wide: true }));
    s += layer(k, E.big, F[2], 1150, 200, (ke) => Ch.bigNum({ x: 1150, y: 200, num: '14 片 → 50%', fs: 150, u: U, k: ke - E.big, rot: -1, id: 'big' }));

    // ----- 句70:四樣東西打勾、牙刷沒看到 -----
    if (k >= F[2]) {
      s += sh(Ch.plate('我們查過的研究', 48, { fill: K.YELLOW }).svg, 727, 128, k - F[2], 'src', 'src', { rot: -1.5, wide: true });
      CARDS.forEach((c, i) => {
        const kk = k - F[2], x = cardX(i);
        s += sh(`<rect x="${-CW / 2}" y="-200" width="${CW}" height="400" fill="${K.PAPER}" stroke-linejoin="miter"/><rect x="${-CW / 2}" y="-200" width="${CW}" height="20" fill="${pal.main}" stroke="none"/>` +
          Ch.icon(c.icn(pal), 0, -5, c.box) + txt(c.label, 0, 142, 64, K.INK), x, CY, kk, 'card', 'card' + i);
        s += sh(checkSvg(), x, CY - 150, k - E.tick[i], 'check', 'tick' + i);
      });
      if (k >= E.strip) {
        const kk = k - E.strip;
        s += sh(`<rect x="-648" y="-105" width="1296" height="210" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
          `<rect x="-615" y="-55" width="110" height="110" fill="${K.INK}" stroke="none"/><rect x="-603" y="-43" width="86" height="86" fill="${K.PAPER}" stroke="none"/>` +
          Ch.icon(ic(pal, 'toothbrush', {}), -130, 0, 540, true) + txt('牙刷:沒看到', 400, 0, 64, K.INK), 1188, 725, now(kk), 'card', 'strip', { wide: true });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_fourteen', dur: 15.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
