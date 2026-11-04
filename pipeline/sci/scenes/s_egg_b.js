/* snack 場景 s_egg_b(句 57–59)蛋價怎麼來。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–2。淺底,鴿子不出場。
 * 句57:長方桌(場景自畫)+ 左「蛋商」藍小人、右「蛋農代表」紅小人(句首同時彈入);「農業部」處右下來源牌;「蛋價是」處桌上價牌「? 元」彈入、兩人伸手扶住。
 * 句58:退場;磅秤(句首)→「台斤」處一籃蛋落在秤上 →「2024」處日曆牌「2024 年 10 月」→「台北市」處來源牌 →「一台斤」處大數字「34 元」加說明「1 台斤」。
 * 句59:退場;兩欄板:左「老闆:一台斤多少」磅秤、右「你:加一顆多少」荷包蛋(「你在算」處彈入);「你們兩個」處中間畫「≠」牌;之後靜止。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.1, end: 6.25 }, { start: 6.37, end: 13.035 }, { start: 13.155, end: 19.775 }];
  const U = 1.43;
  const BLUE = 'hsl(205 70% 52%)', RED = 'hsl(352 70% 52%)', SKIN = 'hsl(28 60% 80%)';
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const NS = (s) => s.replace('stroke-linejoin="miter"', 'stroke="none"');

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || '' };
    });
  }
  // 詞出現的格:詞在句中的位置比例 × 句長秒數 + start
  function wk(L, i, word) {
    const l = L[i], at = l.text ? l.text.indexOf(word) : -1, r = at >= 0 ? at / l.text.length : 0;
    return K.frame(l.start + Math.round((l.end - l.start) * r * 10) / 10);
  }

  // 長方桌(中心 0,0;x ±340、y -110..110)
  function table() {
    const top = 'hsl(30 55% 56%)', leg = 'hsl(28 50% 38%)';
    return R(-300, -60, 40, 170, leg) + R(260, -60, 40, 170, leg) + R(-340, -110, 680, 50, top) + R(-340, -72, 680, 12, 'hsl(28 50% 44%)').replace('stroke-linejoin="miter"', 'stroke="none"');
  }
  // 手臂:肩 (x1,y1) → 手 (x2,y2),回傳以中點為原點的內容與中點
  function arm(x1, y1, x2, y2, col) {
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy), th = 36;
    const nx = -dy / len * th / 2, ny = dx / len * th / 2, ax = x1 - mx, ay = y1 - my, bx = x2 - mx, by = y2 - my;
    const pts = [[ax + nx, ay + ny], [bx + nx, by + ny], [bx - nx, by - ny], [ax - nx, ay - ny]].map((v) => `${f(v[0])},${f(v[1])}`).join(' ');
    return { x: mx, y: my, svg: `<polygon points="${pts}" fill="${col}"/><circle cx="${f(bx)}" cy="${f(by)}" r="26" fill="${SKIN}"/>` };
  }
  // 「≠」牌(內容以 px,中心在原點)
  function neq(size) {
    const h = size / 2;
    return R(-h, -h, size, size, K.YELLOW) + NS(R(-h * 0.56, -h * 0.34, h * 1.12, h * 0.17, K.INK)) + NS(R(-h * 0.56, h * 0.12, h * 1.12, h * 0.17, K.INK)) +
      `<polygon points="${f(h * 0.2)},${f(-h * 0.74)} ${f(h * 0.46)},${f(-h * 0.74)} ${f(-h * 0.2)},${f(h * 0.74)} ${f(-h * 0.46)},${f(h * 0.74)}" fill="${K.INK}" stroke="none"/>`;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : 2;
    let s = '';

    if (ph === 0) {                                                          // 句57:桌子、兩邊的人、價牌
      const q = k - F[0], p = K.pop(q);
      s += K.paper(table(), { x: 960, y: 670, sx: p, sy: p, k: 'prop', id: 'table', enter: q < 2, wide: true });
      [[420, BLUE, 'pL', '蛋商'], [1500, RED, 'pR', '蛋農代表']].forEach((v) => {
        s += K.paper(PS.person({ main: v[1] }), { x: v[0], y: 480, scale: 2, sx: p, sy: p, k: 'prop', id: v[2], enter: q < 2 });
        const pl = Ch.plate(v[3], 72, { chip: v[1], padX: 0.8 });
        s += Ch.sheet(pl.svg, { x: v[0], y: 214, rot: v[0] < 960 ? -1.5 : 1.5, u: U, k: q, kind: 'plate', id: v[2] + 'N', wide: true });
      });
      s += Ch.srcTag('農業部官員(公視報導)', { pal, x: 1828, y: 770, anchor: 'right', k: k - wk(L, 0, '農業部'), id: 'src' });
      const kt = k - wk(L, 0, '蛋價是');
      s += Ch.priceFlip({ pal, x: 960, y: 400, from: '?', unit: '元', fs: 110, k: kt, id: 'pf' });
      if (kt >= 1) {
        const pa = K.pop(kt - 1);
        [[500, 440, 800, 420, BLUE, 'aL'], [1420, 440, 1120, 420, RED, 'aR']].forEach((v) => {
          const a = arm(v[0], v[1], v[2], v[3], v[4]);
          s += K.paper(a.svg, { x: a.x, y: a.y, sx: pa, sy: pa, k: 'prop', id: v[5], wide: true });
        });
      }
    } else if (ph === 1) {                                                   // 句58:磅秤、蛋、日曆、1 台斤 34 元
      const q = k - F[1], p = K.pop(q);
      s += K.paper(PS.scale(pal), { x: 500, y: 600, scale: 1.8, sx: p, sy: p, k: 'prop', id: 'scale', enter: q < 2 });
      const kc = k - wk(L, 1, '台斤');
      if (kc >= 0) {
        const pc = K.pop(kc);
        s += K.paper(PS.eggCrate(pal), { x: 500, y: 333, scale: 1.53, sx: pc, sy: pc, k: 'prop', id: 'crate', enter: kc < 2, wide: true });
      }
      s += Ch.dateTag({ pal, x: 1600, y: 330, top: '2024 年', main: '10 月', size: 320, rot: 2, k: k - wk(L, 1, '2024'), id: 'date' });
      s += Ch.srcTag('台北市蛋商公會 批發價', { pal, x: 1828, y: 780, anchor: 'right', k: k - wk(L, 1, '台北市'), id: 'src' });
      s += Ch.bigNum({ x: 1100, y: 400, num: '34', unit: '元', note: '1 台斤', fs: 260, k: k - wk(L, 1, '一台斤'), id: 'num' });
    } else {                                                                 // 句59:兩欄板 + ≠
      const q = k - F[2], kr = k - wk(L, 2, '你在算');
      const tc = { pal, x: 960, y: 460, w: 1500, h: 640, gap: 200, fs: 64, id: 'tc' };
      s += Ch.twoCol(Object.assign({ left: { title: '老闆：一台斤多少', k: q }, right: { title: '你：加一顆多少', k: kr } }, tc));
      const pos = Ch.twoColPos(tc), pl = K.pop(q), pr = K.pop(kr - 1);
      if (q >= 1) s += K.paper(PS.scale(pal), { x: pos[0].x, y: 508, scale: 2, sx: pl, sy: pl, k: 'prop', id: 'scaleS', enter: q < 3 });
      if (kr >= 1) s += K.paper(PS.friedEgg(pal), { x: pos[1].x, y: 528, scale: 2.8, sx: pr, sy: pr, k: 'prop', id: 'egg', enter: kr < 3 });
      s += Ch.sheet(neq(160), { x: 960, y: 528, rot: -3, u: U, k: k - wk(L, 2, '你們兩個'), kind: 'sheet', id: 'neq', wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_egg_b', dur: 19.8, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
