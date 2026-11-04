/* pearl 場景 p_why_a(句12–15)為什麼要加它。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。淺底,鴿子站左下。
 * 句12:鴿子頭上對話泡「省成本?」(思考臉)。
 * 句13:泡被紅叉打掉,時鐘(時針一小時一小時走)加黃牌「時間」彈出;鴿子指向時鐘。
 * 句14:上一組退場。左襯底:熱鍋 + 三條彎曲散開的澱粉鏈,標「軟Q」;往右的箭頭加「放涼」;右襯底:四條鏈排整齊、鏈與鏈之間黏上黃點,
 *       旁邊硬珍珠,標「變硬」。各元素在對應詞位出現。
 * 句15:上一組退場。灰硬白飯、冰箱雪花、黃牌「同一回事」。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const TXT = ['那珍珠幹嘛要加它,我一開始還以為是為了省成本。', '結果它要對付的是時間。',
    '澱粉煮熟會吸水脹開,珍珠才會又軟又Q,可是只要一放涼,裡面的鏈子又會慢慢排回去黏在一起,珍珠就變硬了。', '隔夜飯冰過會變硬,跟這個是同一回事。'];
  const U = 1.4, PU = 1.38, FOOT = { x: 300, y: 820 };
  const RED = 'hsl(4 72% 48%)', ICE = 'hsl(200 85% 62%)';
  const BUB = { x: 640, y: 325, fs: 72 }, CLK = { x: 1120, y: 400, u: 1.9 }, TIME = { x: 1120, y: 690, fs: 96 };
  const PADY = { y0: 95, y1: 480 }, PADL = { x0: 90, x1: 860 }, PADR = { x0: 1060, x1: 1830 };
  const ITEM_Y = 360, LAB_Y = 170;
  const ARR = { x: 960, y: 300 }, ARR_LAB = { x: 960, y: 432, fs: 56 };
  const POT = { x: 235, u: 0.75 };
  const CURLS = [{ x: 440, y: 355, bend: 1, rot: 20 }, { x: 590, y: 345, bend: 0.85, rot: -55 }, { x: 775, y: 365, bend: 1, rot: 130 }];
  const BUN = { x: 1290, u: 0.85, rows: 4, pitch: 46 }, HARD = { x: 1690, u: 1.25 };
  const RICE = { x: 860, y: 400, u: 2.2 }, SNOW = { x: 1380, y: 400 }, SAME = { x: 1120, y: 700, fs: 96 };
  const f = (x) => +(+x).toFixed(2);

  // 沒有時間軸時的預設句時間(每秒 6.5 字)
  const DEF = (() => { let t = 0.08; return TXT.map((s) => { const d = s.length / 6.5, o = { start: +t.toFixed(2), end: +(t + d).toFixed(2) }; t += d + 0.12; return o; }); })();
  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: typeof l.text === 'string' && l.text ? l.text : TXT[i] };
    });
  }
  // 句內某詞的起始格(字數比例換算)
  const kwF = (l, kw) => { const i = l.text.indexOf(kw), r = i < 0 ? 0 : i / l.text.length; return K.frame(Math.round((l.start + r * (l.end - l.start)) * 10) / 10); };
  // 整組退場:自第 k0 格起 2 格縮小(以 (x,y) 為中心)後消失;k0 為 null = 不退場
  function shr(str, x, y, k, k0) {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  }
  // 彈入的 px 字牌;q = 出現後第幾格
  const plate = (txt, fs, o, q, id) => Ch.sheet(Ch.plate(txt, fs, o.style).svg, { x: o.x, y: o.y, rot: o.rot, u: U, k: q, kind: 'sheet', id, wide: true });
  // 彈入的單位制紙片(圖解)
  function prop(svg, o, q, id) {
    const p = K.pop(q);
    if (p <= 0) return '';
    return K.paper(svg, { x: o.x, y: o.y, rot: o.rot, scale: o.u, sx: p, sy: p, k: o.kind || 'prop', id, enter: q < 2, wide: o.wide });
  }
  // 矩形襯底(px 尺寸,以 K.paper 彈入)
  function pad(x0, x1, y0, y1, pal, q, id) {
    const p = K.pop(q);
    if (p <= 0) return '';
    const w = x1 - x0, h = y1 - y0;
    return K.paper(`<rect x="${f(-w / 2 / U)}" y="${f(-h / 2 / U)}" width="${f(w / U)}" height="${f(h / U)}" fill="${pal.pad}" stroke-linejoin="miter"/>`,
      { x: (x0 + x1) / 2, y: (y0 + y1) / 2, scale: U, sx: p, sy: p, k: 'ground', id, enter: q < 2, wide: true });
  }
  const line = (d, w, col) => `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
  const rope = (d, w, col) => line(d, w + 9, K.PAPER) + line(d, w, col);

  // 四條排整齊的鏈,鏈與鏈接觸處黏上黃點
  function bundle(pal) {
    let s = '';
    for (let j = 0; j < BUN.rows; j++) s += `<g transform="translate(0 ${f((j - (BUN.rows - 1) / 2) * BUN.pitch)})">${PP.chain(pal, {})}</g>`;
    for (let j = 0; j < BUN.rows - 1; j++) {
      const y = (j - (BUN.rows - 1) / 2) * BUN.pitch + BUN.pitch / 2;
      for (let i = 0; i < 8; i++) s += `<circle cx="${f((i - 3.5) * 50)}" cy="${f(y)}" r="8" fill="${K.YELLOW}" stroke="${K.INK}" stroke-width="3.5"/>`;
    }
    return s;
  }
  const arrow = (pal) => `<polygon points="-62,-24 6,-24 6,-52 66,0 6,52 6,24 -62,24" fill="${pal.main}" stroke-linejoin="round"/>`;
  const redX = () => rope('M -72 -72 L 72 72', 30, RED) + rope('M 72 -72 L -72 72', 30, RED);
  const snow = () => [0, 60, 120].map((a) => `<g transform="rotate(${a})">${rope('M -105 0 L 105 0', 20, ICE)}</g>`).join('') +
    [0, 60, 120].map((a) => `<g transform="rotate(${a})">${line('M -86 -20 L -105 0 L -86 20 M 86 -20 L 105 0 L 86 20', 9, ICE)}</g>`).join('');

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // ---- 句12–13:省成本泡、紅叉、時鐘 ----
    if (k < F[2] + 2) {
      let g = '';
      const q0 = k - F[0];
      g += Ch.bubble('省成本?', { x: BUB.x, y: BUB.y, fs: BUB.fs, tail: 'bl', u: U, k: q0, id: 'bub' });
      const qx = k - F[1];
      g += prop(redX(), { x: BUB.x, y: BUB.y, u: U, kind: 'mark' }, qx, 'x');
      const qc = k - (F[1] + 2), hr = 12 + Math.min(6, Math.max(0, Math.floor(qc / 3)));
      g += prop(PP.clock(pal, { h: hr }), { x: CLK.x, y: CLK.y, u: CLK.u }, qc, 'clock');
      g += plate('時間', TIME.fs, { x: TIME.x, y: TIME.y, style: { fill: K.YELLOW, ink: K.INK } }, k - (F[1] + 4), 'time');
      s += shr(g, 900, 500, k, F[2]);
    }

    // ---- 句14:軟Q → 變硬 ----
    if (k >= F[2] + 2 && k < F[3] + 2) {
      const S = F[2] + 2, q = k - S;
      const kC = Math.max(kwF(L[2], '吸水脹開'), S + 3), kSoft = Math.max(kwF(L[2], '又軟又Q'), kC + 6);
      const kCool = Math.max(kwF(L[2], '一放涼'), kSoft + 4), kBun = Math.max(kwF(L[2], '黏在一起'), kCool + 6), kHard = Math.max(kwF(L[2], '變硬了'), kBun + 6);
      let g = '';
      g += pad(PADL.x0, PADL.x1, PADY.y0, PADY.y1, pal, q, 'padL');
      g += prop(PP.pot(pal, {}), { x: POT.x, y: ITEM_Y, u: POT.u }, q - 1, 'pot');
      CURLS.forEach((c, i) => { g += prop(PP.chain(pal, { bend: c.bend }), { x: c.x, y: c.y, rot: c.rot, u: 0.62, wide: true }, k - (kC + 2 * i), 'curl' + i); });
      g += plate('軟Q', 80, { x: 270, y: LAB_Y, style: { fill: K.YELLOW, ink: K.INK } }, k - kSoft, 'soft');
      g += prop(arrow(pal), { x: ARR.x, y: ARR.y, u: U }, k - kCool, 'arrow');
      g += plate('放涼', ARR_LAB.fs, { x: ARR_LAB.x, y: ARR_LAB.y, style: {} }, k - (kCool + 1), 'cool');
      g += pad(PADR.x0, PADR.x1, PADY.y0, PADY.y1, pal, k - (kCool + 2), 'padR');
      g += prop(bundle(pal), { x: BUN.x, y: ITEM_Y, u: BUN.u, wide: true }, k - kBun, 'bundle');
      g += prop(PP.pearl(pal, { hard: true }), { x: HARD.x, y: ITEM_Y, u: HARD.u }, k - (kHard + 1), 'hard');
      g += plate('變硬', 80, { x: 1245, y: LAB_Y, style: { fill: pal.main, ink: pal.onMain } }, k - kHard, 'hardL');
      s += shr(g, 960, 290, k, F[3]);
    }

    // ---- 句15:冰過的硬飯 ----
    if (k >= F[3] + 2) {
      const q = k - (F[3] + 2);
      s += prop(PP.rice(pal, { hard: true }), { x: RICE.x, y: RICE.y, u: RICE.u }, q, 'rice');
      s += prop(snow(), { x: SNOW.x, y: SNOW.y, u: 1.1 }, q - 2, 'snow');
      s += plate('同一回事', SAME.fs, { x: SAME.x, y: SAME.y, style: { fill: K.YELLOW, ink: K.INK } }, q - 4, 'same');
    }

    // ---- 鴿子站左下 ----
    let pose;
    if (k < F[1]) pose = K.expr(K.clip('idle', k), 'think');
    else if (k < F[2]) pose = K.clip('point', k - F[1]);
    else if (k >= F[3] && k - F[3] < 6) pose = K.clip('nod', k - F[3]);
    else pose = K.clip('idle', k);
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_why_a', dur: 14, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
