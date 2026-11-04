/* turtle 場景 §23 t_light_b(句 85–87,17.2 秒)大灣的二十四隻(內容段高潮)。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 夜景(句85–86):深色夜空紙片鋪滿,左海、中沙灘、右飯店(高 540)。
 * 句85:牌「2020 墾丁 大灣」與大數字「24 隻」在句首;24 隻小海龜(各 72px,六欄四列鬆散隊伍,位置用 hash 偏移)逐格朝右邊飯店爬。
 * 句86:飯店窗戶分 4 格逐步變暗;水桶彈入,小海龜逐隻跳向桶口消失,計數牌 0/24 → 24/24;水桶移到海邊。
 * 句87:夜空整組退場(縮小兩格),白天配色回來;飯店與成年海龜左右各一,中間兩條線:上面粗實線掛燈泡,下面細虛線掛牙刷;停留。
 * 字牌一律用 Charts(px 紙片);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;
  const DEF = [{ start: 0.03, end: 6.51 }, { start: 6.63, end: 10.7 }, { start: 10.82, end: 16.17 }];
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const NIGHT = 'hsl(170 45% 14%)';
  const f = (x) => +(+x).toFixed(2);

  // 夜景座標
  const HOTEL_N = { x: 1600, y: 352, box: 540 };
  const NT = 24, ROWS = 4, TSIZE = 72, SHIFT = 170;
  const BUCKET = { x: 690, y: 722 }, BUCKET_SEA_DX = [70, 140, 210];
  // 白天座標
  const HOTEL_D = { x: 380, y: 440, box: 540 }, TURTLE_D = { x: 1560, y: 450, box: 470 };
  const LINE_X0 = 625, LINE_X1 = 1310, LINE_UP = 380, LINE_DN = 580;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const iconSheet = (pal, n, o, x, y, box, p) => Ch.sheet(Ch.icon(ic(pal, n, o), 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: n, wide: PT.LIST[n].wide }, p));
  // 以絕對座標繪製的紙片:content 用絕對 px,cx,cy 為紙片中心
  const absSheet = (content, cx, cy, o) => Ch.sheet(`<g transform="translate(${f(-cx)} ${f(-cy)})">${content}</g>`, Object.assign({ x: cx, y: cy, u: U }, o));
  const poly = (pts, fill) => `<polygon points="${pts.map((p) => f(p[0]) + ',' + f(p[1])).join(' ')}" fill="${fill}"/>`;
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const shrinkWrap = (j, cx, cy, s) => (j < 0 ? s : j >= OUT.length ? '' : `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`);

  // ---------- 夜景 ----------
  function sky() {
    let c = R(-875, -375, 1750, 750, NIGHT).replace('stroke="none"', 'stroke-linejoin="miter"');
    for (let i = 0; i < 44; i++) {
      c += `<circle cx="${f(-850 + K.hash(i * 3.1 + 1) * 1700)}" cy="${f(-360 + K.hash(i * 7.7 + 2) * 500)}" r="${f(2.5 + K.hash(i * 5.3 + 3) * 4)}"` +
        ` fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return Ch.sheet(c, { x: 960, y: 460, u: U, kind: 'sky', id: 'sky' });
  }
  function sea() {
    const top = [[85, 590], [140, 570], [200, 590], [260, 570], [320, 590], [380, 570], [440, 590], [500, 570], [560, 595]];
    const pts = top.concat([[610, 625], [590, 690], [612, 760], [585, 835], [85, 835]]);
    let c = poly(pts, 'hsl(205 55% 30%)');
    [[200, 680], [350, 740], [190, 795], [450, 680]].forEach((p) => { c += R(p[0] - 60, p[1] - 7, 120, 14, 'hsl(205 55% 44%)'); });
    return absSheet(c, 348, 702, { kind: 'sea', id: 'sea' });
  }
  function sand() {
    const pts = [[560, 608], [800, 598], [1300, 602], [1835, 598], [1835, 835], [585, 835], [600, 760], [585, 690]];
    let c = poly(pts, 'hsl(38 42% 50%)');
    [[900, 805], [1250, 795], [1600, 815], [1050, 620]].forEach((p) => { c += R(p[0] - 50, p[1] - 5, 100, 10, 'hsl(38 42% 42%)'); });
    return absSheet(c, 1210, 716, { kind: 'sand', id: 'sand', wide: true });
  }
  // 窗戶亮度:step 0–4,每格多暗五扇(先半暗再全暗)
  function windows(step) {
    return Array.from({ length: 20 }, (_, i) => (i < 5 * step ? (i < 5 * (step - 1) ? 0 : 0.5) : 1));
  }
  // 小海龜 i:起點與終點(進度 0–1 對應爬行距離)
  function tBase(i) {
    const r = i % ROWS, c = Math.floor(i / ROWS);
    return { x: 640 + c * 76 + (r % 2) * 38 + (K.hash(i * 3 + 1) - 0.5) * 28, y: 650 + r * 44 + (K.hash(i * 3 + 2) - 0.5) * 14 };
  }
  const hatch = (pal, x, y, ang) => Ch.sheet(Ch.icon(ic(pal, 'hatchling', { ang }), 0, 0, TSIZE), { x, y, u: U, kind: 'prop', id: 'hatch' });

  // 水桶(紅色,桶口在桶身上緣):中心 (x,y)
  function bucket(x, y, k) {
    const c = `<path d="M -78 -66 Q 0 -190 78 -66" fill="none" stroke="${K.INK}" stroke-width="9" stroke-linecap="round"/>` +
      poly([[-92, -72], [92, -72], [72, 96], [-72, 96]], 'hsl(8 75% 55%)') + R(-102, -88, 204, 24, 'hsl(8 70% 38%)') + R(-60, -20, 120, 14, 'hsl(8 75% 66%)');
    return Ch.sheet(c, { x, y, u: U, k, kind: 'bucket', id: 'bucket' });
  }

  // 夜景整組(依句內格序 st 繪製;k 為目前格)
  function night(pal, k, F, L) {
    const N85 = K.frame(L[0].end) - F[0], N86 = K.frame(L[1].end) - F[1];
    const f0 = F[0] + 3, k86 = k - F[1];
    // 計數與水桶
    const kv0 = at(L[1], 0.34), span = Math.round(0.42 * N86);
    const van = Array.from({ length: NT }, (_, i) => kv0 + Math.floor(i * span / NT));
    const kBucket = at(L[1], 0.28), kMove = at(L[1], 0.86);
    const cnt = van.filter((v) => v <= k).length;
    const bx = BUCKET.x - (k < kMove ? 0 : BUCKET_SEA_DX[Math.min(k - kMove, BUCKET_SEA_DX.length - 1)]);
    const step = k < F[1] ? 0 : Math.min(4, Math.floor(k86 / 2) + 1);

    let s = sky() + sea() + sand();
    s += iconSheet(pal, 'moon', {}, 240, 215, 170, { id: 'moon' });
    s += iconSheet(pal, 'hotel', { lit: windows(step) }, HOTEL_N.x, HOTEL_N.y, HOTEL_N.box, { id: 'hotel' });
    // 小海龜
    for (let i = 0; i < NT; i++) {
      const b = tBase(i);
      const T = N85 * (0.78 + 0.16 * K.hash(i * 5 + 7));
      const prog = Math.max(0, Math.min(1, (Math.min(k, F[1]) - f0) / T));
      let x = b.x + SHIFT * prog, y = b.y, sc = 1;
      const moving = k < F[1] && prog > 0 && prog < 1;
      const ang = 90 + (moving ? (((k + i) % 2) ? 7 : -7) : 0);
      if (k >= van[i]) continue;                             // 已進桶
      if (k === van[i] - 1 && k >= F[1]) {                   // 跳向桶口
        x = (x + BUCKET.x) / 2; y = (y + BUCKET.y - 80) / 2; sc = 0.62;
      }
      const t = hatch(pal, x, y, ang);
      s += sc === 1 ? t : `<g transform="translate(${f(x)} ${f(y)}) scale(${sc}) translate(${f(-x)} ${f(-y)})">${t}</g>`;
    }
    if (k >= F[1] && k >= kBucket) s += bucket(bx, BUCKET.y, k - kBucket);
    // 牌與數字
    const pl = Ch.plate('2020 墾丁 大灣', 84, { fill: K.YELLOW });
    s += Ch.sheet(pl.svg, { x: 860, y: 180, rot: -1.5, u: U, k: k - F[0], kind: 'tag', id: 'where', wide: true });
    if (k < F[1]) {
      s += Ch.bigNum({ x: 860, y: 400, num: '24', unit: '隻', fs: 200, u: U, k: k - F[0], id: 'n24' });
    } else {
      s += Ch.bigNum({ x: 860, y: 400, num: `${cnt}/24`, fs: 200, u: U, id: 'cnt' });
    }
    return s;
  }

  // ---------- 句87 ----------
  function line87(pal, k, F, L) {
    const kk = (p) => k - at(L[2], p);
    const grow = (j) => (j < 0 ? 0 : [1 / 3, 2 / 3, 1][Math.min(j, 2)]);
    let s = iconSheet(pal, 'hotel', { lit: 1 }, HOTEL_D.x, HOTEL_D.y, HOTEL_D.box, { id: 'hotel', k: k - F[2] });
    s += iconSheet(pal, 'turtle', {}, TURTLE_D.x, TURTLE_D.y, TURTLE_D.box, { id: 'turtle', k: k - F[2] });
    const W = LINE_X1 - LINE_X0, cx = (LINE_X0 + LINE_X1) / 2;
    // 上:粗實線(由左到右畫出),中間掛燈泡
    const gu = grow(kk(0.22)), lu = W * gu;
    if (gu > 0) s += absSheet(R(LINE_X0, LINE_UP - 16, lu, 32, K.INK), LINE_X0 + lu / 2, LINE_UP, { kind: 'line', id: 'thick', wide: true });
    s += iconSheet(pal, 'bulb', { on: true, rays: true }, cx, LINE_UP, 200, { id: 'bulb', k: kk(0.38) });
    // 下:細虛線,中間掛牙刷
    const gd = grow(kk(0.56)), ld = W * gd;
    if (gd > 0) {
      const dash = 60, n = 7, pitch = (W - dash) / (n - 1);
      let c = '';
      for (let i = 0; i < n; i++) if (i * pitch + dash <= ld + 0.5) c += R(LINE_X0 + i * pitch, LINE_DN - 7, dash, 14, K.INK);
      s += absSheet(c, LINE_X0 + ld / 2, LINE_DN, { kind: 'line', id: 'thin', wide: true });
    }
    s += iconSheet(pal, 'toothbrush', {}, cx, LINE_DN, 540, { id: 'brush', k: kk(0.74) });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    let s = '';
    if (k < F[2]) s = night(pal, k, F, L);
    else {
      const j = k - F[2];
      s = shrinkWrap(j, 960, 460, night(pal, F[2] - 1, F, L)) + line87(pal, k, F, L);
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_light_b', dur: 17.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
