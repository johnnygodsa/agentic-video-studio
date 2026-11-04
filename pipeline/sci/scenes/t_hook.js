/* turtle 場景 §1 t_hook(句 1–4)開場鉤子,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句1:告示(海龜加字)彈入;鴿子從左走入、停下、約 45% 處歪頭 doubt。
 * 句2:鴿子拿出記錄板;12% 牙刷彈入、38% 虛線箭頭、62% 箭頭上小「?」彈入。
 * 句3:句首虛線斷開;牙刷、告示各自退到兩側(依序,不同時);50% 處中間掉下墨底黃字「?」牌(壓扁回彈)。
 * 句4:夜空紙片(深色)蓋住牆面上半、鴿子 shock 後 surprised;15% 起「?」牌周圍 12 條光線每格亮 2 條。「?」牌留在原位。
 * 同時在動的非文字元素 ≤ 2 組(鴿子 + 一個物件)。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PT = (typeof window !== 'undefined' && window.PropsTurtle) || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 330, y: 800 };                  // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0, end: 5.445 }, { start: 5.565, end: 10.135 }, { start: 10.255, end: 14.69 }, { start: 14.81, end: 17.95 }];
  const WALK_N = 14, STEP = 36;                     // 走進來:14 格,每格 36px
  const NOTICE = { x: 1540, y: 450, w: 520, h: 660, endX: 1570 };
  const BRUSH = { x: 700, y: 290, u: 2.5, endX: 440, endY: 250 };
  const ARR = { a: [1010, 310], b: [1290, 395] };    // 虛線箭頭起迄
  const Q = { x: 960, y: 470, size: 260, u: 2 };    // 墨底黃字「?」牌最後位置
  const RETREAT = [0, 0.4, 0.75, 1];
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
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  // 告示:紙白底、頂端主色帶加紅圖釘、海龜、兩行字
  function noticeSheet(pal, x, y, k) {
    const w = NOTICE.w, h = NOTICE.h;
    const c = `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="80" fill="${pal.main}" stroke="none"/>` +
      `<circle cx="0" cy="${-h / 2 + 40}" r="18" fill="${PT.C.red}"/>` +
      Ch.icon(ic(pal, 'turtle', {}), 0, -70, 420) + txt('一次性備品', 0, 160, 76, K.INK) + txt('會傷害海龜', 0, 250, 76, K.INK);
    return Ch.sheet(c, { x, y, u: U, k, kind: 'notice', id: 'notice' });
  }

  // 虛線箭頭:segs 為沿線的比例區間;head = 末端箭頭是否畫出
  function arrowSheet(segs, head, k) {
    const [ax, ay] = ARR.a, [bx, by] = ARR.b, cx = (ax + bx) / 2, cy = (ay + by) / 2;
    const p0 = [ax - cx, ay - cy], dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len;
    const pt = (t) => [p0[0] + dx * t, p0[1] + dy * t];
    let c = '';
    segs.forEach(([s0, s1]) => {
      const a = pt(s0), b = pt(s1);
      [[K.PAPER, 30], [K.INK, 18]].forEach(([col, w]) => {
        c += `<line x1="${f(a[0])}" y1="${f(a[1])}" x2="${f(b[0])}" y2="${f(b[1])}" stroke="${col}" stroke-width="${w}" stroke-dasharray="36 20" stroke-linecap="butt"/>`;
      });
    });
    if (head) {
      const e = pt(1), nx = -uy, ny = ux, bk = [e[0] - ux * 70, e[1] - uy * 70];
      c += `<polygon points="${f(e[0] + ux * 10)},${f(e[1] + uy * 10)} ${f(bk[0] + nx * 44)},${f(bk[1] + ny * 44)} ${f(bk[0] - nx * 44)},${f(bk[1] - ny * 44)}" fill="${K.INK}" stroke-linejoin="round"/>`;
    }
    return Ch.sheet(c, { x: cx, y: cy, u: U, k, kind: 'arrow', id: 'arrow', wide: true });
  }

  function brush(pal, x, y, k) {
    const p = K.pop(k);
    if (p <= 0) return '';
    const e = PT.LIST.toothbrush;
    return K.paper(e.fn(pal, {}), { x, y, rot: -8, scale: BRUSH.u, sx: p, sy: p, k: 'prop', id: 'brush', enter: k < 2, wide: e.wide });
  }

  function sky(k) {
    let c = '<rect x="-868" y="-334" width="1736" height="668" fill="hsl(170 45% 14%)" stroke-linejoin="miter"/>';
    for (let i = 0; i < 46; i++) {
      const x = -840 + K.hash(i * 3.1 + 1) * 1680, y = -320 + K.hash(i * 7.7 + 2) * 640, r = 2.5 + K.hash(i * 5.3 + 3) * 4;
      c += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return Ch.sheet(c, { x: 960, y: 426, u: U, k, kind: 'sky', id: 'sky' });
  }

  function halo(n) {
    if (n <= 0) return '';
    let c = '';
    for (let i = 0; i < Math.min(12, n); i++) {
      c += `<g transform="rotate(${i * 30})"><rect x="-14" y="-240" width="28" height="64" fill="${K.YELLOW}"/></g>`;
    }
    return Ch.sheet(c, { x: Q.x, y: Q.y, u: U, kind: 'halo', id: 'halo', wide: true });
  }

  function pigeonPose(k, F, kTilt, kArr) {
    let p, dx = 0, enter = false;
    if (k < kArr) { p = K.clip('walk', k - F[0]); dx = (kArr - k) * STEP; enter = true; }
    else if (k < kTilt) p = K.clip('idle', k);
    else if (k < kTilt + 6) p = K.expr(K.clip('tilt', k - kTilt), 'doubt');
    else if (k < F[1]) p = K.expr(K.clip('idle', k), 'doubt');
    else if (k < F[1] + 3) p = K.clip('write_out', 2 - (k - F[1]));             // 拿出記錄板
    else if (k < F[2]) p = K.clip('write', k - F[1] - 3);
    else if (k < F[2] + 3) p = K.clip('write_out', k - F[2]);                   // 收起記錄板
    else if (k < F[3]) p = K.clip('idle', k);
    else if (k < F[3] + 8) p = K.clip('shock', k - F[3]);
    else p = K.expr(K.clip('idle', k), 'surprised');
    return { pose: Object.assign({}, p, { flip: 1 }), dx, enter };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kTilt = F[0] + Math.max(WALK_N + 8, at(L, 0, 0.45) - F[0]), kArr = F[0] + WALK_N;
    const kBrush = at(L, 1, 0.12), kArrow = at(L, 1, 0.38), kQs = at(L, 1, 0.62);
    const kBreak = F[2], kBrushGo = kBreak + 3, kNoticeGo = kBreak + 7, kDrop = at(L, 2, 0.5);
    const kHalo = at(L, 3, 0.15);
    const night = k >= F[3];

    // 牆面下方:地板(底色以外的一塊,不是紙片)
    let s = `<rect x="0" y="800" width="1920" height="280" fill="${pal.pad}"/><rect x="0" y="790" width="1920" height="12" fill="hsl(${pal.h} 45% 62%)"/>`;

    if (!night) {
      const kn = k - F[0];
      const go = RETREAT[Math.max(0, Math.min(k - kNoticeGo + 1, 3))];
      s += noticeSheet(pal, NOTICE.x + (NOTICE.endX - NOTICE.x) * go, NOTICE.y, kn);
      const gb = RETREAT[Math.max(0, Math.min(k - kBrushGo + 1, 3))];
      if (k >= kBrush) {
        s += brush(pal, BRUSH.x + (BRUSH.endX - BRUSH.x) * gb, BRUSH.y + (BRUSH.endY - BRUSH.y) * gb, k - kBrush);
      }
      if (k >= kArrow && k < kBreak) s += arrowSheet([[0, 1]], true, k - kArrow);
      else if (k >= kBreak && k < kBreak + 3) s += arrowSheet([[0, 0.3], [0.7, 1]], true);
      if (k >= kQs && k < kBreak) {
        const p = K.pop(k - kQs);
        s += K.tile('?', { x: (ARR.a[0] + ARR.b[0]) / 2, y: (ARR.a[1] + ARR.b[1]) / 2 - 8, size: 130, rot: -6, u: U, fill: K.INK, ink: K.YELLOW, sx: p, sy: p, id: 'q1', enter: k - kQs < 2 });
      }
    } else {
      s += sky(k - F[3]);
    }

    if (night && k >= kHalo) s += halo(2 * (k - kHalo + 1));
    if (k >= kDrop) {
      const d = K.drop(k - kDrop);
      s += K.tile('?', { x: Q.x, y: Q.y + d.dy * (Q.y + Q.size), size: Q.size, rot: -3, u: Q.u, fill: K.INK, ink: K.YELLOW, sx: d.sx, sy: d.sy, anchor: 'bottom', id: 'q', enter: d.enter });
    }

    const pg = pigeonPose(k, F, kTilt, kArr);
    if (k >= kArr) s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: FOOT.y, scale: U, id: 'main', enter: pg.enter });
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_hook', dur: 18, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
