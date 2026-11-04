/* salary 場景 s_happy_b(句 28–32)兩邊都對一半。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 版面沿用 PropsSalary.RANK_LAYOUT 的鴿子欄(左,面向右、全場在位),舞台在 x 450–1800。
 * 開頭(第 0 格)= s_happy_a 末格:基林斯沃斯名牌、手機三則通知、2021 日曆牌、「3 萬多 人」大數字卡、來源牌 PNAS 2021;第 1–2 格縮掉、第 3 格全空,
 * 同格折線圖底、軸標題、刻度與康納曼的線(7.5 萬美元變平、黃牌「7.5 萬美元」)彈入。
 * 句28:藍線(基林斯沃斯 2021)由左至右畫出,一路往上不平;詞「天花板」黃牌「沒有天花板」;線畫完後兩條線的名牌彈出。來源牌 PNAS 2021。
 * 句29:襯底紙蓋住圖,兩張剪影名牌(康納曼、基林斯沃斯)一格一步走向同一張桌子;詞「2023」日曆牌彈出。來源牌 PNAS 2023。
 * 句30:襯底紙與名牌退場,圖重畫;最底下紅線(最不開心的兩成)畫到 10 萬美元變平;詞「十萬美元」處垂直虛線、黃點、刻度「10 萬」轉黃。
 * 句31:藍線(其他人)直直往上;詞「最開心」處綠線畫出,10 萬之後更陡;詞「更快」處 10 萬後那段轉黃。
 * 句32:鴿子頭上笑臉計量表彈入,指針晃來晃去。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale, FS = 56;
  const DEF = [
    { start: 0.01, end: 3.37, text: '他的資料裡沒有天花板,錢越多,平均就越開心。' },
    { start: 3.49, end: 9.795, text: '兩邊的結果對不起來,2023 年康納曼和基林斯沃斯乾脆一起回頭重算基林斯沃斯的資料。' },
    { start: 9.915, end: 14.54, text: '最不開心的那兩成人,年收入到十萬美元左右就不會再更開心了。' },
    { start: 14.66, end: 20.095, text: '其他人大致上是錢越多越開心,最開心的那一群,過了十萬美元反而漲得更快。' },
    { start: 20.215, end: 23.44, text: '錢買不買得到快樂,要先看你本來是哪一種人呀。' }];
  const f = (x) => +(+x).toFixed(2);
  // 圖(px):襯底紙 x 450–1800、y 170–710(鴿子欄在左);資料 x = 年收入(萬美元)0–15、y = 開心程度 0–1
  const PANEL = { x0: 450, y0: 170, w: 1350, h: 540 };
  const X0 = 620, PXW = 70, YB = 690, YH = 400;
  const xv = (v) => X0 + PXW * v, yv = (h) => YB - YH * h;
  const RIGHT = 1780;                                             // 端點牌的右緣
  const COL = { kah: K.INK, kil: 'hsl(205 72% 44%)', low: 'hsl(4 72% 50%)', high: 'hsl(135 62% 34%)' };
  const FN = {
    kah: (x) => (x < 7.5 ? 0.2 + 0.5 * (1 - Math.pow(1 - x / 7.5, 2)) : 0.7),
    kil: (x) => 0.28 + 0.62 * Math.log(1 + x / 2.5) / Math.log(7),
    low: (x) => (x < 10 ? 0.06 + 0.11 * (1 - Math.pow(1 - x / 10, 2)) : 0.17),
    mid: (x) => 0.26 + 0.34 * x / 15,
    high: (x) => (x < 10 ? 0.62 + 0.018 * x : 0.8 + 0.04 * (x - 10)),
  };
  const DRAW = 16;                                                // 一條線畫完的格數
  const CARD = { w: 336, h1: 230, h2: FS * 1.62 };
  const TABLE = { x: 1125, y: 657, top: 640 };
  const WALK = { steps: 8, per: 2 };                              // 走 8 步、每步 2 格
  const OUT = [0.6, 0.25];                                        // 退場縮放(第 3 格消失)
  const OUT0 = [1.1, 0.55];                                       // 開頭收掉 s_happy_a 的牌:放大一點再縮小,第三格消失
  const COVER = { x: 1125, y: 497.5, w: 1350, h: 665 };            // 上緣 165、下緣 830:陰影不進字幕帶
  const COVER_POP = [0.55, 0.9, 1];
  const WOBBLE = [0.5, 0.72, 0.94, 0.72, 0.5, 0.28, 0.06, 0.28];  // 計量表指針值,每 2 格換一個

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const text = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const paperPx = (content, o) => K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
    { x: o.x, y: o.y, rot: o.rot, scale: U, sx: o.sx, sy: o.sy, k: o.kind, id: o.id, enter: o.enter, wide: true });
  // 進場 kin(出現後第幾格,<0 未出現)、退場 kout(開始退場後第幾格,<0 未退場)
  function place(content, o, kin, kout, pops) {
    let sc = kin < 0 ? 0 : pops ? pops[Math.min(kin, pops.length - 1)] : K.pop(kin);
    if (kout >= 0) sc = kout < OUT.length ? OUT[kout] : 0;
    if (sc <= 0) return '';
    return paperPx(content, Object.assign({}, o, { sx: sc, sy: sc, enter: kin < 2 || (kout >= 0 && kout < 2) }));
  }
  // s_happy_a 末格的牌:kIn = 99(已彈完)、kOut = 開始縮掉後第幾格(<0 未縮)
  function pieceA(content, o, kOut) {
    let p = 1;
    if (kOut >= 0) { if (kOut >= OUT0.length) return ''; p = OUT0[kOut]; }
    return paperPx(content, Object.assign({}, o, { sx: p, sy: p, enter: kOut >= 0 }));
  }
  function goneA(str, cx, cy, kOut) {
    if (kOut < 0) return str;
    if (kOut >= OUT0.length) return '';
    const p = OUT0[kOut];
    return `<g transform="translate(${f(cx)} ${f(cy)}) scale(${p}) translate(${f(-cx)} ${f(-cy)})">${str}</g>`;
  }
  function cardA(pal, name) {                                     // 同 s_happy_a 的名牌
    const w = 360, h = 390, top = -h / 2 + 24;
    return rect(-w / 2, -h / 2, w, h, K.PAPER) + rect(-140, top, 280, 236, pal.pad) +
      `<circle cx="0" cy="-76" r="46" fill="${K.INK}"/>` +
      `<path d="M -96 66 V 14 Q -96 -22 -56 -24 H 56 Q 96 -22 96 14 V 66 Z" fill="${K.INK}"/>` +
      rect(-w / 2, 92, w, h / 2 - 92, pal.main) + text(name, 0, 143, 64, pal.onMain);
  }

  // 右緣對齊的字牌;fill/ink 指定色牌
  function tag(s, right, y, kin, id, o) {
    o = o || {};
    const p = Ch.plate(s, FS, { fill: o.fill, ink: o.ink });
    return Ch.sheet(p.svg, { x: (o.anchor === 'left' ? right + p.w / 2 : right - p.w / 2), y, rot: o.rot, u: U, k: kin, kind: 'sheet', id, wide: true });
  }

  const pathD = (fn, a, b) => { const pts = []; for (let v = a; v <= b + 1e-6; v += 0.5) pts.push(`${f(xv(v))} ${f(yv(fn(v)))}`); return 'M ' + pts.join(' L '); };
  // 折線:p = 畫出比例(0–1,依 x 由左至右);紙白底線加色線
  function curve(fn, col, p, id, a, b, w) {
    if (p <= 0) return '';
    const d = pathD(fn, a == null ? 0 : a, b == null ? 15 : b), lw = w || 14;
    const dash = (c, sw) => `<path d="${d}" pathLength="100" fill="none" stroke="${c}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"` +
      ` stroke-dasharray="${f(Math.min(1, p) * 100)} 200"/>`;
    return Ch.sheet(dash(K.PAPER, lw + 10) + dash(col, lw), { x: 0, y: 0, u: U, kind: 'curve', id, wide: true });
  }
  const prog = (k) => (k < 0 ? 0 : Math.min(1, (k + 1) / DRAW));

  // 襯底紙圖框、軸標題與刻度(全場)
  // kb = 圖底出現後第幾格(<0 未出現);軸標題在刻度列左側(x 450–858),5 萬刻度牌左緣 ≥ 888,兩者不相交
  function chartBase(pal, kHi, kb) {
    if (kb < 0) return '';
    let s = Ch.sheet(rect(-PANEL.w / 2, -PANEL.h / 2, PANEL.w, PANEL.h, pal.pad) + rect(-PANEL.w / 2, PANEL.h / 2 - 14, PANEL.w, 14, K.INK),
      { x: PANEL.x0 + PANEL.w / 2, y: PANEL.y0 + PANEL.h / 2, u: U, k: kb, kind: 'lineBase', id: 'base', wide: true });
    s += tag('開心程度', PANEL.x0 + 24, 222, kb, 'yT', { fill: K.YELLOW, anchor: 'left', rot: -1.5 });
    s += tag('年收入(美元)', PANEL.x0, 771, kb, 'xT', { anchor: 'left' });
    [5, 10, 15].forEach((v) => {
      const hi = v === 10 && kHi >= 0;
      s += tag(v + ' 萬', xv(v) + Ch.plate(v + ' 萬', FS).w / 2, 771, kb, 'tick' + v, hi ? { fill: K.INK, ink: K.YELLOW } : {});
    });
    return s;
  }

  // 剪影名牌(不畫臉):上半色塊加頭與肩膀剪影,下半名字牌
  function nameCard(pal, name) {
    const w = CARD.w, H = CARD.h1 + CARD.h2, top = -H / 2, yb = top + CARD.h1, dark = `hsl(${pal.h} 25% 28%)`;
    return rect(-w / 2, top, w, CARD.h1, `hsl(${pal.h} 42% 74%)`) +
      `<circle cx="0" cy="${f(top + 88)}" r="46" fill="${dark}" stroke="none"/>` +
      `<path d="M -104 ${f(yb)} Q -104 ${f(yb - 92)} 0 ${f(yb - 92)} Q 104 ${f(yb - 92)} 104 ${f(yb)} Z" fill="${dark}" stroke="none"/>` +
      rect(-w / 2, yb, w, CARD.h2, K.PAPER) + text(name, 0, yb + CARD.h2 / 2, FS, K.INK);
  }
  const table = () => rect(-450, -17, 900, 34, 'hsl(24 55% 40%)') + rect(-400, 17, 30, 120, 'hsl(24 55% 30%)') + rect(370, 17, 30, 120, 'hsl(24 55% 30%)');

  function pigeonPose(k, name) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kC = k - F[2];                                          // 句30 起:襯底紙與名牌退場
    const kB = k - (F[0] + 3);                                    // 圖底出現後第幾格(第 0–2 格收掉 s_happy_a 的牌)
    let s = '';

    // 來源牌(論文年份與期刊):第 0 格同 s_happy_a 末格
    s += k < F[1] ? Ch.srcTag('PNAS 2021 論文 基林斯沃斯', { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src' })
      : Ch.srcTag('PNAS 2023 論文 基林斯沃斯與康納曼', { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src', k: k - F[1] });

    // 開頭:s_happy_a 末格的牌(基林斯沃斯名牌、手機三則通知、2021 日曆牌、3 萬多人)第 1 格起縮掉
    if (k < F[0] + 3) {
      const kO = k - (F[0] + 1);
      s += goneA(Ch.dateTag({ x: 1500, y: 330, top: '論文', main: '2021', size: 220, rot: 2, k: 99, pal, id: 'd21' }), 1500, 330, kO);
      s += pieceA(cardA(pal, '基林斯沃斯'), { x: 660, y: 440, rot: -1.5, kind: 'card', id: 'cardK' }, kO);
      s += pieceA(Ch.icon({ svg: PT.phone(pal, { screen: pal.pad }), w: 100, h: 194 }, 0, 0, 460), { x: 1080, y: 450, kind: 'prop', id: 'phone' }, kO);
      let nt = '';
      [[330, -2], [430, 1.5], [530, -1]].forEach((b, i) => {
        const p = Ch.plate('你現在開心嗎?', FS, { chip: pal.main, padX: 0.8 });
        nt += Ch.sheet(p.svg, { x: 1080, y: b[0], rot: b[1], u: U, k: 99, kind: 'sheet', id: 'nt' + i, wide: true });
      });
      s += goneA(nt, 1080, 430, kO);
      s += goneA(Ch.bigNum({ x: 1500, y: 700, num: '3 萬多', unit: '人', fs: 150, rot: 1, k: 99, id: 'n3' }), 1500, 700, kO);
    }

    // 圖框、軸標題與刻度
    s += chartBase(pal, k - wordK(L[2], '十萬美元'), kB);

    if (k < F[2]) {
      // 句28(與句29 被蓋住的底圖):康納曼的線(與圖底同格出現)與藍線(圖底後 1 格起畫)
      if (kB >= 0) {
        s += curve(FN.kah, COL.kah, 1, 'kah');
        s += tag('7.5 萬美元', 1230 + Ch.plate('7.5 萬美元', FS).w / 2, 485, kB, 'k75', { fill: K.YELLOW, rot: -1.5 });
        s += tag('康納曼', RIGHT, 485, kB, 'kahL', { fill: COL.kah, ink: K.PAPER, rot: 1 });
      }
      const kS = F[0] + 4;                                        // 藍線起畫格
      s += curve(FN.kil, COL.kil, prog(k - kS), 'kil');
      const kw = Math.max(wordK(L[0], '天花板'), kS + 2);
      if (k >= kw) s += tag('沒有天花板', 1130 + Ch.plate('沒有天花板', FS).w / 2, 235, k - kw, 'nolid', { fill: K.YELLOW, rot: -1.5 });
      if (k >= kS + DRAW) s += tag('基林斯沃斯', RIGHT, 256, k - kS - DRAW, 'kilL', { fill: COL.kil, ink: K.PAPER, rot: -1 });
    } else {
      // 句30–32:三條線
      const lowK = kC, midK = k - F[3], hiK = k - wordK(L[3], '最開心');
      s += curve(FN.low, COL.low, prog(lowK), 'low');
      if (lowK >= DRAW) s += tag('最不開心的兩成', RIGHT, 554, lowK - DRAW, 'lowL', { fill: COL.low, ink: K.PAPER, rot: 1 });
      const kb = wordK(L[2], '十萬美元');
      if (k >= kb) {                                              // 10 萬美元:垂直虛線、黃點
        let g = '';
        for (let y = 290; y < YB; y += 44) g += rect(xv(10) - 4, y, 8, 26, K.INK);
        s += Ch.sheet(g, { x: 0, y: 0, u: U, k: k - kb, kind: 'guide', id: 'guide', wide: true });
        s += Ch.sheet(`<circle cx="${f(xv(10))}" cy="${f(yv(FN.low(10)))}" r="22" fill="${K.YELLOW}"/><circle cx="${f(xv(10))}" cy="${f(yv(FN.low(10)))}" r="8" fill="${K.INK}" stroke="none"/>`,
          { x: 0, y: 0, u: U, k: k - kb, kind: 'dot', id: 'bend' });
      }
      s += curve(FN.mid, COL.kil, prog(midK), 'mid');
      if (midK >= 4) s += tag('其他人', 860 - Ch.plate('其他人', FS).w / 2, 490, midK - 4, 'midL', { fill: COL.kil, ink: K.PAPER, rot: -1, anchor: 'left' });
      s += curve(FN.high, COL.high, prog(hiK), 'high');
      if (hiK >= DRAW) s += tag('最開心的一群', RIGHT, 215, hiK - DRAW, 'highL', { fill: COL.high, ink: K.PAPER, rot: 1 });
      const kf = wordK(L[3], '更快');
      if (k >= kf) s += curve(FN.high, K.YELLOW, 1, 'hiY', 10, 15, 16);
    }

    // 句29:兩張名牌走向桌子(舞台 x 450–1800)
    const kw0 = k - (F[1] + 2), step = Math.max(0, Math.min(WALK.steps, Math.floor(kw0 / WALK.per))), bob = kw0 >= 0 && step < WALK.steps && step % 2 === 1 ? -14 : 0;
    if (k >= F[1] && k < F[2] + OUT.length) {
      const ko = kC >= 0 ? kC : -1;
      s += place(rect(-COVER.w / 2, -COVER.h / 2, COVER.w, COVER.h, pal.pad), { x: COVER.x, y: COVER.y, kind: 'cover', id: 'cover' }, k - F[1], ko, COVER_POP);
      const kt = k - (F[1] + 2);
      s += place(nameCard(pal, '康納曼'), { x: 640 + (940 - 640) * step / WALK.steps, y: 478 + bob, rot: bob ? -2 : 1, kind: 'nameCard', id: 'cardH' }, kt, ko);
      s += place(nameCard(pal, '基林斯沃斯'), { x: 1650 + (1310 - 1650) * step / WALK.steps, y: 345 + (478 - 345) * step / WALK.steps + bob, rot: bob ? 2 : -1, kind: 'nameCard', id: 'cardK' }, k - F[1], ko);
      s += place(table(), { x: TABLE.x, y: TABLE.y, rot: 0, kind: 'table', id: 'table' }, kt, ko);
      const k23 = wordK(L[1], '2023');
      if (k >= k23 && ko < 0) s += Ch.dateTag({ x: 1125, y: 320, top: '論文', main: '2023', size: 190, rot: -3, k: k - k23, id: 'd23' });
    }

    // 鴿子:整場在左欄(同 s_happy_a、s_rank_b)
    const P = RL.pigeon;
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    s += K.pigeon(pigeonPose(k, 'look'), { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    // 句32:鴿子頭上的笑臉計量表
    if (k >= F[4]) {
      const km = k - F[4];
      if (km >= 0) {
        const j = Math.floor(km / 2), v = WOBBLE[j % WOBBLE.length];
        s += K.paper(PS.meter(pal, { v }), { x: P.x, y: 320, rot: [-4, 0, 4, 0][j % 4], scale: 1.1, sx: K.pop(km), sy: K.pop(km), k: 'prop', id: 'meter', enter: km < 2 });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_happy_b', dur: 25, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
