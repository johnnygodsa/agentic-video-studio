/* 認真鴿:可動骨架、表情組、動作片段庫。純函式,不依賴 DOM。
 * 座標系 300x300,腳底約 y=280,預設嘴朝左。畫面是 pose 的純函式(同 pose 同圖)。
 * pigeonSVG(pose) 回傳 <g>(最外層帶 filter="url(#pap)",頁面需先放入 PAP_DEFS)。
 * 片段更新率固定 POSE_FPS(頓感,不補間):poseAt(clip, t) 取整格姿勢。
 * 禁用 Math.random / Date / 計時器 / CSS 動畫。 */
(function () {
  const COLORS = {
    body: '#8E9AAF', head: '#A9B4C6', wing: '#6C7890', tail: '#5B6578',
    neck: '#3FA796', beak: '#FFD23F', leg: '#FFD23F', board: '#FFD23F',
    paper: '#FFF8E7', ink: '#1B1414', lid: '#7C879B', mouth: '#5A2A2A',
  };
  const POSE_FPS = 10;
  const PAP_DEFS = '<filter id="pap" x="-20%" y="-20%" width="140%" height="140%">' +
    '<feDropShadow dx="5" dy="6" stdDeviation="0" flood-color="#1B1414" flood-opacity=".45"/></filter>';

  // 樞紐與固定座標
  const EYE = [114, 92, 15];            // cx, cy, r
  const HEAD_PIV = [130, 160];          // 頭繞頸根
  const BEAK_PIV = [88, 106];           // 上下喙樞紐
  const SHOULDER = [146, 176], WING_TIP = [222, 206];
  const TAIL_PIV = [206, 220];
  const HIP_L = [150, 238], HIP_R = [186, 236];
  const FEET = [168, 280];              // 身體縮放/傾斜的地面基點

  // 姿勢預設值(基準站姿)
  const BASE = {
    flip: 0, hop: 0, squash: 1, xs: 1, bodyTilt: 0,
    headRot: 0, headDx: 0, headDy: 0, tail: 0, wing: 0, wlen: 1, legL: 0, legR: 0, prop: 'none',
    beak: 0, lid: 0.5, lidTilt: 0, pdx: -3, pdy: 5, ps: 1,
  };

  // 表情只改頭部(眼與嘴)參數
  const EXPR = {
    normal:     { lid: 0.5,  lidTilt: 0,  pdx: -3, pdy: 5,  ps: 1,    beak: 0 },
    surprised:  { lid: 0,    lidTilt: 0,  pdx: 0,  pdy: 0,  ps: 0.55, beak: 0.25 },
    doubt:      { lid: 0.45, lidTilt: 18, pdx: -4, pdy: 3,  ps: 1,    beak: 0 },
    smug:       { lid: 0.75, lidTilt: 0,  pdx: -3, pdy: 6,  ps: 1,    beak: 0 },
    speechless: { lid: 1,    lidTilt: 0,  pdx: 0,  pdy: 0,  ps: 1,    beak: 0 },
    think:      { lid: 0.15, lidTilt: 0,  pdx: -3, pdy: -6, ps: 1,    beak: 0 },
    look:       { lid: 0.2,  lidTilt: 0,  pdx: 0,  pdy: 0,  ps: 1,    beak: 0 },
    talkA:      { lid: 0.5,  lidTilt: 0,  pdx: -3, pdy: 5,  ps: 1,    beak: 0.4 },
    talkB:      { lid: 0.5,  lidTilt: 0,  pdx: -3, pdy: 5,  ps: 1,    beak: 0.8 },
  };

  const f = (x) => +(+x).toFixed(2);
  const rotStr = (a, c) => `rotate(${f(a)} ${c[0]} ${c[1]})`;
  const rotPt = (x, y, deg, c) => {
    const r = deg * Math.PI / 180, dx = x - c[0], dy = y - c[1];
    return [c[0] + dx * Math.cos(r) - dy * Math.sin(r), c[1] + dx * Math.sin(r) + dy * Math.cos(r)];
  };
  const poly = (pts, fill) => `<polygon points="${pts}" fill="${fill}"/>`;

  function eyeSVG(p) {
    const [cx, cy, r] = EYE, L = Math.max(0, Math.min(1, p.lid));
    if (L >= 0.97) {  // 一條線
      return `<path d="M${cx - 17},${cy + 1} h34" stroke="${COLORS.ink}" stroke-width="3.5" stroke-linecap="round" fill="none"/>`;
    }
    let s = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${COLORS.paper}"/>`;
    const pr = 6 * p.ps, maxd = r - pr - 1.5;
    let dx = p.pdx, dy = p.pdy;
    const d = Math.hypot(dx, dy);
    if (d > maxd) { dx *= maxd / d; dy *= maxd / d; }
    s += `<circle cx="${f(cx + dx)}" cy="${f(cy + dy)}" r="${f(pr)}" fill="${COLORS.ink}" stroke="none"/>`;
    if (L > 0.01) {
      const y0 = cy - r + 2 * r * L, w = Math.sqrt(Math.max(0, r * r - (y0 - cy) * (y0 - cy)));
      const large = y0 > cy ? 1 : 0;
      s += `<g transform="${rotStr(p.lidTilt, [cx, cy])}" stroke="none">` +
        `<path d="M${f(cx - w)},${f(y0)} A${r},${r} 0 ${large} 1 ${f(cx + w)},${f(y0)} Z" fill="${COLORS.lid}"/>` +
        `<path d="M${f(cx - w - 2)},${f(y0)} H${f(cx + w + 2)}" stroke="${COLORS.ink}" stroke-width="3.5" stroke-linecap="round"/></g>`;
    }
    return s;
  }

  function beakSVG(p) {
    const o = Math.max(0, Math.min(1, p.beak)), bp = BEAK_PIV;
    const du = o * 4, dl = -o * 24;
    let s = '';
    if (o > 0.04) {  // 嘴內
      const tu = rotPt(44, 108, du, bp), tl = rotPt(44, 108, dl, bp);
      s += `<polygon points="88,103 ${f(tu[0])},${f(tu[1])} ${f(tl[0])},${f(tl[1])} 88,112" fill="${COLORS.mouth}" stroke="none"/>`;
    }
    s += `<g transform="${rotStr(du, bp)}">${poly('86,92 44,108 88,106', COLORS.beak)}</g>`;
    s += `<g transform="${rotStr(dl, bp)}">${poly('88,106 44,108 88,118', COLORS.beak)}</g>`;
    return s;
  }

  function boardSVG(scale) {
    const lines = `<path d="M-18,-14 h36 M-18,0 h36 M-18,14 h22" stroke="${COLORS.ink}" stroke-width="4" fill="none"/>`;
    return `<g transform="scale(${scale})"><rect x="-28" y="-36" width="56" height="72" fill="${COLORS.board}" stroke="${COLORS.paper}" stroke-width="4"/>` +
      `<rect x="-12" y="-42" width="24" height="12" fill="${COLORS.tail}" stroke="${COLORS.paper}" stroke-width="4"/>${lines}</g>`;
  }

  function pigeonSVG(pose) {
    const p = Object.assign({}, BASE, EXPR[(pose || {}).expr] || {}, pose || {});
    const leg = (hip, a, dx) =>
      `<g transform="${rotStr(a, hip)}" stroke="${COLORS.leg}" stroke-width="6" stroke-linecap="round" fill="none">` +
      `<path d="M${hip[0]},${hip[1]} L${hip[0] + dx},${hip[1] + 36} l-14,6 M${hip[0] + dx},${hip[1] + 36} l12,7"/></g>`;
    let s = '';
    s += leg(HIP_L, p.legL, -6) + leg(HIP_R, p.legR, 6);
    if (p.prop === 'side') {
      s += `<g transform="translate(52 214) rotate(-9)">${boardSVG(1)}</g>`;
    }
    s += `<g transform="${rotStr(p.tail, TAIL_PIV)}">${poly('212,196 272,214 258,250 206,238', COLORS.tail)}</g>`;
    s += poly('92,150 196,128 240,176 218,238 122,248 80,206', COLORS.body);
    // 頭(含頸斑、喙、眼)
    s += `<g transform="translate(${f(p.headDx)} ${f(p.headDy)}) ${rotStr(p.headRot, HEAD_PIV)}">` +
      poly('96,162 84,88 120,56 164,68 168,118 142,164', COLORS.head) +
      poly('92,146 154,134 150,168 98,176', COLORS.neck) +
      beakSVG(p) + eyeSVG(p) + '</g>';
    // 翅膀(肩為樞紐);prop:'wing' 時記錄板跟著翅膀尖且保持直立
    let board = '';
    if (p.prop === 'wing') {
      board = `<g transform="translate(${WING_TIP[0]} ${WING_TIP[1]}) rotate(${f(-p.wing)}) translate(-8 -12) rotate(-9)">${boardSVG(0.85)}</g>`;
    }
    // wlen:翅膀沿肩向外的伸長倍率(指向動作用)
    const wpts = [[132, 166], [208, 158], [226, 204], [152, 218]]
      .map(([x, y]) => `${f(SHOULDER[0] + (x - SHOULDER[0]) * p.wlen)},${y}`).join(' ');
    s += `<g transform="${rotStr(p.wing, SHOULDER)}">${poly(wpts, COLORS.wing)}${board}</g>`;
    const sx = (1 + (1 - p.squash) * 0.5) * p.xs;
    const root = `<g transform="translate(${FEET[0]} ${f(FEET[1] - p.hop)}) rotate(${f(p.bodyTilt)}) scale(${f(sx)} ${f(p.squash)}) translate(${-FEET[0]} ${-FEET[1]})">${s}</g>`;
    const flip = p.flip ? ' transform="translate(300 0) scale(-1 1)"' : '';
    return `<g filter="url(#pap)"><g${flip} stroke="${COLORS.paper}" stroke-width="4" stroke-linejoin="round">${root}</g></g>`;
  }

  // ---------- 片段 ----------
  const mk = (o) => Object.assign({}, BASE, EXPR[o && o.expr] || {}, o || {});
  const range = (n, fn) => Array.from({ length: n }, (_, i) => mk(fn(i)));

  const CLIPS = {
    idle: { loop: true, frames: range(20, (i) => {
      const s = (1 - Math.cos(2 * Math.PI * i / 20)) / 2;      // 呼吸 0..1
      const o = { squash: f(1 + 0.012 * s), headDy: -Math.round(s * 2), wing: -Math.round(s * 2) };
      if (i === 8 || i === 9) o.tail = 2;
      if (i === 13) o.lid = 0.8;
      if (i === 14) o.lid = 1;
      if (i === 15) o.lid = 0.75;
      return o;
    }) },
    blink: { loop: false, frames: [{ lid: 0.75 }, { lid: 1 }, { lid: 0.65 }].map(mk) },
    nod: { loop: false, frames: [
      { headRot: 0 }, { headRot: -12, headDy: 3 }, { headRot: -2 },
      { headRot: -12, headDy: 3 }, { headRot: -2 }, { headRot: 0 },
    ].map(mk) },
    tilt: { loop: false, frames: [
      { headRot: 0 }, { headRot: 7, lidTilt: 6 }, { headRot: 13, lidTilt: 12 },
      { headRot: 13, lidTilt: 12 }, { headRot: 7, lidTilt: 6 }, { headRot: 0 },
    ].map(mk) },
    talk: { loop: true, frames: [
      { beak: 0 }, { beak: 0.6, headDy: 1 }, { beak: 0.2 }, { beak: 0.9, headDy: 1 }, { beak: 0.4 }, { beak: 0.1 },
    ].map(mk) },
    // 低頭寫字:循環部分固定在書寫姿勢(進出場靠 nod/tilt 類片段銜接)
    write: { loop: true, frames: range(8, (i) => {
      const w = [0, 1, 0, -1, 0, 1, 0, -1][i], v = [0, 1, 1, 0, -1, -1, 0, 1][i];
      return { prop: 'side', headRot: -42 + 2 * w, headDy: 6, headDx: 0, bodyTilt: -2,
        wing: 128 + 7 * v, beak: i % 2 ? 0.1 : 0, lid: 0.45 };
    }) },
    // 驚嚇:壓扁蓄力 → 彈起離地 46 → 最高點拉長張翅 → 落地壓扁 → 回站姿
    shock: { loop: false, frames: [
      {},
      { squash: 0.8, headDy: 7, wing: 10, tail: 6, expr: 'surprised' },
      { hop: 26, squash: 1.04, xs: 0.94, wing: -55, wlen: 1.1, tail: -12, legL: 14, legR: -14, headDy: -2, expr: 'surprised' },
      { hop: 46, squash: 1, xs: 0.9, wing: -85, wlen: 1.3, tail: -18, legL: 20, legR: -20, headDy: 0, headRot: 3, expr: 'surprised' },
      { hop: 30, squash: 1.02, xs: 0.96, wing: -65, wlen: 1.2, tail: -10, legL: 14, legR: -14, expr: 'surprised' },
      { hop: 8, wing: -30, wlen: 1.1, legL: 6, legR: -6, expr: 'surprised' },
      { squash: 0.8, wing: 8, headDy: 7, expr: 'surprised' },
      { squash: 0.96, expr: 'normal' },
    ].map(mk) },
    shrug: { loop: false, frames: [
      {},
      { wing: -35, wlen: 1.1, headDy: 3, squash: 0.98 },
      { wing: -88, wlen: 1.25, headDy: 9, headRot: -5, squash: 0.94, expr: 'speechless' },
      { wing: -92, wlen: 1.25, headDy: 9, headRot: -5, squash: 0.94, expr: 'speechless' },
      { wing: -92, wlen: 1.25, headDy: 9, headRot: -5, squash: 0.94, expr: 'doubt' },
      { wing: -55, wlen: 1.1, headDy: 5, squash: 0.97, expr: 'doubt' },
      { wing: -15, headDy: 1 },
      {},
    ].map(mk) },
    // 指向:翅膀朝嘴的方向伸出身體外(wing≈186 水平略朝上,wlen 拉長)
    point: { loop: false, frames: [
      { wing: 0 }, { wing: 60, wlen: 1.1 }, { wing: 125, wlen: 1.25, headRot: 3 }, { wing: 165, wlen: 1.4, headRot: 4 },
      { wing: 186, wlen: 1.5, headRot: 4, expr: 'look' }, { wing: 182, wlen: 1.5, headRot: 4, expr: 'look' },
    ].map(mk) },
    // 指回站姿
    point_out: { loop: false, frames: [
      { wing: 150, wlen: 1.35, headRot: 3, expr: 'look' }, { wing: 70, wlen: 1.1, headRot: 1 }, {},
    ].map(mk) },
    // 寫字回站姿(第 1 格起收起板子)
    write_out: { loop: false, frames: [
      { prop: 'side', headRot: -26, headDy: 4, bodyTilt: -1, wing: 85, lid: 0.45 },
      { headRot: -10, headDy: 2, wing: 35 },
      {},
    ].map(mk) },
    walk: { loop: true, frames: range(8, (i) => {
      const ph = 2 * Math.PI * i / 8, sn = Math.sin(ph);
      return { legL: Math.round(26 * sn), legR: Math.round(-26 * sn),
        hop: Math.round(2 * Math.abs(Math.cos(ph))) , headDx: Math.round(-4 * Math.cos(ph)) + 4,
        wing: Math.round(-4 * sn), tail: Math.round(3 * sn) };
    }) },
    hop: { loop: false, frames: [
      {},
      { squash: 0.92, headDy: 3 },
      { hop: 18, squash: 1.03, legL: 14, legR: -14, wing: -20, tail: -6 },
      { hop: 26, squash: 1.03, legL: 18, legR: -18, wing: -28, tail: -8 },
      { hop: 8, legL: 8, legR: -8, wing: -10 },
      { squash: 0.96, headDy: 2 },
    ].map(mk) },
    // 左右翻面:最後一格是鏡像站姿(flip=1)
    turn: { loop: false, frames: [
      {}, { xs: 0.55, headRot: 4 }, { xs: 0.55, headRot: 4, flip: 1 }, { flip: 1 },
    ].map(mk) },
  };

  function frameCount(clip) {
    const c = typeof clip === 'string' ? CLIPS[clip] : clip;
    return c.frames.length;
  }

  function poseAt(clip, t) {
    const c = typeof clip === 'string' ? CLIPS[clip] : clip;
    const n = c.frames.length;
    let i = Math.floor(Math.max(0, t) * POSE_FPS + 1e-9);
    i = c.loop ? i % n : Math.min(i, n - 1);
    return c.frames[i];
  }

  const API = { COLORS, POSE_FPS, PAP_DEFS, BASE, EXPR, CLIPS, pigeonSVG, poseAt, frameCount, mk };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.Pigeon = API;
})();
