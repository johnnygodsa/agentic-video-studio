/* turtle 場景 §15 t_loop(句 53–56,17.6 秒)繞一大圈與分解傳言。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句53:髒淨灘袋(加「太髒」)→ 回收符號打紅叉 → 箭頭通往焚化爐。
 * 句54:上面一幕退場(焚化爐留下);飯店走直線(直達)、海邊走大彎(繞一大圈),兩條路線匯到同一座焚化爐。
 * 句55:全部退場;手機加虛線對話泡「四五百年?」,下方一支牙刷。
 * 句56:牙刷退場;鴿子低頭翻記錄板、收板、聳肩;泡泡下方多一個虛線泡「出處?」(不做印章)。
 * 字牌一律用 Charts(px 紙片,描邊一致);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 300, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.05, end: 5.03 }, { start: 5.15, end: 9.42 }, { start: 9.54, end: 13.44 }, { start: 13.56, end: 17.57 }];
  const INC = { x: 1640, y: 440, box: 500 };       // 焚化爐(句53–54 共用)
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const RED = 'hsl(6 75% 55%)', GREEN = 'hsl(130 50% 40%)';
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
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
  // 髒淨灘袋:素面袋加褐色污漬(單位繪製,供 Ch.icon 嵌入)
  function dirtyBag(pal) {
    let s = PT.LIST.bag.fn(pal, { col: 'hsl(38 22% 60%)' });
    [[-30, 20, 22], [24, -10, 16], [-6, 62, 18], [34, 52, 14], [-36, -34, 12]].forEach((c) => {
      s += `<circle cx="${c[0]}" cy="${c[1]}" r="${c[2]}" fill="hsl(28 42% 28%)" stroke="none"/>`;
    });
    return { svg: s, w: PT.LIST.bag.w, h: PT.LIST.bag.h };
  }
  // 回收符號:紙白圓底加三條順時針綠色彎箭頭(px,中心在原點)
  function recycleSvg(r) {
    let s = `<circle cx="0" cy="0" r="${f(r + 42)}" fill="${K.PAPER}"/>`;
    for (let i = 0; i < 3; i++) {
      const a0 = (i * 120 - 78) * Math.PI / 180, a1 = a0 + 82 * Math.PI / 180;
      const p0 = [r * Math.cos(a0), r * Math.sin(a0)], p1 = [r * Math.cos(a1), r * Math.sin(a1)];
      const t = [-Math.sin(a1), Math.cos(a1)], n = [Math.cos(a1), Math.sin(a1)];
      s += `<path d="M ${f(p0[0])} ${f(p0[1])} A ${r} ${r} 0 0 1 ${f(p1[0])} ${f(p1[1])}" fill="none" stroke="${GREEN}" stroke-width="32" stroke-linecap="butt"/>` +
        `<polygon points="${f(p1[0] + n[0] * 36)},${f(p1[1] + n[1] * 36)} ${f(p1[0] - n[0] * 36)},${f(p1[1] - n[1] * 36)} ${f(p1[0] + t[0] * 52)},${f(p1[1] + t[1] * 52)}" fill="${GREEN}" stroke="none"/>`;
    }
    return s;
  }
  const crossSvg = (len, th) => [45, -45].map((a) => `<g transform="rotate(${a})">${R(-len / 2, -th / 2, len, th, RED)}</g>`).join('');
  // 海邊小景:沙灘加海水(單位,中心在原點,約 220×160)
  function waveSvg() {
    const pts = [[-110, 20]];
    for (let i = 0; i <= 8; i++) pts.push([-110 + i * 27.5, 20 + (i % 2 ? -14 : 0)]);
    pts.push([110, 80], [-110, 80]);
    return `<polygon points="-110,-20 110,-20 110,80 -110,80" fill="hsl(40 60% 76%)"/>` +
      `<polygon points="${pts.map((p) => `${f(p[0])},${f(p[1])}`).join(' ')}" fill="hsl(205 65% 55%)" stroke="none"/>` +
      `<circle cx="-60" cy="-10" r="12" fill="hsl(38 70% 60%)" stroke="none"/>`;
  }

  // ---------- 句53 ----------
  function s53(pal, ks) {
    let s = Ch.sheet(Ch.icon(dirtyBag(pal), 0, 0, 340), { x: 700, y: 400, u: U, k: ks.bag, kind: 'prop', id: 'bag' });
    const pl = Ch.plate('太髒', 72, { fill: K.YELLOW });
    s += Ch.sheet(pl.svg, { x: 700, y: 650, rot: -2, u: U, k: ks.tag, kind: 'tag', id: 'dirty', wide: true });
    s += Ch.sheet(recycleSvg(100), { x: 1130, y: 330, u: U, k: ks.sign, kind: 'sign', id: 'rec' });
    s += Ch.sheet(crossSvg(340, 36), { x: 1130, y: 330, u: U, k: ks.x, kind: 'cross', id: 'x' });
    return s + arrow(850, 640, 1440, 640, { th: 44, hw: 112, hl: 80, fill: pal.main, k: ks.arrow, id: 'go' });
  }
  const incin = (pal, kk) => iconSheet(pal, 'incinerator', { tall: 0.55, restaurant: false }, INC.x, INC.y, INC.box, { k: kk, id: 'burner' });

  // ---------- 句54 ----------
  function s54(pal, q) {
    const kA = (n) => q.a - n, kB = (n) => q.b - n;
    let s = iconSheet(pal, 'hotel', { lit: 0.8 }, 740, 215, 230, { k: q.a, id: 'hotel' });
    s += Ch.route({ pal, u: U, fs: 56, r: 28, th: 18, id: 'ra', stops: [
      { x: 940, y: 230, label: '直達', labelSide: 'up', k: kA(3) }, { x: 1420, y: 400, k: kA(8) }] });
    s += Ch.sheet(Ch.icon({ svg: waveSvg(), w: 220, h: 160 }, 0, 0, 230), { x: 760, y: 680, u: U, k: q.b, kind: 'prop', id: 'shore' });
    s += Ch.route({ pal, u: U, fs: 56, r: 28, th: 18, id: 'rb', stops: [
      { x: 940, y: 700, k: kB(3) }, { x: 1010, y: 800, k: kB(6) }, { x: 1230, y: 800, k: kB(9) }, { x: 1300, y: 650, k: kB(12) }, { x: 1420, y: 560, k: kB(15) }] });
    const pl = Ch.plate('繞一大圈', 64, { fill: K.YELLOW });
    return s + Ch.sheet(pl.svg, { x: 1050, y: 560, rot: -2, u: U, k: q.tag, kind: 'tag', id: 'loop', wide: true });
  }

  // ---------- 句55–56 ----------
  const BUB = { x: 1130, y: 330, fs: 140 }, PHONE = { x: 1660, y: 490, box: 380 }, BRUSH = { x: 1130, y: 730, box: 560 };
  function s55(pal, ks) {
    let s = iconSheet(pal, 'phone', {}, PHONE.x, PHONE.y, PHONE.box, { k: ks.phone, id: 'phone' });
    s += Ch.bubble('四五百年?', { x: BUB.x, y: BUB.y, fs: BUB.fs, dashed: true, tail: 'br', u: U, k: ks.bub, id: 'rumor' });
    return s;
  }
  const brushSheet = (pal, kk) => iconSheet(pal, 'toothbrush', {}, BRUSH.x, BRUSH.y, BRUSH.box, { k: kk, rot: -4, id: 'brush' });

  function pigeonPose(k, st) {
    let pose;
    if (k >= st.w0 && k < st.w1) pose = K.expr(K.clip('write', k - st.w0), 'look');
    else if (k >= st.w1 && k < st.w1 + 3) pose = K.expr(K.clip('write_out', k - st.w1), 'look');
    else if (k >= st.shrug && k < st.shrug + K.P.CLIPS.shrug.frames.length) pose = K.expr(K.clip('shrug', k - st.shrug), 'doubt');
    else if (k >= st.tilt && k < st.tilt + 6 && k < st.w0) pose = K.expr(K.clip('tilt', k - st.tilt), 'doubt');
    else pose = K.expr(K.clip('idle', k), k >= st.shrug ? 'doubt' : 'look');
    return Object.assign({}, pose, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const sec = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;
    const st = { tilt: at(L[2], 0.3), w0: F[3] + 2, w1: at(L[3], 0.45), shrug: at(L[3], 0.55) };
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, st), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (sec === 0) {                               // 句53
      const q = k - F[0];
      s += s53(pal, { bag: q, tag: k - at(L[0], 0.12), sign: k - at(L[0], 0.3), x: k - at(L[0], 0.45), arrow: k - at(L[0], 0.68) });
      s += incin(pal, k - at(L[0], 0.55));
    } else if (sec === 1) {                        // 句54
      const out = shrink(k, F[1], 1050, 440);
      if (out) s += out(s53(pal, { bag: 99, tag: 99, sign: 99, x: 99, arrow: 99 }));
      s += incin(pal, 99);
      s += s54(pal, { a: k - F[1], b: k - at(L[1], 0.4), tag: k - at(L[1], 0.8) });
    } else {                                       // 句55–56
      if (sec === 2) {
        const out = shrink(k, F[2], 1250, 450);
        if (out) s += out(incin(pal, 99) + s54(pal, { a: 99, b: 99, tag: 99 }));
        s += s55(pal, { bub: k - F[2], phone: k - F[2] });
        s += brushSheet(pal, k - at(L[2], 0.45));
      } else {
        s += s55(pal, { bub: 99, phone: 99 });
        const out = shrink(k, F[3], BRUSH.x, BRUSH.y);
        if (out) s += out(brushSheet(pal, 99));
        s += Ch.bubble('出處?', { x: 1000, y: 650, fs: 120, dashed: true, tail: null, u: U, k: k - at(L[3], 0.62), id: 'source' });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_loop', dur: 17.6, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
