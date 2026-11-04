/* snack 場景 s_old_a(句 12–15)夜市比銅板老,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 佈景:夜空紙片、左上燈泡串、右上「?」記號全程;鴿子從左走入站左下;廟在中上,小攤排在廟前。
 * 句12:日曆牌「1908」(說到「紀錄是」)→ 地名牌「高雄旗津」→ 廟(匾額天后宮)彈入、三個小攤依序彈入 → 時鐘牌「晚上 6 點–12 點」加鬧鐘 → 來源小牌「臺灣日日新報(轉引)」。
 * 句13:日曆牌、時鐘、鬧鐘、來源退場;地名牌換「士林夜市」、廟匾額拿掉、廟口加第 4 個攤車;「日治時代」「百年」兩張牌;來源小牌「台北市市場處」。
 * 句14:右欄牌與攤車退場;空白價牌「? 元」彈入;鴿子翻資料夾(開合交替)翻不到。
 * 句15:資料夾退場、鴿子 shrug,價牌維持「?」。
 * 同時在動的非文字元素 ≤ 2 組(鴿子 + 一個物件);退場一律 2 格縮小。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PS = (typeof window !== 'undefined' && window.PropsSnack) || require('../props_snack.js');
  const U = 1.4;                                    // 鴿子倍率(高約 318px)
  const FOOT = { x: 330, y: 810 };
  const WALK_N = 14, STEP = 36;
  const NIGHT = 'hsl(24 45% 14%)';
  const DATE = { x: 340, y: 300, size: 304 };
  const BULB = { x: 1000, y: 128, w: 760 };
  const TEMPLE = { x: 940, y: 365, u: 1.33 };
  const STALL_U = 0.62, STALL_Y = 710, STALLS = [710, 940, 1170, 1400];   // 第 4 個在句 13 加入
  const COL = 1520;                                  // 右欄中心 x
  const LOC = { y: 255, fs: 64 }, CLK = { y: 400, fs: 56 }, ALM = { y: 580, u: 0.8 };
  const ZHI = { y: 385, fs: 64 }, HUN = { y: 510, fs: 72 };
  const PRICE = { x: 1480, y: 440, fs: 130 };
  const W5 = [[100, 1], [130, 1], [150, 1]];          // 抱資料夾
  const LOWW = [[90, 1], [45, 1]];                    // 放下
  const SH = [146, 176], WT = [76, 30];
  const DEF_TXT = ['夜市本身老很多,目前查得到比較早的紀錄是 1908 年,有人在高雄旗津的天后宮前面擺夜市,從晚上六點開到半夜十二點。',
    '士林夜市也是日治時代就有攤販聚在廟口,台北市市場處的說法是已經有百年歷史。', '一百多年前的夜市一碗賣多少,我查不到。', '這一題我先認輸吧。'];
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
  const R = (i, w) => Math.max(0, DEF_TXT[i].indexOf(w)) / DEF_TXT[i].length;      // 詞在句中的位置比例
  const rc = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' stroke="none"'}/>`;
  const shr = (str, x, y, k, k0) => {                // 自第 k0 格起 2 格縮小後消失
    if (!str) return '';
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };
  const popP = (k) => K.pop(k);

  function sky() {
    let c = rc(18, 18, 1884, 1044, NIGHT, ' stroke-linejoin="miter"');
    for (let i = 0; i < 42; i++) {
      const x = 60 + K.hash(i * 3.1 + 1) * 1800, y = 60 + K.hash(i * 7.7 + 2) * 760, r = 2.5 + K.hash(i * 5.3 + 3) * 3.5;
      c += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return `<g filter="url(#papw)" stroke="${K.PAPER}" stroke-width="4" stroke-linejoin="round">${c}</g>`;
  }

  function tip(w) {                                  // 翅尖的畫面座標
    const a = w[0] * Math.PI / 180, vx = WT[0] * w[1], vy = WT[1];
    const px = SH[0] + vx * Math.cos(a) - vy * Math.sin(a), py = SH[1] + vx * Math.sin(a) + vy * Math.cos(a);
    return { x: FOOT.x + U * (300 - px - 132), y: FOOT.y - 280 * U + U * py };
  }

  function pigeonState(k, F, kArr) {
    const idle = (e) => K.expr(K.clip('idle', k), e || 'normal');
    const wp = (w, e) => Object.assign({}, idle(e), { wing: w[0], wlen: w[1] });
    let p, dx = 0, enter = false, hold = null;
    if (k < kArr) { p = K.clip('walk', k - F[0]); dx = (kArr - k) * STEP; enter = true; }
    else if (k < F[2]) p = idle();
    else if (k < F[3]) { const i = Math.min(k - F[2], 2); p = wp(W5[i], k >= F[2] + 12 ? 'doubt' : 'normal'); if (i >= 2) hold = W5[2]; }
    else if (k < F[3] + 2) p = wp(LOWW[k - F[3]], 'normal');
    else p = K.clip('shrug', Math.min(k - (F[3] + 2), 7));
    return { pose: Object.assign({}, p, { flip: 1 }), dx, enter, hold };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kArr = F[0] + WALK_N;
    // 句 12 事件格
    const eDate = at(L, 0, R(0, '紀錄是')), eLoc = Math.max(at(L, 0, R(0, '高雄旗津')), eDate + 3);
    const eTemple = Math.max(at(L, 0, R(0, '天后宮')), eLoc + 3), eClock = Math.max(at(L, 0, R(0, '晚上六點')), eTemple + 12);
    const eSrc = Math.max(at(L, 0, R(0, '半夜')), eClock + 4);
    // 句 13 事件格
    const e4 = F[1] + 2, eZhi = Math.max(at(L, 1, R(1, '日治時代')), F[1] + 5), eSrc2 = Math.max(at(L, 1, R(1, '台北市市場處')), eZhi + 3);
    const eHun = Math.max(at(L, 1, R(1, '百年')), eSrc2 + 3);
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    const card = (s, fs, x, y, kk, id, o) => Ch.sheet(Ch.plate(s, fs, o || {}).svg, { x, y, u: U, k: kk, kind: 'lab', id });
    let s = sky();

    // 燈泡串、「?」記號(全程)
    s += prop('bulbString', { w: BULB.w, sag: 30, n: 7 }, { x: BULB.x, y: BULB.y, scale: 1, sx: popP(k - F[0]), sy: popP(k - F[0]), id: 'bulbs', enter: k - F[0] < 2 });
    s += Ch.triviaMark({ u: U, k: k - F[0] });

    // 句 12:日曆牌(句 13 退場)
    if (k >= eDate && k < F[1] + 2) {
      s += shr(Ch.dateTag({ x: DATE.x, y: DATE.y, top: '西元', main: '1908', size: DATE.size, rot: -4, k: k - eDate, id: 'date' }), DATE.x, DATE.y, k, F[1]);
    }
    // 地名牌:句 12「高雄旗津」→ 句 13「士林夜市」→ 句 14 退場
    if (k >= eLoc && k < F[2] + 2) {
      const name = k < F[1] ? '高雄旗津' : '士林夜市', kk = k < F[1] ? k - eLoc : k - F[1];
      s += shr(card(name, LOC.fs, COL, LOC.y, kk, 'loc'), COL, LOC.y, k, F[2]);
    }
    // 廟與小攤(廟全程;匾額到句 13 拿掉;小攤句 14 退場)
    if (k >= eTemple) {
      const kk = k - eTemple, p = popP(kk);
      s += prop('temple', { plaque: k < F[1] ? '天后宮' : '' }, { x: TEMPLE.x, y: TEMPLE.y, scale: TEMPLE.u, sx: p, sy: p, enter: kk < 2 });
      for (let i = 0; i < 4; i++) {
        const k0 = i < 3 ? eTemple + 3 + 3 * i : e4;
        if (k < k0 || k >= F[2] + 2) continue;
        const ks = k - k0, ps = popP(ks);
        s += shr(prop('stall', { sign: '小吃' }, { x: STALLS[i], y: STALL_Y, scale: STALL_U, sx: ps, sy: ps, id: 'stall' + i, enter: ks < 2 }), STALLS[i], STALL_Y, k, F[2]);
      }
    }
    // 時鐘牌加鬧鐘、來源小牌(句 12;句 13 退場)
    if (k >= eClock && k < F[1] + 2) {
      const kk = k - eClock, p = popP(kk);
      const clk = card('晚上 6 點–12 點', CLK.fs, COL, CLK.y, kk, 'clk');
      const alm = prop('alarm', {}, { x: COL, y: ALM.y, rot: 5, scale: ALM.u, sx: p, sy: p, enter: kk < 2 });
      s += shr(clk, COL, CLK.y, k, F[1]) + shr(alm, COL, ALM.y, k, F[1]);
    }
    if (k >= eSrc && k < F[1] + 2) {
      s += shr(Ch.srcTag('臺灣日日新報(轉引)', { pal, u: U, x: 1830, y: 760, anchor: 'right', k: k - eSrc, id: 'src1' }), 1600, 760, k, F[1]);
    }
    // 句 13:日治時代、百年、來源小牌(句 14 退場)
    if (k >= eZhi && k < F[2] + 2) s += shr(card('日治時代', ZHI.fs, COL, ZHI.y, k - eZhi, 'zhi'), COL, ZHI.y, k, F[2]);
    if (k >= eSrc2 && k < F[2] + 2) {
      s += shr(Ch.srcTag('台北市市場處', { pal, u: U, x: 1830, y: 760, anchor: 'right', k: k - eSrc2, id: 'src2' }), 1690, 760, k, F[2]);
    }
    if (k >= eHun && k < F[2] + 2) s += shr(card('百年', HUN.fs, COL, HUN.y, k - eHun, 'hun', { fill: K.YELLOW, ink: K.INK }), COL, HUN.y, k, F[2]);

    // 句 14 起:空白價牌「? 元」(全程到結束)
    if (k >= F[2]) s += Ch.priceFlip({ x: PRICE.x, y: PRICE.y, from: '?', unit: '元', fs: PRICE.fs, pal, k: k - F[2], id: 'pf' });

    // 鴿子與資料夾
    const pg = pigeonState(k, F, kArr);
    if (k >= kArr) s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: FOOT.y, scale: U, id: 'main', enter: pg.enter });
    if (k >= F[2] + 2 && k < F[3] + 2) {
      const tp = tip(W5[2]), kk = k - (F[2] + 2), p = popP(kk), x = tp.x + 20, y = tp.y - 10;
      const open = kk >= 3 && Math.floor((kk - 3) / 4) % 2 === 0;
      s += shr(prop('folder', { open }, { x, y, rot: -4, scale: 0.9, sx: p, sy: p, enter: kk < 2 }), x, y, k, F[3]);
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_old_a', dur: 19.7, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
