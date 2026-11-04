/* turtle 場景 §6 t_brush_a(句 17–19,固定鏡頭)主角登場。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句17:主色圓形襯底上立著一支牙刷,名牌「主角」;鴿子指;右上「?」記號彈入(之後留到下一場 t_brush_b 才退場)。
 * 句18:舊物退場;刷毛特寫(尼龍白毛),年份牌「1938」、標籤「尼龍」。
 * 句19:年份牌、標籤退場;刷毛換成粗黑硬毛(整片重新彈入);野豬彈入,脖子缺一撮毛,旁邊虛線泡「…」表示無言;鴿子聳肩。
 * 事件都在該句 start 後依句長比例出現;同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), Ch = W.Charts || require('../charts.js'), PT = W.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 330, y: 800 };
  const DEF = [{ start: 0, end: 2.6 }, { start: 2.7, end: 5.6 }, { start: 5.7, end: 8.6 }];
  const DISC = { x: 1060, y: 440, r: 330 }, BRUSH = { sc: 2.6 }, NAME = { x: 1640, y: 450, fs: 110 };
  const CLOSE = { x: 1180, w: 900, yNylon: 550, yHog: 365 }, YEAR = { x: 900, y: 197 }, NYLON = { x: 1450, y: 197, fs: 100 };
  const BOAR = { x: 1010, y: 672, sc: 1.5 }, DOTS = { x: 1400, y: 610, fs: 96 };
  const OUT = [0.7, 0.35];                          // 退場縮小兩格
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const prop = (pal, n, o, p) => K.paper(PT.LIST[n].fn(pal, o), Object.assign({ k: 'prop', id: n, wide: PT.LIST[n].wide, scale: U }, p));
  function shrink(k, kOut, cx, cy) {
    if (kOut == null || k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  const face = (p) => Object.assign({}, p, { flip: 1 });

  // 刷毛特寫(px,中心在原點,寬 CLOSE.w):base 為主色刷頭,上面一排毛束。mode 'nylon' = 白色圓頭細毛;'hog' = 粗黑硬毛(長短不齊、鋸齒頂)
  function bristles(pal, mode) {
    const w = CLOSE.w;
    let c = `<rect x="${-w / 2}" y="45" width="${w}" height="100" rx="38" fill="${pal.main}" stroke-linejoin="round"/>`;
    if (mode === 'nylon') {
      const n = 6, tw = 118, gap = (w - 60 - n * tw) / (n - 1);
      for (let i = 0; i < n; i++) {
        const x0 = -w / 2 + 30 + i * (tw + gap);
        c += `<rect x="${f(x0)}" y="-230" width="${tw}" height="280" rx="${tw / 2 - 6}" fill="${K.PAPER}" stroke-linejoin="round"/>`;
        for (let j = 1; j < 6; j++) c += `<line x1="${f(x0 + j * tw / 6)}" y1="-205" x2="${f(x0 + j * tw / 6)}" y2="42" stroke="hsl(200 14% 82%)" stroke-width="5" stroke-linecap="round"/>`;
      }
    } else {
      const n = 4, tw = 170, gap = (w - 70 - n * tw) / (n - 1), tops = [-250, -200, -265, -215];
      for (let i = 0; i < n; i++) {
        const x0 = -w / 2 + 35 + i * (tw + gap), y0 = tops[i];
        let pts = `${f(x0)},50 ${f(x0)},${y0 + 30}`;
        for (let j = 0; j < 6; j++) pts += ` ${f(x0 + (j + 0.5) * tw / 6)},${y0 + (j % 2 ? 16 : -8) + (j * 9) % 14} ${f(x0 + (j + 1) * tw / 6)},${y0 + 26 + (j * 7) % 11}`;
        pts += ` ${f(x0 + tw)},50`;
        c += `<polygon points="${pts}" fill="hsl(25 25% 13%)" stroke-linejoin="round"/>`;
        for (let j = 1; j < 5; j++) c += `<line x1="${f(x0 + j * tw / 5)}" y1="${y0 + 55}" x2="${f(x0 + j * tw / 5 + (j % 2 ? 4 : -4))}" y2="42" stroke="hsl(25 18% 30%)" stroke-width="6" stroke-linecap="round"/>`;
      }
    }
    return c;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const e17 = { disc: F[0], brush: F[0] + 1, name: at(L[0], 0.35), point: at(L[0], 0.35), mark: at(L[0], 0.62) };
    const e18 = { close: F[1], year: at(L[1], 0.25), nylon: at(L[1], 0.5) };
    const e19 = { swap: F[2], boar: at(L[2], 0.3), dots: at(L[2], 0.42), shrug: at(L[2], 0.6) };
    const sec = k < F[1] ? 0 : k < F[2] ? 1 : 2;

    // 鴿子姿勢
    let pose;
    if (sec === 0) pose = k >= e17.point ? K.expr(K.clip('point', k - e17.point), 'look') : K.expr(K.clip('idle', k), 'look');
    else if (sec === 1) pose = k < F[1] + 3 ? K.expr(K.clip('point_out', k - F[1]), 'look') : K.expr(K.clip('idle', k), 'look');
    else pose = k >= e19.shrug ? K.clip('shrug', k - e19.shrug) : K.expr(K.clip('idle', k), 'look');
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(face(pose), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // ----- 句17:圓形襯底 + 立著的牙刷 + 名牌(句18 開頭退場) -----
    const o17 = shrink(k, F[1], DISC.x, DISC.y);
    if (sec === 0 || (sec === 1 && o17 && k < F[1] + 2)) {
      if (o17) {
        let g = '';
        const kd = k - e17.disc;
        if (kd >= 0) {
          const p = K.pop(kd);
          g += K.paper(`<circle cx="0" cy="0" r="${f(DISC.r / U)}" fill="${pal.main}"/>`, { x: DISC.x, y: DISC.y, scale: U, sx: p, sy: p, k: 'disc', id: 'disc', enter: kd < 2 });
        }
        const kb = k - e17.brush;
        if (kb >= 0) {
          const p = K.pop(kb);
          g += K.paper(PT.LIST.toothbrush.fn(pal, {}), { x: DISC.x, y: DISC.y, rot: -84, scale: BRUSH.sc, sx: p, sy: p, k: 'prop', id: 'brush', wide: true, enter: kb < 2 });
        }
        const kn = k - e17.name;
        if (kn >= 0) {
          const q = Ch.plate('主角', NAME.fs, { fill: K.YELLOW });
          g += Ch.sheet(q.svg, { x: NAME.x, y: NAME.y, u: U, k: kn, kind: 'name', id: 'name', rot: 3, wide: true });
        }
        s += o17(g);
      }
    }

    // ----- 句18–19:刷毛特寫(句19 開頭整片重新彈入換成硬毛) -----
    if (sec >= 1) {
      const kc = sec === 1 ? k - e18.close : k - e19.swap;
      s += Ch.sheet(bristles(pal, sec === 1 ? 'nylon' : 'hog'), { x: CLOSE.x, y: sec === 1 ? CLOSE.yNylon : CLOSE.yHog, u: U, k: kc, kind: 'close', id: sec === 1 ? 'nylon' : 'hog' });
    }
    // 年份牌與標籤(句19 開頭各自在原位縮掉退場)
    if (sec >= 1) {
      const oy = shrink(k, F[2], YEAR.x, YEAR.y), on = shrink(k, F[2], NYLON.x, NYLON.y);
      const ky = k - e18.year, kn = k - e18.nylon;
      if (oy && ky >= 0) s += oy(Ch.bigNum({ x: YEAR.x, y: YEAR.y, num: '1938', fs: 150, u: U, k: ky, rot: -2, id: 'year' }));
      if (on && kn >= 0) s += on(Ch.sheet(Ch.plate('尼龍', NYLON.fs, { fill: pal.main, ink: pal.onMain }).svg, { x: NYLON.x, y: NYLON.y, u: U, k: kn, kind: 'label', id: 'nylon', rot: 2, wide: true }));
    }

    // ----- 句19:野豬 + 無言泡 -----
    if (sec === 2) {
      const kb = k - e19.boar;
      if (kb >= 0) {
        const p = K.pop(kb);
        s += K.paper(PT.LIST.boar.fn(pal, { bald: true }), { x: BOAR.x, y: BOAR.y, scale: BOAR.sc, sx: p, sy: p, k: 'prop', id: 'boar', enter: kb < 2 });
      }
      const kd = k - e19.dots;
      if (kd >= 0) s += Ch.bubble('…', { x: DOTS.x, y: DOTS.y, fs: DOTS.fs, dashed: true, tail: 'bl', u: U, k: kd, id: 'dots', rot: 2 });
    }

    // ----- 右上「?」記號:句17 後段彈入,留到本場結束 -----
    s += Ch.triviaMark({ u: U, k: k - e17.mark });
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_brush_a', dur: 8.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
