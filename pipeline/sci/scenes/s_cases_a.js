/* snack 場景 s_cases_a(句 41–45)單店案例一。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。淺底,鴿子站左下(全程 idle)。
 * 句41:上半紙片內一條平滑指數線由左畫到右;下半三張歪斜價牌「? 元」自句中「單看」處起逐張冒出。
 * 句42:平滑線與價牌退場;便當圖 + 招牌字牌「鬍鬚張 魯肉飯便當」;價牌 85;「2026」處日曆牌「2026 年 1 月」;句 55% 價牌翻成 89 元。
 * 句43:日曆牌退場換黃牌「+4 元」;「4.7%」處右下大數字「4.7%」。
 * 句44:整組退場;牛肉麵圖 + 招牌「三商巧福 原汁牛肉麵」;日曆牌「2026 年 2 月」;價牌 175 → 185 元(55%);「報導」處來源牌「報導指出」、「九個月」處計數牌「9 個月內第 2 次」。
 * 句45:整組退場;羹碗 + 燈籠「基隆廟口 螃蟹羹」;日曆牌「2026 年 3 月」;價牌「80–90 元」→「100 元」(55%)。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF_TXT = ['指數是全台灣平均出來的,看起來很溫和,單看幾家店就比較刺激了。', '鬍鬚張的魯肉飯便當在 2026 年 1 月從 85 元調到 89 元。',
    '四塊錢聽起來還好吧,換算下來是 4.7% 左右。', '三商巧福的原汁牛肉麵 2026 年 2 月從 175 元漲到 185 元,報導說這是九個月裡面的第二次。',
    '基隆廟口的螃蟹羹在 2026 年 3 月漲到 100 元,之前是 80 到 90 元。'];
  const DEF = [{ start: 0.08, end: 4.53 }, { start: 4.65, end: 9.3 }, { start: 9.42, end: 13.1 }, { start: 13.22, end: 21.5 }, { start: 21.62, end: 26.86 }];
  const U = 1.43, PU = 1.36;                          // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const FOOD = { x: 730, y: 540 }, SIGN = { x: 720, y: 215, fs: 68 };
  const DATE = { x: 1180, y: 440, size: 250 }, PRICE = { x: 1585, y: 440, fs: 88 };
  const PLUS = { x: 1180, y: 440, fs: 88 }, BIG = { x: 1585, y: 700, fs: 150 };
  const CNT = { x: 1230, y: 650, fs: 56 }, SRC = { x: 1230, y: 745 };
  const PANEL = { x: 1160, y: 280, w: 1320, h: 320 };   // 句41 上半:平滑線紙片(x 500–1820、y 120–440)
  const TAGS = [{ x: 800, y: 640, rot: -9 }, { x: 1170, y: 580, rot: 7 }, { x: 1540, y: 650, rot: -6 }];
  const RED = 'hsl(4 72% 48%)';
  const CASES = [
    { i: 1, food: 'bento', s: 1.85, sign: '鬍鬚張 魯肉飯便當', date: ['2026 年', '1 月'], from: 85, to: 89, drop: 3 },
    { i: 3, food: 'beefNoodle', s: 2.35, sign: '三商巧福 原汁牛肉麵', date: ['2026 年', '2 月'], from: 175, to: 185, drop: 4 },
    { i: 4, food: 'soupBowl', s: 2.2, lantern: ['基隆廟口', '螃蟹羹'], foodY: 565, date: ['2026 年', '3 月'], from: '80–90', to: 100, drop: null },
  ];
  const f = (x) => +(+x).toFixed(2);
  const T = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const R = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ''}/>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || DEF_TXT[i] };
    });
  }
  // 句內某比例或某關鍵詞的格編號
  const at = (L, i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
  const atKw = (L, i, kw) => at(L, i, Math.max(0, L[i].text.indexOf(kw)) / L[i].text.length);
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心);k0 為 null = 不退場
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  // 燈籠(中心含上下蓋與流蘇):兩行字
  function lantern(l1, l2) {
    return R(-40, -140, 80, 24, K.INK, ' stroke-linejoin="miter"') +
      `<rect x="-165" y="-116" width="330" height="176" rx="70" fill="${RED}"/>` +
      `<rect x="-148" y="-99" width="296" height="142" rx="58" fill="none" stroke="hsl(4 72% 34%)" stroke-width="5"/>` +
      T(l1, 0, -66, 60, K.YELLOW) + T(l2, 0, 10, 60, K.YELLOW) +
      R(-40, 60, 80, 24, K.INK, ' stroke-linejoin="miter"') + R(-6, 84, 12, 40, K.YELLOW, ' stroke-linejoin="miter"');
  }

  // 句41 上半的平滑指數線:p = 0–1 已畫比例
  function curve(pal, p) {
    const w = 1180, x0 = -w / 2, y0 = 105, amp = 215, n = 48, m = Math.max(1, Math.round(n * p));
    let c = R(-PANEL.w / 2 + 70, y0 + 24, PANEL.w - 140, 8, K.INK, ' stroke="none"');
    const pts = [];
    for (let j = 0; j <= m; j++) { const s = j / n; pts.push([x0 + w * s, y0 - amp * (Math.exp(3.2 * s) - 1) / (Math.exp(3.2) - 1)]); }
    c += `<polyline points="${pts.map((v) => `${f(v[0])},${f(v[1])}`).join(' ')}" fill="none" stroke="${K.INK}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>`;
    if (p >= 1) c += `<circle cx="${f(pts[m][0])}" cy="${f(pts[m][1])}" r="22" fill="${K.YELLOW}" stroke="${K.INK}" stroke-width="7"/>`;
    return R(-PANEL.w / 2, -PANEL.h / 2, PANEL.w, PANEL.h, pal.pad, ' stroke-linejoin="miter"') + c;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // 句41 平滑線 + 三張歪斜價牌(句42 起退場)
    if (k < F[1] + 2) {
      const q = k - F[0], kT = Math.max(atKw(L, 0, '單看'), F[0] + 8);
      const pn = Math.min(1, Math.max(0, q - 1) / 6);
      let g = Ch.sheet(curve(pal, pn), { x: PANEL.x, y: PANEL.y, u: U, k: q, kind: 'sheet', id: 'curve', wide: true });
      s += shr(g, PANEL.x, PANEL.y, k, F[1]);
      TAGS.forEach((tg, j) => {
        const kj = k - (kT + 4 * j);
        s += shr(Ch.priceFlip({ pal, x: tg.x, y: tg.y, from: '?', unit: '元', fs: 100, rot: tg.rot, u: U, k: kj, id: 'jag' + j }), tg.x, tg.y, k, F[1]);
      });
    }

    // 句42–45 三個案例
    CASES.forEach((cs, ci) => {
      const S = F[cs.i] + 2, kOut = cs.drop == null ? null : F[cs.drop];
      if (k < S || (kOut != null && k >= kOut + 2)) return;
      const q = k - S, p = K.pop(q), fy = cs.foodY || FOOD.y;
      const kDate = Math.max(atKw(L, cs.i, '2026'), S + 4), kFlip = Math.max(at(L, cs.i, 0.55), kDate + 3);
      const out = (str, x, y) => shr(str, x, y, k, kOut);
      const PS_ = PS.LIST[cs.food];
      s += out(K.paper(PS_.fn(pal, {}), { x: FOOD.x, y: fy, scale: cs.s, sx: p, sy: p, k: 'prop', id: cs.food, wide: PS_.wide, enter: q < 2 }), FOOD.x, fy);
      if (cs.sign) {
        const pl = Ch.plate(cs.sign, SIGN.fs, { fill: pal.main, ink: pal.onMain });
        s += out(Ch.sheet(pl.svg, { x: SIGN.x, y: SIGN.y, u: U, k: q, kind: 'sign', id: 'sign' + ci, wide: true }), SIGN.x, SIGN.y);
      } else {
        s += out(Ch.sheet(lantern(cs.lantern[0], cs.lantern[1]), { x: SIGN.x, y: 245, u: U, k: q, kind: 'sign', id: 'lantern', wide: true }), SIGN.x, 245);
      }
      s += out(Ch.priceFlip({ pal, x: PRICE.x, y: PRICE.y, from: cs.from, to: cs.to, unit: '元', fs: PRICE.fs, rot: -2, u: U, k: q - 2, kFlip: k - kFlip, id: 'pf' + ci }), PRICE.x, PRICE.y);

      // 日曆牌:案例一在句43 起換成「+4 元」
      const kDateOut = ci === 0 ? F[2] : kOut;
      if (k >= kDate && !(kDateOut != null && k >= kDateOut + 2)) {
        s += shr(Ch.dateTag({ x: DATE.x, y: DATE.y, top: cs.date[0], main: cs.date[1], size: DATE.size, rot: -3, u: U, k: k - kDate, id: 'date' + ci }), DATE.x, DATE.y, k, kDateOut);
      }
      if (ci === 0 && k >= F[2] + 2) {
        const pl = Ch.plate('+4 元', PLUS.fs, { fill: K.YELLOW, ink: K.INK }), kB = Math.max(atKw(L, 2, '4.7%'), F[2] + 6);
        s += out(Ch.sheet(pl.svg, { x: PLUS.x, y: PLUS.y, rot: -4, u: U, k: k - (F[2] + 2), kind: 'plus', id: 'plus' }), PLUS.x, PLUS.y);
        s += out(Ch.bigNum({ x: BIG.x, y: BIG.y, num: '4.7%', fs: BIG.fs, rot: 2, u: U, k: k - kB, id: 'big' }), BIG.x, BIG.y);
      }
      if (ci === 1) {                                                      // 句44 來源牌與計數牌
        const kS = Math.max(atKw(L, 3, '報導'), kFlip + 3), kC = Math.max(atKw(L, 3, '九個月'), kS + 3);
        const cp = Ch.plate('9 個月內第 2 次', CNT.fs, { fill: K.YELLOW, ink: K.INK });
        s += Ch.sheet(cp.svg, { x: CNT.x, y: CNT.y, rot: 2, u: U, k: k - kC, kind: 'cnt', id: 'cnt', wide: true });
        s += Ch.srcTag('報導指出', { pal, x: SRC.x, y: SRC.y, anchor: 'center', k: k - kS, id: 'src' });
      }
    });

    // 鴿子站左下(全程 idle)
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, K.expr(K.clip('idle', k), 'normal'), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_cases_a', dur: 26.9, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
