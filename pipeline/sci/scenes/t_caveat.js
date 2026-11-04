/* turtle 場景 §14 t_caveat(句 50–52,12.7 秒)老實交代。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句50:鴿子舉記錄板;兩張空的編號牌「第一」「第二」並排彈入。
 * 句51:「第二」退場、「第一」展開:正字記錄表、標題列「志工登記」、量尺方格加「科學抽樣」、方格打紅叉。
 * 句52:「第一」退場、「第二」展開(海面):飯店、漂來的牙刷、箭頭從上方指入、「誰的?」標籤、飯店與牙刷之間虛線加問號。
 * 字牌一律用 Charts(px 紙片,描邊一致);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 300, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.07, end: 1.71 }, { start: 1.83, end: 5.11 }, { start: 5.23, end: 12.63 }];
  const SMALL_A = { x: 895, y: 440, w: 590, h: 620 }, SMALL_B = { x: 1535, y: 440, w: 590, h: 620 };   // 句50 兩張並排
  const BIG = { x: 1215, y: 440, w: 1230, h: 640 };                                                     // 句51–52 展開
  const HEAD = 130;                                // 牌頭高
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const RED = 'hsl(6 75% 55%)';
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const R = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' stroke-linejoin="miter"'}/>`;
  const NS = ' stroke="none"';
  const T = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  // 圖解嵌進 px 紙片:box = 最長邊 px
  const iconSheet = (pal, n, o, x, y, box, p) => Ch.sheet(Ch.icon(ic(pal, n, o), 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: n, wide: PT.LIST[n].wide }, p));
  // 退場:kOut 為退場起始格;回傳 null = 已消失,否則包上縮放群組的函式
  function shrink(k, kOut, cx, cy) {
    if (kOut == null || k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  // 粗箭頭(px):起點 → 尖端。o: {th(桿粗),hw(頭寬),hl(頭長),fill,k,id}
  function arrow(x0, y0, x1, y1, o) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, px = -uy, py = ux, th = o.th, hw = o.hw, hl = o.hl;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, bx = x1 - ux * hl, by = y1 - uy * hl;
    const pts = [[x0 + px * th / 2, y0 + py * th / 2], [bx + px * th / 2, by + py * th / 2], [bx + px * hw / 2, by + py * hw / 2], [x1, y1],
      [bx - px * hw / 2, by - py * hw / 2], [bx - px * th / 2, by - py * th / 2], [x0 - px * th / 2, y0 - py * th / 2]];
    return Ch.sheet(`<polygon points="${pts.map((p) => `${f(p[0] - cx)},${f(p[1] - cy)}`).join(' ')}" fill="${o.fill}"/>`,
      { x: cx, y: cy, u: U, k: o.k, kind: 'arrow', id: o.id, wide: Math.min(Math.abs(dx), Math.abs(dy)) < 0.33 * Math.max(Math.abs(dx), Math.abs(dy)) });
  }

  // 牌底(含牌頭):title 置中(小牌)或靠左(展開);body = 牌身底色;extra = 牌身內加的內容(px,中心 = 牌心)
  function cardBase(pal, c, o, k) {
    let s = R(-c.w / 2, -c.h / 2, c.w, c.h, o.body) + R(-c.w / 2, -c.h / 2, c.w, HEAD, pal.main, NS);
    s += T(o.title, o.left ? -c.w / 2 + 130 : 0, -c.h / 2 + HEAD / 2 + 4, 96, pal.onMain);
    s += o.extra || '';
    return Ch.sheet(s, { x: c.x, y: c.y, u: U, k, kind: 'card', id: o.id });
  }
  const emptyBody = (c) => `<rect x="${f(-c.w / 2 + 40)}" y="${f(-c.h / 2 + HEAD + 40)}" width="${f(c.w - 80)}" height="${f(c.h - HEAD - 80)}"` +
    ` fill="none" stroke="${K.INK}" stroke-width="8" stroke-dasharray="24 16"/>`;
  // 海面:牌身下半的藍色鋸齒浪
  function sea(c) {
    const y0 = 110, pts = [];
    for (let i = 0; i <= 16; i++) pts.push([-c.w / 2 + i * c.w / 16, y0 + (i % 2 ? -26 : 0)]);
    pts.push([c.w / 2, c.h / 2], [-c.w / 2, c.h / 2]);
    return `<polygon points="${pts.map((p) => `${f(p[0])},${f(p[1])}`).join(' ')}" fill="hsl(205 60% 58%)"${NS}/>`;
  }
  // 量尺方格(5×5,上緣與左緣有刻度),中心在原點,邊長 s
  function gridSvg(pal, s) {
    const n = 5, cell = s / n, h = s / 2;
    let c = R(-h, -h, s, s, K.PAPER);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      if ((i + j) % 2 === 0) c += R(-h + i * cell, -h + j * cell, cell, cell, pal.pad, NS);
    }
    for (let i = 0; i <= n; i++) c += R(-h + i * cell - 3, -h, 6, s, K.INK, NS) + R(-h, -h + i * cell - 3, s, 6, K.INK, NS);
    for (let i = 0; i < 20; i++) c += R(-h + i * s / 20 - 1.5, -h - 22, 3, i % 5 === 0 ? 22 : 12, K.INK, NS);
    return c;
  }
  const crossSvg = (len, th) => [45, -45].map((a) => `<g transform="rotate(${a})">${R(-len / 2, -th / 2, len, th, RED, NS)}</g>`).join('');

  // 句51 展開的「第一」整組(退場時各 k 取 99)
  function bigA(pal, kBase, ks) {
    const c = BIG;
    let s = cardBase(pal, c, { title: '第一', left: true, body: K.PAPER, id: 'A' }, kBase);
    s += iconSheet(pal, 'tallySheet', { tally: [7, 4, 9, 3, 6, 2, 8, 5, 10, 4, 3, 7, 2, 6, 1, 5, 3, 2, 4] }, c.x - 300, c.y + 55, 480, { k: ks.tally });
    const pl = Ch.plate('志工登記', 64, { fill: K.PAPER });
    s += Ch.sheet(pl.svg, { x: c.x - c.w / 2 + 560, y: c.y - c.h / 2 + HEAD / 2, u: U, k: ks.tag, kind: 'tag', id: 'vol', wide: true });
    s += Ch.sheet(gridSvg(pal, 340), { x: c.x + 300, y: c.y + 20, u: U, k: ks.grid, kind: 'grid', id: 'grid' });
    const lab = Ch.plate('科學抽樣', 64, { fill: K.PAPER });
    s += Ch.sheet(lab.svg, { x: c.x + 300, y: c.y + 255, u: U, k: ks.lab, kind: 'tag', id: 'sci', wide: true });
    return s + Ch.sheet(crossSvg(380, 34), { x: c.x + 300, y: c.y + 20, u: U, k: ks.cross, kind: 'cross', id: 'x' });
  }

  function pigeonPose(k, reacts, expr) {
    let pose = null;
    for (const r of reacts) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (k >= r.k0 && k < r.k0 + n) { pose = K.expr(K.clip(r.clip, k - r.k0), r.expr || expr); break; }
    }
    pose = pose || K.expr(K.clip('idle', k), expr);
    return Object.assign({}, pose, { prop: 'wing', wing: 110, flip: 1 });   // 舉著記錄板、面向右
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const sec = k < F[1] ? 0 : k < F[2] ? 1 : 2;
    const kB0 = F[0] + 5;                          // 句50:第二張晚五格
    const kBigA = F[1] + 2, kBigB = F[2] + 2;      // 展開(前一張退場後兩格)
    const e51 = { tally: at(L[1], 0.15), tag: at(L[1], 0.32), nod: at(L[1], 0.34), grid: at(L[1], 0.5), lab: at(L[1], 0.58), cross: at(L[1], 0.72) };
    const e52 = { hotel: at(L[2], 0.1), brush: at(L[2], 0.2), arrow: at(L[2], 0.3), tilt: at(L[2], 0.3), who: at(L[2], 0.45), line: at(L[2], 0.6), q: at(L[2], 0.72) };

    const reacts = [{ k0: e51.nod, clip: 'nod' }, { k0: e52.tilt, clip: 'tilt', expr: 'doubt' }];
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, reacts, k >= e52.tilt ? 'doubt' : 'look'), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (sec === 0 || (sec === 1 && k < kBigA)) {   // 兩張空牌(句51 開頭 B 退場、A 暫留)
      const b = sec === 1 ? shrink(k, F[1], SMALL_B.x, SMALL_B.y) : (s2) => s2;
      s += cardBase(pal, SMALL_A, { title: '第一', body: K.PAPER, extra: emptyBody(SMALL_A), id: 'A' }, k - F[0]);
      if (b && k >= kB0) s += b(cardBase(pal, SMALL_B, { title: '第二', body: K.PAPER, extra: emptyBody(SMALL_B), id: 'B' }, k - kB0));
    } else if (sec === 1) {                        // 句51:第一 展開
      s += bigA(pal, k - kBigA, { tally: k - e51.tally, tag: k - e51.tag, grid: k - e51.grid, lab: k - e51.lab, cross: k - e51.cross });
    } else {                                       // 句52:第一 退場、第二 展開
      const a = shrink(k, F[2], BIG.x, BIG.y);
      if (a && k < kBigB) s += a(bigA(pal, 99, { tally: 99, tag: 99, grid: 99, lab: 99, cross: 99 }));
      if (k >= kBigB) {
        s += cardBase(pal, BIG, { title: '第二', left: true, body: 'hsl(195 70% 84%)', extra: sea(BIG), id: 'B' }, k - kBigB);
        const cx = BIG.x, cy = BIG.y;
        s += iconSheet(pal, 'hotel', { lit: 0.8 }, cx - 420, cy - 20, 300, { k: k - e52.hotel });
        s += iconSheet(pal, 'toothbrush', {}, cx + 300, cy + 120, 540, { k: k - e52.brush, rot: -8, id: 'brush' });
        s += arrow(cx + 520, cy - 170, cx + 380, cy + 50, { th: 44, hw: 100, hl: 70, fill: RED, k: k - e52.arrow, id: 'in' });
        const who = Ch.plate('誰的?', 80, { fill: K.YELLOW });
        s += Ch.sheet(who.svg, { x: cx + 300, y: cy + 250, rot: 3, u: U, k: k - e52.who, kind: 'tag', id: 'who', wide: true });
        s += Ch.sheet(`<path d="M -137 -27 L 137 27" stroke="${K.INK}" stroke-width="16" stroke-dasharray="34 22" fill="none"/>`,
          { x: cx - 125, y: cy + 80, u: U, k: k - e52.line, kind: 'link', id: 'link', wide: true });
        if (k - e52.q >= 0) s += K.tile('?', { x: cx - 125, y: cy + 80, size: 130, rot: 5, u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(k - e52.q), sy: K.pop(k - e52.q), id: 'q', enter: k - e52.q < 2 });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_caveat', dur: 12.7, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
