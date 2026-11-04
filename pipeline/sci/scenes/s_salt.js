/* salary 場景 s_salt(句 33–35)薪水與鹽;「?」記號彈入。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–2。
 * 接在 s_happy_b 之後:第 0 格 = s_happy_b 末格(三條折線圖與軸牌、10 萬虛線、PNAS 2023 來源牌、左欄鴿子與頭上笑臉計量表);
 * 第 1–2 格只收圖表(0.6、0.3)、計量表與來源牌,第 3 格起新東西彈入。鴿子整場在左欄(RANK_LAYOUT),舞台在 x 450–1800。
 * 來源牌「Merriam-Webster 用法說明」第 3 格、右上「?」記號第 4 格彈入,全場不退。
 * 句33:虛線對話泡「士兵的薪水是鹽」(傳言)第 3 格彈入;詞「鹽」鹽袋;詞「古羅馬」羅馬頭盔。
 * 句34:三件退場;句首起牌「拉丁文」加字牌 salarium;詞「鹽」鹽罐加字牌 sal;詞「變來」箭頭 sal → salarium;
 *       詞「文獻」字牌組退場,卷軸彈入、石碑與放大鏡跟著掃過(每 2 格一步、八步);詞「找不到」黃牌;詞「士兵」鹽袋;詞「紀錄」鹽袋變灰。
 * 句35:詞「1879」卷軸、放大鏡、黃牌、鹽袋、石碑退場,同格 1879 日曆牌加第一本厚辭典彈入;詞「後來」起每 2 格複製出一本辭典,共六本。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js'),
    SN = Wn.PropsSnack || require('../props_snack.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale, FS = 56;
  const DEF = [
    { start: 0.06, end: 6.39, text: '對了,說到薪水,網路上常看到一個說法,英文的薪水這個字來自鹽,因為古羅馬士兵領的是鹽。' },
    { start: 6.51, end: 13.64, text: '這個字確實是從拉丁文的鹽變來的,可是羅馬留下來的文獻裡,找不到士兵拿鹽當薪水的紀錄。' },
    { start: 13.76, end: 20.8, text: '這個故事比較可能是後人看字面推出來的,1879 年的一本拉丁文辭典這樣寫,後來大家就一直照抄。' }];
  const f = (x) => +(+x).toFixed(2);
  const ST = 3;                                                   // 新畫面開始彈入的格(收掉 2 格後)
  const SHR = [0.6, 0.3];                                         // 退場縮放(第 3 格消失)
  // 佈局(px;舞台 x 450–1800,鴿子在左欄)
  const BUB = { x: 940, y: 235, fs: 64 }, HELM = { x: 720, y: 570, s: 1.8 }, BAG = { x: 1380, y: 575, s: 2.2 };   // 句33
  const SHK = { x: 646, y: 290, s: 1.1 }, SAL = { x: 646, y: 545, fs: 100 }, SALA = { x: 1435, y: 545, fs: 100 }, LAT = { x: 1435, y: 380, fs: 64 }, ARROW = { x: 955, y: 545 };   // 句34
  const STE = { x: 700, y: 525, s: 2.2 }, SCR = { x: 1180, y: 545, s: 1.9 }, BAG2 = { x: 1640, y: 570, s: 1.5 }, NF = { x: 1100, y: 215, fs: 100 };   // 句34 後半
  const MAG = { s: 2.2, steps: [[620, 470], [700, 430], [780, 470], [860, 430], [1000, 480], [1100, 520], [1180, 470], [1280, 520]], per: 2 };   // 放大鏡鏡片中心路徑
  const BOOK = { xs: [620, 830, 1040, 1250, 1460, 1670], y: 600, s: 1.5, rots: [-2, 1.5, -1, 2, -1.5, 1], per: 2 }, DATE = { x: 580, y: 285, size: 220 };   // 句35
  // 舊圖(s_happy_b 末格,版面數值同它)
  const PANEL = { x0: 450, y0: 170, w: 1350, h: 540 }, X0 = 620, PXW = 70, YB = 690, YH = 400, RIGHT = 1780;
  const xv = (v) => X0 + PXW * v, yv = (h) => YB - YH * h;
  const COL = { low: 'hsl(4 72% 50%)', kil: 'hsl(205 72% 44%)', high: 'hsl(135 62% 34%)' };
  const FN = {
    low: (x) => (x < 10 ? 0.06 + 0.11 * (1 - Math.pow(1 - x / 10, 2)) : 0.17),
    mid: (x) => 0.26 + 0.34 * x / 15,
    high: (x) => (x < 10 ? 0.62 + 0.018 * x : 0.8 + 0.04 * (x - 10)),
  };

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  // 退場:以 (x,y) 為中心縮小,k0 = 開始退場的格;未到 k0 原樣
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const sc = k0 == null || k < k0 ? 1 : (k - k0 < SHR.length ? SHR[k - k0] : 0);
    if (sc >= 1) return str;
    return sc <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${sc}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };
  // 單位繪製的圖解紙片:kin = 出現後第幾格(<0 未出現)
  const prop = (c, x, y, sc, kin, id, rot) => {
    const p = K.pop(kin);
    if (p <= 0) return '';
    return K.paper(c, { x, y, rot: rot || 0, scale: sc, sx: p, sy: p, k: 'prop', id, enter: kin < 2, wide: true });
  };
  const plateAt = (str, fs, x, y, kin, id, o, rot) => Ch.sheet(Ch.plate(str, fs, o).svg, { x, y, rot, u: U, k: kin, kind: 'sheet', id, wide: true });
  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const rectR = (x, y, w, h, fill, rx, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="${rx}" fill="${fill}"${ex || ''}/>`;
  const NS = ' stroke="none"';

  // ---------- 舊圖(s_happy_b 末格) ----------
  const pathD = (fn, a, b) => { const pts = []; for (let v = a; v <= b + 1e-6; v += 0.5) pts.push(`${f(xv(v))} ${f(yv(fn(v)))}`); return 'M ' + pts.join(' L '); };
  function curve(fn, col, id, a, b, w) {
    const d = pathD(fn, a == null ? 0 : a, b == null ? 15 : b), lw = w || 14;
    const dash = (c, sw) => `<path d="${d}" pathLength="100" fill="none" stroke="${c}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="100 200"/>`;
    return Ch.sheet(dash(K.PAPER, lw + 10) + dash(col, lw), { x: 0, y: 0, u: U, kind: 'curve', id, wide: true });
  }
  const oldTag = (s, right, y, id, o) => {
    o = o || {};
    const p = Ch.plate(s, FS, { fill: o.fill, ink: o.ink });
    return Ch.sheet(p.svg, { x: o.anchor === 'left' ? right + p.w / 2 : right - p.w / 2, y, rot: o.rot, u: U, kind: 'sheet', id, wide: true });
  };
  const OLD_SRC = 'PNAS 2023 論文 基林斯沃斯與康納曼';
  const oldSrc = (pal) => Ch.srcTag(OLD_SRC, { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src' });
  function oldChart(pal) {
    let s = Ch.sheet(rect(-PANEL.w / 2, -PANEL.h / 2, PANEL.w, PANEL.h, pal.pad) + rect(-PANEL.w / 2, PANEL.h / 2 - 14, PANEL.w, 14, K.INK),
      { x: PANEL.x0 + PANEL.w / 2, y: PANEL.y0 + PANEL.h / 2, u: U, kind: 'lineBase', id: 'base', wide: true });
    s += oldTag('開心程度', PANEL.x0 + 24, 222, 'yT', { fill: K.YELLOW, anchor: 'left', rot: -1.5 });
    s += oldTag('年收入(美元)', PANEL.x0, 771, 'xT', { anchor: 'left' });
    [5, 10, 15].forEach((v) => { s += oldTag(v + ' 萬', xv(v) + Ch.plate(v + ' 萬', FS).w / 2, 771, 'tick' + v, v === 10 ? { fill: K.INK, ink: K.YELLOW } : {}); });
    s += curve(FN.low, COL.low, 'low') + oldTag('最不開心的兩成', RIGHT, 554, 'lowL', { fill: COL.low, ink: K.PAPER, rot: 1 });
    let g = '';
    for (let y = 290; y < YB; y += 44) g += rect(xv(10) - 4, y, 8, 26, K.INK);
    s += Ch.sheet(g, { x: 0, y: 0, u: U, kind: 'guide', id: 'guide', wide: true });
    s += Ch.sheet(`<circle cx="${f(xv(10))}" cy="${f(yv(FN.low(10)))}" r="22" fill="${K.YELLOW}"/><circle cx="${f(xv(10))}" cy="${f(yv(FN.low(10)))}" r="8" fill="${K.INK}" stroke="none"/>`,
      { x: 0, y: 0, u: U, kind: 'dot', id: 'bend' });
    s += curve(FN.mid, COL.kil, 'mid') + oldTag('其他人', 860 - Ch.plate('其他人', FS).w / 2, 490, 'midL', { fill: COL.kil, ink: K.PAPER, rot: -1, anchor: 'left' });
    s += curve(FN.high, COL.high, 'high') + oldTag('最開心的一群', RIGHT, 215, 'highL', { fill: COL.high, ink: K.PAPER, rot: 1 });
    s += curve(FN.high, K.YELLOW, 'hiY', 10, 15, 16);
    return s;
  }
  // s_happy_b 末格的笑臉計量表(k = 249:指針 0.28、不轉)
  const oldMeter = (pal) => K.paper(PS.meter(pal, { v: 0.28 }), { x: RL.pigeon.x, y: 320, rot: 0, scale: 1.1, k: 'prop', id: 'meter' });

  // ---------- 本場自畫的圖解 ----------
  // 卷軸(兩端軸、紙面、灰色行)
  function scroll() {
    let s = rect(-100, -60, 200, 120, 'hsl(40 50% 88%)');
    [0, 1, 2, 3].forEach((i) => { s += rectR(-72, -36 + i * 24, i === 3 ? 90 : 144, 9, 'hsl(30 20% 55%)', 4, NS); });
    return s + rectR(-118, -72, 26, 144, PS.C.kraftD, 12) + rectR(92, -72, 26, 144, PS.C.kraftD, 12);
  }
  const arrowC = () => rect(-135, -17, 210, 34, K.INK) + `<polygon points="65,-50 140,0 65,50" fill="${K.INK}" stroke-linejoin="miter"/>`;

  function pigeonPose(k, name) {
    const p = K.clip('idle', 250 + k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // 開頭:s_happy_b 末格的圖表、計量表、舊來源牌從第 1 格起縮掉(第 0 格原樣)
    const wOld = Ch.plate(OLD_SRC, RL.src.fs, { chip: 1, padX: 0.8 }).w;
    s += shr(oldChart(pal), PANEL.x0 + PANEL.w / 2, PANEL.y0 + PANEL.h / 2, k, 1);
    s += shr(oldSrc(pal), RL.src.x + wOld / 2, RL.src.y, k, 1);
    s += shr(oldMeter(pal), RL.pigeon.x, 320, k, 1);

    // 來源牌與「?」記號(全場)
    s += Ch.srcTag('Merriam-Webster 用法說明', { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, k: k - ST, id: 'src' });
    s += Ch.triviaMark({ u: U, k: k - ST - 1 });

    // 句33:傳言泡、鹽袋、羅馬頭盔(句34 起退場)
    {
      const x1 = F[1], kBag = Math.max(wordK(L[0], '鹽'), ST + 1), kHel = Math.max(wordK(L[0], '古羅馬'), kBag + 3);
      s += shr(Ch.bubble('士兵的薪水是鹽', { x: BUB.x, y: BUB.y, fs: BUB.fs, dashed: true, tail: 'bl', u: U, k: k - ST, id: 'rumor' }), BUB.x, BUB.y, k, x1);
      s += shr(prop(PS.saltbag(pal), BAG.x, BAG.y, BAG.s, k - kBag, 'bag', 1), BAG.x, BAG.y, k, x1);
      s += shr(prop(PS.helmet(), HELM.x, HELM.y, HELM.s, k - kHel, 'helm', -1), HELM.x, HELM.y, k, x1);
    }

    // 句34:salarium ← sal(詞「文獻」起退場);句首第 3 格起牌「拉丁文」與 salarium
    const kx = wordK(L[1], '文獻'), kDate = wordK(L[2], '1879');
    {
      const kLat = F[1] + ST, kSal = Math.max(wordK(L[1], '鹽'), kLat + 2), kArr = Math.max(wordK(L[1], '變來'), kSal + 2);
      s += shr(plateAt('拉丁文', LAT.fs, LAT.x, LAT.y, k - kLat, 'lat', { fill: K.YELLOW }, -1.5), LAT.x, LAT.y, k, kx);
      s += shr(plateAt('salarium', SALA.fs, SALA.x, SALA.y, k - kLat, 'sala', {}, 1), SALA.x, SALA.y, k, kx);
      s += shr(prop(PS.shaker(), SHK.x, SHK.y, SHK.s, k - kSal, 'shk', -2), SHK.x, SHK.y, k, kx);
      s += shr(plateAt('sal', SAL.fs, SAL.x, SAL.y, k - kSal, 'sal', {}, -1), SAL.x, SAL.y, k, kx);
      s += shr(Ch.sheet(arrowC(), { x: ARROW.x, y: ARROW.y, u: U, k: k - kArr, kind: 'arrow', id: 'arr', wide: true }), ARROW.x, ARROW.y, k, kx);
    }

    // 句34 後半:卷軸(詞「文獻」,字牌組退場後)、石碑、放大鏡、找不到、鹽袋;詞「1879」起退場
    {
      const kScr = kx + 2, kSte = kScr + 2;
      s += shr(prop(scroll(), SCR.x, SCR.y, SCR.s, k - kScr, 'scr', 1.5), SCR.x, SCR.y, k, kDate);
      s += shr(prop(PS.stele(pal), STE.x, STE.y, STE.s, k - kSte, 'ste', 0), STE.x, STE.y, k, kDate);
      const kM = kSte + 2, step = Math.max(0, Math.min(MAG.steps.length - 1, Math.floor((k - kM) / MAG.per))), lc = MAG.steps[step];
      const mx = lc[0] + 26 * MAG.s, my = lc[1] + 26 * MAG.s;
      s += shr(prop(SN.magnifier(), mx, my, MAG.s, k - kM, 'mag', 0), mx, my, k, kDate);
      const kNf = Math.max(wordK(L[1], '找不到'), kM + 4);
      s += shr(plateAt('找不到', NF.fs, NF.x, NF.y, k - kNf, 'nf', { fill: K.YELLOW }, -1.5), NF.x, NF.y, k, kDate);
      const kBg = Math.max(wordK(L[1], '士兵'), kScr + 2), kGrey = Math.max(wordK(L[1], '紀錄'), kBg + 2);
      const bagC = k >= kGrey ? `<g opacity=".4">${PS.saltbag(pal)}</g>` : PS.saltbag(pal);
      s += shr(prop(bagC, BAG2.x, BAG2.y, BAG2.s, k - kBg, 'bag2', 1), BAG2.x, BAG2.y, k, kDate);
    }

    // 句35:詞「1879」日曆牌與第一本辭典(與上面的物件同格交替)、詞「後來」起一本接一本
    {
      const kCopy = Math.max(wordK(L[2], '後來'), kDate + 4);
      s += Ch.dateTag({ x: DATE.x, y: DATE.y, top: '出版', main: '1879', size: DATE.size, rot: -3, k: k - kDate, id: 'd1879' });
      BOOK.xs.forEach((bx, i) => {
        const kin = i === 0 ? k - kDate : k - (kCopy + (i - 1) * BOOK.per);
        s += prop(PS.dict(pal, { text: '辭典' }), bx, BOOK.y, BOOK.s, kin, 'book' + i, BOOK.rots[i]);
      });
    }

    // 鴿子(左欄、面向右、整場在位):表情隨句換
    {
      const P = RL.pigeon, name = k >= F[2] ? 'doubt' : k >= F[1] ? 'think' : 'look';
      s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
      s += K.pigeon(pigeonPose(k, name), { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_salt', dur: 22, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
