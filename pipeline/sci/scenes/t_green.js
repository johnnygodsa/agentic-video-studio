/* turtle 場景 §16 t_green(句 57–60,13.2 秒)綠蠵龜的名字。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句57:記錄板翻頁、牙刷那頁打勾;板子退場,海龜從右邊游入(逐格位移、不補間)。
 * 句58:名牌「綠蠵龜」、箭頭指向褐色的殼;鴿子歪頭 doubt;右上「?」記號彈入。
 * 句59:箭頭退場;殼下方的綠色帶子逐格亮起(示意),標「脂肪」加箭頭;鴿子拿出放大鏡(場景內自畫)。
 * 句60:海龜換「無言」表情看鏡頭;放大鏡縮到鴿子背後;「?」記號彈出。
 * 海龜是畫面主體(寬 920px);字牌一律用 Charts(px 紙片,描邊一致);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 300, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.09, end: 1.71 }, { start: 1.82, end: 5.9 }, { start: 6.02, end: 9.45 }, { start: 9.56, end: 13.12 }];
  const TURTLE = { x: 1300, y: 450, box: 920 };    // 海龜(寬 920、高約 500)
  const BOARD = { x: 1180, y: 450, w: 1100, h: 600 };
  const MAG = { x: 660, y: 560 };                  // 放大鏡鏡面中心
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const BAND = ['hsl(110 55% 78%)', 'hsl(110 55% 60%)', 'hsl(110 55% 45%)'];   // 綠色帶子逐格亮起
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const R = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' stroke="none"'}/>`;
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const enter = (s) => s.replace('data-k=', 'data-enter="1" data-k=');      // 位移中的紙片標為進場中(不計邊距與出界)
  function shrink(k, kOut, cx, cy) {
    if (kOut == null || k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  function arrow(x0, y0, x1, y1, o) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, px = -uy, py = ux, th = o.th, hw = o.hw, hl = o.hl;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, bx = x1 - ux * hl, by = y1 - uy * hl;
    const pts = [[x0 + px * th / 2, y0 + py * th / 2], [bx + px * th / 2, by + py * th / 2], [bx + px * hw / 2, by + py * hw / 2], [x1, y1],
      [bx - px * hw / 2, by - py * hw / 2], [bx - px * th / 2, by - py * th / 2], [x0 - px * th / 2, y0 - py * th / 2]];
    return Ch.sheet(`<polygon points="${pts.map((p) => `${f(p[0] - cx)},${f(p[1] - cy)}`).join(' ')}" fill="${o.fill}"/>`,
      { x: cx, y: cy, u: U, k: o.k, kind: 'arrow', id: o.id, wide: Math.min(Math.abs(dx), Math.abs(dy)) < 0.33 * Math.max(Math.abs(dx), Math.abs(dy)) });
  }

  // 海龜加殼下綠色帶子(帶子在腹甲上緣、殼的正下方;band = 顏色或 null)。單位繪製,同 PT.turtle 的座標
  function turtleIc(pal, o) {
    let svg = PT.LIST.turtle.fn(pal, { expr: o.expr, headUp: o.headUp });
    if (o.band) {
      svg += `<g transform="translate(-10 -14)"><path d="M -116 23 L 30 23 L 30 46 L -20 49 C -72 49 -104 41 -116 23 Z" fill="${o.band}" stroke="none"/></g>`;
    }
    return { svg, w: PT.LIST.turtle.w, h: PT.LIST.turtle.h };
  }
  const turtleSheet = (pal, o, x, y, p) => Ch.sheet(Ch.icon(turtleIc(pal, o), 0, 0, TURTLE.box), Object.assign({ x, y, u: U, kind: 'prop', id: 'turtle', wide: PT.LIST.turtle.wide }, p));

  // 記錄板(夾板加兩頁):j<0 第一頁(只有橫線);j = 翻頁後第幾格(0–2 翻面、3 起第二頁:牙刷)
  function boardSvg(pal, j) {
    const b = BOARD, sx = j < 0 || j >= 3 ? 1 : [0.6, 0.12, 0.6][j], page2 = j >= 2;
    let c = R(-b.w / 2, -b.h / 2, b.w, b.h, K.YELLOW, ' stroke-linejoin="miter"') + R(-60, -b.h / 2 - 24, 120, 48, '#5B6578', ' stroke-linejoin="miter"');
    c += `<g transform="translate(0 22) scale(${sx} 1)">${R(-500, -250, 1000, 500, K.PAPER)}`;
    if (!page2) {
      for (let i = 0; i < 6; i++) c += R(-420, -190 + i * 74, i % 3 === 2 ? 520 : 840, 22, `hsl(${pal.h} 20% 78%)`);
    } else {
      c += `<g transform="rotate(-10 -150 20)">${Ch.icon(ic(pal, 'toothbrush', {}), -150, 20, 560)}</g>`;
    }
    return c + '</g>';
  }
  const checkSvg = () => `<polygon points="-120,6 -76,-38 -34,6 84,-110 128,-66 -34,92" fill="hsl(130 55% 40%)"/>`;
  // 放大鏡(px,鏡面中心在原點,握柄朝左下)
  function magnifierSvg() {
    return R(-140, -140, 280, 280, 'none', ' stroke="none"') +
      `<g transform="rotate(135)">${R(86, -20, 170, 40, 'hsl(26 48% 25%)')}</g>` +
      `<circle cx="0" cy="0" r="98" fill="${K.INK}"/><circle cx="0" cy="0" r="78" fill="hsl(195 70% 84%)" stroke="none"/>` +
      `<polygon points="-50,-30 -30,-52 -8,-52 -50,-12" fill="${K.PAPER}" stroke="none"/>`;
  }

  function pigeonPose(k, st) {
    let pose = null;
    for (const r of [{ k0: st.tilt, clip: 'tilt', expr: 'doubt' }, { k0: st.nod, clip: 'nod', expr: 'normal' }]) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (k >= r.k0 && k < r.k0 + n) { pose = K.expr(K.clip(r.clip, k - r.k0), r.expr); break; }
    }
    pose = pose || K.expr(K.clip('idle', k), k >= st.tilt && k < st.nod ? 'doubt' : 'look');
    return Object.assign({}, pose, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const sec = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;
    const e57 = { flip: at(L[0], 0.2), check: at(L[0], 0.4), out: at(L[0], 0.5), swim: at(L[0], 0.55) };
    const e58 = { tag: F[1], arrow: at(L[1], 0.3), tilt: at(L[1], 0.5), q: at(L[1], 0.7) };
    const e59 = { arrowOut: F[2], band: F[2] + 2, label: at(L[2], 0.25), arrow: at(L[2], 0.4), mag: at(L[2], 0.55) };
    const e60 = { hide: at(L[3], 0.4), qOut: at(L[3], 0.55) };
    const st = { tilt: e58.tilt, nod: e60.hide };

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    // 放大鏡(畫在鴿子之前,收到背後時被遮住)
    if (k >= e59.mag) {
      const km = k - e59.mag, mag = Ch.sheet(magnifierSvg(), { x: MAG.x, y: MAG.y, u: U, k: sec === 2 ? km : 99, kind: 'prop', id: 'lens' });
      const j = k - e60.hide;
      if (sec < 3 || j < 0) s += mag;
      else if (j < 3) s += `<g transform="translate(400 700) scale(${[0.8, 0.55, 0.3][j]}) translate(-400 -700)">${enter(mag)}</g>`;
    }
    s += K.pigeon(pigeonPose(k, st), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (sec === 0) {                               // 句57
      const out = shrink(k, e57.out, BOARD.x, BOARD.y);
      if (out) {
        s += out(Ch.sheet(boardSvg(pal, k < e57.flip ? -1 : k - e57.flip), { x: BOARD.x, y: BOARD.y, u: U, k: k - F[0], kind: 'board', id: 'pages', rot: -1 }) +
          Ch.sheet(checkSvg(), { x: BOARD.x + 330, y: BOARD.y + 20, u: U, k: k - e57.check, kind: 'check', id: 'tick' }));
      }
      const j = k - e57.swim;
      if (j >= 0) {                                // 海龜游入:逐格位移 170px,頭抬起,上下各 12px 起伏
        const x = TURTLE.x + 170 * Math.max(0, 6 - j), y = TURTLE.y + (j < 6 && j % 2 ? 12 : 0);
        const sh = turtleSheet(pal, { headUp: j < 6 }, x, y, {});
        s += j < 6 ? enter(sh) : sh;
      }
    } else {
      const band = sec === 1 ? null : BAND[Math.min(k - e59.band, 2)] || null;
      const sp = sec === 3 ? 'speechless' : 'normal';
      s += turtleSheet(pal, { expr: sp, band: sec === 1 || k < e59.band ? null : band }, TURTLE.x, TURTLE.y, {});
      if (sec === 1) {                             // 句58:名牌、箭頭、「?」
        const nm = Ch.plate('綠蠵龜', 100, { fill: K.YELLOW });
        s += Ch.sheet(nm.svg, { x: 700, y: 175, rot: -2, u: U, k: k - e58.tag, kind: 'tag', id: 'name', wide: true });
        s += arrow(880, 245, 1090, 330, { th: 40, hw: 100, hl: 70, fill: pal.main, k: k - e58.arrow, id: 'toShell' });
        s += Ch.triviaMark({ u: U, k: k - e58.q, id: 'q' });
      } else {
        const nm = Ch.plate('綠蠵龜', 100, { fill: K.YELLOW });
        s += Ch.sheet(nm.svg, { x: 700, y: 175, rot: -2, u: U, kind: 'tag', id: 'name', wide: true });
        if (sec === 2) {                           // 句59:舊箭頭退場、脂肪標籤與箭頭
          const out = shrink(k, e59.arrowOut, 985, 288);
          if (out) s += out(arrow(880, 245, 1090, 330, { th: 40, hw: 100, hl: 70, fill: pal.main, id: 'toShell' }));
          s += Ch.triviaMark({ u: U, id: 'q' });
        } else {
          s += Ch.triviaMark({ u: U, k: 99, kOut: k - e60.qOut, id: 'q' });
        }
        const fat = Ch.plate('脂肪', 80, { fill: 'hsl(110 55% 45%)', ink: K.PAPER });
        s += Ch.sheet(fat.svg, { x: 840, y: 745, rot: 2, u: U, k: sec === 2 ? k - e59.label : 99, kind: 'tag', id: 'fat', wide: true });
        s += arrow(950, 685, 1110, 545, { th: 40, hw: 100, hl: 70, fill: 'hsl(110 55% 45%)', k: sec === 2 ? k - e59.arrow : 99, id: 'toFat' });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_green', dur: 13.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
