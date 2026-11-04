/* snack 場景 s_hook(句 1–7)開場鉤子,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 佈景:深色夜空紙片鋪滿(四邊留 18px 淺底邊,無 data-k、不入外框檢查)、右上一串燈泡、右半攤車;鴿子從左走入站左下。
 * 句1:價牌「100 元」已在;55% 日曆牌「2023 年 3 月」彈入,緊接(60% 或晚 2 格)價牌翻成 150。
 * 句2:「+50」黃牌彈在價牌左側。
 * 句3:鴿子舉起百元鈔(surprised),鈔票頂端遠低於價牌頂端。
 * 句4:鈔票收起;日曆牌與「+50」退場;三枚硬幣彈入、上方「銅板美食」字牌。
 * 句5:攤車、價牌、硬幣、字牌退場;鴿子手拿記錄板;中央資料夾先關、句首後 5 格開。
 * 句6:資料夾退場;兩張榜單(罵最兇/漲最多,放大 1.25 倍)彈入,三條連線對不上(左1→右3;左2→右2 畫到一半斷掉打叉;左3→榜外下方打叉;右榜第 1 名不被連到)。
 * 句7:右榜第 1 名整列蓋上墨底黃字「?」橫條(傾斜 -3 度),鬧鐘彈在兩榜之間上方。
 * 同時在動的非文字元素 ≤ 2 組(鴿子 + 一個物件);退場一律 2 格縮小。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PS = (typeof window !== 'undefined' && window.PropsSnack) || require('../props_snack.js');
  const U = 1.4;                                    // 鴿子倍率(高約 318px)
  const FOOT = { x: 330, y: 810 };                  // 鴿子腳底落點(面向右:flip)
  const WALK_N = 14, STEP = 36;
  const NIGHT = 'hsl(24 45% 14%)';
  const TAG = { x: 1050, y: 450, fs: 96 };          // 價牌
  const STALL = { x: 1560, y: 565, u: 1.55 };
  const DATE = { x: 340, y: 300, size: 304 };
  const P50 = { x: 690, y: 335, fs: 88 };
  const COINS = [{ n: 'coin50', x: 440 }, { n: 'coin10', x: 600 }, { n: 'coin10', x: 760 }], COIN_Y = 360, COIN_U = 1.6;
  const COINLAB = { x: 600, y: 215, fs: 72 };
  const FOLDER = { x: 1150, y: 460, u: 3.0 }, FLAB = { x: 1150, y: 782, fs: 60 };
  const BS = 1.25;                                  // 榜單放大倍率
  const BOARD = { w: 380 * BS, h: 420 * BS, y: 535, xl: 802.5, xr: 1597.5 };   // 兩張榜單(群組置中於 x 560–1840,間距 320)
  const ALARM = { x: 1200, y: 375, u: 0.85 };        // 兩榜之間上方(右榜上方放不下:燈泡串與榜單之間只剩約 110px)
  const QT = { w: 430, h: 112, fs: 80 };           // 蓋住右榜第 1 名整列的「?」橫條
  const SH = [146, 176], WT = [76, 30];             // 翅膀肩與翅尖(鴿子單位座標)
  const W3 = [[60, 1.1], [125, 1.25], [170, 1.4], [190, 1.4]];   // 舉鈔票
  const LOW = [[120, 1.2], [50, 1.05]];                          // 放下
  const W5 = [[100, 1], [130, 1], [150, 1]];                     // 拿記錄板
  const DEF_TXT = ['寧夏夜市有一攤骰子牛,小份的本來賣 100 元,2023 年 3 月變成 150 元。', '一次多了五十塊。', '你手上那張百元鈔直接不夠用。',
    '以前大家把這種東西叫銅板美食,口袋裡掏幾個銅板就能吃的那種。', '我就跑去翻主計總處的物價資料,想知道銅板美食到底是從哪裡開始要掏鈔票的。',
    '結果翻到一個我完全沒料到的東西,被罵最兇的那幾樣小吃,有的根本排不上漲最多的。', '漲最多的那一項,你可能今天早上才剛吃過。'];
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

  // 夜空紙片(淺底邊 18px);不帶 data-k,不入外框檢查。星點避開字幕帶
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
    else if (k < F[3]) { const w = W3[Math.min(k - F[2], 3)]; p = wp(w, 'surprised'); if (k - F[2] >= 1) hold = { kind: 'bill', w }; }
    else if (k < F[4]) p = k - F[3] < 2 ? wp(LOW[k - F[3]], 'normal') : idle();
    else { const i = Math.min(k - F[4], 2), w = W5[i]; p = wp(w, k >= F[6] ? 'smug' : 'normal'); if (i >= 2) hold = { kind: 'clip', w }; }
    return { pose: Object.assign({}, p, { flip: 1 }), dx, enter, hold };
  }

  // 榜單:紙白底、主色標題帶、三列(名次圓章 + 空白條)
  function board(pal, x, title, k, id) {
    const w = 380, h = 420;
    let c = rc(-w / 2, -h / 2, w, h, K.PAPER, ' stroke-linejoin="miter"') + rc(-w / 2, -h / 2, w, 100, pal.main) + txt(title, 0, -h / 2 + 50, 64, pal.onMain);
    for (let i = 0; i < 3; i++) {
      const cy = -50 + 100 * i;
      c += rc(-70, cy - 38, 230, 76, `hsl(${pal.h} 35% 88%)`) + `<circle cx="-120" cy="${cy}" r="38" fill="${K.INK}" stroke="none"/>` + txt(String(i + 1), -120, cy + 2, 56, K.YELLOW);
    }
    return Ch.sheet(`<g transform="scale(${BS})">${c}</g>`, { x, y: BOARD.y, u: U, k, kind: 'board', id });
  }
  const rowY = (i) => BOARD.y + BS * (-50 + 100 * i);

  // 連線:自 a 畫向 b,prog = 0–1(三格畫完);紙白襯底加墨線
  function link(a, b, k, id, mx) {
    if (k < 0) return '';
    const pr = [0.34, 0.67, 1][Math.min(k, 2)] * (mx || 1), ex = a[0] + (b[0] - a[0]) * pr, ey = a[1] + (b[1] - a[1]) * pr;
    const d = `M ${f(a[0])} ${f(a[1])} L ${f(ex)} ${f(ey)}`;
    const c = `<path d="${d}" fill="none" stroke="${K.PAPER}" stroke-width="24" stroke-linecap="round"/><path d="${d}" fill="none" stroke="${K.INK}" stroke-width="13" stroke-linecap="round"/>`;
    return K.paper(c, { x: 0, y: 0, scale: 1, k: 'line', id, wide: true });
  }
  function cross(x, y, k, id) {
    const p = popP(k);
    if (p <= 0) return '';
    const R = 'hsl(4 68% 52%)', d = 'M -30 -30 L 30 30 M 30 -30 L -30 30';
    const c = `<path d="${d}" fill="none" stroke="${K.PAPER}" stroke-width="30" stroke-linecap="round"/><path d="${d}" fill="none" stroke="${R}" stroke-width="16" stroke-linecap="round"/>`;
    return K.paper(c, { x, y, scale: 1, sx: p, sy: p, k: 'prop', id: id || 'cross', enter: k < 2 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kArr = F[0] + WALK_N;
    const kDate = at(L, 0, 0.55), kFlip = Math.max(at(L, 0, 0.6), kDate + 2);
    const kA = Math.max(at(L, 5, 0.35), F[5] + 6), kB = Math.max(at(L, 5, 0.55), kA + 4), kC = Math.max(at(L, 5, 0.75), kB + 4), kX = kC + 3;
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    let s = sky();

    // 右上燈泡串(全程)
    s += prop('bulbString', { w: 900, sag: 30, n: 8 }, { x: 1370, y: 128, scale: 1, sx: popP(k - F[0]), sy: popP(k - F[0]), id: 'bulbs', enter: k - F[0] < 2 });

    // 攤車與價牌(句 1 起,句 5 退場)
    if (k < F[4] + 2) {
      const kk = k - F[0], p = popP(kk);
      const stall = prop('stall', { sign: '骰子牛' }, { x: STALL.x, y: STALL.y, scale: STALL.u, sx: p, sy: p, enter: kk < 2 });
      const price = Ch.priceFlip({ x: TAG.x, y: TAG.y, from: 100, to: 150, unit: '元', fs: TAG.fs, pal, k: kk, kFlip: k - kFlip });
      s += shr(stall, STALL.x, STALL.y, k, F[4]) + shr(price, TAG.x, TAG.y, k, F[4]);
    }
    // 句 1 日曆牌(句 4 退場)、句 2「+50」(句 4 退場)
    if (k >= kDate && k < F[3] + 2) {
      s += shr(Ch.dateTag({ x: DATE.x, y: DATE.y, top: '3 月', main: '2023 年', size: DATE.size, rot: -4, k: k - kDate, id: 'date' }), DATE.x, DATE.y, k, F[3]);
    }
    if (k >= F[1] && k < F[3] + 2) {
      const pl = Ch.plate('+50', P50.fs, { fill: K.YELLOW, ink: K.INK });
      s += shr(Ch.sheet(pl.svg, { x: P50.x, y: P50.y, rot: -5, u: U, k: k - F[1], kind: 'plus', id: 'p50' }), P50.x, P50.y, k, F[3]);
    }
    // 句 4 硬幣與字牌(句 5 退場)
    if (k >= F[3] + 2 && k < F[4] + 2) {
      COINS.forEach((c, i) => {
        const p = popP(k - (F[3] + 2));
        s += shr(prop(c.n, {}, { x: c.x, y: COIN_Y, scale: COIN_U, sx: p, sy: p, id: c.n + i, enter: k - (F[3] + 2) < 2 }), c.x, COIN_Y, k, F[4]);
      });
      if (k >= F[3] + 6) {
        const pl = Ch.plate('銅板美食', COINLAB.fs, {});
        s += shr(Ch.sheet(pl.svg, { x: COINLAB.x, y: COINLAB.y, u: U, k: k - (F[3] + 6), kind: 'coinlab', id: 'coinlab' }), COINLAB.x, COINLAB.y, k, F[4]);
      }
    }
    // 句 5 資料夾(句 6 退場)
    if (k >= F[4] + 2 && k < F[5] + 2) {
      const kk = k - (F[4] + 2), p = popP(kk), pl = Ch.plate('主計總處 物價', FLAB.fs, {});
      const fo = prop('folder', { open: k >= F[4] + 5 }, { x: FOLDER.x, y: FOLDER.y, scale: FOLDER.u, sx: p, sy: p, enter: kk < 2 });
      const lab = Ch.sheet(pl.svg, { x: FLAB.x, y: FLAB.y, u: U, k: kk, kind: 'flabel', id: 'flabel' });
      s += shr(fo + lab, FOLDER.x, FOLDER.y, k, F[5]);
    }
    // 句 6 榜單與連線;句 7「?」牌與鬧鐘
    if (k >= F[5] + 2) {
      s += board(pal, BOARD.xl, '罵最兇', k - (F[5] + 2), 'bl') + board(pal, BOARD.xr, '漲最多', k - (F[5] + 2), 'br');
      const ax = BOARD.xl + BOARD.w / 2 + 6, bx = BOARD.xr - BOARD.w / 2 - 6, MB = 0.22, ex = [1226, 765];
      s += link([ax, rowY(0)], [bx, rowY(2)], k - kA, 'lA') + link([ax, rowY(1)], [bx, rowY(1)], k - kB, 'lB', MB) + link([ax, rowY(2)], ex, k - kC, 'lC');
      s += cross(ax + (bx - ax) * MB, rowY(1), k - (kB + 3), 'crossB') + cross(ex[0], ex[1], k - kX, 'crossC');
    }
    if (k >= F[6]) {
      const kk = k - F[6], d = K.drop(kk);
      const qc = rc(-QT.w / 2, -QT.h / 2, QT.w, QT.h, K.INK, ' stroke-linejoin="miter"') + txt('?', 0, 3, QT.fs, K.YELLOW);
      s += K.paper(`<g transform="scale(${f(1 / U)})" stroke-width="${f(4 * U)}">${qc}</g>`, { x: BOARD.xr + 1, y: rowY(0) + d.dy * 200, rot: -3, scale: U, sx: 1 + (d.sx - 1) * 0.35, sy: 1 + (d.sy - 1) * 0.35, k: 'qbar', id: 'q', enter: d.enter, wide: true });
      if (kk >= 4) { const p = popP(kk - 4); s += prop('alarm', {}, { x: ALARM.x, y: ALARM.y, rot: 6, scale: ALARM.u, sx: p, sy: p, enter: kk - 4 < 2 }); }
    }

    // 鴿子與手上的東西
    const pg = pigeonState(k, F, kArr);
    if (k >= kArr) s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: FOOT.y, scale: U, id: 'main', enter: pg.enter });
    if (pg.hold) {
      const tp = tip(pg.hold.w);
      if (pg.hold.kind === 'bill') s += prop('bill100', {}, { x: tp.x + 165, y: tp.y - 22, rot: -5, scale: 0.95 });
      else s += prop('clipboard', {}, { x: tp.x + 10, y: tp.y + 10, rot: -6, scale: 0.9 });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_hook', dur: 40, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
