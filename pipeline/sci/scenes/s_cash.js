/* salary 場景 s_cash(句 38–39)一百萬排多長;「?」記號。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–1。
 * 乾淨舞台:左欄鴿子(PropsSalary.RANK_LAYOUT 鴿子欄)、左上來源牌「自算 央行公告 千元鈔長 160mm」。比例照真實:足球場 105 m = 105·U px,千元鈔 0.16 m。
 * 句38:一疊千元鈔(7 張,每格掉一張)句首彈入;詞「千元鈔」位置黃牌「100 萬 = 1,000 張」;詞「排起來」位置鴿子拿的捲尺彈入;詞「多長」位置「?」記號彈入。
 * 句39:句首疊鈔與牌縮走、足球場(俯視)彈入;詞「16」位置左上「千元鈔一張 16 公分」小圖;詞「一千張」位置一條千元鈔線從左邊球門向右畫出(14 格、每 100 張換一個深淺,捲尺同步拉出),
 *       畫完後「160 公尺」牌彈入;詞「足球場」位置場上牌「約 105 公尺」;詞「一大截」位置超出球場的那段下方黃條加牌「多出一大截」,鴿子 surprised。最後事件後停 ≥1.5 秒。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js');
  const RL = PS.RANK_LAYOUT, PU = RL.pigeon.scale, U = 1.4, FD = PS.FIELD;
  const DEF = [
    { start: 0.09, end: 3.58, text: '一百萬如果全部換成千元鈔,一張接一張排起來有多長?' },
    { start: 3.7, end: 9.405, text: '千元鈔一張長 16 公分,一千張頭尾接起來是 160 公尺,比一座足球場還長一大截。' }];
  const f = (x) => +(+x).toFixed(2);
  const FU = 8.4, FPS_ = 1.6;                                   // 足球場:px 每公尺、紙片 scale
  const FX0 = 470, FY = 520;                                    // 場的左緣(球門線)、中線 y
  const FX = FX0 + FD.len / 2 * FU, STRIP_LEN = 160 * FU, STRIP_H = 14, DRAW_N = 14;
  const STACK = { x: 1130, y: 640, n: 7, sc: 1.1, dy: 17 };
  const FIELD_POP = [0.55, 0.9, 1];
  const TAPE = { x: 300, y: 715, sc: 0.8, rot: -4 };

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  const rawRect = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ''}/>`;
  const sheetPlate = (txt, fs, o) => Ch.sheet(Ch.plate(txt, fs, { fill: o.fill }).svg, { x: o.x, y: o.y, rot: o.rot, u: U, k: o.k, kind: 'sheet', id: o.id, wide: true });

  function pigeonPose(k, name) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }

  // 一疊千元鈔:第 i 張句首起每格掉一張;句39 起兩格縮走。kx = 縮走後第幾格(<0 = 未開始)
  function stack(pal, k, kx) {
    if (kx >= 2) return '';
    const ex = kx >= 0 ? [0.7, 0.35][kx] : 1;
    let s = '';
    for (let i = 0; i < STACK.n; i++) {
      const ki = k - i, p = K.pop(ki) * ex;
      if (p <= 0) continue;
      s += K.paper(PS.bill(pal), { x: STACK.x + (i % 3 - 1) * 6, y: STACK.y - i * STACK.dy, rot: i % 2 ? 1.5 : -1.5, scale: STACK.sc, sx: p, sy: p,
        k: 'prop', id: 'bill' + i, enter: ki < 2 || kx >= 0, wide: true });
    }
    return s;
  }

  // 一千張排成的線:左緣 = 球門線,每 100 張(16 m)換一個深淺;p = 0–1
  function strip(pal, kd) {
    if (kd < 0) return '';
    const p = Math.min(1, (kd + 1) / DRAW_N), len = STRIP_LEN * p, seg = 16 * FU;
    let c = rawRect(FX0, FY - STRIP_H / 2, len, STRIP_H, PS.C.blue);
    for (let i = 1; i < 10; i += 2) {
      const a = FX0 + i * seg;
      if (a < FX0 + len) c += rawRect(a, FY - STRIP_H / 2, Math.min(seg, FX0 + len - a), STRIP_H, PS.C.blueD, ' stroke="none"');
    }
    return K.paper(c, { x: 0, y: 0, scale: 1, k: 'strip', id: 'strip', enter: kd < 2, wide: true });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F0 = K.frame(L[0].start), F1 = K.frame(L[1].start);
    const kStack = k - F0, kx = k >= F1 ? k - F1 : -1;
    const kPlate = Math.max(wordK(L[0], '千元鈔'), F0 + 8), kTape = wordK(L[0], '排起來'), kMark = wordK(L[0], '多長');
    const kBill16 = wordK(L[1], '16'), kStrip = Math.max(wordK(L[1], '一千張'), F1 + 8), kStripEnd = kStrip + DRAW_N;
    const k160 = Math.max(wordK(L[1], '160'), kStripEnd), k105 = wordK(L[1], '足球場'), kOver = Math.max(wordK(L[1], '一大截'), k105 + 8);
    let s = '';

    // 來源牌(全場)
    s += Ch.srcTag('自算 央行公告 千元鈔長 160mm', { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, k: kStack, id: 'src' });

    // 句39:足球場(俯視)
    if (k >= F1) {
      const q = k - F1, p = FIELD_POP[Math.min(q, FIELD_POP.length - 1)];     // 不過衝:大張紙過衝會壓進字幕帶
      s += K.paper(PS.field(pal, { u: FU, ps: FPS_, bills: 0 }), { x: FX, y: FY, scale: FPS_, sx: p, sy: p, k: 'prop', id: 'field', enter: q < 2, wide: true });
    }
    s += strip(pal, k - kStrip);

    // 句38:鈔疊與「100 萬 = 1,000 張」
    s += stack(pal, kStack, kx);
    if (k >= kPlate && kx < 2) {
      const ex = kx >= 0 ? [0.7, 0.35][kx] : 1, q = k - kPlate, p = K.pop(q) * ex;
      s += K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${Ch.plate('100 萬 = 1,000 張', 96, { fill: K.YELLOW }).svg}</g>`,
        { x: STACK.x, y: 330, rot: -1.5, scale: U, sx: p, sy: p, k: 'sheet', id: 'p1000', enter: q < 2 || kx >= 0, wide: true });
    }

    // 句39:「16 公分」小圖(左上,來源牌右側)
    if (k >= kBill16) {
      const q = k - kBill16, p = K.pop(q);
      s += K.paper(PS.bill(pal), { x: 880, y: 150, scale: 0.5, sx: p, sy: p, k: 'prop', id: 'bill16', enter: q < 2, wide: true });
      s += sheetPlate('16 公分', 56, { x: 1130, y: 150, rot: 1, k: q, id: 'p16' });
    }

    // 句39:端點牌「160 公尺」、場上牌「約 105 公尺」、超出段黃條與「多出一大截」
    if (k >= k105) s += sheetPlate('約 105 公尺', 64, { x: FX, y: FY - 130, rot: -1, k: k - k105, id: 'p105' });
    if (k >= k160) s += sheetPlate('160 公尺', 64, { x: FX0 + STRIP_LEN - 190, y: FY - 80, rot: 1.5, k: k - k160, id: 'p160', fill: K.YELLOW });
    if (k >= kOver) {
      const q = k - kOver, w = (FX0 + STRIP_LEN - (FX0 + FD.len * FU)) * Math.min(1, (q + 1) / 3), x0 = FX0 + FD.len * FU;
      s += K.paper(rawRect(x0, FY + 28, w, 14, K.YELLOW, ' stroke="none"'), { scale: 1, k: 'strip', id: 'over', enter: q < 2, wide: true });
      s += sheetPlate('多出一大截', 64, { x: x0 + (STRIP_LEN - FD.len * FU) / 2, y: FY + 110, rot: -1, k: q - 1, id: 'pover' });
    }

    // 鴿子(腳下襯底、拿捲尺)
    const P = RL.pigeon, name = k >= kOver ? 'surprised' : k >= F1 ? 'normal' : 'look';
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    s += K.pigeon(pigeonPose(k, name), { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    if (k >= kTape) {
      const q = k - kTape, p = K.pop(q), out = k >= kStrip ? Math.min(4, k - kStrip + 1) / 4 : 0;
      s += K.paper(PS.tape(pal, { out }), { x: TAPE.x, y: TAPE.y, rot: TAPE.rot, scale: TAPE.sc, sx: p, sy: p, k: 'prop', id: 'tape', enter: q < 2, wide: true });
    }

    // 「?」記號(右上,句38 詞「多長」)
    s += Ch.triviaMark({ k: k - kMark, id: 'trivia' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_cash', dur: 11, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
