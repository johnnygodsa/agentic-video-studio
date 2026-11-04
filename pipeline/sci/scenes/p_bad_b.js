/* pearl 場景 p_bad_b(句 30–34)沒人能證實,只驗原料。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。淺底,鴿子站左下(全程 idle)。
 * 句30:大問號牌 + 字牌「沒人能證實」。
 * 句31:退場;虛線泡「沒照流程?煮不夠久?」+ 來源牌「三立引總部錄音」。
 * 句32:退場;左:放大鏡罩著原料袋,「檢驗報告」處旁邊打大勾;右:「門市煮好」處大鍋(在放大鏡外面)+ 牌「這鍋沒人驗」。
 * 句33:對比留到句首 0.8 秒才退場;勾選清單兩項 q:當天幾點煮的(句首 0.8 秒出現) / 放了多久(關鍵詞處出現)。
 * 句34:清單退場;字牌「新北市衛生局：將稽查」+ 小牌「結果未出」(「稽查」處)。
 * 退場一律 2 格縮小。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const DEF_TXT = ['不過這一杯是不是真的壞掉,現在沒有人能證實,我也沒辦法幫它下結論。',
    '總部那邊有另一種說法,有報導引了總部人員的錄音,說門市沒有照標準流程,或者煮的時間不夠久,都有可能會酸。',
    '總部說已經把那一批原料送回去做品質測試,也跟供應商要了檢驗報告,問題是,如果毛病出在門市煮好以後放太久,只驗原料是驗不出來的。',
    '我自己是覺得啦,要讓人相信,除了原料的報告以外,那家店當天幾點煮的珍珠、放了多久,也應該一起講清楚吧。', '有報導說新北市衛生局會派人去稽查,目前還沒有結果。'];
  const DEF = (() => { let t = 0.08; return DEF_TXT.map((s) => { const d = { start: t, end: t + s.length / 6.5 }; t = d.end + 0.12; return d; }); })();
  const U = 1.43, PU = 1.45;                           // 紙片倍率、鴿子倍率
  const FOOT = { x: 270, y: 805 };
  const QM = { x: 880, y: 400, size: 300 }, QP = { x: 1390, y: 400, fs: 110 };
  const BUB = { x: 1130, y: 400, fs: 80 }, BSRC = { x: 1537, y: 545 };
  const LENS = { gx: 800, gy: 400, s: 2.8 };           // 放大鏡玻璃中心與倍率(玻璃中心在單位 (-21,-21))
  const BAGS = { x: 800, y: 400, s: 1.35 };
  const TICK = { x: 1160, y: 330, b: 150 };
  const POT = { x: 1540, y: 470, s: 1.3 }, PLAB = { x: 1540, y: 750, fs: 70 };
  const CL = { x: 800, y: 300, w: 720, rowH: 120, gap: 30, fs: 72 };
  const NEWS = { x: 1100, y: 380, fs: 80 }, RES = { x: 1100, y: 560, fs: 56 };
  const EXP = ['think', 'doubt', 'doubt', 'normal', 'normal'];
  const CHECK = [[-0.5, 0.02], [-0.3, -0.18], [-0.1, 0.08], [0.38, -0.52], [0.58, -0.34], [-0.08, 0.48]];
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
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心);k0 為 null = 不退場
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const prop = (n, o, x, y, sc, kk, id) => { const p = K.pop(kk); return p <= 0 ? '' : K.paper(PP.LIST[n].fn(pal, o), { x, y, scale: sc, sx: p, sy: p, k: 'prop', id, wide: PP.LIST[n].wide, enter: kk < 2 }); };
    let s = '';

    // 句30:大問號牌 + 「沒人能證實」;句31 起退場
    if (k >= F[0] && k < F[1] + 2) {
      const kk = k - F[0], p = K.pop(kk), pl = Ch.plate('沒人能證實', QP.fs, { fill: K.YELLOW, ink: K.INK });
      let g = K.tile('?', { x: QM.x, y: QM.y, size: QM.size, rot: -4, u: U, fill: K.INK, ink: K.YELLOW, sx: p, sy: p, id: 'bigq', enter: kk < 2 });
      g += Ch.sheet(pl.svg, { x: QP.x, y: QP.y, rot: 2, u: U, k: kk - 2, kind: 'big', id: 'nobody', wide: true });
      s += shr(g, 1130, 400, k, F[1]);
    }
    // 句31:虛線泡 + 來源牌;句32 起退場
    if (k >= F[1] + 2 && k < F[2] + 2) {
      const kk = k - (F[1] + 2);
      let g = Ch.bubble('沒照流程?煮不夠久?', { x: BUB.x, y: BUB.y, fs: BUB.fs, dashed: true, tail: 'bl', u: U, k: kk, id: 'maybe' });
      g += Ch.srcTag('三立引總部錄音', { pal, x: BSRC.x, y: BSRC.y, anchor: 'right', u: U, k: kk - 3, id: 'src' });
      s += shr(g, 1130, 450, k, F[2]);
    }

    // 句32:放大鏡罩原料袋(打勾)vs 放大鏡外的大鍋;留到句33 清單第一項(句首 0.8 秒)出現才退場
    const kL1 = F[3] + 8;
    if (k >= F[2] + 2 && k < kL1) {
      const k0 = F[2] + 2, kTick = Math.max(atKw(L, 2, '檢驗報告'), k0 + 6), kPot = Math.max(atKw(L, 2, '門市煮好'), kTick + 4);
      let g = prop('lens', {}, LENS.gx + 21 * LENS.s, LENS.gy + 21 * LENS.s, LENS.s, k - (k0 + 3), 'lens');
      g += prop('bag', {}, BAGS.x, BAGS.y, BAGS.s, k - k0, 'bag');
      const kt = k - kTick, b = TICK.b * 1.2;
      g += Ch.sheet(`<polygon points="${CHECK.map((p) => `${f(p[0] * b)},${f(p[1] * b)}`).join(' ')}" fill="${pal.text}"/>`,
        { x: TICK.x, y: TICK.y, u: U, k: kt, kind: 'checkMark', id: 'tick' });
      g += prop('pot', {}, POT.x, POT.y, POT.s, k - kPot, 'pot');
      const pl = Ch.plate('這鍋沒人驗', PLAB.fs, { fill: K.INK, ink: K.YELLOW });
      g += Ch.sheet(pl.svg, { x: PLAB.x, y: PLAB.y, rot: 2, u: U, k: k - kPot - 2, kind: 'potLabel', id: 'unchecked', wide: true });
      s += shr(g, 1100, 460, k, kL1 - 2);
    }

    // 句33:勾選清單兩項「?」;句34 起退場
    if (k >= kL1 && k < F[4] + 2) {
      const k1 = kL1, k2 = Math.max(atKw(L, 3, '放了多久'), k1 + 3);
      const g = Ch.checklist({ pal, x: CL.x, y: CL.y, w: CL.w, rowH: CL.rowH, gap: CL.gap, fs: CL.fs, u: U, id: 'cl', items: [
        { label: '當天幾點煮的', state: 'q', k: k - k1, kState: k - k1 - 2 }, { label: '放了多久', state: 'q', k: k - k2, kState: k - k2 - 2 }] });
      s += shr(g, CL.x + CL.w / 2, CL.y + CL.rowH + CL.gap / 2, k, F[4]);
    }

    // 句34:新北市衛生局字牌 + 結果未出
    if (k >= F[4] + 2) {
      const kn = k - (F[4] + 2), kr = Math.max(atKw(L, 4, '稽查'), F[4] + 8);
      const pn = Ch.plate('新北市衛生局：將稽查', NEWS.fs, { fill: K.YELLOW, ink: K.INK }), pr = Ch.plate('結果未出', RES.fs, { fill: K.INK, ink: K.YELLOW });
      s += Ch.sheet(pn.svg, { x: NEWS.x, y: NEWS.y, rot: -2, u: U, k: kn, kind: 'news', id: 'news', wide: true });
      s += Ch.sheet(pr.svg, { x: RES.x, y: RES.y, rot: 2, u: U, k: k - kr, kind: 'result', id: 'result', wide: true });
    }

    // 鴿子站左下(全程 idle)
    const ln = Math.max(0, L.findIndex((l, i) => k < F[i + 1] || i === L.length - 1));
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 400, h: 26, u: U, pal });
    s += K.pigeon(Object.assign({}, K.expr(K.clip('idle', k), EXP[ln]), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_bad_b', dur: 32, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
