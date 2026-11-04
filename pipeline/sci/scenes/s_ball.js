/* snack 場景 s_ball(句 63–69)地瓜球;「?」記號開頭彈入、句 69 結尾前 5 格退場。固定鏡頭。params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句63(夜景):夜空紙片、燈泡串、攤車招牌「地瓜球」;鴿子走入左下;「空氣」雲朵(詞「空氣」)飄進紙袋(詞「賣給你」)、
 *       紙袋移到鴿子手上(詞「你還吃」),鴿子 smug(圖庫沒有 happy 表情,以 smug 代)。
 * 句64起整場換淺底:夜空、燈泡串、攤車、紙袋、雲朵退場。
 * 句64:地瓜球未剖大特寫(直徑約 520px)加名牌「地瓜球」。
 * 句65:左剖面「麵糰」(bubble 0.15、skin 0.8)加來源小牌;詞「下油鍋」起右剖面「下鍋」(bubble 0.6、skin 0.6、球較大)與箭頭。
 * 句66:油鍋裡一顆球;詞「壓」撈網壓下、球壓扁(sx/sy);詞「擠」三顆油滴擠出;詞「鬆開」撈網抬起球回圓;詞「空氣」箭頭進去。各步配字牌。
 * 句67:三顆剖面由小到大(bubble 0.3/0.65/1、skin 0.8/0.5/0.25)逐顆彈入,加「球越大 皮越薄」牌。
 * 句68:最後一顆 hollow:1 skin 0.2 大特寫,牌「裡面全空」。
 * 句69:詞「工法」彈「工法」小牌;鴿子舉起地瓜球,詞「咬下去」咬一口、speechless。
 * 同時在動的非文字元素 ≤ 2 組;退場一律 2 格縮小。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PS = (typeof window !== 'undefined' && window.PropsSnack) || require('../props_snack.js');
  const U = 1.4;                                    // 鴿子倍率(高約 318px)
  const FOOT = { x: 330, y: 810 };                  // 鴿子腳底落點(面向右:flip)
  const WALK_N = 14, STEP = 36;
  const NIGHT = 'hsl(24 45% 14%)';
  const STALL = { x: 1560, y: 565, u: 1.55 };
  const SH = [146, 176], WT = [76, 30];             // 翅膀肩與翅尖(鴿子單位座標)
  const W5 = [[100, 1], [130, 1], [150, 1]];        // 接紙袋
  const W3 = [[60, 1.1], [125, 1.25], [170, 1.4], [190, 1.4]];   // 舉到嘴邊
  const OIL = 'hsl(42 90% 52%)', AIR = 'hsl(200 75% 62%)';
  const DEF_TXT = ['不過夜市有一樣東西,老闆光明正大地把空氣賣給你,你還吃得很開心。', '我講的是地瓜球。',
    '營養師的解釋是,地瓜和地瓜粉揉成糰的時候會把空氣揉進去,下油鍋之後氣體受熱膨脹,球就被撐大了。',
    '老闆一直拿撈網去壓它,是把吸進去的油擠出來,一鬆開空氣又跑進去,再加熱就再膨脹一次。', '這樣反覆壓個幾輪,球越來越大,皮越來越薄。',
    '最後裡面就空掉了。', '地瓜球空心是工法,跟偷斤減兩沒有關係,只是你咬下去的第一口確實是空氣嘛。'];
  const DEF = (() => { let t = 0; return DEF_TXT.map((s) => { const d = { start: t, end: t + s.length / 6.5 }; t = d.end + 0.12; return d; }); })();
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const texts = (params) => { const L = (params && params.lines) || []; return DEF_TXT.map((s, i) => (L[i] && L[i].text) || s); };
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

  function tip(w) {                                  // 翅尖的畫面座標
    const a = w[0] * Math.PI / 180, vx = WT[0] * w[1], vy = WT[1];
    const px = SH[0] + vx * Math.cos(a) - vy * Math.sin(a), py = SH[1] + vx * Math.sin(a) + vy * Math.cos(a);
    return { x: FOOT.x + U * (300 - px - 132), y: FOOT.y - 280 * U + U * py };
  }

  const cloudSvg = () => `<g fill="${K.PAPER}"><circle cx="-42" cy="10" r="30"/><circle cx="-4" cy="-10" r="42"/><circle cx="44" cy="6" r="32"/>` +
    `<rect x="-42" y="10" width="86" height="32"/></g><path d="M -30 8 C -16 -6, -4 -2, 8 -14 M 10 20 C 24 10, 34 14, 44 6" fill="none" stroke="${AIR}" stroke-width="6" stroke-linecap="round"/>`;
  const arrowSvg = () => `<polygon points="-90,-14 40,-14 40,-36 102,0 40,36 40,14 -90,14" fill="${AIR}"/>`;
  const dropSvg = () => `<path d="M 0 -30 C 18 -6, 20 12, 0 20 C -20 12, -18 -6, 0 -30 Z" fill="${OIL}"/>`;

  function pigeonState(k, F, kArr, kTake, kO) {
    const idle = (e) => K.expr(K.clip('idle', k), e || 'normal');
    const wp = (w, e) => Object.assign({}, idle(e), { wing: w[0], wlen: w[1] });
    let p, dx = 0, enter = false;
    if (k < kArr) { p = K.clip('walk', k - F[0]); dx = (kArr - k) * STEP; enter = true; }
    else if (k < kTake) p = idle();
    else if (k < F[1]) p = wp(W5[Math.min(k - kTake, 2)], k >= kTake + 4 ? 'smug' : 'normal');
    else if (k < F[6]) p = idle();
    else {
      p = wp(W3[Math.min(k - F[6], 3)], k >= kO + 3 ? 'speechless' : 'normal');
      if (k >= kO && k < kO + 3) p.beak = k === kO ? 0.5 : 0.9;
    }
    return { pose: Object.assign({}, p, { flip: 1 }), dx, enter };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), T = texts(params);
    const F = L.map((l) => K.frame(l.start)), kArr = F[0] + WALK_N;
    const wk = (i, w, fb) => { const s = T[i], j = s.indexOf(w); return at(L, i, j < 0 ? fb : j / s.length); };
    const prop = (n, o, extra) => K.paper(PS.LIST[n].fn(pal, o || {}), Object.assign({ k: 'prop', id: n, wide: PS.LIST[n].wide }, extra));
    const lab = (s, fs, x, y, kk, id, fill) => Ch.sheet(Ch.plate(s, fs, fill ? { fill } : {}).svg, { x, y, u: U, k: kk, kind: 'lab', id });
    const ball = (o, x, y, u, kk, id) => { const p = popP(kk); return p <= 0 ? '' : prop('sweetBall', o, { x, y, scale: u, sx: p, sy: p, id, enter: kk < 2 }); };

    // 句 63 時間點
    const kBag = F[0] + 12, kCloud = wk(0, '空氣', 0.44), kPut = Math.max(wk(0, '賣給你', 0.6), kCloud + 6);
    const kTake = Math.min(Math.max(wk(0, '你還吃', 0.75), kPut + 8), F[1] - 9);
    // 句 66 各步
    const kA = Math.max(wk(3, '壓', 0.19), F[3] + 8), kB = Math.max(wk(3, '擠', 0.42), kA + 5), kC = Math.max(wk(3, '鬆開', 0.53), kB + 5), kD = Math.max(wk(3, '空氣', 0.58), kC + 4);
    const kR = Math.max(wk(2, '下油鍋', 0.56), F[2] + 10);
    // 句 69
    const kTag = Math.max(wk(6, '工法', 0.17), F[6] + 3), kO = Math.max(wk(6, '咬下去', 0.58), F[6] + 8);
    const kQOut = K.frame(L[6].end) - 5;

    const hold0 = tip(W5[2]), hold6 = tip(W3[3]);
    let s = '';

    // ===== 夜景(句 63;句 64 起退場) =====
    if (k < F[1] + 2) {
      const e = F[1];
      s += shr(sky(), 960, 540, k, e);
      const kk = k - F[0], p = popP(kk);
      s += shr(prop('bulbString', { w: 900, sag: 30, n: 8 }, { x: 1200, y: 128, scale: 1, sx: p, sy: p, id: 'bulbs', enter: kk < 2 }), 1200, 128, k, e);
      s += shr(prop('stall', { sign: '地瓜球' }, { x: STALL.x, y: STALL.y, scale: STALL.u, sx: p, sy: p, id: 'stall', enter: kk < 2 }), STALL.x, STALL.y, k, e);
      if (k >= kCloud && k < kPut + 2) {
        s += shr(lab('空氣', 56, 1225, 360, k - kCloud, 'airlab'), 1225, 360, k, kPut);
      }
    }

    // ===== 句 64:大特寫 + 名牌 =====
    if (k >= F[1] && k < F[2] + 2) {
      const g = ball({}, 1150, 395, 3.8, k - (F[1] + 1), 'ball1') + lab('地瓜球', 96, 1150, 745, k - (F[1] + 3), 'ball1lab');
      s += shr(g, 1150, 540, k, F[2]);
    }

    // ===== 句 65:兩格剖面 =====
    if (k >= F[2] && k < F[3] + 2) {
      let g = ball({ cut: true, bubble: 0.15, skin: 0.8 }, 790, 405, 3.4, k - F[2], 'cutL') + lab('麵糰', 84, 790, 748, k - F[2], 'labL');
      g += Ch.srcTag('營養師說法(ETtoday)', { x: 580, y: 118, anchor: 'left', pal, k: k - F[2], id: 'src' });
      if (k >= kR) {
        const kk = k - kR;
        g += Ch.sheet(`<g transform="translate(0 0)">${arrowSvg()}</g>`, { x: 1130, y: 405, u: 1, rot: 0, k: kk, kind: 'arrow', id: 'arrow', wide: true });
        g += ball({ cut: true, bubble: 0.6, skin: 0.6 }, 1470, 405, 3.4, kk, 'cutR') + lab('下鍋', 84, 1470, 748, kk, 'labR');
      }
      s += shr(g, 1130, 430, k, F[3]);
    }

    // ===== 句 66:壓、擠、鬆開、空氣進去 =====
    if (k >= F[3] && k < F[4] + 2) {
      const kk = k - F[3], p = popP(kk), R = 69 * 1.9, bottom = 631, bx = 1148;
      let sx = 1, sy = 1, ny = 250;
      if (k >= kA && k < kC) { [sx, sy, ny] = k === kA ? [1.12, 0.8, 330] : [1.3, 0.55, 382]; }
      else if (k >= kC && k < kC + 2) { [sx, sy, ny] = k === kC ? [0.95, 1.1, 330] : [1.02, 0.98, 250]; }
      let g = prop('fryPot', {}, { x: 1200, y: 630, scale: 2.4, sx: p, sy: p, enter: kk < 2 });
      g += K.paper(`<g transform="rotate(-37) translate(65 43)">${PS.skimmer(pal, {})}</g>`, { x: bx, y: ny, scale: 1.7, sx: p, sy: p, k: 'prop', id: 'skimmer', wide: true, enter: kk < 2 });
      g += prop('sweetBall', {}, { x: bx, y: bottom - R * sy * p, scale: 1.9, sx: sx * p, sy: sy * p, id: 'potball', enter: kk < 2 });
      if (k >= kB) {
        [[938, 540], [1358, 540], [1148, 692]].forEach((d, i) => {
          const dk = k - kB, dy = [0, 10, 24, 40][Math.min(dk, 3)], pp = popP(dk);
          g += shr(K.paper(dropSvg(), { x: d[0], y: d[1] + dy, scale: 1.6, sx: pp, sy: pp, k: 'drop', id: 'drop' + i, enter: dk < 2 }), d[0], d[1] + dy, k, kD);
        });
      }
      const step = k >= kD ? ['空氣', kD] : k >= kC ? ['鬆開', kC] : k >= kB ? ['擠', kB] : k >= kA ? ['壓', kA] : null;
      if (step) g += lab(step[0], 110, 740, 330, k - step[1], 'steplab', K.YELLOW);
      if (k >= kD) {
        const dk = k - kD, pp = popP(dk);
        g += K.paper(arrowSvg(), { x: 875, y: 525, scale: 1.2, sx: pp, sy: pp, k: 'arrow', id: 'airL', enter: dk < 2, wide: true });
        g += K.paper(arrowSvg(), { x: 1421, y: 525, rot: 180, scale: 1.2, sx: pp, sy: pp, k: 'arrow', id: 'airR', enter: dk < 2, wide: true });
      }
      s += shr(g, 1200, 460, k, F[4]);
    }

    // ===== 句 67:三顆剖面由小到大 =====
    if (k >= F[4] && k < F[5] + 2) {
      const U4 = 2.55, kq = F[4] + 18;
      let g = ball({ cut: true, bubble: 0.3, skin: 0.8 }, 726, 430, U4, k - F[4], 'c1');
      g += ball({ cut: true, bubble: 0.65, skin: 0.5 }, 1135, 430, U4, k - (F[4] + 8), 'c2');
      g += ball({ cut: true, bubble: 1, skin: 0.25 }, 1597, 430, U4, k - (F[4] + 16), 'c3');
      g += lab('球越大 皮越薄', 84, 1190, 750, k - kq, 'c4lab');
      s += shr(g, 1190, 450, k, F[5]);
    }

    // ===== 句 68–69:最後一顆全空 =====
    if (k >= F[5]) {
      s += ball({ cut: true, bubble: 1, skin: 0.2, hollow: 1 }, 1200, 390, 3.0, k - F[5], 'hollow');
      s += lab('裡面全空', 84, 1200, 748, k - (F[5] + 3), 'hollowlab');
    }
    if (k >= kTag) s += Ch.srcTag('工法', { x: 1470, y: 748, anchor: 'left', pal, k: k - kTag, id: 'tag' });

    // ===== 鴿子與手上的東西 =====
    const pg = pigeonState(k, F, kArr, kTake, kO);
    if (k >= kArr) s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    if (k >= F[6] + 1) {                              // 手上的地瓜球(畫在鴿子後面,嘴在前)
      const bp = popP(k - (F[6] + 1));
      let c = PS.LIST.sweetBall.fn(pal, { bubble: 1 });
      if (k >= kO + 3) c += `<circle cx="-86" cy="-20" r="36" fill="${pal.bg}" stroke="none"/><circle cx="-60" cy="-14" r="14" fill="hsl(46 85% 82%)" stroke="none"/>`;
      s += K.paper(c, { x: hold6.x + 82, y: hold6.y + 12, scale: 1.1, sx: bp, sy: bp, k: 'prop', id: 'handball', enter: k - (F[6] + 1) < 2 });
    }
    s += K.pigeon(pg.pose, { x: FOOT.x - pg.dx, y: FOOT.y, scale: U, id: 'main', enter: pg.enter });

    // 句 63:空氣雲朵與紙袋(畫在鴿子前面)
    if (k >= kBag && k < F[1] + 2) {
      const e = F[1], kk = k - kBag, p = popP(kk);
      const stage = k < kTake ? 0 : k < kTake + 2 ? 1 : k < kTake + 4 ? 2 : 3;
      const BP = [[1060, 650, 1.3], [860, 650, 1.2], [660, 655, 1.05], [hold0.x + 20, hold0.y - 10, 0.9]][stage];
      let g = '';
      if (k >= kCloud) {
        const kc = k - kCloud, rel = BP[2] / 1.3;
        let c;
        if (k < kPut) c = [1225, 480, 1.3];
        else if (k < kPut + 1) c = [1180, 505, 1.3];
        else if (k < kPut + 2) c = [1110, 545, 1.2];
        else c = [BP[0], BP[1] - 112 * rel, 1.1 * rel];
        const cp = popP(kc);
        g += K.paper(cloudSvg(), { x: c[0], y: c[1], scale: c[2], sx: cp, sy: cp, k: 'prop', id: 'cloud', enter: kc < 2 });
      }
      g += prop('paperBag', {}, { x: BP[0], y: BP[1], scale: BP[2], sx: p, sy: p, id: 'bag', enter: kk < 2 });
      s += shr(g, BP[0], BP[1], k, e);
    }

    // 「?」記號:開頭彈入,句 69 結尾前 5 格退場
    s += Ch.triviaMark({ k: k - F[0], kOut: k - kQOut });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_ball', dur: 31.2, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
