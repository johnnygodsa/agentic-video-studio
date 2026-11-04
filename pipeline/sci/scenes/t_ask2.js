/* turtle 場景 §30 t_ask2(句 121–124,13.9 秒)兩個問題。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 固定鏡頭,鴿子在左下(面向右)。右側大字牌與選項牌用原尺寸直接出現(不過衝),牌內的圖與字再逐一彈入。
 * 句121:大字牌「兩個問題」,下方「問題一」「問題二」兩個小牌依序彈入;鴿子說話。
 * 句122:左上「問題一」;兩張大選項牌「環保」(葉子)與「省成本」(硬幣)。
 * 句123:左上換「問題二」;三張選項牌「吸管」「漁網」「海邊的燈」。
 * 句124:留言框(我選…因為…)出現,鴿子指向它。
 * 同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 800 };                 // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0.07, end: 2.17 }, { start: 2.29, end: 7.03 }, { start: 7.15, end: 11.71 }, { start: 11.83, end: 13.88 }];
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const TAG = { x: 310, y: 230, fs: 110 };         // 左上「問題一/二」
  const CARDS_Y = 460, CARDS_H = 420;
  const GREEN = 'hsl(130 45% 45%)', GREEN_D = 'hsl(130 50% 30%)';
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const now = (k) => (k < 0 ? -1 : 3);             // 大紙片直接以原尺寸出現
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const poly = (pts, fill) => `<polygon points="${pts.map((p) => f(p[0]) + ',' + f(p[1])).join(' ')}" fill="${fill}"/>`;
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const text = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="${anchor || 'middle'}"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  function shrink(k, kOut, cx, cy) {
    if (k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }

  // 葉子(單位,約 150×240;自己畫)
  function leafIc() {
    let s = R(-5, 85, 10, 52, 'hsl(28 45% 36%)') + `<path d="M 0 -105 C 76 -58 78 48 0 108 C -78 48 -76 -58 0 -105 Z" fill="${GREEN}"/>` + R(-5, -92, 10, 196, GREEN_D);
    [-40, 0, 40].forEach((y) => {
      s += poly([[0, y], [36, y - 32], [36, y - 23], [0, y + 9]], GREEN_D) + poly([[0, y], [-36, y - 32], [-36, y - 23], [0, y + 9]], GREEN_D);
    });
    return { svg: s, w: 156, h: 240 };
  }

  // 一張選項牌:icon 在上、字在下。o: {x, w, label, fs, icn(ic 物件), box, k(牌), kIcon}
  function option(o) {
    let s = Ch.sheet(`<rect x="${-o.w / 2}" y="${-CARDS_H / 2}" width="${o.w}" height="${CARDS_H}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-o.w / 2}" y="${-CARDS_H / 2}" width="${o.w}" height="22" fill="${o.pal.main}" stroke="none"/>`,
    { x: o.x, y: CARDS_Y, u: U, k: now(o.k), kind: 'option', id: o.label, wide: o.w / CARDS_H > 3 });
    s += Ch.sheet(Ch.icon(o.icn, 0, 0, o.box), { x: o.x, y: CARDS_Y - 75, u: U, k: o.kIcon, kind: 'prop', id: o.label + 'I' });
    return s + Ch.sheet(text(o.label, 0, 0, o.fs, K.INK), { x: o.x, y: CARDS_Y + 135, u: U, k: o.kIcon + 1, kind: 'label', id: o.label + 'T', wide: true });
  }
  const labelTag = (pal, str, k) => Ch.sheet(Ch.plate(str, TAG.fs, { fill: K.YELLOW }).svg, { x: TAG.x, y: TAG.y, rot: -2, u: U, k, kind: 'tag', id: str, wide: true });

  // 留言框(自己畫):主色標題條「留言」、頭像、「我選____」「因為____」
  const BOX = { x: 1280, y: 440, w: 1080, h: 440 };
  function commentBox(pal, kBox, kA, kB) {
    const a = BOX.w / 2, b = BOX.h / 2;
    let s = Ch.sheet(R(-a, -b, BOX.w, BOX.h, K.PAPER) + R(-a, -b, BOX.w, 112, pal.main) + text('留言', 0, -b + 56, 80, pal.onMain) +
      `<circle cx="${-a + 120}" cy="30" r="72" fill="${pal.pad}" stroke="none"/><circle cx="${-a + 120}" cy="8" r="26" fill="${PT.C.grey}" stroke="none"/>` +
      `<path d="M ${-a + 62} 78 C ${-a + 70} 40 ${-a + 170} 40 ${-a + 178} 78 C ${-a + 150} 100 ${-a + 90} 100 ${-a + 62} 78 Z" fill="${PT.C.grey}" stroke="none"/>`,
    { x: BOX.x, y: BOX.y, u: U, k: now(kBox), kind: 'comment', id: 'box', wide: true });
    const line = (str, y, k, id) => Ch.sheet(text(str, -270, y, 76, K.INK, 'start') + R(-100, y + 44, 400, 10, K.INK),
      { x: BOX.x, y: BOX.y, u: U, k, kind: 'line', id, wide: true });
    return s + line('我選', -12, kA, 'pick') + line('因為', 92, kB, 'why');
  }

  function pigeonPose(k, F, st) {
    let p;
    if (k < F[1]) p = K.expr(K.clip('talk', k), 'look');
    else if (k >= st.t1 && k < st.t1 + 6) p = K.expr(K.clip('tilt', k - st.t1), 'think');
    else if (k >= st.t2 && k < st.t2 + 6 && k < F[3]) p = K.expr(K.clip('tilt', k - st.t2), 'think');
    else if (k >= st.pt) p = K.expr(K.clip('point', k - st.pt), 'look');
    else p = K.expr(K.clip('idle', k), 'look');
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const st = { t1: at(L[1], 0.6), t2: at(L[2], 0.7), pt: at(L[3], 0.1) };
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, F, st), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (k < F[1]) {                                // 句121
      s += Ch.sheet(Ch.plate('兩個問題', 170, { fill: K.YELLOW }).svg, { x: 1130, y: 300, rot: -1.5, u: U, k: now(k - F[0]), kind: 'tag', id: 'two', wide: true });
      s += Ch.sheet(Ch.plate('問題一', 120, {}).svg, { x: 1000, y: 640, rot: -2, u: U, k: k - at(L[0], 0.4), kind: 'tag', id: 'q1', wide: true });
      s += Ch.sheet(Ch.plate('問題二', 120, {}).svg, { x: 1540, y: 640, rot: 2, u: U, k: k - at(L[0], 0.65), kind: 'tag', id: 'q2', wide: true });
    } else {
      const o1 = shrink(k, F[1], 1130, 470);       // 句121 的牌在句122 開頭退場
      if (o1) s += o1(Ch.sheet(Ch.plate('兩個問題', 170, { fill: K.YELLOW }).svg, { x: 1130, y: 300, rot: -1.5, u: U, k: 99, kind: 'tag', id: 'two', wide: true }) +
        Ch.sheet(Ch.plate('問題一', 120, {}).svg, { x: 1000, y: 640, rot: -2, u: U, k: 99, kind: 'tag', id: 'q1', wide: true }) +
        Ch.sheet(Ch.plate('問題二', 120, {}).svg, { x: 1540, y: 640, rot: 2, u: U, k: 99, kind: 'tag', id: 'q2', wide: true }));
    }

    if (k >= F[1] && k < F[2]) {                   // 句122:兩張大選項牌
      s += labelTag(pal, '問題一', k - F[1]);
      s += option({ pal, x: 890, w: 600, label: '環保', fs: 100, icn: leafIc(), box: 230, k: k - at(L[1], 0.08), kIcon: k - at(L[1], 0.08) });
      s += option({ pal, x: 1530, w: 600, label: '省成本', fs: 100, icn: ic(pal, 'coin', {}), box: 230, k: k - at(L[1], 0.5), kIcon: k - at(L[1], 0.5) });
    } else if (k >= F[2]) {
      const o2 = shrink(k, F[2], 1210, CARDS_Y);   // 句122 的牌在句123 開頭退場
      if (o2) {
        s += o2(labelTag(pal, '問題一', 99) +
          option({ pal, x: 890, w: 600, label: '環保', fs: 100, icn: leafIc(), box: 230, k: 99, kIcon: 99 }) +
          option({ pal, x: 1530, w: 600, label: '省成本', fs: 100, icn: ic(pal, 'coin', {}), box: 230, k: 99, kIcon: 99 }));
      }
    }

    if (k >= F[2] && k < F[3]) {                   // 句123:三張選項牌
      s += labelTag(pal, '問題二', k - F[2]);
      const kk = [at(L[2], 0.02), at(L[2], 0.3), at(L[2], 0.6)];
      s += option({ pal, x: 790, w: 400, label: '吸管', fs: 80, icn: ic(pal, 'straw', {}), box: 230, k: k - kk[0], kIcon: k - kk[0] });
      s += option({ pal, x: 1210, w: 400, label: '漁網', fs: 80, icn: ic(pal, 'net', {}), box: 230, k: k - kk[1], kIcon: k - kk[1] });
      s += option({ pal, x: 1630, w: 400, label: '海邊的燈', fs: 80, icn: ic(pal, 'bulb', { rays: true }), box: 230, k: k - kk[2], kIcon: k - kk[2] });
    } else if (k >= F[3]) {
      const o3 = shrink(k, F[3], 1210, CARDS_Y);   // 句123 的牌在句124 開頭退場
      if (o3) {
        s += o3(labelTag(pal, '問題二', 99) +
          option({ pal, x: 790, w: 400, label: '吸管', fs: 80, icn: ic(pal, 'straw', {}), box: 230, k: 99, kIcon: 99 }) +
          option({ pal, x: 1210, w: 400, label: '漁網', fs: 80, icn: ic(pal, 'net', {}), box: 230, k: 99, kIcon: 99 }) +
          option({ pal, x: 1630, w: 400, label: '海邊的燈', fs: 80, icn: ic(pal, 'bulb', { rays: true }), box: 230, k: 99, kIcon: 99 }));
      }
      s += commentBox(pal, k - F[3], k - at(L[3], 0.12), k - at(L[3], 0.3));
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_ask2', dur: 13.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
