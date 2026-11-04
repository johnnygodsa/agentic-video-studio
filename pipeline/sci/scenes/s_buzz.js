/* snack 場景 s_buzz(句 20–23)網路溫度計討論榜。淺底。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 句20:手機(中央)彈入、「網路溫度計」牌、四個對話泡每 8 格冒一個。
 * 句21:泡與牌收掉、手機縮到左上角(3 格頓步);標題「2025 漲價討論榜」;前五名(滷肉飯…牛肉麵)在各詞起點逐列彈入。
 * 句22:後五名(肉圓、蚵仔煎、加蛋、蛋餅、臭豆腐)在各詞起點彈入。兩欄各五列(左 1–5、右 6–10),每列 = 名次牌 + 圖解 + 品名。
 * 句23:便條「算的是討論量」「不代表正負評價」貼在標題下 + 右上來源牌;「量到的是」起手機退場、十列縮成左側一欄(3 格頓步)並冒出對話泡;
 *       「跟實際」起「≠」與價牌「漲多少」彈出;之後靜止。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const DEF = [
    { start: 0.05, end: 4.64, text: '回到現在,網路溫度計每年會統計哪些小吃的漲價被討論得最兇。' },
    { start: 4.76, end: 9.35, text: '2025 年那一版的前五名是滷肉飯、水餃、雞排、手搖飲和牛肉麵。' },
    { start: 9.47, end: 12.44, text: '後面還有肉圓、蚵仔煎、加蛋、蛋餅和臭豆腐。' },
    { start: 12.56, end: 21.46, text: '不過要講清楚,這個榜算的是網路上的討論量,它自己也寫了不代表正負評價,量到的是大家多愛講,跟實際漲多少沒有關係。' }];
  const U = 1.4;
  const ITEMS = [['滷肉飯', 'braisedPorkRice'], ['水餃', 'dumplings'], ['雞排', 'chickenCutlet'], ['手搖飲', 'bobaCup'], ['牛肉麵', 'beefNoodle'],
    ['肉圓', 'meatball'], ['蚵仔煎', 'oysterOmelet'], ['加蛋', 'friedEgg'], ['蛋餅', 'eggPancake'], ['臭豆腐', 'stinkyTofu']];
  const BUBBLES = [['又漲了?', 560, 330, 'br', -2], ['也太貴了吧', 1400, 330, 'bl', 2], ['不會吧', 520, 650, 'tr', 1.5], ['怎麼又漲價', 1440, 660, 'tl', -1.5]];
  const PHONE = { x0: 960, y0: 500, s0: 2.2, x1: 150, y1: 190, s1: 0.95 };
  // 兩種版面:EXP = 兩欄五列(含圖解)、CMP = 左側單欄(無圖解)
  const EXP = { h: 88, tile: 96, ic: 84, fs: 64, pw: 300, cx: [470, 1290], y0: 374, pitch: 96 };
  const CMP = { h: 72, tile: 80, ic: 0, fs: 56, pw: 206, cx: 250, y0: 124, pitch: 72 };
  const STEPS = [0.35, 0.7, 1];
  const f = (x) => +(+x).toFixed(2), lerp = (a, b, s) => a + (b - a) * s;
  const R = (x, y, w, h, fill, ns) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ns ? ' stroke="none"' : ' stroke-linejoin="miter"'}/>`;
  const T = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="${anchor || 'middle'}"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || d.text };
    });
  }
  // 詞在句中的起點(位置比例估計,對齊 0.1 秒)→ 格編號
  const wordFrame = (l, word) => {
    const i = l.text.indexOf(word), n = l.text.length;
    return K.frame(l.start + (i < 0 ? 0 : i / n) * (l.end - l.start));
  };

  // 一列內容(中心在原點):名次牌 + 圖解 + 品名;g 為版面參數(可為兩版之間的內插)
  function rowContent(i, g, pal) {
    const ic = g.ic > 8 ? g.ic : 0, W = g.tile + 8 + (ic ? ic + 8 : 0) + 6 + g.pw, x0 = -W / 2, h = g.h;
    const n = i + 1, nf = n < 10 ? Math.round(h * 0.78) : 56;
    let c = R(x0, -h / 2, W, h, K.PAPER) + R(x0, -h / 2, g.tile, h, pal.main, true) + T(String(n), x0 + g.tile / 2, 2, nf, pal.onMain);
    if (ic) {
      const it = PS.LIST[ITEMS[i][1]];
      c += Ch.icon({ svg: it.fn(pal, {}), w: it.w, h: it.h }, x0 + g.tile + 8 + ic / 2, 0, ic);
    }
    return { svg: c + T(ITEMS[i][0], x0 + g.tile + 8 + (ic ? ic + 8 : 0) + 6, 0, g.fs, K.INK, 'start'), W };
  }
  function rowGeom(i, s) {
    const e = EXP, c = CMP, ex = e.cx[i < 5 ? 0 : 1], ey = e.y0 + (i % 5) * e.pitch, cy = c.y0 + i * c.pitch;
    return { g: { h: lerp(e.h, c.h, s), tile: lerp(e.tile, c.tile, s), ic: lerp(e.ic, c.ic, Math.min(1, s / 0.7)), fs: lerp(e.fs, c.fs, s), pw: lerp(e.pw, c.pw, s) },
      x: lerp(ex, c.cx, s), y: lerp(ey, cy, s) };
  }

  // 「≠」牌:黃底墨色符號(不依賴字型)
  function neq() {
    return R(-75, -75, 150, 150, K.YELLOW) + R(-44, -26, 88, 16, K.INK, true) + R(-44, 10, 88, 16, K.INK, true) +
      `<polygon points="-36,46 -14,46 36,-46 14,-46" fill="${K.INK}" stroke="none"/>`;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const WF = ITEMS.map((it, i) => wordFrame(L[i < 5 ? 1 : 2], it[0]));
    const FC = wordFrame(L[3], '量到的是'), FP = wordFrame(L[3], '跟實際');
    let s = '';

    if (k < F[1]) {                                                          // 句20:手機 + 牌 + 對話泡
      const q = k - F[0];
      s += K.paper(PT.LIST.phone.fn(pal, {}), { x: PHONE.x0, y: PHONE.y0, scale: PHONE.s0, sx: K.pop(q), sy: K.pop(q), k: 'prop', id: 'phone', enter: q < 2 });
      const p = Ch.plate('網路溫度計', 80, { fill: K.INK, ink: K.PAPER, chip: pal.main, padX: 1 });
      s += Ch.sheet(p.svg, { x: 960, y: 170, u: U, k: q - 3, kind: 'sheet', id: 'tag', wide: true });
      BUBBLES.forEach((b, i) => {
        s += Ch.bubble(b[0], { x: b[1], y: b[2], fs: 64, tail: b[3], rot: b[4], k: q - (8 + 8 * i), id: 'bub' + i });
      });
    } else {
      // 手機:句21 縮到左上角(3 格頓步),句23 開始縮小退場
      const j = k - F[1], st = STEPS[Math.min(Math.max(j, 0), 2)];
      const pe = k < FC ? 1 : [0.6, 0.3][k - FC] || 0;
      if (pe > 0) {
        const sc = lerp(PHONE.s0, PHONE.s1, st) * pe;
        s += K.paper(PT.LIST.phone.fn(pal, {}), { x: lerp(PHONE.x0, PHONE.x1, st), y: lerp(PHONE.y0, PHONE.y1, st), scale: sc, k: 'prop', id: 'phone' });
      }
      const tp = Ch.plate('2025 漲價討論榜', 68, { fill: K.INK, ink: K.PAPER, chip: pal.main, padX: 1 });
      s += Ch.sheet(tp.svg, { x: 960, y: 138, u: U, k: k - (F[1] + 3), kind: 'sheet', id: 'title', wide: true });
      // 十列:兩欄 → (句23)左側單欄
      const sc = k < FC ? 0 : STEPS[Math.min(k - FC, 2)];
      ITEMS.forEach((it, i) => {
        const rg = rowGeom(i, sc), rc = rowContent(i, rg.g, pal);
        s += Ch.sheet(rc.svg, { x: rg.x, y: rg.y, u: U, k: k - WF[i], kind: 'rank', id: 'r' + i, wide: true });
      });
      if (k >= F[3]) {                                                       // 句23:便條 + 來源牌
        const q = k - F[3];
        const n1 = Ch.plate('算的是討論量', 56, { fill: K.YELLOW, padX: 1 }), n2 = Ch.plate('不代表正負評價', 56, { fill: K.YELLOW, padX: 1 });
        const left = 960 - (n1.w + n2.w + 36) / 2;
        s += Ch.sheet(n1.svg, { x: left + n1.w / 2, y: 262, rot: -1.2, u: U, k: q, kind: 'note', id: 'n1', wide: true });
        s += Ch.sheet(n2.svg, { x: left + n1.w + 36 + n2.w / 2, y: 262, rot: 1.2, u: U, k: q - 2, kind: 'note', id: 'n2', wide: true });
        s += Ch.srcTag('網路溫度計 2025', { pal, x: 1828, y: 130, anchor: 'right', k: q - 4, id: 'src' });
        s += Ch.bubble('大家多愛講', { x: 760, y: 560, fs: 76, tail: 'br', rot: -1, k: k - (FC + 4), id: 'bubC' });
        s += Ch.sheet(neq(), { x: 1230, y: 560, u: U, k: k - FP, kind: 'sheet', id: 'neq' });
        s += Ch.priceFlip({ pal, x: 1530, y: 580, from: '漲多少', fs: 90, k: k - (FP + 2), id: 'pf' });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_buzz', dur: 21.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
