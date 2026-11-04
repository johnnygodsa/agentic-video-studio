/* snack 場景 s_abroad(句 88–93)國外物價。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–5。
 * 三國各一個版面,換國家時上一國整組(含來源牌)退場;每國左上一張國名大牌(字高 110px),整國保留;鴿子站左下。
 * 句88 日本:國名牌 + 磚牆「1000 円」彈入;拉麵碗推著價牌「? 円」往右加速(逐格位置由格數算),撞上牆後牆晃 3 格。
 * 句89 拉麵、價牌、牆退場;大數字「72 間」+ 說明「2024 年倒閉的拉麵店」+ 來源「帝國資料銀行」。
 * 句90 韓國:國名牌;橫條「2020 年 100」「2025 年年中 124.56」;「約 +25%」黃牌與來源小牌在「25%」詞級時間。
 * 句91 長條與黃牌退場;紫菜飯捲大圖 + 價牌 3,500 → 3,700 韓元(「漲到」詞級時間翻牌)+ 小牌「首爾 2025 年 11 月」(詞級時間)。
 * 句92 中國:國名牌;折線圖底板與一條幾乎平的線(min -3、max 3)。
 * 句93 兩點「2023 +0.2%」「2024 +0.2%」依詞級時間出現;來源小牌「中國國家統計局」。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.04, end: 6.74 }, { start: 6.86, end: 12.27 }, { start: 12.39, end: 19.17 }, { start: 19.29, end: 26.425 }, { start: 26.545, end: 27.78 }, { start: 27.9, end: 33.145 }];
  const DEFT = ['出了台灣也差不多,日本的拉麵店有個說法叫一千圓之壁,一碗超過一千圓客人就不太願意買單。', '2024 年日本倒閉的拉麵店有 72 間,帝國資料銀行說這是歷年最多。',
    '韓國的外食物價,官方指數從 2020 年到 2025 年年中漲了大約 25% 這麼多。', '首爾的紫菜飯捲一條從 3,500 韓元漲到 3,700 韓元,這是 2025 年 11 月跟前一年同月比的價錢。',
    '中國就不太一樣了。', '官方的整體物價在 2023 年和 2024 年都只漲 0.2%,幾乎沒在動。'];
  const U = 1.43, PU = 1.36;                        // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const COUNTRY = ['日本', '日本', '韓國', '韓國', '中國', '中國'], CFS = 110, CPOS = { x: 105, y: 200 };   // 國名牌:左緣 105、中心 y 200(高 178)
  // 日本:磚牆、拉麵碗與價牌
  const WALL = { x: 1555, y: 490, s: 1.8 }, RAMEN = { y: 490, s: 1.5, end: 784 }, SIGN = { fs: 110, end: 1112 }, PUSH = { d: 180, p0: 14, n: 10 };
  const SHAKE = [-1.8, 1.2, -0.6];
  // 韓國:橫條
  const BARS = { x: 470, y: 330, w: 1340, rowH: 140, gap: 30, labelW: 440 };
  // 中國:折線圖
  const LC = { x: 520, y: 230, w: 1300, h: 450, fs: 72, min: -3, max: 3 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || DEFT[i] };
    });
  }
  // 詞級時間(格):詞的起始字索引 ÷ 句長 × 句長秒數 + start,對齊 0.1 秒
  function wordFrame(l, tok) {
    const idx = l.text.indexOf(tok), r = idx < 0 ? 0 : idx / l.text.length;
    return Math.max(K.frame(l.start), K.frame(Math.round((l.start + r * (l.end - l.start)) * 10) / 10 + 0.001));
  }

  // 折線圖兩點座標(同 Charts.lineChart 的算法,無標題)
  function lcPoints() {
    const tag = Ch.plate('+0.2%', LC.fs), lab = Ch.plate('2023', LC.fs), padX = Math.max(tag.w, lab.w) / 2 + 20;
    const y = LC.y + LC.h - (0.2 - LC.min) / (LC.max - LC.min) * LC.h;
    return { x0: LC.x + padX, x1: LC.x + LC.w - padX, y };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let si = 0;
    F.forEach((v, i) => { if (k >= v) si = i; });
    const q = k - F[si], first = [0, 0, 2, 2, 4, 4][si], qc = k - F[first];   // qc:該國出現後第幾格
    let s = '';

    // ---- 國名牌(整國保留)----
    const cp = Ch.plate(COUNTRY[si], CFS, { fill: K.INK, ink: K.YELLOW, chip: pal.main });
    s += Ch.sheet(cp.svg, { x: CPOS.x + cp.w / 2, y: CPOS.y, u: U, k: qc, kind: 'country', id: 'country' + first, wide: true });

    if (si === 0) {                                                          // 句88:拉麵推價牌撞牆
      const j = Math.max(0, Math.min(PUSH.n, q - PUSH.p0)), sh = PUSH.d * (j / PUSH.n) * (j / PUSH.n), c = q - (PUSH.p0 + PUSH.n);
      const rot = c >= 0 && c < SHAKE.length ? SHAKE[c] : 0, p = K.pop(q - 5);
      s += K.paper(PS.wall(pal, { text: '1000 円' }), { x: WALL.x, y: WALL.y, scale: WALL.s, sx: K.pop(q), sy: K.pop(q), rot, k: 'prop', id: 'wall', enter: q < 2 });
      if (p > 0) s += K.paper(PS.ramen(), { x: Math.round(RAMEN.end - PUSH.d + sh), y: RAMEN.y, scale: RAMEN.s, sx: p, sy: p, k: 'prop', id: 'ramen', enter: q - 5 < 2 });
      s += Ch.priceFlip({ pal, x: Math.round(SIGN.end - PUSH.d + sh), y: RAMEN.y, from: '?', unit: '円', fs: SIGN.fs, u: U, k: q - 5, id: 'sign' });
    } else if (si === 1) {                                                   // 句89:72 間
      s += Ch.bigNum({ x: 1140, y: 400, num: '72', unit: '間', note: '2024 年倒閉的拉麵店', fs: 340, noteFs: 80, u: U, k: q, kNote: q - 3, id: 'num' });
      s += Ch.srcTag('帝國資料銀行', { pal, x: 1820, y: 120, anchor: 'right', fs: 44, u: U, k: q - 6, id: 'src' });
    } else if (si === 2) {                                                   // 句90:韓國橫條
      s += Ch.hbars({ pal, x: BARS.x, y: BARS.y, w: BARS.w, rowH: BARS.rowH, gap: BARS.gap, labelW: BARS.labelW, fs: 64, numFs: 84, max: 124.56, u: U, id: 'kr', bars: [
        { label: '2020 年', value: 100, text: '100', grey: true, k: q - 2 },
        { label: '2025 年年中', value: 124.56, text: '124.56', hi: true, k: q - 8 }] });
      const kw = k - wordFrame(L[2], '25%');
      const tag = Ch.plate('約 +25%', 88, { fill: K.YELLOW });
      s += Ch.sheet(tag.svg, { x: 1600, y: 725, rot: -2, u: U, k: kw, kind: 'tag', id: 'pct', wide: true });
      s += Ch.srcTag('韓國統計廳(報導引用)', { pal, x: 1820, y: 120, anchor: 'right', fs: 44, u: U, k: kw, id: 'src' });
    } else if (si === 3) {                                                   // 句91:紫菜飯捲、價牌
      const p = K.pop(q);
      s += K.paper(PS.kimbap(), { x: 1150, y: 290, scale: 2.6, sx: p, sy: p, k: 'prop', id: 'kimbap', enter: q < 2, wide: true });
      s += Ch.priceFlip({ pal, x: 1150, y: 590, from: '3,500', to: '3,700', unit: '韓元', fs: 110, u: U, k: q - 3, kFlip: k - wordFrame(L[3], '漲到'), id: 'kimbapPrice' });
      s += Ch.srcTag('首爾 2025 年 11 月', { pal, x: 1820, y: 120, anchor: 'right', fs: 44, u: U, k: k - wordFrame(L[3], '2025 年'), id: 'src' });
    } else {                                                                 // 句92–93:中國折線
      const pt = lcPoints();
      const k0 = si === 5 ? k - wordFrame(L[5], '2023') : -1, k1 = si === 5 ? k - wordFrame(L[5], '2024') : -1;
      s += Ch.lineChart({ pal, x: LC.x, y: LC.y, w: LC.w, h: LC.h, fs: LC.fs, min: LC.min, max: LC.max, u: U, id: 'lc', k: si === 4 ? qc - 0 : undefined, pts: [
        { label: '2023', value: 0.2, text: '+0.2%', k: k0 }, { label: '2024', value: 0.2, text: '+0.2%', k: k1 }] });
      const len = pt.x1 - pt.x0;                                             // 一條幾乎平的線(句92 先出現,句93 兩點出現後由折線圖接手)
      s += Ch.sheet(`<polygon points="${f(-len / 2)},-7 ${f(len / 2)},-7 ${f(len / 2)},7 ${f(-len / 2)},7" fill="${K.INK}"/>`,
        { x: (pt.x0 + pt.x1) / 2, y: pt.y, u: U, k: si === 4 ? q - 4 : 99, kind: 'flat', id: 'flat', wide: true });
      if (si === 5) s += Ch.srcTag('中國國家統計局', { pal, x: 1820, y: 120, anchor: 'right', fs: 44, u: U, k: q, id: 'src' });
    }

    // ---- 鴿子(左下)----
    const base = K.clip('idle', k), pose = si === 1 ? K.expr(base, 'surprised') : si >= 4 ? K.expr(base, 'doubt') : base;
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_abroad', dur: 33.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
