/* pearl 場景 p_same_b(句8–11)醋酸澱粉怎麼做、上限、合法性。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 淺底,鴿子站右下(面向左)。film.json 此場景另有 tail 1.0 秒。
 * 句8:小工廠(左)與澱粉鏈(中)彈入;「接到」詞位起小方塊零件一顆一顆接上鏈子(每 2 格多一顆,共 4 顆)。
 * 句9:四顆零件各蓋上小鎖頭(每 2 格一個);「酸」字牌在「醋酸」詞位出現,「嚐不出」詞位被紅叉打掉。
 * 句10:上一句整組退場;大數字「2.5%」說明牌「最多只能接這麼多」(「最多」詞位)、來源牌「歐盟規格」(「歐盟」詞位)。
 * 句11:上一句退場;勾選清單兩項:台灣合法添加物(「合法」詞位打勾)、國際評估沒訂上限(「沒有幫它訂」詞位打勾,最後元素)。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const DEF_TXT = ['醋酸澱粉是工廠拿澱粉去跟醋酸類的原料反應,把一小段東西接到澱粉那條長長的鏈子上。', '接上去以後它就被綁死在澱粉上面,已經不算是醋酸了,所以嚐不出酸味。',
    '而且能接的量很少,歐盟的規格寫最多只能佔 2.5% 這麼一點。', '它在台灣是合法的食品添加物,國際上的專家評估過,也沒有幫它訂每天能吃多少的上限。'];
  const DEF = [{ start: 0.05, end: 6.25 }, { start: 6.37, end: 11.47 }, { start: 11.59, end: 15.89 }, { start: 16.01, end: 22.21 }];
  const U = 1.43, PU = 1.42;
  const FOOT = { x: 1560, y: 820 };
  const FAC = { x: 260, y: 640, s: 1.1 };
  const CH = { x: 880, y0: 320, s: 3.0, step: 50, order: [1, 4, 6, 2], tagY: 26.5, dy: 19.5 };   // y0 = 鏈上珠子中心線;tagY = 零件中心相對鏈中心(單位)
  const LOCK = { s: 0.93 }, SOUR = { x: 800, y: 700, size: 160 };
  const BIG = { x: 900, y: 360, fs: 220 }, SRC = { x: 900, y: 690 };
  const CL = { x: 500, y: 290, w: 780, rowH: 110, gap: 30, fs: 64 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || DEF_TXT[i] };
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
  // 紅叉(兩條交叉的紅條,中心在原點,單位繪製)
  const crossSVG = () => ['rotate(45)', 'rotate(-45)'].map((r) => `<rect transform="${r}" x="-120" y="-14" width="240" height="28" fill="hsl(4 72% 48%)" stroke-linejoin="miter"/>`).join('');

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kEnd = K.frame(L[3].end);
    let s = '';

    // ---- 句8–9:工廠、澱粉鏈、零件、小鎖頭、酸字牌 ----
    if (k < F[2] + 2) {
      let g = '';
      g += prop(pal, 'factory', {}, { x: FAC.x, y: FAC.y, s: FAC.s, q: k - F[0], id: 'fac' });
      const kT0 = Math.max(atKw(L, 0, '接到'), F[0] + 6), nt = k < kT0 ? 0 : Math.min(4, 1 + Math.floor((k - kT0) / 2));
      const cy = CH.y0 + (nt > 0 ? CH.dy * CH.s : 0);
      g += prop(pal, 'chain', { tags: nt, bend: 0 }, { x: CH.x, y: cy, s: CH.s, q: k - (F[0] + 2), id: 'chain' });
      // 句9:每個零件蓋上小鎖頭
      CH.order.forEach((idx, j) => {
        const lx = CH.x + (idx - 3.5) * CH.step * CH.s, ly = cy + CH.tagY * CH.s;
        g += prop(pal, 'lock', {}, { x: lx, y: ly, s: LOCK.s, q: k - (F[1] + 2 * j), id: 'lock' + j });
      });
      // 酸字牌 + 紅叉
      const kS = Math.max(atKw(L, 1, '醋酸'), F[1] + 8), qs = k - kS, ps = K.pop(qs);
      if (ps > 0) g += K.tile('酸', { x: SOUR.x, y: SOUR.y, size: SOUR.size, rot: -4, u: U, sx: ps, sy: ps, id: 'sour', enter: qs < 2 });
      const kX = Math.max(atKw(L, 1, '嚐不出'), kS + 3), qx = k - kX, px = K.pop(qx);
      if (px > 0) g += K.paper(crossSVG(), { x: SOUR.x, y: SOUR.y, scale: 0.8, sx: px, sy: px, k: 'prop', id: 'cross', enter: qx < 2 });
      s += shr(g, 760, 550, k, F[2]);
    }
    // ---- 句10:2.5% ----
    if (k >= F[2] + 2 && k < F[3] + 2) {
      const q = k - (F[2] + 2), kN = Math.max(atKw(L, 2, '最多'), F[2] + 5), kS = Math.max(atKw(L, 2, '歐盟'), F[2] + 7);
      let g = Ch.bigNum({ x: BIG.x, y: BIG.y, num: '2.5%', fs: BIG.fs, rot: -2, u: U, k: q, kNote: k - kN, note: '最多只能接這麼多', id: 'big' });
      g += Ch.srcTag('歐盟規格', { pal, x: SRC.x, y: SRC.y, anchor: 'center', u: U, k: k - kS, id: 'src' });
      s += shr(g, BIG.x, 520, k, F[3]);
    }
    // ---- 句11:兩項打勾 ----
    if (k >= F[3] + 2) {
      const k0 = F[3] + 2, k1 = Math.max(atKw(L, 3, '國際'), k0 + 4);
      const c0 = Math.max(atKw(L, 3, '合法'), k0 + 3), c1 = Math.min(Math.max(atKw(L, 3, '沒有幫它訂'), k1 + 3), kEnd - 15);
      s += Ch.checklist({ x: CL.x, y: CL.y, w: CL.w, rowH: CL.rowH, gap: CL.gap, fs: CL.fs, pal, u: U, id: 'cl', items: [
        { label: '台灣合法添加物', state: 'check', k: k - k0, kState: k - c0 }, { label: '國際評估沒訂上限', state: 'check', k: k - k1, kState: k - c1 }] });
    }

    // ---- 鴿子(右下,面向左) ----
    let pz;
    if (k < F[1]) pz = K.expr(K.clip('idle', k), 'look');
    else if (k < F[2]) pz = K.expr(K.clip('tilt', k - F[1]), 'normal');
    else if (k < F[3]) pz = K.clip('point', k - F[2]);
    else pz = K.expr(K.clip('idle', k), 'smug');
    s += K.ground({ x: FOOT.x - 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pz, { flip: 0 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_same_b', dur: 22.3, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
