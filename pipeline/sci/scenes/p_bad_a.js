/* pearl 場景 p_bad_a(句 25–29)那杯有沒有可能壞掉。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。淺底,鴿子站左下(全程 idle)。
 * 句25:虛線泡「那杯是壞掉了嗎」(呼應留言)。
 * 句26:泡退場,大字牌「有可能」。
 * 句27:牌退場;大鍋(無熱氣)在左,細菌自右側 3x3 格依索引逐隻冒出(每 step 格一隻,上限 9);句 62% 處第一隻變鼓肚並吐出「酸」字牌。
 * 句28:整組退場;溫度計(高約 40%)+ 來源牌「食藥署」+ 大數字「2 小時」+說明牌「室溫不要放超過」,全在句首出現、整句留著。
 * 句29:整組退場;原料袋改字「粉圓」+牌「煮好幾小時內用完」。
 * 退場一律 2 格縮小,新的一組在退場開始時即彈入(位置不重疊)。細菌位置全由索引算,無亂數。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const DEF_TXT = ['回到留言區問的那一題,這杯珍珠有沒有可能是壞掉的?', '有可能,這也是最普通的解釋。',
    '煮熟的澱粉泡在糖水裡,又放在室溫,對細菌來講根本就是吃到飽,牠們把糖吃掉以後會產生酸,東西餿掉會有酸味就是這樣來的。',
    '食藥署的說法是,煮好的食物放在 7 度到 60 度中間,細菌長得最快,所以在室溫不要放超過 2 小時。', '賣粉圓的廠商自己也會建議,煮好的珍珠幾個小時之內就要用完。'];
  const DEF = (() => { let t = 0.08; return DEF_TXT.map((s) => { const d = { start: t, end: t + s.length / 6.5 }; t = d.end + 0.12; return d; }); })();
  const U = 1.43, PU = 1.45;                           // 紙片倍率、鴿子倍率
  const FOOT = { x: 270, y: 805 };
  const POT = { x: 900, y: 470, s: 1.35 };
  const GERM = { s: 0.66, slots: [[1620, 470], [1460, 470], [1300, 470], [1460, 320], [1460, 620], [1620, 320], [1300, 320], [1620, 620], [1300, 620]] };
  const SOUR = { x: 1752, y: 470, size: 120 };
  const THERMO = { x: 780, y: 470, s: 1.76 };
  const BIG = { x: 1290, y: 380, fs: 170 }, SRC = { x: 1290, y: 665 };
  const BAG = { x: 880, y: 450, s: 1.8 }, PLATE = { x: 1450, y: 450, fs: 72 };
  const BUB = { x: 1130, y: 330, fs: 84 }, CARD = { x: 1130, y: 400, fs: 200 };
  const EXP = ['doubt', 'normal', 'doubt', 'normal', 'normal'];
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

    // 句25:虛線泡;句26 起退場
    if (k >= F[0] && k < F[1] + 2) {
      s += shr(Ch.bubble('那杯是壞掉了嗎', { x: BUB.x, y: BUB.y, fs: BUB.fs, dashed: true, tail: 'bl', u: U, k: k - F[0], id: 'q' }), BUB.x, BUB.y, k, F[1]);
    }
    // 句26:大字牌「有可能」;句27 起退場
    if (k >= F[1] + 2 && k < F[2] + 2) {
      const pl = Ch.plate('有可能', CARD.fs, { fill: K.YELLOW, ink: K.INK });
      s += shr(Ch.sheet(pl.svg, { x: CARD.x, y: CARD.y, rot: -2, u: U, k: k - (F[1] + 2), kind: 'big', id: 'maybe', wide: true }), CARD.x, CARD.y, k, F[2]);
    }

    // 句27:大鍋 + 細菌;句28 起退場
    if (k >= F[2] + 2 && k < F[3] + 2) {
      const kg = F[2] + 2, step = Math.max(1, Math.round((at(L, 2, 0.5) - kg) / 8));
      const kFull = Math.max(at(L, 2, 0.62), kg + step * 8 + 2);
      let g = prop('pot', { steam: false }, POT.x, POT.y, POT.s, k - kg, 'pot');
      for (let i = 0; i < 9; i++) {
        const ki = k - (kg + 1 + step * i);
        if (ki < 0) break;
        g += prop('germ', { full: i === 0 && k >= kFull }, GERM.slots[i][0], GERM.slots[i][1], GERM.s, ki, 'germ' + i);
      }
      if (k >= kFull + 1) {
        const p = K.pop(k - kFull - 1);
        g += K.tile('酸', { x: SOUR.x, y: SOUR.y, size: SOUR.size, rot: 6, u: U, sx: p, sy: p, id: 'sour', enter: k - kFull - 1 < 2 });
      }
      s += shr(g, 1260, 470, k, F[3]);
    }

    // 句28:溫度計 + 食藥署 + 2 小時;句29 起退場
    if (k >= F[3] + 2 && k < F[4] + 2) {
      const kb = F[3] + 2;                               // 大字與溫度計一起在句首出現,整句留在畫面
      let g = prop('thermo', {}, THERMO.x, THERMO.y, THERMO.s, k - (F[3] + 2), 'thermo');
      g += Ch.srcTag('食藥署', { pal, x: SRC.x, y: SRC.y, anchor: 'center', u: U, k: k - (F[3] + 4), id: 'src' });
      g += Ch.bigNum({ x: BIG.x, y: BIG.y, num: '2 小時', fs: BIG.fs, note: '室溫不要放超過', rot: 2, u: U, k: k - kb, kNote: k - kb - 3, id: 'two' });
      s += shr(g, 1030, 470, k, F[4]);
    }

    // 句29:原料袋改字「粉圓」+ 牌
    if (k >= F[4] + 2) {
      const kp = Math.max(atKw(L, 4, '煮好'), F[4] + 6), pl = Ch.plate('煮好幾小時內用完', PLATE.fs, { fill: K.YELLOW, ink: K.INK });
      s += prop('bag', { text: '粉圓' }, BAG.x, BAG.y, BAG.s, k - (F[4] + 2), 'bag');
      s += Ch.sheet(pl.svg, { x: PLATE.x, y: PLATE.y, rot: -2, u: U, k: k - kp, kind: 'plate', id: 'use', wide: true });
    }

    // 鴿子站左下(全程 idle)
    const ln = Math.max(0, L.findIndex((l, i) => k < F[i + 1] || i === L.length - 1));
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 400, h: 26, u: U, pal });
    s += K.pigeon(Object.assign({}, K.expr(K.clip('idle', k), EXP[ln]), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_bad_a', dur: 28, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
