/* pearl 場景 p_same_a(句6–7)醋酸澱粉 vs 醋。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–1。淺底,鴿子站左下(面向右)。
 * 句6:兩欄板「醋酸澱粉 vs 醋」(左,澱粉袋 + 醋瓶)、「老婆餅 vs 老婆」(右,「大概」處彈入:老婆餅 + 問號人形紙片),鴿子攤手。
 * 句7:兩欄板整組退場;醋瓶特寫,瓶內小圓點(醋酸)每格換位置亂跑(種子 = 句索引*1000 + 格數*8 + 序號);「醋酸」字牌;
 *      舌頭由右滑入碰到瓶身,同格彈出「酸!」(此為最後一個元素,保證在段落結束前 1.5 秒出現)。鴿子指向瓶子。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const DEF_TXT = ['醋酸澱粉的名字裡面有醋酸,可是它跟醋的關係,大概就像老婆餅跟老婆。', '醋會酸,是因為裡面的醋酸泡在水裡可以自由活動,你的舌頭碰得到它。'];
  const DEF = [{ start: 0.05, end: 5.15 }, { start: 5.27, end: 10.37 }];
  const U = 1.43, PU = 1.42;
  const FOOT = { x: 270, y: 820 };
  const TC = { x: 1260, y: 470, w: 1100, h: 620, fs: 56 };
  const BAG = { x: 864, y: 570, s: 1.5 }, VIN6 = { x: 1100, y: 575, s: 1.35 }, WIFE = { x: 1430, y: 570, s: 1.6 }, PERSON = { x: 1700, y: 580, s: 1.5 };
  const VIN = { x: 1150, y: 500, s: 2.5 }, LAB = { x: 850, y: 310, fs: 64 };
  const TONG = { y: 560, s: 2.0, xs: [1640, 1590, 1535, 1490, 1452] }, SOUR = { x: 1500, y: 330, fs: 120 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { idx: l.idx != null ? +l.idx : 6 + i, start: l.start != null && isFinite(l.start) ? +l.start : d.start,
        end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || DEF_TXT[i] };
    });
  }
  const at = (L, i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
  const atKw = (L, i, kw) => at(L, i, Math.max(0, L[i].text.indexOf(kw)) / L[i].text.length);
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };
  function prop(pal, name, args, o) {
    const e = PP.LIST[name], p = K.pop(o.q);
    if (p <= 0) return '';
    return K.paper(e.fn(pal, args), { x: o.x, y: o.y, rot: o.rot, scale: o.s, sx: p, sy: p, k: 'prop', id: o.id, wide: e.wide, enter: o.q < 2 });
  }
  // 問號人形紙片(單位繪製,中心附近)
  const personSVG = () => `<circle cx="0" cy="-74" r="34" fill="${K.INK}"/><polygon points="-46,-30 46,-30 62,96 -62,96" fill="${K.INK}"/>` +
    `<text x="0" y="34" font-family="GenSen" font-size="100" text-anchor="middle" dominant-baseline="central" fill="${K.YELLOW}" stroke="none">?</text>`;
  // 瓶內小圓點(醋瓶單位座標):上下兩個空區,每格換位置;觸碰後偏向右側
  function dotsSVG(seed, touched) {
    let c = '';
    for (let j = 0; j < 8; j++) {
      const h1 = K.hash(seed + j * 3 + 1), h2 = K.hash(seed + j * 3 + 2), h3 = K.hash(seed + j * 3 + 3), up = h1 < 0.5;
      let x = up ? -28 + 56 * h2 : -46 + 92 * h2;
      if (touched) x = 6 + 40 * h2;
      const y = up ? -36 + 20 * h3 : 78 + 24 * h3;
      c += `<circle cx="${f(x)}" cy="${f(y)}" r="7" fill="${K.YELLOW}" stroke="${K.INK}" stroke-width="2"/>`;
    }
    return c;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kEnd = K.frame(L[1].end);
    let s = '';

    // ---- 句6:兩欄板 ----
    const kV = Math.max(atKw(L, 0, '醋的關係'), F[0] + 6);
    const kR = Math.max(kV + 3, Math.min(atKw(L, 0, '大概'), F[1] - 21));
    if (k < F[1] + 2) {
      let g = Ch.twoCol({ x: TC.x, y: TC.y, w: TC.w, h: TC.h, fs: TC.fs, pal, u: U, id: 'tc',
        left: { title: '醋酸澱粉 vs 醋', k: k - F[0] }, right: { title: '老婆餅 vs 老婆', k: k - kR } });
      g += prop(pal, 'bag', {}, { x: BAG.x, y: BAG.y, s: BAG.s, q: k - (F[0] + 2), id: 'bag' });
      g += prop(pal, 'vinegar', {}, { x: VIN6.x, y: VIN6.y, s: VIN6.s, q: k - kV, id: 'vin6' });
      g += prop(pal, 'wifecake', {}, { x: WIFE.x, y: WIFE.y, s: WIFE.s, q: k - (kR + 2), id: 'wife' });
      const qp = k - (kR + 6), pp = K.pop(qp);
      if (pp > 0) g += K.paper(personSVG(), { x: PERSON.x, y: PERSON.y, scale: PERSON.s, sx: pp, sy: pp, k: 'prop', id: 'person', enter: qp < 2 });
      s += shr(g, TC.x, TC.y, k, F[1]);
    }

    // ---- 句7:醋瓶特寫 + 亂跑的小圓點 + 舌頭碰到 → 酸! ----
    if (k >= F[1] + 2) {
      const q = k - (F[1] + 2), p = K.pop(q);
      const kTouch = Math.max(F[1] + 8, Math.min(atKw(L, 1, '舌頭') + 4, kEnd - 15)), touched = k >= kTouch;
      s += prop(pal, 'vinegar', {}, { x: VIN.x, y: VIN.y, s: VIN.s, q, id: 'vin' });
      if (p > 0 && q >= 2) {
        s += K.paper(dotsSVG(L[1].idx * 1000 + k * 8, touched), { x: VIN.x, y: VIN.y, scale: VIN.s, sx: p, sy: p, k: 'prop', id: 'dots', enter: q < 4 });
      }
      const kLab = Math.max(atKw(L, 1, '醋酸'), F[1] + 6);
      s += Ch.sheet(Ch.plate('醋酸', LAB.fs, { fill: K.YELLOW }).svg, { x: LAB.x, y: LAB.y, rot: -3, u: U, k: k - kLab, kind: 'sheet', id: 'lab', wide: true });
      const i = k - (kTouch - 4);
      if (i >= 0) {
        const x = TONG.xs[Math.min(i, TONG.xs.length - 1)];
        s += prop(pal, 'tongue', { ang: 90 }, { x, y: TONG.y, s: TONG.s, q: i, id: 'tongue' });
      }
      if (touched) {
        s += Ch.sheet(Ch.plate('酸!', SOUR.fs, { fill: K.YELLOW }).svg, { x: SOUR.x, y: SOUR.y, rot: 4, u: U, k: k - kTouch, kind: 'sheet', id: 'sour', wide: true });
      }
    }

    // ---- 鴿子(左下,面向右) ----
    let pz;
    if (k < kR + 8) pz = K.expr(K.clip('idle', k), 'normal');
    else if (k < F[1]) pz = K.clip('shrug', k - (kR + 8));
    else pz = K.clip('point', k - F[1]);
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pz, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_same_a', dur: 10.4, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
