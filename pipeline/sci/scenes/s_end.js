/* snack 場景 s_end(句 112–118)收尾,全片最大一鏡,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 場景內索引 0–6 = 句 112–118。
 * 句112:淺底;50 元硬幣大特寫(直徑約 450px)彈入,「1992」日曆牌在詞「1992」處(句長 39% 處)彈入。
 * 句113:句首換夜空(兩排燈泡);硬幣與日曆牌在夜空上 2 格縮小退場;六台攤車一字排開、每 2 格彈入一台(招牌依序骰子牛、牛排、雞排、地瓜球、珍奶、早餐);
 *       鴿子自左走到中間前方,舉翅,手上拿一枚 50 元硬幣。
 * 句114:三張空白問題牌自上方逐張降下(各隔 3 格),落定後三塊編號牌 1、2、3 一起彈在各牌上方。
 * 句115–117:第 1、2、3 張牌各在句首翻面(換成黃底):① 上升價格線加「? 元」;② 「+5」或 縮小的雞排;③ 50 元硬幣加「?」。
 * 句118:硬幣縮小退場,鴿子翅膀指向右下方,留言框(場景內自畫的對話框)彈在字幕帶上緣。最後一個事件後靜止到 dur。
 * 同時在動的非文字元素 ≤ 2 組;退場一律 2 格縮小。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PS = (typeof window !== 'undefined' && window.PropsSnack) || require('../props_snack.js');
  const U = 1.38;                                  // 鴿子倍率(高約 313px)
  const FOOT = { x: 960, y: 810 };                  // 鴿子腳底落點(面向右:flip)
  const WALK_N = 14, STEP = 36;
  const NIGHT = 'hsl(24 45% 14%)';
  const COIN = { x: 600, y: 450, u: 4.5 };          // 句 112 大硬幣(直徑 450px)
  const DATE = { x: 1250, y: 450, size: 480 };
  const STALLS = ['骰子牛', '牛排', '雞排', '地瓜球', '珍奶', '早餐'];
  const AW = [null, 'hsl(4 68% 52%)', 'hsl(200 55% 48%)'];     // 遮雨棚色輪替(null = 主色)
  const ST = { xs: [205.4, 430, 654.6, 1265.4, 1490, 1714.6], y: 660, u: 0.62 };   // 左三台 x 100–760、右三台 x 1160–1820(中間留給鴿子)
  const CARD = { w: 480, h: 270, y: 315, xs: [420, 960, 1500] };
  const BADGE = { y: 130, s: 76, fs: 56 };
  const U1 = 1.4;                                   // 以 px 繪製的紙片倍率(描邊 5.6px)
  const BOX = { x: 1335, y: 800, w: 300, h: 52, fs: 48 };      // 留言框
  const W5 = [[100, 1], [130, 1], [150, 1]];        // 舉起、拿硬幣
  const PT = [[60, 1.1], [110, 1.3], [125, 1.6]];   // 指向留言框
  const FLIP = [['b', 0.6], ['b', 0.2], ['y', 0.5], ['y', 1.06]];   // 翻面逐格:面別與水平縮放
  const RED = 'hsl(4 68% 52%)', TAN = 'hsl(24 30% 78%)';
  const DEF_TXT = ['銅板美食這四個字,靠的是 1992 年才出生的那枚五十塊硬幣。', '它現在還在你的口袋裡,只是一枚已經不太夠用。', '影片的最後,我想問你三個問題。',
    '第一個問題,一份小吃超過多少錢你就不買了,你心裡那條線在哪裡?', '第二個問題,漲五塊跟份量變少,你比較能接受哪一種,理由是什麼?',
    '第三個問題,你家附近還有哪一樣東西,真的一個五十塊銅板就買得到?', '留言跟我說吧,記得寫上理由。'];
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
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const rc = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' stroke="none"'}/>`;
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };
  const popP = (k) => K.pop(k);
  // 以 px 繪製的紙片(中心在 (o.x,o.y);描邊 5.6px)
  const px = (content, o) => K.paper(`<g transform="scale(${(1 / U1).toFixed(5)})" stroke-width="${f(4 * U1)}">${content}</g>`,
    Object.assign({ scale: U1 }, o));
  // 內嵌圖解(單位內容放到 (cx,cy),縮放 s,描邊約 5.6px)
  const emb = (str, cx, cy, s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${s})" stroke-width="${f(5.6 / s)}">${str}</g>`;

  // 夜空紙片(淺底邊 18px);不帶 data-k,不入外框檢查。星點避開字幕帶
  function sky() {
    let c = rc(18, 18, 1884, 1044, NIGHT, ' stroke-linejoin="miter"');
    for (let i = 0; i < 42; i++) {
      const x = 60 + K.hash(i * 3.1 + 1) * 1800, y = 60 + K.hash(i * 7.7 + 2) * 760, r = 2.5 + K.hash(i * 5.3 + 3) * 3.5;
      c += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return `<g filter="url(#papw)" stroke="${K.PAPER}" stroke-width="4" stroke-linejoin="round">${c}</g>`;
  }

  function tip(w, wx) {                              // 翅尖的畫面座標
    const a = w[0] * Math.PI / 180, vx = 76 * w[1], vy = 30;
    const pxx = 146 + vx * Math.cos(a) - vy * Math.sin(a), pyy = 176 + vx * Math.sin(a) + vy * Math.cos(a);
    return { x: wx + U * (300 - pxx - 132), y: FOOT.y - 280 * U + U * pyy };
  }
  const HOLD = tip(W5[2], FOOT.x);

  function pigeonState(k, kW, kArr, F6) {
    const idle = (e) => K.expr(K.clip('idle', k), e || 'normal');
    const wp = (w, e) => Object.assign({}, idle(e), { wing: w[0], wlen: w[1] });
    let p, dx = 0, enter = false, hold = false;
    if (k < kArr) { p = K.clip('walk', k - kW); dx = (kArr - k) * STEP; enter = true; }
    else if (k < F6) { const i = Math.min(k - kArr, 2); p = wp(W5[i]); hold = i >= 2; }
    else p = wp(PT[Math.min(k - F6, 2)], 'smug');
    return { pose: Object.assign({}, p, { flip: 1 }), dx, enter, hold };
  }

  // 問題牌:面 b = 空白紙白、y = 黃底內容(i = 0,1,2)
  function face(kind, i, pal) {
    const W = CARD.w, H = CARD.h;
    if (kind === 'b') {
      return rc(-W / 2, -H / 2, W, H, K.PAPER, ' stroke-linejoin="miter"') +
        `<rect x="${-W / 2 + 24}" y="${-H / 2 + 24}" width="${W - 48}" height="${H - 48}" fill="none" stroke="${TAN}" stroke-width="5" stroke-dasharray="16 11"/>`;
    }
    let c = rc(-W / 2, -H / 2, W, H, K.YELLOW, ' stroke-linejoin="miter"');
    if (i === 0) {
      c += `<path d="M -205 -85 L -205 85 L 20 85" fill="none" stroke="${K.INK}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>` +
        `<path d="M -188 58 L -142 40 L -102 52 L -58 8 L -22 -14 L 22 -58" fill="none" stroke="${K.INK}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>` +
        `<circle cx="22" cy="-58" r="15" fill="${RED}" stroke="none"/>` + txt('? 元', 142, 2, 84, K.INK);
    } else if (i === 1) {
      c += txt('+5', -152, 4, 104, K.INK) + txt('或', -30, 6, 72, K.INK) + emb(PS.LIST.chickenCutlet.fn(pal), 118, 4, 0.55);
    } else {
      c += emb(PS.LIST.coin50.fn(pal), -85, 0, 1.9) + txt('?', 135, 4, 170, K.INK);
    }
    return c;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kDate = Math.max(at(L, 0, 0.39), F[0] + 3);
    const kS = (i) => F[1] + 2 + 2 * i, kW = F[1] + 8, kArr = kW + WALK_N, kBadge = F[2] + 12;
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    let s = '';

    // 句 112:大硬幣與日曆牌(句 113 起在夜空上縮小退場)
    if (k < F[1] + 2) {
      const kk = k - F[0], p = popP(kk);
      const coin = K.paper(`<g stroke-width="1.25">${PS.LIST.coin50.fn(pal, {})}</g>`, { x: COIN.x, y: COIN.y, scale: COIN.u, sx: p, sy: p, k: 'prop', id: 'coinBig', enter: kk < 2 });
      s += shr(coin, COIN.x, COIN.y, k, F[1]);
      if (k >= kDate) s += shr(Ch.dateTag({ x: DATE.x, y: DATE.y, main: '1992', size: DATE.size, rot: -4, k: k - kDate, id: 'date' }), DATE.x, DATE.y, k, F[1]);
    }
    if (k >= F[1]) s += sky();

    // 句 113 起:兩排燈泡
    if (k >= F[1]) {
      const kk = k - F[1], p = popP(kk);
      [128, 310].forEach((y, i) => {
        s += prop('bulbString', { w: 1700, sag: 30, n: 12 }, { x: 960, y, scale: 1, sx: p, sy: p, id: 'bulbs' + i, enter: kk < 2 });
      });
    }
    // 六台攤車一字排開
    STALLS.forEach((nm, i) => {
      if (k < kS(i)) return;
      const kk = k - kS(i), p = popP(kk), x = ST.xs[i];
      s += prop('stall', { sign: nm, awning: AW[i % 3] || pal.main }, { x, y: ST.y, scale: ST.u, sx: p, sy: p, id: 'stall' + i, enter: kk < 2 });
    });

    // 句 114:三張問題牌降下;句 115–117 逐張翻面
    CARD.xs.forEach((cx, i) => {
      const kd = F[2] + 3 * i;
      if (k < kd) return;
      const kf = k - F[3 + i];
      let o, kind = 'b', sxw = 1;
      if (k - kd < 6) {
        const d = K.drop(k - kd);
        o = { y: CARD.y + d.dy * 420, sx: 1 + (d.sx - 1) * 0.35, sy: 1 + (d.sy - 1) * 0.35, enter: d.enter };
      } else {
        o = { y: CARD.y };
        if (kf >= 0) { const fl = FLIP[Math.min(kf, 3)]; kind = fl[0]; sxw = fl[1]; }
        o.sx = sxw;
      }
      s += px(face(kind, i, pal), Object.assign({ x: cx, k: 'card', id: 'card' + i }, o));
    });
    if (k >= kBadge) {
      CARD.xs.forEach((cx, i) => {
        const kk = k - kBadge, p = popP(kk);
        const c = rc(-BADGE.s / 2, -BADGE.s / 2, BADGE.s, BADGE.s, K.YELLOW, ' stroke-linejoin="miter"') + txt(String(i + 1), 0, 3, BADGE.fs, K.INK);
        s += px(c, { x: cx, y: BADGE.y, sx: p, sy: p, k: 'badge', id: 'badge' + i, enter: kk < 2 });
      });
    }

    // 句 118:留言框
    if (k >= F[6] + 2) {
      const kk = k - (F[6] + 2), p = popP(kk), w = BOX.w, h = BOX.h;
      const c = `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="24" fill="${K.PAPER}"/>` +
        `<polygon points="${-w / 2 + 2},-14 ${-w / 2 - 40},10 ${-w / 2 + 2},32" fill="${K.PAPER}"/>` + txt('留言', 0, 3, BOX.fs, K.INK);
      s += px(c, { x: BOX.x, y: BOX.y, sx: p, sy: p, k: 'prop', id: 'msgBox', enter: kk < 2 });
    }

    // 鴿子與手上的硬幣
    if (k >= kW) {
      const pg = pigeonState(k, kW, kArr, F[6]);
      if (k >= kArr) s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
      s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: FOOT.y, scale: U, id: 'main', enter: pg.enter });
      if (pg.hold || (k >= F[6] && k < F[6] + 2)) {
        const cx = HOLD.x + 48, cy = HOLD.y + 4;
        s += shr(prop('coin50', {}, { x: cx, y: cy, scale: 1, id: 'heldCoin' }), cx, cy, k, F[6]);
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_end', dur: 26, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
