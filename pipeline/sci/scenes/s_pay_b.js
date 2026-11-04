/* snack 場景 s_pay_b(句 99–103,含 tail)薪水二:全體薪資。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 句99:底部一條墨色橫線加牌「基本工資 = 底線」(句首);上方薪資袋與來源牌「主計總處」(「主計總處」處);袋下字牌「經常性薪資 47,884(2025 平均)」(「經常性」處)。
 * 句100:99 的東西 2 格縮小退場;右卡「47,884 / 2025」(句首),箭頭加左卡「39,217 / 2016」(「2016」處);黃牌「+22%」(「22%」處)、「自算」小牌(其後 4 格,保留到句103 開頭)。
 * 句101:全部退場(自算除外);hbars(x 430–1840、max 40)三條:整體物價 14.3%(藍)、薪水 22%(綠)、外食 26.6%(主色),依「薪水」「外食」詞位置逐條。
 * 句102:鴿子懷裡四樣小吃(雞排、珍奶、滷肉飯、地瓜球)句首彈入;薪水條右側打勾加「贏物價」(「贏過」處)、打叉加「輸外食」(「輸給」處);
 *       雞排與珍奶依「每天」「買的」處先後落到地上(逐格位置見 FALL),剩一半在懷裡。
 * 句103:hbars 與記號退場;十個小人排一排(x 500–1750,同時彈入);較高的橫線「平均 47,884」(「平均數」處)、腰部高度橫線「中位數 38,406」(「中位數」處);
 *       「有一半」處左邊五個依序變灰;最後靜止到 dur。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const DEF = [{ start: 0.025, end: 8.355 }, { start: 8.475, end: 14.53 }, { start: 14.65, end: 21.405 }, { start: 21.525, end: 25.31 }, { start: 25.43, end: 31.88 }];
  const TXT = ['可是基本工資只是底線,主計總處另外算了全體受僱員工的經常性薪資,2025 年平均是 47,884 元。', '同一個數字在 2016 年是 39,217 元,十年漲了 22% 左右。',
    '物價 14.3%、薪水 22%、外食 26.6%,這三個數字擺在一起看。', '薪水有贏過整體物價,偏偏輸給你每天都要買的那一餐。', '而且這是平均數,2025 年的中位數是 38,406 元,有一半的人領不到這個數字。'];
  const U = 1.43, PU = 1.36;                                   // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const INK = K.INK, RED = 'hsl(4 78% 48%)', GREEN = 'hsl(130 45% 45%)', BLUE = 'hsl(205 70% 52%)', TICK = 'hsl(130 55% 38%)';
  const CX = 1135;                                             // 內容區水平中心(x 430–1840)
  const BARS = { x: 430, y: 140, w: 1410, rowH: 140, gap: 60, labelW: 440, fs: 72, numFs: 90 };
  const MK = { gx: 1565, px: 1603, ty: 345, cy: 455 };         // 記號中心 x、字牌左緣、打勾與打叉的 y
  const FOODS = [                                              // 懷裡四樣(2×2 排,中心約 (292,690));drop = 落地順序(0 = 不落地)
    { n: 'chickenCutlet', s: 0.42, ax: 240, ay: 640, gx: 520, gy: 761, drop: 1, rot: 24 },
    { n: 'bobaCup', s: 0.4, ax: 344, ay: 640, gx: 640, gy: 757, drop: 2, rot: -30 },
    { n: 'braisedPorkRice', s: 0.46, ax: 240, ay: 742, drop: 0 },
    { n: 'sweetBall', s: 0.5, ax: 344, ay: 742, drop: 0 }];
  const FALL = [0.12, 0.34, 0.6, 0.85, 1];                    // 落下後第 1–5 格走完全程的比例(水平線性、垂直平方)
  const PPL = { x0: 500, x1: 1750, cy: 540, s: 1.2 };          // 小人排:腰部高度約 y 576
  const LN = { x: 1135, w: 1390, avgY: 345, medY: 576, th: 14 };
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  const tickG = () => `<polygon points="-34,4 -17,-13 -5,0 22,-30 40,-12 -5,36" fill="${TICK}" stroke-linejoin="miter"/>`;
  function crossG() {
    const a = 10, L = 40, p = [[-a, -L], [a, -L], [a, -a], [L, -a], [L, a], [a, a], [a, L], [-a, L], [-a, a], [-L, a], [-L, -a], [-a, -a]];
    return `<g transform="rotate(45)"><polygon points="${p.map((v) => v.join(',')).join(' ')}" fill="${RED}" stroke-linejoin="miter"/></g>`;
  }
  const ARROW = `<polygon points="-70,-14 20,-14 20,-42 72,0 20,42 20,14 -70,14" fill="${INK}" stroke-linejoin="miter"/>`;

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const pos = (i, word, defIdx) => {                      // 詞在句中的位置比例 → 格編號
      const tx = ((params && params.lines && params.lines[i] && params.lines[i].text) || TXT[i]), j = tx.indexOf(word), idx = j >= 0 ? j : defIdx;
      return K.frame(L[i].start + idx / tx.length * (L[i].end - L[i].start));
    };
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    const sh = (svg, x, y, kk, kind, id, rot, wide) => Ch.sheet(svg, { x, y, rot, u: U, k: kk, kind, id, wide: wide !== false });
    // 各事件的格
    const kEnv = Math.max(pos(0, '主計總處', 11), F[0] + 4), kLab = Math.max(pos(0, '經常性', 26), kEnv + 4);
    const kR = F[1], kL = Math.max(pos(1, '2016', 7), kR + 4), kPlus = Math.max(pos(1, '22%', 29), kL + 6), kSelf = kPlus + 4;
    const kB0 = F[2] + 2, kB1 = Math.max(pos(2, '薪水', 9), kB0 + 6), kB2 = Math.max(pos(2, '外食', 16), kB1 + 6);
    const kTick = Math.max(pos(3, '贏過', 3), F[3] + 4), kCross = Math.max(pos(3, '輸給', 12), kTick + 6);
    const kD = [0, Math.max(pos(3, '每天', 15), kCross + 4)]; kD.push(Math.max(pos(3, '買的', 19), kD[1] + 6));
    const kP = F[4] + 2, kAvg = Math.max(pos(4, '平均數', 4), kP + 5), kMed = Math.max(pos(4, '中位數', 15), kAvg + 6), kGrey = Math.max(pos(4, '有一半', 29), kMed + 6);
    let s = '';

    // ---- 句99:底線、薪資袋、字牌、來源牌 ----
    if (k < F[1] + 2) {
      let g = '';
      g += sh(R(-LN.w / 2, -9, LN.w, 18, INK), CX, 685, k - F[0], 'floor', 'floor');
      g += sh(Ch.plate('基本工資 = 底線', 60, { chip: INK }).svg, CX, 757, k - F[0], 'flabel', 'flabel');
      if (k >= kEnv) {
        const q = k - kEnv, p = K.pop(q);
        g += K.paper(PS.LIST.payEnvelope.fn(pal, {}), { x: CX, y: 320, scale: 2.4, sx: p, sy: p, k: 'prop', id: 'env', wide: PS.LIST.payEnvelope.wide, enter: q < 2 });
        g += Ch.srcTag('主計總處', { pal, x: 1830, y: 120, anchor: 'right', k: q, id: 'src' });
      }
      if (k >= kLab) g += sh(Ch.plate('經常性薪資 47,884(2025 平均)', 60, { chip: pal.main }).svg, CX, 565, k - kLab, 'elabel', 'elabel', -1);
      s += shr(g, CX, 420, k, F[1]);
    }

    // ---- 句100:39,217 → 47,884 ----
    if (k >= F[1] && k < F[2] + 2) {
      let g = '';
      const nc = (num, yr, x, kk, fill, ink, id) => {
        let c = sh(Ch.plate(num, 110, { fill, ink }).svg, x, 340, kk, 'num', id + 'n', 0);
        c += sh(Ch.plate(yr, 60, { chip: fill === K.PAPER ? INK : pal.main }).svg, x, 495, kk, 'yr', id + 'y', 0);
        return c;
      };
      g += nc('47,884', '2025 年', 1500, k - kR, pal.main, pal.onMain, 'nr');
      if (k >= kL) {
        g += nc('39,217', '2016 年', 800, k - kL, K.PAPER, INK, 'nl');
        g += sh(ARROW, 1150, 340, k - kL, 'arrow', 'arrow');
      }
      if (k >= kPlus) g += sh(Ch.plate('+22%', 140, { fill: K.YELLOW }).svg, 1150, 675, k - kPlus, 'plus', 'plus', -3);
      s += shr(g, CX, 450, k, F[2]);
    }
    if (k >= kSelf && k < F[4] + 2) {                        // 自算小牌(句100 起,句103 開頭退場)
      s += shr(sh(Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 }).svg, 1740, 780, k - kSelf, 'src', 'self'), 1740, 780, k, F[4]);
    }

    // ---- 句101–102:三條長條、打勾打叉 ----
    if (k >= kB0 && k < F[4] + 2) {
      let g = Ch.hbars({ pal, x: BARS.x, y: BARS.y, w: BARS.w, rowH: BARS.rowH, gap: BARS.gap, labelW: BARS.labelW, fs: BARS.fs, numFs: BARS.numFs, max: 40, id: 'pay', bars: [
        { label: '整體物價', value: 14.3, text: '14.3%', color: BLUE, k: k - kB0 },
        { label: '薪水', value: 22, text: '22%', color: GREEN, k: k - kB1 },
        { label: '外食', value: 26.6, text: '26.6%', color: pal.main, k: k - kB2 }] });
      if (k >= kTick) {
        const q = k - kTick, pl = Ch.plate('贏物價', 56, { padX: 0.5, chip: TICK });
        g += sh(tickG(), MK.gx, MK.ty, q, 'mark', 'tick', 0, false) + sh(pl.svg, MK.px + pl.w / 2, MK.ty, q, 'mlab', 'tickL', 0);
      }
      if (k >= kCross) {
        const q = k - kCross, pl = Ch.plate('輸外食', 56, { padX: 0.5, chip: RED });
        g += sh(crossG(), MK.gx, MK.cy, q, 'mark', 'cross', 0, false) + sh(pl.svg, MK.px + pl.w / 2, MK.cy, q, 'mlab', 'crossL', 0);
      }
      s += shr(g, CX, 420, k, F[4]);
    }

    // ---- 句103:十個小人、兩條線 ----
    if (k >= kP) {
      const q = k - kP, p = K.pop(q);
      for (let i = 0; i < 10; i++) {
        const gi = i < 5 ? k - (kGrey + i) : -1, grey = gi >= 0, m = gi === 0 ? 0.88 : 1;
        s += K.paper(PS.LIST.person.fn(pal, { grey }), { x: PPL.x0 + i * (PPL.x1 - PPL.x0) / 9, y: PPL.cy, scale: PPL.s * m, sx: p, sy: p, k: 'prop', id: 'pp' + i, enter: q < 2 });
      }
      if (k >= kAvg) {
        const q2 = k - kAvg;
        s += sh(R(-LN.w / 2, -LN.th / 2, LN.w, LN.th, pal.main), LN.x, LN.avgY, q2, 'line', 'avg');
        s += sh(Ch.plate('平均 47,884', 68, { chip: pal.main }).svg, 1530, 270, q2, 'avgL', 'avgL', 0);
      }
      if (k >= kMed) {
        const q2 = k - kMed;
        s += sh(R(-LN.w / 2, -LN.th / 2, LN.w, LN.th, INK), LN.x, LN.medY, q2, 'line', 'med');
        s += sh(Ch.plate('中位數 38,406', 68, { chip: INK }).svg, 1480, 745, q2, 'medL', 'medL', 0);
      }
    }

    // ---- 鴿子與小吃 ----
    const e = k >= F[4] ? 'doubt' : k >= kD[1] ? 'surprised' : k >= kCross ? 'doubt' : k >= kTick ? 'smug' : 'normal';
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, K.expr(K.clip('idle', k), e), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    if (k >= F[3]) {
      FOODS.forEach((fd) => {
        let x = fd.ax, y = fd.ay, rot = 0, p = K.pop(k - F[3]);
        if (fd.drop && k >= kD[fd.drop]) {
          const j = k - kD[fd.drop], fp = FALL[Math.min(j, FALL.length - 1)];
          x = fd.ax + (fd.gx - fd.ax) * fp; y = fd.ay + (fd.gy - fd.ay) * fp * fp; rot = fd.rot * fp; p = 1;
        }
        s += prop(fd.n, {}, { x, y, rot, scale: fd.s, sx: p, sy: p, id: 'food_' + fd.n, enter: k - F[3] < 2 });
      });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_pay_b', dur: 33.4, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
