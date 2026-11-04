/* pearl 場景 p_why_b(句16–18)為什麼耐冰耐煮。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–2。淺底,鴿子站左下。
 * 句16:上下兩條掛著零件的澱粉鏈(下面那條上下翻轉,零件相對),下面那條週期性往上靠、碰到後左右抖兩格再彈開(9 格一輪);
 *       上方黃牌「多接的零件」,「排不回去」詞位出現黃牌「靠不攏」。
 * 句17:上一組退場。左:加冰手搖杯 + 牌「耐冰」;右:大鍋 + 牌「耐煮」(詞位);下方來源牌「五桐號說法」。
 * 句18:上一組退場。大鍋(「一大鍋」詞位標牌)→ 箭頭 →(「冰奶茶」詞位)加冰手搖杯標「泡冰奶茶」,右側時鐘(時針每步一小時走半圈到句尾)標「慢慢吸」;
 *       杯出現後鴿子每 14 格歪頭一次(慢慢吸)。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const TXT = ['鏈子上多接了那一小段以後,中間卡了東西,就比較排不回去。', '五桐號講的用途是讓珍珠比較耐冰、比較耐煮,跟研究寫的對得起來。',
    '你想想看喔,手搖店的珍珠一煮就是一大鍋,煮完還要泡在冰奶茶裡面讓你慢慢吸,它不變硬才奇怪吧。'];
  const U = 1.4, PU = 1.38, FOOT = { x: 300, y: 820 };
  // 句16
  const CH = { x: 1100, yA: 300, u: 1.6, tags: 4, cycle: 9 }, GAP = [90, 62, 34, 14, 6, 6, 6, 40, 76], JIT = [0, 0, 0, 0, 0, 8, -8, 0, 0];
  const NOTE = { x: 1100, y: 150, fs: 64 }, STUCK = { x: 1650, y: 400, fs: 80 };
  // 句17
  const CUP17 = { x: 880, y: 300, u: 1.15 }, POT17 = { x: 1400, y: 300, u: 0.95 }, TAG17 = { y: 560, fs: 120 }, SRC = { x: 1150, y: 740, fs: 44 };
  // 句18
  const POT18 = { x: 700, y: 400, u: 1.4 }, CUP18 = { x: 1300, y: 400, u: 1.7 }, ARR = { x: 1000, y: 400 }, CLK = { x: 1650, y: 330, u: 1.2 };
  const LAB18 = { potY: 690, cupY: 690, clkY: 500, fs: 64 };
  const f = (x) => +(+x).toFixed(2);

  const DEF = (() => { let t = 0.08; return TXT.map((s) => { const d = s.length / 6.5, o = { start: +t.toFixed(2), end: +(t + d).toFixed(2) }; t += d + 0.12; return o; }); })();
  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: typeof l.text === 'string' && l.text ? l.text : TXT[i] };
    });
  }
  const kwF = (l, kw) => { const i = l.text.indexOf(kw), r = i < 0 ? 0 : i / l.text.length; return K.frame(Math.round((l.start + r * (l.end - l.start)) * 10) / 10); };
  function shr(str, x, y, k, k0) {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  }
  const plate = (txt, fs, o, q, id) => Ch.sheet(Ch.plate(txt, fs, o.style).svg, { x: o.x, y: o.y, rot: o.rot, u: U, k: q, kind: 'sheet', id, wide: true });
  function prop(svg, o, q, id) {
    const p = K.pop(q);
    if (p <= 0) return '';
    return K.paper(svg, { x: o.x, y: o.y, rot: o.rot, scale: o.u, sx: p, sy: p * (o.flipY ? -1 : 1), k: o.kind || 'prop', id, enter: q < 2, wide: o.wide });
  }
  const arrow = (pal) => `<polygon points="-62,-24 6,-24 6,-52 66,0 6,52 6,24 -62,24" fill="${pal.main}" stroke-linejoin="round"/>`;

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const Y = { fill: K.YELLOW, ink: K.INK };
    let s = '';

    // ---- 句16:兩條掛零件的鏈靠不攏 ----
    if (k < F[1] + 2) {
      const q = k - F[0], ph = Math.max(0, q - 3) % CH.cycle, kS = Math.max(kwF(L[0], '排不回去'), F[0] + 8);
      const yB = CH.yA + 85 * CH.u + GAP[ph];
      let g = '';
      g += prop(PP.chain(pal, { tags: CH.tags }), { x: CH.x, y: CH.yA, u: CH.u, wide: true }, q, 'chainA');
      g += prop(PP.chain(pal, { tags: CH.tags }), { x: CH.x + JIT[ph], y: yB, u: CH.u, wide: true, flipY: true }, q - 1, 'chainB');
      g += plate('多接的零件', NOTE.fs, { x: NOTE.x, y: NOTE.y, style: {} }, q - 2, 'note');
      g += plate('靠不攏', STUCK.fs, { x: STUCK.x, y: STUCK.y, style: Y, rot: 3 }, k - kS, 'stuck');
      s += shr(g, 1100, 400, k, F[1]);
    }

    // ---- 句17:耐冰、耐煮 ----
    if (k >= F[1] + 2 && k < F[2] + 2) {
      const S = F[1] + 2, q = k - S, kBoil = Math.max(kwF(L[1], '耐煮'), S + 4);
      let g = '';
      g += prop(PP.cup(pal, { ice: true }), { x: CUP17.x, y: CUP17.y, u: CUP17.u }, q, 'cup');
      g += plate('耐冰', TAG17.fs, { x: CUP17.x, y: TAG17.y, style: Y, rot: -2 }, q - 1, 'ice');
      g += prop(PP.pot(pal, {}), { x: POT17.x, y: POT17.y, u: POT17.u }, k - kBoil, 'pot');
      g += plate('耐煮', TAG17.fs, { x: POT17.x, y: TAG17.y, style: Y, rot: 2 }, k - (kBoil + 1), 'boil');
      g += Ch.srcTag('五桐號說法', { pal, x: SRC.x, y: SRC.y, fs: SRC.fs, anchor: 'center', u: U, k: q - 2, id: 'src' });
      s += shr(g, 1150, 450, k, F[2]);
    }

    // ---- 句18:一大鍋 → 冰奶茶,時鐘走半圈 ----
    if (k >= F[2] + 2) {
      const S = F[2] + 2, q = k - S, end = K.frame(L[2].end);
      const kPot = kwF(L[2], '一大鍋'), kArr = Math.max(kwF(L[2], '泡在'), S + 5), kCup = Math.max(kwF(L[2], '冰奶茶'), kArr + 2), kClk = kCup + 2;
      s += prop(PP.pot(pal, {}), { x: POT18.x, y: POT18.y, u: POT18.u }, q, 'pot');
      s += plate('一大鍋', LAB18.fs, { x: POT18.x, y: LAB18.potY, style: {} }, k - Math.max(kPot, S + 2), 'potL');
      s += prop(arrow(pal), { x: ARR.x, y: ARR.y, u: U }, k - kArr, 'arrow');
      s += prop(PP.cup(pal, { ice: true }), { x: CUP18.x, y: CUP18.y, u: CUP18.u }, k - kCup, 'cup');
      s += plate('泡冰奶茶', LAB18.fs, { x: CUP18.x, y: LAB18.cupY, style: Y }, k - (kCup + 1), 'cupL');
      const pr = Math.max(0, Math.min(1, (k - kClk) / Math.max(1, end - kClk))), hr = 3 + Math.floor(pr * 6 + 1e-6);
      s += prop(PP.clock(pal, { h: hr }), { x: CLK.x, y: CLK.y, u: CLK.u }, k - kClk, 'clock');
      s += plate('慢慢吸', 56, { x: CLK.x, y: LAB18.clkY, style: Y }, k - (kClk + 1), 'clkL');
    }

    // ---- 鴿子站左下 ----
    let pose;
    if (k < F[1]) pose = K.expr(K.clip('idle', k), 'doubt');
    else if (k < F[2]) pose = K.clip('idle', k);
    else {
      const kC = Math.max(kwF(L[2], '冰奶茶'), F[2] + 7) + 2, c = (k - kC) % 14;
      pose = k >= kC && c < 6 ? K.expr(K.clip('tilt', c), 'smug') : K.expr(K.clip('idle', k), 'smug');
    }
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_why_b', dur: 14, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
