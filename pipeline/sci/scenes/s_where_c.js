/* snack 場景 s_where_c(句 83–87)單看一年。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 句83:左上年份牌「2023」;四條(hbars x 430–1840,max 5)臺北 4.01(hi)、高雄 3.07、新北 2.74、臺中 2.64,每 2 格一條;鴿子站左側。
 * 句84:舊的一組 2 格縮小退場;年份牌換成「2025」;新順序一組臺中 1.89、新北 1.78、臺北 1.71、高雄 1.58 每 2 格一條。
 * 句85:年份牌與長條退場;標題牌「外食費 十年」加「自算」小牌;兩條臺北 十年 27.4%、全國 26.6%(max 40)。
 * 句86:年份牌「2025 外食費」;兩條臺中 4.0%、全國 3.4%(max 5)。
 * 句87:圖表退場;鴿子走到右邊、轉身,把行李箱往左推出畫面(逐格位置由格數計算),最後靜止 ≥ 1 秒。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.08, end: 7.27 }, { start: 7.39, end: 14.5 }, { start: 14.63, end: 20.18 }, { start: 20.3, end: 25.23 }, { start: 25.35, end: 27.42 }];
  const U = 1.43, PU = 1.36, SU = 1.5;               // 紙片倍率、鴿子倍率(高約 309px)、行李箱倍率(寬約 270px)
  const FOOT = { x: 245, y: 820 };
  const CITY = { 臺北: 'hsl(205 70% 52%)', 新北: 'hsl(130 45% 45%)', 臺中: 'hsl(25 90% 58%)', 高雄: 'hsl(280 50% 55%)' };
  const BX = 430, BW = 1410;
  const TAG = { x: 245, y: 270, size: 240 };         // 年份牌(左上,高約 259px,距鴿子頭頂 ≥ 100px)
  const WALK_N = 8, WALK_DX = 390, PUSH_AT = 12, SUIT_X = 240, PIG_X = FOOT.x + WALK_DX, PUSH_STEP = 10, PUSH_N = 9;
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  // 四城市長條(max 5):order = [[城市, 值, 文字, hi]],每條 kk(i) 格出現;q<0 全不畫
  function cityBars(pal, order, id, kk) {
    return Ch.hbars({ pal, x: BX, y: 176, w: BW, rowH: 116, gap: 40, labelW: 320, fs: 72, numFs: 88, max: 5, id, bars: order.map((o, i) => (
      { label: o[0], value: o[1], text: o[2], color: CITY[o[0]], hi: !!o[3], k: kk(i) })) });
  }
  // 兩條長條
  function twoBars(pal, rows, id, max, labelW, kk) {
    return Ch.hbars({ pal, x: BX, y: 290, w: BW, rowH: 160, gap: 60, labelW, fs: 72, numFs: 100, max, id, bars: rows.map((r, i) => (
      { label: r[0], value: r[1], text: r[2], color: r[3], grey: !r[3], k: kk(i) })) });
  }
  const yearTag = (pal, main, top, k, id) => Ch.dateTag({ x: TAG.x, y: TAG.y, size: TAG.size, top, main, color: pal.main, u: U, k, id });

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : 4;
    const q = k - F[ph];
    let s = '';

    if (ph === 0) {                                                          // 句83:2023 四城市
      s += yearTag(pal, '2023', null, q, 'tag');
      s += cityBars(pal, [['臺北', 4.01, '4.01%', true], ['高雄', 3.07, '3.07%'], ['新北', 2.74, '2.74%'], ['臺中', 2.64, '2.64%']], 'b83', (i) => q - 1 - i * 2);
    } else if (ph === 1) {                                                   // 句84:舊組 2 格退場,2025 新順序
      s += yearTag(pal, '2025', null, q, 'tag');
      if (q < 2) {
        const sc = q === 0 ? 0.8 : 0.55, cx = BX + BW / 2, cy = 176 + (4 * 116 + 3 * 40) / 2;
        s += `<g transform="translate(${f(cx)} ${f(cy)}) scale(${sc}) translate(${f(-cx)} ${f(-cy)})">` +
          cityBars(pal, [['臺北', 4.01, '4.01%', true], ['高雄', 3.07, '3.07%'], ['新北', 2.74, '2.74%'], ['臺中', 2.64, '2.64%']], 'b83', () => undefined) + '</g>';
      }
      s += cityBars(pal, [['臺中', 1.89, '1.89%'], ['新北', 1.78, '1.78%'], ['臺北', 1.71, '1.71%'], ['高雄', 1.58, '1.58%']], 'b84', (i) => q - 2 - i * 2);
    } else if (ph === 2) {                                                   // 句85:外食費十年
      const pl = Ch.plate('外食費 十年', 72, { chip: pal.main, padX: 1 }), sp = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
      const tx = BX + pl.w / 2, sx = BX + pl.w + 24 + sp.w / 2;
      s += Ch.sheet(pl.svg, { x: tx, y: 190, u: U, k: q, kind: 'sheet', id: 'title', wide: true });
      s += Ch.sheet(sp.svg, { x: sx, y: 190, u: U, k: q - 4, kind: 'src', id: 'self', wide: true });
      s += twoBars(pal, [['臺北 十年', 27.4, '27.4%', CITY.臺北], ['全國', 26.6, '26.6%', null]], 'b85', 40, 400, (i) => q - i * 4);
    } else if (ph === 3) {                                                   // 句86:2025 外食費
      s += yearTag(pal, '2025', '外食費', q, 'tag');
      s += twoBars(pal, [['臺中', 4.0, '4.0%', CITY.臺中], ['全國', 3.4, '3.4%', null]], 'b86', 5, 320, (i) => q - 2 - i * 4);
    }

    // 鴿子:左側站著;句87 走到右邊、轉身、把行李箱往左推出畫面
    const idle = (kk) => K.expr(K.clip('idle', kk), 'normal');
    let pose, px = FOOT.x, enter = false, ground = { x: FOOT.x + 20, w: 340 };
    if (ph < 4) {
      pose = Object.assign({}, idle(k), { flip: 1 });
    } else {
      const j = q, i = j - PUSH_AT;
      ground = { x: 460, w: 740 };
      if (j < WALK_N) { pose = Object.assign({}, K.clip('walk', j), { flip: 1 }); px = FOOT.x + (j + 1) * WALK_DX / WALK_N; enter = true; }
      else {
        px = PIG_X;
        if (j === WALK_N) pose = K.clip('turn', 2);
        else if (j === WALK_N + 1) pose = K.clip('turn', 1);
        else if (i < 0) pose = idle(0);
        else if (i < PUSH_N) { pose = K.expr(K.clip('walk', i), 'normal'); px = PIG_X - PUSH_STEP * (i + 1); }
        else { pose = idle(0); px = PIG_X - PUSH_STEP * PUSH_N; }
      }
      const ks = j - (WALK_N + 1);                                           // 行李箱:轉身時彈入,之後推出
      if (ks >= 0) {
        const sh = i < 0 ? 0 : 5 * (i + 1) * (i + 1);
        const sxp = SUIT_X - (i < 0 ? 0 : PUSH_STEP * Math.min(i + 1, PUSH_N)) - sh, p = K.pop(ks);
        if (sxp > -260) s += K.paper(PS.LIST.suitcase.fn(pal), { x: sxp, y: FOOT.y - 14 - 94 * SU, scale: SU, sx: p, sy: p, k: 'prop', id: 'suitcase', enter: true });      }
    }
    s += K.ground({ x: ground.x, y: FOOT.y + 4, w: ground.w, h: 22, u: U, pal });
    s += K.pigeon(pose, { x: px, y: FOOT.y, scale: PU, id: 'main', enter });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_where_c', dur: 28.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
