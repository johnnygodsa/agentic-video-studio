/* snack 場景 s_old_b(句 16–19)夜市牛排,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 佈景:深色夜空紙片、上方一串燈泡、鴿子站左下(全程在場,面向右);右上「?」記號全程在,句 19 結尾前 5 格退場。
 * 句16:日曆牌「西元 1976」句首彈入;路牌「八德路」(詞「八德路」);攤車招牌「平價牛排」(詞「平價牛排」)。
 * 句17:前三者退場;鐵板大圖(寬 852px)牛排加馬鈴薯 → 詞「麵條」換成一搓麵條 → 詞「蛋」多一顆蛋;下方字牌隨三態換字。
 * 句18:鐵板退場;價牌「45 元」句首;來源小牌「食力」(詞「食力」);虛線對話泡「也有人說 40 元」(詞「另外也有人說」)。鴿子 doubt。
 * 句19:前者退場;現代攤位與價牌「45 元」彈入;手搖杯(詞「一杯飲料」前)彈在兩者之間,鴿子聳肩。
 * 退場一律 2 格縮小;同時在動的非文字元素 ≤ 2 組(鴿子 + 一個物件)。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PS = (typeof window !== 'undefined' && window.PropsSnack) || require('../props_snack.js');
  const U = 1.4;                                    // 鴿子倍率(高約 318px)
  const FOOT = { x: 330, y: 810 };                  // 鴿子腳底落點(面向右:flip)
  const NIGHT = 'hsl(24 45% 14%)';
  const BULBS = { x: 1100, y: 128, w: 700 };
  const DATE = { x: 400, y: 280, size: 330 };
  const ROAD = { x: 880, y: 330, fs: 80 };
  const STALL1 = { x: 1400, y: 540, u: 1.7 };
  const PLATE = { x: 1080, y: 430, u: 3.0 };        // 鐵板大圖:284×3.0 = 852px 寬
  const PLAB = { x: 1080, y: 745, fs: 64 };
  const P45 = { x: 830, y: 400, fs: 190 };
  const SRC = { x: 1210, y: 330 };
  const BUB = { x: 1420, y: 690, fs: 84 };
  const P45B = { x: 740, y: 420, fs: 130 };
  const STALL2 = { x: 1560, y: 545, u: 1.4 };
  const CUP = { x: 1150, y: 555, u: 2.0 };
  const DEF_TXT = ['我查得到的是 1976 年,台北八德路的巷子裡有人開始賣平價牛排。',
    '鐵板直接端上桌,旁邊的馬鈴薯換成一搓麵條,再打一顆蛋,你現在在夜市吃到的牛排就是這個配置。',
    '那一客牛排當年賣 45 元,這是食力的報導寫的,另外也有人說是 40 元。',
    '一客牛排四十幾塊,這個價錢呀,現在在夜市大概只夠買一杯飲料。'];
  const DEF = (() => { let t = 0; return DEF_TXT.map((s) => { const d = { start: t, end: t + s.length / 6.5 }; t = d.end + 0.12; return d; }); })();
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (L, i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
  const rc = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' stroke="none"'}/>`;
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };
  const popP = (k) => K.pop(k);

  // 夜空紙片(淺底邊 18px);不帶 data-k,不入外框檢查。星點避開字幕帶
  function sky() {
    let c = rc(18, 18, 1884, 1044, NIGHT, ' stroke-linejoin="miter"');
    for (let i = 0; i < 42; i++) {
      const x = 60 + K.hash(i * 3.1 + 1) * 1800, y = 60 + K.hash(i * 7.7 + 2) * 760, r = 2.5 + K.hash(i * 5.3 + 3) * 3.5;
      c += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return `<g filter="url(#papw)" stroke="${K.PAPER}" stroke-width="4" stroke-linejoin="round">${c}</g>`;
  }

  // 鴿子姿勢:全程站左下面向右;句 18 起 doubt;句 19 杯子出現時聳肩
  function pigeonPose(k, F, kCup) {
    let p;
    if (k >= kCup) p = K.clip('shrug', Math.min(k - kCup + 1, 7));
    else if (k >= F[2]) p = K.expr(K.clip('idle', k), 'doubt');
    else p = K.expr(K.clip('idle', k), 'normal');
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kDate = F[0], kRoad = at(L, 0, 0.4), kStall = at(L, 0, 0.65);
    const kN = at(L, 1, 0.39), kE = at(L, 1, 0.54);
    const kSrc = at(L, 2, 0.43), kBub = at(L, 2, 0.65);
    const kStall2 = F[3] + 2, kP45b = F[3] + 4, kCup = Math.max(at(L, 3, 0.68), F[3] + 8), kOut = K.frame(L[3].end) - 5;
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    let s = sky();

    // 燈泡串(全程)
    s += prop('bulbString', { w: BULBS.w, sag: 30, n: 6 }, { x: BULBS.x, y: BULBS.y, scale: 1, id: 'bulbs' });

    // 句 16:日曆牌、路牌、攤車(句 17 退場)
    if (k < F[1] + 2) {
      let c = '';
      c += Ch.dateTag({ x: DATE.x, y: DATE.y, top: '西元', main: '1976', size: DATE.size, rot: -4, k: k - kDate, id: 'date' });
      if (k >= kRoad) {
        const pl = Ch.plate('八德路', ROAD.fs, { fill: 'hsl(150 55% 28%)', ink: K.PAPER }), h = ROAD.fs * 1.62;
        const pole = rc(-9, h / 2 - 4, 18, 56, K.INK, ' stroke-linejoin="miter"');
        c += Ch.sheet(pole + pl.svg, { x: ROAD.x, y: ROAD.y, rot: 2, u: U, k: k - kRoad, kind: 'road', id: 'road' });
      }
      if (k >= kStall) {
        const p = popP(k - kStall);
        c += prop('stall', { sign: '平價牛排' }, { x: STALL1.x, y: STALL1.y, scale: STALL1.u, sx: p, sy: p, id: 'stall1', enter: k - kStall < 2 });
      }
      s += shr(c, 960, 400, k, F[1]);
    }

    // 句 17:鐵板大圖三態(句 18 退場)
    if (k >= F[1] + 2 && k < F[2] + 2) {
      const kk = k - (F[1] + 2), p = popP(kk), j = Math.min(k - kN >= 0 ? k - kN : 9, k - kE >= 0 ? k - kE : 9);
      const hop = j === 0 ? 1.06 : j === 1 ? 0.98 : 1;
      const noodle = k >= kN, egg = k >= kE;
      const txt = egg ? '牛排 + 麵條 + 蛋' : noodle ? '牛排 + 麵條' : '牛排 + 馬鈴薯';
      const sc = p * hop;
      const pl = prop('steakPlate', { side: noodle ? 'noodle' : 'potato', egg }, { x: PLATE.x, y: PLATE.y, scale: PLATE.u, sx: sc, sy: sc, id: 'steak', enter: kk < 2 });
      const lab = Ch.plate(txt, PLAB.fs, {});
      const lb = Ch.sheet(lab.svg, { x: PLAB.x, y: PLAB.y, u: U, k: kk, kind: 'steaklab', id: 'steaklab' });
      s += shr(pl + lb, PLATE.x, 590, k, F[2]);
    }

    // 句 18:價牌 45 元、來源小牌、虛線對話泡(句 19 退場)
    if (k >= F[2] + 2 && k < F[3] + 2) {
      let c = Ch.priceFlip({ x: P45.x, y: P45.y, from: 45, unit: '元', fs: P45.fs, pal, k: k - (F[2] + 2), id: 'p45' });
      c += Ch.srcTag('食力', { x: SRC.x, y: SRC.y, anchor: 'left', fs: 48, pal, k: k - Math.max(kSrc, F[2] + 4), id: 'src' });
      c += Ch.bubble('也有人說 40 元', { x: BUB.x, y: BUB.y, fs: BUB.fs, dashed: true, tail: 'tl', rot: -2, k: k - Math.max(kBub, F[2] + 6), id: 'bub' });
      s += shr(c, 1000, 480, k, F[3]);
    }

    // 句 19:現代攤位、價牌 45 元、手搖杯
    if (k >= kStall2) {
      const p = popP(k - kStall2);
      s += prop('stall', { sign: '手搖飲', awning: 'hsl(190 60% 45%)' }, { x: STALL2.x, y: STALL2.y, scale: STALL2.u, sx: p, sy: p, id: 'stall2', enter: k - kStall2 < 2 });
    }
    if (k >= kP45b) s += Ch.priceFlip({ x: P45B.x, y: P45B.y, from: 45, unit: '元', fs: P45B.fs, pal, k: k - kP45b, id: 'p45b' });
    if (k >= kCup) {
      const p = popP(k - kCup);
      s += prop('bobaCup', {}, { x: CUP.x, y: CUP.y, scale: CUP.u, sx: p, sy: p, id: 'cup', enter: k - kCup < 2 });
    }

    // 「?」記號:全程在右上;句 19 結尾前 5 格退場
    s += Ch.triviaMark({ k: k + 3, kOut: k - kOut, id: 'trivia' });

    // 鴿子
    s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, F, kCup), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_old_b', dur: 22.2, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
