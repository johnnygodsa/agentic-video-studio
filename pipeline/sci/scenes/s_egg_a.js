/* snack 場景 s_egg_a(句 52–56)加蛋。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 句52:字牌「討論榜 第 8 名 加蛋」彈入,蛋餅、鍋鏟(鏟上一顆荷包蛋)彈入;唸到「加蛋」時紅圈 4 格畫出、鍋鏟下壓、蛋飛到蛋餅上(逐格位置由時間算)。
 * 句53:前一鏡全退;折線圖「蛋類指數(2021=100)」底板與 2021 點出現;唸到「2022」出第二點、「26.4%」出黃牌、「隔年」出 2023 點;右上來源牌「主計總處」。
 * 句54:唸到「2024」出點、「13.6%」出黃牌、「2025」出最後一點。
 * 句55:折線圖縮小上移(不再畫黃牌),下方彈出價牌「? 元」(不寫任何加蛋價格);唸到「加蛋」時左邊彈出字牌「加蛋」。
 * 句56:鴿子從左走入、攤手(shrug);唸到「留給你」彈出小牌「這題留給你」。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [
    { start: 0.06, end: 4.115, text: '討論榜上有一個很妙的項目叫加蛋,它連食物都不算,是一個動作。' },
    { start: 4.235, end: 10.765, text: '蛋在主計總處有自己的指數,2022 年一年就漲了 26.4% 左右,隔年又再漲一成。' },
    { start: 10.885, end: 15.865, text: '可是 2024 年它跌了 13.6% 左右,2025 年繼續往下掉。' },
    { start: 15.985, end: 20.36, text: '蛋價掉下來的那兩年,你有看過哪一家店的加蛋跟著降價嗎?' },
    { start: 20.48, end: 22.78, text: '這個我沒有資料,留給你自己回想。' }];
  const U = 1.43, PU = 1.36;                               // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 }, WALK_N = 8, STEP = 38;
  const RED = 'hsl(6 75% 50%)';
  const VALS = [100, 126.4, 139.9, 120.9, 114.9], YEARS = ['2021', '2022', '2023', '2024', '2025'], VMAX = 150, VMIN = 90;
  const BIG = { x: 240, y: 238, w: 1480, h: 348, fs: 72, lo: VMIN };          // 句53–54:繪圖區 x 240–1720、y 238–586
  const SMALL = { x: 480, y: 206, w: 1240, h: 274, fs: 56, lo: VMIN };        // 句55–56:縮小上移
  const MINUS = '−';
  const PLATE = { x: 960, y: 235, fs: 84 };                                  // 句52 字牌
  const PCK = { x: 1330, y: 620, s: 1.9 }, SPA = { x: 640, y: 640, s: 2.0 }, EGG = { s: 1.1, x0: 774, y0: 500, x1: 1330, y1: 590, h: 148 * 1.1 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || d.text };
    });
  }
  // 詞級時間(估):該詞起始字位置比例 × 句長 + start,取整格
  const wordFrame = (L, i, word) => {
    const l = L[i], n = Math.max(1, l.text.length), p = Math.max(0, l.text.indexOf(word));
    return K.frame(Math.round((l.start + p / n * (l.end - l.start)) * 10) / 10);
  };

  // 折線圖點位(與 Charts.lineChart 內部公式一致)
  function geom(c) {
    const fs = c.fs, tags = VALS.map((v) => Ch.plate(String(v), fs)), labs = YEARS.map((y) => Ch.plate(y, fs));
    const padX = Math.max(...tags.map((p) => p.w), ...labs.map((p) => p.w)) / 2 + 20, r = Math.max(16, fs * 0.3), gapY = Math.max(16, fs * 0.25);
    const yTop = c.y + fs * 1.62 + r + gapY, yBot = c.y + c.h, up = VMAX;
    return { r, labH: labs[0].h, P: VALS.map((v, i) => ({ x: c.x + padX + i * (c.w - 2 * padX) / 4, y: yBot - (v - c.lo) / (up - c.lo) * (yBot - yTop) })) };
  }

  function chart(pal, c, ks) {
    return Ch.lineChart({ pal, x: c.x, y: c.y, w: c.w, h: c.h, fs: c.fs, min: VMIN, max: VMAX, title: '蛋類指數(2021=100)', id: 'lc', k: ks[0],
      pts: VALS.map((v, i) => ({ label: YEARS[i], value: v, k: ks[i] })) });
  }

  // 黃牌放在對應線段中點的正下方、年份標籤列之下(字高 56px;牌頂距線段最低點 ≥ 40px)
  function delta(pal, text, pa, pb, g, c, k, id) {
    const p = Ch.plate(text, 56, { fill: K.YELLOW, padX: 0.8 });
    const top = Math.max(c.y + c.h + 16 + g.labH + 14, Math.max(pa.y, pb.y) + 40);
    return Ch.sheet(p.svg, { x: (pa.x + pb.x) / 2, y: top + p.h / 2, u: U, k, kind: 'delta', id, wide: true });
  }

  function ring(w, h, frac) {
    const c = `<ellipse cx="0" cy="0" rx="${f(w / 2)}" ry="${f(h / 2)}" fill="none" stroke="${RED}" stroke-width="10" stroke-linecap="round"` +
      ` pathLength="100" stroke-dasharray="${f(frac * 100)} 100"/>`;
    return K.paper(c, { x: PLATE.x, y: PLATE.y, k: 'ring', id: 'ring', wide: true });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[3] ? 1 : k < F[4] ? 2 : 3;
    let s = '';

    if (ph === 0) {                                                          // 句52:字牌 + 蛋餅 + 鍋鏟 + 蛋
      const q = k - F[0], kT = wordFrame(L, 0, '加蛋'), j = k - kT, pl = Ch.plate('討論榜 第 8 名 加蛋', PLATE.fs, { chip: pal.main, padX: 1 });
      s += Ch.sheet(pl.svg, { x: PLATE.x, y: PLATE.y, u: U, k: q, kind: 'sheet', id: 'rank', wide: true });
      const pp = K.pop(q - 1);
      s += K.paper(PS.eggPancake(pal), { x: PCK.x, y: PCK.y, scale: PCK.s, sx: pp, sy: pp, k: 'prop', id: 'pancake', enter: q - 1 < 2, wide: true });
      // 鍋鏟:j<0 平放;j0–2 下壓;之後回彈到 10°
      const rot = j < 0 ? 0 : [8, 16, 26, 26, 26, 26, 26, 26, 18, 12][Math.min(j, 9)] || 10;
      const ps = K.pop(q - 2);
      s += K.paper(PS.spatula(pal), { x: SPA.x, y: SPA.y, rot: j >= 10 ? 10 : rot, scale: SPA.s, sx: ps, sy: ps, k: 'prop', id: 'spatula', enter: q - 2 < 2, wide: true });
      // 蛋:j<1 在鏟面上;j1–8 拋物線飛向蛋餅;j8 落地壓扁、j9 回彈
      let ex = EGG.x0, ey = EGG.y0, er = 0, sx = 1, sy = 1;
      if (j >= 1) {
        const a = Math.min(1, j / 8);
        ex = EGG.x0 + (EGG.x1 - EGG.x0) * a;
        ey = EGG.y0 + (EGG.y1 - EGG.y0) * a - 200 * 4 * a * (1 - a);
        er = 14 * a;
      }
      if (j === 8) { sx = 1.2; sy = 0.78; } else if (j === 9) { sx = 0.95; sy = 1.08; }
      const pe = K.pop(q - 3);
      s += K.paper(PS.friedEgg(pal), { x: ex, y: ey + (1 - sy) * EGG.h / 2, rot: er, scale: EGG.s, sx: sx * pe, sy: sy * pe, k: 'prop', id: 'egg', enter: q - 3 < 2, wide: true });
      if (j >= 0) s += ring(pl.w + 120, pl.h + 84, [0.3, 0.62, 0.9, 1][Math.min(j, 3)]);
    } else {                                                                 // 句53 起:折線圖
      const cfg = ph === 1 ? BIG : SMALL, q = k - F[1], g = geom(cfg);
      const kp = [q, k - wordFrame(L, 1, '2022'), k - wordFrame(L, 1, '隔年'), k - wordFrame(L, 2, '2024'), k - wordFrame(L, 2, '2025')];
      s += chart(pal, cfg, kp);
      s += Ch.srcTag('主計總處', { pal, x: 1720, y: 140, anchor: 'right', k: q, id: 'src' });
      if (ph === 1) {                                                        // 句53–54:黃牌
        s += delta(pal, '+26.4%', g.P[0], g.P[1], g, cfg, k - wordFrame(L, 1, '26.4%'), 'd1');
        s += delta(pal, MINUS + '13.6%', g.P[2], g.P[3], g, cfg, k - wordFrame(L, 2, '13.6%'), 'd3');
      }
      if (ph >= 2) {                                                         // 句55 起:價牌「? 元」
        const q3 = k - F[3];
        s += Ch.priceFlip({ pal, x: 1150, y: 722, from: '?', unit: '元', fs: 100, k: q3, id: 'pf' });
        const kA = k - wordFrame(L, 3, '加蛋');
        const pl = Ch.plate('加蛋', 100, { fill: K.YELLOW, padX: 1 });
        s += Ch.sheet(pl.svg, { x: 780, y: 722, u: U, k: kA, kind: 'sheet', id: 'egg', wide: true });
      }
      if (ph === 3) {                                                        // 句56:鴿子攤手、小牌
        const q4 = k - F[4], kArr = F[4] + WALK_N;
        let pose, dx = 0, enter = false;
        if (k < kArr) { pose = K.clip('walk', q4); dx = (kArr - k) * STEP; enter = true; }
        else pose = K.clip('shrug', k - kArr);
        pose = Object.assign({}, pose, { flip: 1 });
        if (k >= kArr) s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
        s += K.pigeon(pose, { x: FOOT.x - dx, y: FOOT.y, scale: PU, id: 'main', enter });
        const tg = Ch.plate('這題留給你', 56, { fill: K.YELLOW, padX: 0.8 });
        s += Ch.sheet(tg.svg, { x: 250, y: 400, u: U, k: k - wordFrame(L, 4, '留給你'), kind: 'sheet', id: 'leave', wide: true });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_egg_a', dur: 22.8, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
