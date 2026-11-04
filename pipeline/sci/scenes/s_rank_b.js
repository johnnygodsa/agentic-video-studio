/* salary 場景 s_rank_b(句 9–12)一百萬在哪。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 接在 s_rank_a 之後:版面用 PropsSalary.RANK_LAYOUT(十等份階梯在右側 x 420–1800,鴿子在左欄、腳底固定、面向右)。
 * 開頭狀態:九根柱已在、只有第 5 根(黃)有數值 54.6;左上固定來源牌。
 * 句9:「100 萬」marker 線與牌句首彈入(落在 D8 與 D9 之間);詞位置「95.9」→ D8 轉黃加數值牌;「133.6」→ D9 轉黃加數值牌(第 5 根退回主色、數值保留)。
 * 句10:前 8 根由左至右每格一根變灰(D9 黃保留);詞「贏過」位置(至少在灰完後)黃牌「贏過八成以上」彈入(句12 起隨襯底紙蓋住而不畫)。
 * 句11:鴿子 doubt、舉牌(紙牌加木棍,棍尾藏在鴿頭後)「中上?」句首彈入;詞「中上」位置翻牌 → 「前兩成」。
 * 句12:整片紙(襯底色)蓋住階梯、牌退場;黃牌「100 萬 ÷ 12 個月」、「自算」牌句首彈入,12 格日曆(月份、千元鈔、「8 萬多」)每格晚一格逐一加快彈入(約 1 秒內出完)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale;
  const DEF = [
    { start: 0.055, end: 5.0, text: '一百萬要往後排很遠,前兩成的門檻是 95.9 萬,前一成是 133.6 萬。' },
    { start: 5.1, end: 8.5, text: '年薪一百萬,已經贏過八成以上的上班族了。' },
    { start: 8.6, end: 11.5, text: '我原本以為一百萬頂多算中上而已呢。' },
    { start: 11.6, end: 14.0, text: '一百萬平均到每個月,是八萬多塊。' }];
  const f = (x) => +(+x).toFixed(2);
  const SIGN = { x: 250, y: 420, fs: 76, stickDx: 50, stickLen: 120, rot: -3 };
  const COVER = { x: 1113, y: 509, w: 1434, h: 658 };            // 句12 蓋住階梯的襯底紙(上緣 180、下緣 838:陰影不進字幕帶)
  const COVER_POP = [0.55, 0.9, 1];                              // 不過衝:大張紙過衝會壓進字幕帶
  const FLIP = [{ sx: 0.6, back: 0 }, { sx: 0.15, back: 0 }, { sx: 0.15, back: 1 }, { sx: 0.65, back: 1 }, { sx: 1.05, back: 1 }];
  const CELL = { w: 200, h: 210, gapX: 29, gapY: 18, x0: 440.5, y0: 368 };

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  // 詞的起始字索引 ÷ 句長 × 句長秒數 + start → 第幾格
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const text = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  // 以 px 繪製的紙片(同 Charts.sheet,但 sx、sy 可自訂):o: {x,y,rot,sx,sy,kind,id,enter}
  const paperPx = (content, o) => K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
    { x: o.x, y: o.y, rot: o.rot, scale: U, sx: o.sx, sy: o.sy, k: o.kind, id: o.id, enter: o.enter, wide: true });

  // 鴿子:idle 呼吸(眨眼格保留)、面向右(flip)、表情只換眼
  function pigeonPose(k, name) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }

  // 舉牌:卡片加木棍(內容以 px、中心在卡片中心);kFlip<0 = 未翻
  function sign(pal, k, kFlip) {
    if (k < 0) return '';
    const fs = SIGN.fs, w = Math.max(Ch.tw('前兩成', fs), Ch.tw('中上?', fs)) + fs, h = fs * 1.62;
    const fl = kFlip >= 0 ? (kFlip < FLIP.length ? FLIP[kFlip] : { sx: 1, back: 1 }) : { sx: 1, back: 0 };
    const back = fl.back === 1;
    const c = rect(SIGN.stickDx - 8, h / 2 - 4, 16, SIGN.stickLen, 'hsl(24 55% 40%)') +
      rect(-w / 2, -h / 2, w, h, back ? K.YELLOW : K.PAPER) + text(back ? '前兩成' : '中上?', 0, 0, fs, K.INK);
    const p = K.pop(k);
    return paperPx(c, { x: SIGN.x, y: SIGN.y, rot: SIGN.rot, sx: p * fl.sx, sy: p, kind: 'sign', id: 'sign', enter: k < 2 || (kFlip >= 0 && kFlip < FLIP.length) });
  }

  // 句12:12 格日曆(每格:月份色帶、千元鈔、「8 萬多」);第 i 格在 kc ≥ floor(0.7 i) 時彈入(每格約 0.7 格間隔,加快)
  function calendar(pal, kc) {
    let s = '';
    for (let i = 0; i < 12; i++) {
      const k = kc - Math.floor(i * 0.7);
      if (k < 0) continue;
      const col = i % 6, row = Math.floor(i / 6), cx = CELL.x0 + CELL.w / 2 + col * (CELL.w + CELL.gapX), cy = CELL.y0 + CELL.h / 2 + row * (CELL.h + CELL.gapY);
      const w = CELL.w, h = CELL.h;
      const c = rect(-w / 2, -h / 2, w, h, K.PAPER) + rect(-w / 2, -h / 2, w, 62, pal.main) + text(`${i + 1} 月`, 0, -h / 2 + 31, Ch.FS_LABEL, pal.onMain) +
        Ch.icon({ svg: PS.bill(pal), w: 320, h: 140 }, 0, -3, 150) + text('8 萬多', 0, 70, Ch.FS_LABEL, K.INK);
      s += Ch.sheet(c, { x: cx, y: cy, rot: i % 2 ? 1 : -1, u: U, k, kind: 'calCell', id: 'cal' + i, wide: true });
    }
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const C = RL.chart, NOW = 99;
    let s = '';

    // 來源牌(全場)
    s += Ch.srcTag(RL.src.text, { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src' });

    // 十等份階梯:狀態依時間算(句12 起被襯底紙蓋住,仍照畫)
    const k8 = wordK(L[0], '95.9'), k9 = wordK(L[0], '133.6');
    const greyN = Math.max(0, Math.min(8, k - F[1] + 1));
    const grey = Array.from({ length: greyN }, (_, i) => i);
    let hi = [4];
    if (k >= F[0]) hi = [].concat(k >= k8 ? [7] : [], k >= k9 ? [8] : []);
    if (k >= F[1]) hi = greyN >= 8 ? [8] : [7, 8];
    const numKs = RL.vals.map(() => -1);
    numKs[4] = NOW;
    if (k >= F[0]) { numKs[7] = k - k8; numKs[8] = k - k9; }
    s += Ch.decileRow({ x: C.x, y: C.y, w: C.w, h: C.h, max: C.max, pal, id: 'dr', vals: RL.vals, hiIdx: hi, greyIdx: grey, numKs,
      marker: { value: 100, label: '100 萬', k: k - F[0] } });

    // 句10:黃牌「贏過八成以上」(詞「贏過」位置,但不早於灰柱波完成)
    const kw = Math.max(wordK(L[1], '贏過'), F[1] + 8);
    if (k >= kw && k < F[3]) {
      const p = Ch.plate('贏過八成以上', 110, { fill: K.YELLOW });
      s += Ch.sheet(p.svg, { x: 1060, y: 266, rot: -1.5, u: U, k: k - kw, kind: 'sheet', id: 'win', wide: true });
    }

    // 句12:襯底紙蓋住階梯、牌與日曆
    if (k >= F[3]) {
      const q = Math.min(k - F[3], COVER_POP.length - 1), sc = COVER_POP[q];
      s += paperPx(rect(-COVER.w / 2, -COVER.h / 2, COVER.w, COVER.h, pal.pad), { x: COVER.x, y: COVER.y, sx: sc, sy: sc, kind: 'cover', id: 'cover', enter: k - F[3] < 2 });
      const tp = Ch.plate('100 萬 ÷ 12 個月', 84, { fill: K.YELLOW });
      s += Ch.sheet(tp.svg, { x: COVER.x, y: 270, rot: -1, u: U, k: k - F[3] - 1, kind: 'sheet', id: 'calT', wide: true });
      s += Ch.srcTag('自算', { x: 1836, y: RL.src.y, anchor: 'right', pal, k: k - F[3] - 1, id: 'self' });
      s += calendar(pal, k - F[3] - 3);
    }

    // 鴿子(句11 doubt 舉牌;句12 牌退場)與腳下襯底
    const P = RL.pigeon, doubt = k >= F[2] && k < F[3];
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    if (doubt) s += sign(pal, k - F[2], k >= wordK(L[2], '中上') ? k - wordK(L[2], '中上') : -1);
    const name = doubt ? 'doubt' : k >= F[3] ? 'normal' : 'look';
    s += K.pigeon(pigeonPose(k, name), { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_rank_b', dur: 21.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
