/* turtle 場景 §24 t_iucn(句 88–90,18.8 秒)好消息。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 左下鴿子(面向右)。句88:橫向保育等級尺(瀕危 EN、易危 VU、近危 NT、無危 LC 四格,寬 1260)第一格就在;右上「?」記號彈入。
 * 句89:「?」退場;日曆牌「2025 年 10 月」加來源牌「IUCN」;綠蠵龜標記(海龜寬 200)在尺上方從「瀕危」逐格跳到「無危」;
 *   左下方上升折線(四個點逐點畫出)與「1970 年代至今 約」「+28%」。
 * 句90:上一幕整組換成海面板,六個圓點(綠黃混雜)逐個彈入,牌「各海域不一樣」;鴿子點頭一次。
 * 字牌一律用 Charts(px 紙片);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.09, end: 2.35 }, { start: 2.47, end: 13.23 }, { start: 13.36, end: 18.72 }];
  const GREEN = 'hsl(130 50% 40%)';
  const LADDER = { x0: 560, y: 435, w: 315, h: 250 };                  // 四格由左而右:瀕危 … 無危(總寬 1260)
  const CELLS = [{ zh: '瀕危', en: 'EN', col: 'hsl(25 90% 58%)' }, { zh: '易危', en: 'VU', col: 'hsl(46 92% 58%)' },
    { zh: '近危', en: 'NT', col: 'hsl(78 55% 56%)' }, { zh: '無危', en: 'LC', col: 'hsl(130 45% 46%)' }];
  const MARK_Y = 195;
  const CHART = { x0: 520, y0: 572, w: 560, h: 264 };
  const PTS = [[610, 770], [740, 715], [880, 690], [1020, 615]];
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const absSheet = (content, cx, cy, o) => Ch.sheet(`<g transform="translate(${f(-cx)} ${f(-cy)})">${content}</g>`, Object.assign({ x: cx, y: cy, u: U }, o));
  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const cellX = (i) => LADDER.x0 + LADDER.w * (i + 0.5);
  const txt = (s, y, fs, ink) => `<text x="0" y="${y}" font-family="GenSen" font-size="${fs}" text-anchor="middle" dominant-baseline="central" fill="${ink}" stroke="none">${s}</text>`;

  // ---------- 保育等級尺 ----------
  function ladder() {
    let s = '';
    CELLS.forEach((c, i) => {
      const body = rect(-LADDER.w / 2 + 3, -LADDER.h / 2, LADDER.w - 6, LADDER.h, c.col) + txt(c.zh, -34, 84, K.INK) + txt(c.en, 62, 64, K.INK);
      s += Ch.sheet(body, { x: cellX(i), y: LADDER.y, u: U, kind: 'cell', id: c.en, wide: true });
    });
    return s;
  }
  // 綠蠵龜小標記:黃圓底(直徑 210)加海龜(寬 200)
  function marker(pal, col, k, dy) {
    const body = `<circle cx="0" cy="0" r="105" fill="${K.YELLOW}"/>` + Ch.icon(ic(pal, 'turtle', {}), 0, 0, 200);
    return Ch.sheet(body, { x: cellX(col), y: MARK_Y + dy, u: U, k, kind: 'marker', id: 'green' });
  }

  // ---------- 折線圖 ----------
  function chart(pal, n) {
    let c = rect(CHART.x0, CHART.y0, CHART.w, CHART.h, pal.pad);
    c += R(560, 598, 8, 208, K.INK) + R(560, 797, 480, 8, K.INK);
    let seg = '', dots = '';
    for (let i = 1; i < n; i++) {
      const a = PTS[i - 1], b = PTS[i];
      seg += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${K.PAPER}" stroke-width="26" stroke-linecap="round"/>`;
    }
    for (let i = 1; i < n; i++) {
      const a = PTS[i - 1], b = PTS[i];
      seg += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${pal.text}" stroke-width="16" stroke-linecap="round"/>`;
    }
    for (let i = 0; i < n; i++) dots += `<circle cx="${PTS[i][0]}" cy="${PTS[i][1]}" r="19" fill="${K.YELLOW}"/>`;
    return absSheet(c + seg + dots, CHART.x0 + CHART.w / 2, CHART.y0 + CHART.h / 2, { kind: 'chart', id: 'line' });
  }

  // ---------- 句90 海面板 ----------
  const SEA = { x0: 500, y0: 92, w: 1335, h: 740 };
  const DOTS = [[760, 230, 'G'], [1050, 400, 'Y'], [1350, 215, 'G'], [1640, 390, 'Y'], [820, 560, 'Y'], [1480, 560, 'G']];
  function sea(k) {
    let c = rect(SEA.x0, SEA.y0, SEA.w, SEA.h, 'hsl(205 60% 62%)');
    [[640, 150], [1180, 300], [1560, 150], [700, 440], [1250, 520], [1700, 480], [1000, 650]].forEach((p) => { c += R(p[0] - 70, p[1] - 7, 140, 14, 'hsl(205 60% 74%)'); });
    return absSheet(c, SEA.x0 + SEA.w / 2, SEA.y0 + SEA.h / 2, { k, kind: 'sea', id: 'sea' });
  }

  function pigeonPose(k, kNod) {
    const pose = (k >= kNod && k < kNod + 6) ? K.expr(K.clip('nod', k - kNod), 'look') : K.expr(K.clip('idle', k), 'look');
    return Object.assign({}, pose, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, at(L[2], 0.6)), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (k < F[2]) {
      s += ladder();
      s += Ch.triviaMark({ u: U, k: k - F[0], kOut: k >= F[1] ? k - F[1] : -1 });
      if (k >= F[1]) {
        const kk = (p) => k - at(L[1], p);
        const hops = [0.3, 0.38, 0.46], hop = hops.filter((p) => kk(p) >= 0).length;           // 0=瀕危 … 3=無危
        s += marker(pal, hop, k - F[1], 0);
        s += Ch.dateTag({ x: 300, y: 240, top: '2025 年', main: '10 月', size: 240, u: U, k: k - F[1], id: 'date' });
        s += Ch.srcTag('IUCN', { x: 300, y: 428, anchor: 'center', fs: 48, pal, u: U, k: kk(0.06), id: 'iucn' });
        const n = [0.52, 0.58, 0.64, 0.7].filter((p) => kk(p) >= 0).length;
        if (n > 0) s += chart(pal, n);
        const pl = Ch.plate('1970 年代至今 約', 56, { padX: 0.4 });
        s += Ch.sheet(pl.svg, { x: 1450, y: 607, rot: -1.5, u: U, k: kk(0.76), kind: 'tag', id: 'since', wide: true });
        s += Ch.bigNum({ x: 1450, y: 722, num: '+28%', fs: 150, u: U, k: kk(0.82), id: 'n28' });
      }
    } else {
      s += sea(undefined);
      DOTS.forEach((d, j) => {
        s += Ch.sheet(`<circle cx="0" cy="0" r="72" fill="${d[2] === 'G' ? GREEN : K.YELLOW}"/>`,
          { x: d[0], y: d[1], u: U, k: k - F[2] - j * 2, kind: 'dot', id: 'sea' + j });
      });
      const pl = Ch.plate('各海域不一樣', 84, { fill: K.PAPER });
      s += Ch.sheet(pl.svg, { x: 1170, y: 735, rot: -1.5, u: U, k: k - at(L[2], 0.45), kind: 'tag', id: 'diff', wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_iucn', dur: 18.8, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
