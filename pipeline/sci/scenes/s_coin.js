/* snack 場景 s_coin(句 8–11)銅板的前提。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 全場:右上「?」記號(句8 句首彈入、留到結束);鴿子(doubt)站左下。
 * 句8:字牌「銅板美食」(銅板黃底)彈入;鴿子歪頭看(句首後第 3 格起)。
 * 句9:50 元硬幣大圖彈入;句首後第 3 格日曆牌「1992 年 10 月 9 日」、第 6 格來源小牌「中央銀行」。
 * 句10:日曆與來源退場;50 元硬幣變灰、縮小退到左上(3 格);之後口袋(內有一枚 10 元硬幣)彈入。
 * 句11:硬幣與口袋退場;短條(長度 1)與字牌「一個銅板吃一餐 三十幾年」長出;長條(長度 3)與字牌「士林夜市 百年」在「比士林夜市」
 *      一詞(字位置比例估)長出,夜市小攤站在長條右端上方(帶到下一場)。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.095, end: 3.05 }, { start: 3.17, end: 8.94 }, { start: 9.06, end: 11.81 }, { start: 11.93, end: 17.01 }];
  const TXT11 = '一個銅板吃一餐這種事,算起來最多才三十幾年,比士林夜市年輕太多了。', IDX_BI = 22;   // 「比」在句中的字索引
  const PU = 1.36, FOOT = { x: 245, y: 820 };                                  // 鴿子倍率(高約 309px)、腳底落點
  const PLATE = { x: 1010, y: 400, fs: 190 };
  const COIN = { x: 760, y: 430, s: 4.4 }, COIN_AWAY = { x: 650, y: 320, s: 3.0, rot: -10 };
  const DATE = { x: 1390, y: 410, size: 500 }, SRC = { x: 1390, y: 745 };
  const POCKET = { x: 1200, y: 520 };
  const BARS = { x0: 470, h: 110, shortW: 437, longW: 1310, shortY: 355, longY: 625, fs: 72 };
  const STALL = { x: 1580, s: 1.0 };
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const T = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  // 字牌「銅板美食」:銅板在黃底上
  function titlePlate(pal) {
    const fs = PLATE.fs, w = fs * 5, h = fs * 1.62, cw = fs;
    return R(-w / 2, -h / 2, w, h, K.PAPER) + `<rect x="${f(-2 * cw)}" y="${f(-fs * 0.62)}" width="${f(2 * cw)}" height="${f(fs * 1.24)}" fill="${K.YELLOW}" stroke="none"/>` +
      [['銅', -1.5], ['板', -0.5]].map((c) => T(c[0], c[1] * cw, 2, fs, K.INK)).join('') +
      [['美', 0.5], ['食', 1.5]].map((c) => T(c[0], c[1] * cw, 2, fs, pal.text)).join('');
  }

  // 口袋(牛仔褲袋)加露出的 10 元硬幣;中心為整組中心
  function pocket(pal) {
    const D = 'hsl(215 45% 46%)', Dd = 'hsl(215 45% 36%)';
    let c = Ch.icon({ svg: PS.LIST.coin10.fn(pal), w: PS.LIST.coin10.w, h: PS.LIST.coin10.h }, 0, -230, 370);
    c += `<path d="M -270 -140 L 270 -140 L 270 130 Q 270 270 0 270 Q -270 270 -270 130 Z" fill="${D}" stroke-linejoin="round"/>`;
    c += `<rect x="-270" y="-140" width="540" height="56" fill="${Dd}" stroke="none"/>`;
    c += `<path d="M -228 -40 L 228 -40 L 228 125 Q 228 228 0 228 Q -228 228 -228 125 Z" fill="none" stroke="hsl(215 60% 84%)" stroke-width="6" stroke-dasharray="18 12" stroke-linejoin="round"/>`;
    return c;
  }

  // 灰化的 50 元硬幣:inline 濾鏡去色
  function coinGrey(pal) {
    return '<defs><filter id="cgrey"><feColorMatrix type="saturate" values="0.05"/></filter></defs>' +
      `<g filter="url(#cgrey)" opacity=".7">${PS.LIST.coin50.fn(pal)}</g>`;
  }

  // 時間條:長度 w(隨 grow 比例),左緣固定
  function bar(label, y, w, grow, color, id) {
    const pl = Ch.plate(label, BARS.fs, { chip: color, padX: 0.9 }), bw = Math.max(8, w * grow);
    return { plate: pl, bar: K.paper(R(0, 0, bw, BARS.h, color), { x: BARS.x0, y: y - BARS.h / 2, k: 'bar', id: 'bar_' + id, wide: true }) };
  }

  function pigeonPose(k, F) {
    const base = K.expr(K.clip('idle', k), 'doubt'), j = k - (F[0] + 3);
    let p = base;
    if (j >= 0 && k < F[1] + 3) {                                  // 句8 歪頭看:前 3 格偏頭並維持,句9 起 3 格回正
      const idx = k < F[1] ? Math.min(j, 2) : 3 + (k - F[1]);
      p = Object.assign({}, base, K.clip('tilt', idx));
    }
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;
    let s = '';

    if (ph === 0) {                                                          // 句8:字牌
      s += Ch.sheet(titlePlate(pal), { x: PLATE.x, y: PLATE.y, rot: -1, k: k - F[0], kind: 'sheet', id: 'title', wide: true });
    } else if (ph === 1) {                                                   // 句9:50 元硬幣、日曆、來源
      const q = k - F[1], p = K.pop(q);
      s += K.paper(PS.LIST.coin50.fn(pal), { x: COIN.x, y: COIN.y, scale: COIN.s, sx: p, sy: p, k: 'prop', id: 'coin50', enter: q < 2 });
      s += Ch.dateTag({ pal, x: DATE.x, y: DATE.y, size: DATE.size, top: '1992 年', main: '10 月 9 日', rot: 2, k: q - 3, id: 'date' });
      s += Ch.srcTag('中央銀行', { pal, x: SRC.x, y: SRC.y, anchor: 'center', k: q - 6, id: 'src' });
    } else if (ph === 2) {                                                   // 句10:硬幣變灰退開、口袋與 10 元
      const q = k - F[2], P = [0, 0.3, 0.7, 1], pr = P[Math.max(0, Math.min(q - 1, 3))];
      const cx = COIN.x + (COIN_AWAY.x - COIN.x) * pr, cy = COIN.y + (COIN_AWAY.y - COIN.y) * pr, cs = COIN.s + (COIN_AWAY.s - COIN.s) * pr;
      s += K.paper(coinGrey(pal), { x: cx, y: cy, scale: cs, rot: COIN_AWAY.rot * pr, k: 'prop', id: 'coin50' });
      s += Ch.sheet(pocket(pal), { x: POCKET.x, y: POCKET.y, rot: 1, k: q - 4, kind: 'sheet', id: 'pocket', wide: true });
    } else {                                                                 // 句11:兩條時間條
      const q = k - F[3], l = L[3];
      const kBi = K.frame(l.start + (l.end - l.start) * IDX_BI / TXT11.length), qb = k - kBi;
      const GS = [0.25, 0.5, 0.75, 1];
      const sh = bar('一個銅板吃一餐 三十幾年', BARS.shortY, BARS.shortW, q < 0 ? 0 : GS[Math.min(q, 3)], pal.main, 'short');
      const lo = bar('士林夜市 百年', BARS.longY, BARS.longW, qb < 0 ? 0 : qb === 0 ? 0.55 : 1, pal.text, 'long');
      if (q >= 0) {
        s += sh.bar;
        s += Ch.sheet(sh.plate.svg, { x: BARS.x0 + sh.plate.w / 2, y: BARS.shortY - BARS.h / 2 - 78, rot: -1, k: q, kind: 'sheet', id: 'lblShort', wide: true });
      }
      if (qb >= 0) {
        s += lo.bar;
        s += Ch.sheet(lo.plate.svg, { x: BARS.x0 + lo.plate.w / 2, y: BARS.longY - BARS.h / 2 - 78, rot: 1, k: qb, kind: 'sheet', id: 'lblLong', wide: true });
        const p = K.pop(qb);
        s += K.paper(PS.LIST.stall.fn(pal, { sign: '夜市' }), { x: STALL.x, y: BARS.longY - BARS.h / 2 - 150 * STALL.s - 2, scale: STALL.s, sx: p, sy: p, k: 'prop', id: 'stall', wide: true, enter: qb < 2 });
      }
    }
    s += Ch.triviaMark({ k: k - F[0], id: 'trivia' });
    const g = pigeonPose(k, F);
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: 1.43, pal });
    s += K.pigeon(g, { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_coin', dur: 17.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
