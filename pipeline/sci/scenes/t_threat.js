/* turtle 場景 §19 t_threat(句 71–73,13.7 秒)五項威脅。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句71:海龜在中間(寬約 920px),周圍六個「?」依序彈入。
 * 句72:標題「美國國家海洋暨大氣總署 NOAA」;五張項目牌(圖加標籤,排成兩列 3+2)依句長平均分配逐張彈入:
 *      漁船誤捕、棲地消失、獵捕與撿蛋、海洋垃圾纏繞、船隻撞擊;第五張後停約 1.9 秒。
 * 句73:標題退場,上方一條手機對話泡(漁網、延繩釣、快艇);三個圖示依序分四格飛到清單對應的項目(第 4、1、5 項)並打勾。
 * 鴿子在左下當觀察者(每句最多一個反應);內容全在 x 540 以右。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 800 };                 // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0.05, end: 2.34 }, { start: 2.46, end: 9.7 }, { start: 9.82, end: 13.65 }];
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const TURTLE = { x: 1180, y: 500, box: 940 };
  const QS = [[625, 250, 170, -6], [960, 180, 160, 5], [1400, 180, 160, -4], [1725, 260, 170, 6], [1725, 650, 170, -5], [625, 650, 170, 4]];
  const CW = 412, CH = 250;
  const CPOS = [[746, 410], [1188, 410], [1630, 410], [746, 685], [1188, 685]];   // 五張牌的中心
  const ITEMS = ['漁船誤捕', '棲地消失', '獵捕與撿蛋', '海洋垃圾纏繞', '船隻撞擊'];
  const BUB = { x: 1268, y: 170, w: 1120, h: 170 };
  const PHONE = { x: 610, y: 170 };
  const GREEN = 'hsl(130 55% 40%)';
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
  // icon 縮到高度約 h(寬的圖就放寬 box)
  const boxFor = (i, h) => h * Math.max(i.w, i.h) / i.h;

  // ---------- 圖解(場景內自畫,單位繪製、中心在原點) ----------
  const C = PT.C;
  const P = (pts, fill, ex) => `<polygon points="${pts.map((p) => f(p[0]) + ',' + f(p[1])).join(' ')}" fill="${fill}"${ex || ''}/>`;
  const R = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' '}/>`;
  const NS = ' stroke="none"';
  const rope = (d, w, col) => `<path d="${d}" fill="none" stroke="${K.PAPER}" stroke-width="${f(w + 7)}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${d}" fill="none" stroke="${col}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  // 漁船(吊著網):約 210×160
  function fishBoat() {
    let s = R(-58, -86, 10, 104, C.greyD) + rope('M -50 -78 L 84 -16', 6, C.greyD) +
      P([[70, -8], [104, -8], [98, 42], [76, 42]], 'hsl(190 32% 30%)') + R(70, -14, 34, 8, C.orange) +
      R(-32, -36, 66, 52, C.white) + R(-18, -24, 28, 22, C.sky, NS) + R(-38, -46, 78, 12, C.red) +
      P([[-100, 15], [104, 15], [78, 68], [-80, 68]], 'hsl(210 55% 32%)') + R(-100, 15, 204, 12, C.red, NS);
    return { svg: s, w: 216, h: 164 };
  }
  // 被剷平的沙灘:推土機加平坦的沙:約 224×124
  function dozer() {
    let s = R(-52, 6, 114, 34, 'hsl(200 10% 30%)', ' rx="16"') + R(-34, -22, 92, 34, K.YELLOW) + R(-6, -62, 52, 44, K.YELLOW) + R(2, -54, 34, 26, C.sky, NS) +
      R(34, -76, 8, 18, C.greyD, NS) + P([[-62, -26], [-84, -26], [-92, 34], [-66, 36]], C.grey) +
      P([[-112, 40], [-100, 20], [-90, 38]], 'hsl(38 55% 70%)') + P([[-112, 62], [-112, 38], [112, 38], [112, 62]], 'hsl(38 55% 70%)');
    [-28, 8, 44].forEach((x) => { s += `<circle cx="${x}" cy="24" r="8" fill="${C.greyL}" stroke="none"/>`; });
    return { svg: s, w: 232, h: 140 };
  }
  // 蛋(三顆在籃子裡):約 200×140
  function eggs() {
    const egg = (x, y) => `<path d="M ${x} ${y - 44} C ${x + 36} ${y - 44} ${x + 34} ${y + 36} ${x} ${y + 36} C ${x - 34} ${y + 36} ${x - 36} ${y - 44} ${x} ${y - 44} Z" fill="hsl(45 60% 92%)"/>`;
    let s = egg(-46, -16) + egg(48, -16) + egg(0, -30) + P([[-100, 0], [100, 0], [78, 66], [-78, 66]], C.brown);
    [-60, -20, 20, 60].forEach((x) => { s += R(x - 4, 6, 8, 58, C.brownD, NS); });
    return { svg: s + R(-100, -6, 200, 12, C.brownD), w: 208, h: 148 };
  }
  // 快艇(burst:撞擊星):約 190×120
  function speedBoat(burst) {
    let s = rope('M -98 44 q 10 -9 20 0 t 20 0', 7, C.blue) + rope('M -98 62 q 10 -9 20 0 t 20 0', 7, C.blue) +
      P([[-62, -4], [-14, -12], [4, -44], [-44, -34]], C.sky) +
      P([[-72, 4], [92, -16], [70, 44], [-60, 48]], C.white) + P([[-68, 28], [86, 12], [76, 28], [-62, 40]], C.red, NS);
    if (burst) {
      const pts = [];
      for (let i = 0; i < 16; i++) { const a = i * Math.PI / 8, r = i % 2 ? 24 : 46; pts.push([112 + Math.cos(a) * r, -26 + Math.sin(a) * r]); }
      s += P(pts, K.YELLOW);
    }
    return { svg: s, w: burst ? 250 : 200, h: 130 };
  }
  const checkSvg = () => `<g transform="scale(0.42)"><polygon points="-120,6 -76,-38 -34,6 84,-110 128,-66 -34,92" fill="${GREEN}"/></g>`;

  const cardIcon = (pal, i) => [fishBoat(), dozer(), eggs(), ic(pal, 'net', {}), speedBoat(true)][i];
  function cardSvg(pal, i) {
    const icn = cardIcon(pal, i);
    return R(-CW / 2, -CH / 2, CW, CH, K.PAPER, ' stroke-linejoin="miter"') + R(-CW / 2, -CH / 2, CW, 18, pal.main, NS) +
      Ch.icon(icn, 0, -28, boxFor(icn, 140)) + txt(ITEMS[i], 0, 88, 60, K.INK);
  }
  // 手機對話泡裡三個項目:{icn, h(圖高), ox(圖中心相對泡中心), lab, lx}
  const BCELLS = (pal) => [{ icn: ic(pal, 'net', {}), h: 120, ox: -400, lab: '漁網', lx: -250, to: 3 },
    { icn: ic(pal, 'hook', {}), h: 140, ox: -120, lab: '延繩釣', lx: 30, to: 0 }, { icn: speedBoat(false), h: 120, ox: 235, lab: '快艇', lx: 435, to: 4 }];
  const tickPos = (i) => [CPOS[i][0] + 140, CPOS[i][1] - 75];

  function pigeonPose(k, evs) {
    for (const e of evs) {
      const n = K.P.CLIPS[e.clip].frames.length;
      if (k >= e.k0 && k < e.k0 + n) return Object.assign({}, K.expr(K.clip(e.clip, k - e.k0), e.expr), { flip: 1 });
    }
    return Object.assign({}, K.expr(K.clip('idle', k), 'look'), { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const kQ = QS.map((_, i) => (i === 0 ? F[0] : at(L[0], 0.05 + i * 0.11)));
    const kC = [F[1]].concat([0.2, 0.38, 0.56, 0.74].map((p) => at(L[1], p)));
    const kBand = F[2], kFly = [0.12, 0.32, 0.52].map((p) => at(L[2], p));
    const evs = [{ k0: F[0] + 3, clip: 'tilt', expr: 'think' }, { k0: kFly[2] + 4, clip: 'nod', expr: 'look' }];

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, evs), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // ----- 句71:海龜與「?」 -----
    s += layer(k, F[0], F[1], 1180, 450, (ke) => {
      let c = sh(Ch.icon(ic(pal, 'turtle', {}), 0, 0, TURTLE.box), TURTLE.x, TURTLE.y, ke - F[0], 'prop', 'turtle');
      QS.forEach((q, i) => { c += tl('?', q[0], q[1], q[2], ke - kQ[i], 'q' + i, { fill: K.INK, ink: K.YELLOW, rot: q[3] }); });
      return c;
    });

    // ----- 句72–73:標題、五張項目牌 -----
    s += layer(k, F[1], F[2], 1180, 160, (ke) => sh(Ch.plate('美國國家海洋暨大氣總署 NOAA', 72, { fill: K.YELLOW }).svg, 1180, 160, ke - F[1], 'tag', 'title', { rot: -1, wide: true }));
    if (k >= F[1]) {
      ITEMS.forEach((_, i) => {
        s += sh(cardSvg(pal, i), CPOS[i][0], CPOS[i][1], k - kC[i], 'card', 'item' + i);
      });
    }

    // ----- 句73:手機對話泡、三個圖示飛到清單上打勾 -----
    if (k >= kBand) {
      const kk = k - kBand, cells = BCELLS(pal);
      s += sh(Ch.icon(ic(pal, 'phone', {}), 0, 0, 170), PHONE.x, PHONE.y, kk, 'prop', 'phone');
      let b = `<rect x="${-BUB.w / 2}" y="${-BUB.h / 2}" width="${BUB.w}" height="${BUB.h}" rx="44" fill="${K.PAPER}"/>` +
        `<rect x="${-BUB.w / 2 + 12}" y="${-BUB.h / 2 + 12}" width="${BUB.w - 24}" height="${BUB.h - 24}" rx="34" fill="none" stroke="${K.INK}" stroke-width="8"/>`;
      cells.forEach((c) => { b += Ch.icon(c.icn, c.ox, 0, boxFor(c.icn, c.h)) + txt(c.lab, c.lx, 0, 56, K.INK); });
      s += sh(b, BUB.x, BUB.y, kk - 1, 'bubble', 'bubble', { wide: true });
      cells.forEach((c, j) => {
        const kf = k - kFly[j], tp = tickPos(c.to), x0 = BUB.x + c.ox, y0 = BUB.y;
        if (kf >= 0 && kf < 4) {                    // 飛行四格:不補間,每格走四分之一
          const r = (kf + 1) / 4, x = x0 + (tp[0] - x0) * r, y = y0 + (tp[1] - y0) * r;
          s += sh(Ch.icon(c.icn, 0, 0, boxFor(c.icn, 100)), x, y, 3, 'prop', 'fly' + j, { enter: true });
        } else if (kf >= 4) {
          s += sh(checkSvg(), tp[0], tp[1], kf - 4, 'check', 'tick' + j);
        }
      });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_threat', dur: 13.7, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
