/* salary 場景 s_happy_a(句 23–27)七萬五千美元。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 版面沿用 PropsSalary.RANK_LAYOUT 的鴿子欄(左,腳底固定、面向右),舞台在 x 450–1800。名牌 = 紙牌加剪影(不畫臉)加名字條。
 * 句23:笑臉計量表句首彈入、指針在中間輕晃,牌「開心度?」;鴿子 doubt。
 * 句24:計量表與牌退場;來源牌「PNAS 2010 論文」;句首日曆牌 2010;詞「兩位」兩張名牌(康納曼、迪頓)彈入;詞「諾貝爾」黃牌「後來都拿諾貝爾經濟學獎」;
 *       詞「四十五萬份」大數字卡「45 萬 份」加問卷板三張疊起(說明牌「美國人的問卷」)。
 * 句25:句 24 的牌全部退場;折線圖底與兩個軸牌彈入;詞「年收入」折線由左往右逐點長出;詞「七萬五千」轉折點黃牌「7.5 萬美元」;詞「不太會」右側平線逐點長出。
 * 句26:句首價牌「快樂的價格?」掛在平線下(詞「快樂的價格」前就在);詞「傳得很廣」右側三個對話泡逐個彈出(複製這張牌)。
 * 句27:句 25–26 的圖、牌、泡全部退場;來源牌改「PNAS 2021 論文」;日曆牌 2021;詞「基林斯沃斯」名牌;詞「手機」手機彈入,
 *       之後每隔 7 格跳一則通知「你現在開心嗎?」共三則;詞「三萬多」大數字卡「3 萬多 人」。
 * 圖上折線為示意(只示意「平了」),來源牌不標資料點數值。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale;
  const DEF = [
    { start: 0.09, end: 1.895, text: '那錢到底要賺到多少才夠?' },
    { start: 2.015, end: 8.89, text: '2010 年,兩位後來都拿到諾貝爾經濟學獎的學者康納曼和迪頓,分析了四十五萬份美國人的問卷。' },
    { start: 9.01, end: 14.16, text: '他們看到的是年收入到七萬五千美元左右,每天開不開心就不太會再往上走。' },
    { start: 14.28, end: 17.82, text: '這個七萬五千美元後來傳得很廣,常被說成是快樂的價格。' },
    { start: 17.94, end: 23.99, text: '2021 年,另一位研究者基林斯沃斯用手機問了三萬多個上班族,一天問好幾次你現在開不開心。' }];
  const SRC_A = 'PNAS 2010 論文 康納曼與迪頓', SRC_B = 'PNAS 2021 論文 基林斯沃斯';
  const f = (x) => +(+x).toFixed(2);
  const OUT = [1.1, 0.55];                                           // 退場:放大一點再縮小,第三格消失
  const FS = Ch.FS_LABEL;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  // 詞的起始字索引 ÷ 句長 × 句長秒數 + start → 第幾格;不早於句首、不晚於句尾前 1.3 秒(之後沒有時間看)
  const wordK = (l, w) => {
    const i = Math.max(0, l.text.indexOf(w)), k = K.frame(l.start + i / l.text.length * (l.end - l.start));
    return Math.max(K.frame(l.start), Math.min(k, K.frame(l.end - 1.3)));
  };

  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const text = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  // 以 px 繪製的紙片(同 Charts.sheet,但 sx、sy 可自訂)
  const paperPx = (content, o) => K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
    { x: o.x, y: o.y, rot: o.rot, scale: U, sx: o.sx, sy: o.sy, k: o.kind, id: o.id, enter: o.enter, wide: o.wide !== false });
  // 會彈入、也會縮掉的紙片:kIn = 出現後第幾格(<0 未出現)、kOut = 開始退場後第幾格(<0 未退)
  function piece(content, o, kIn, kOut) {
    let p;
    if (kOut >= 0) { if (kOut >= OUT.length) return ''; p = OUT[kOut]; } else { if (kIn < 0) return ''; p = K.pop(kIn); }
    return paperPx(content, Object.assign({}, o, { sx: p, sy: p, enter: kOut >= 0 || kIn < 2 }));
  }
  // 整組字串(Charts 元件回傳的)的退場:以 (cx,cy) 為中心縮放
  function gone(s, cx, cy, kOut) {
    if (kOut < 0) return s;
    if (kOut >= OUT.length) return '';
    const p = OUT[kOut];
    return `<g transform="translate(${f(cx)} ${f(cy)}) scale(${p}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }

  // 鴿子:idle 呼吸(眨眼格保留)、面向右(flip)、表情只換眼
  function pigeonPose(k, name) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }

  // 名牌:紙牌 + 剪影(頭加圓肩,不畫臉) + 名字條。內容以 px、中心在牌中心
  const CARD = { w: 360, h: 390 };
  function card(pal, name) {
    const w = CARD.w, h = CARD.h, top = -h / 2 + 24;
    return rect(-w / 2, -h / 2, w, h, K.PAPER) + rect(-140, top, 280, 236, pal.pad) +
      `<circle cx="0" cy="-76" r="46" fill="${K.INK}"/>` +
      `<path d="M -96 66 V 14 Q -96 -22 -56 -24 H 56 Q 96 -22 96 14 V 66 Z" fill="${K.INK}"/>` +
      rect(-w / 2, 92, w, h / 2 - 92, pal.main) + text(name, 0, 143, 64, pal.onMain);
  }

  const iconPx = (ic, box) => Ch.icon(ic, 0, 0, box);

  // 折線圖(示意):繪圖區 x,y,w,h;收入 0–15 萬美元;開心 0–100
  const CH = { x: 480, y: 240, w: 900, h: 520, pad: 50, top: 150, th: 14, r: 17 };
  const BASE = CH.y + CH.h;
  const xOf = (inc) => CH.x + CH.pad + inc / 15 * (CH.w - 2 * CH.pad);
  const yOf = (v) => BASE - CH.th - v / 100 * (BASE - CH.th - (CH.y + CH.top));
  const RISE = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5], FLAT = [9, 10.5, 12, 13.5, 15], VMAX = 88;
  const PTS = RISE.map((i) => ({ x: xOf(i), y: yOf(VMAX * (1 - Math.pow((7.5 - i) / 8, 2))) })).concat(FLAT.map((i) => ({ x: xOf(i), y: yOf(VMAX) })));
  function seg(a, b, k, id) {
    const dx = a.x - b.x, dy = a.y - b.y, L = Math.hypot(dx, dy) || 1, nx = -dy / L * CH.th / 2, ny = dx / L * CH.th / 2;
    const q = [[-dx / 2 + nx, -dy / 2 + ny], [dx / 2 + nx, dy / 2 + ny], [dx / 2 - nx, dy / 2 - ny], [-dx / 2 - nx, -dy / 2 - ny]];
    return Ch.sheet(`<polygon points="${q.map((v) => `${f(v[0])},${f(v[1])}`).join(' ')}" fill="${K.INK}"/>`,
      { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, u: U, k, kind: 'lineSeg', id, wide: Math.abs(dx) > 3 * Math.abs(dy) });
  }
  function dot(a, k, id, yellow, pal) {
    return Ch.sheet(`<circle cx="0" cy="0" r="${CH.r}" fill="${yellow ? K.YELLOW : pal.main}"/><circle cx="0" cy="0" r="${f(CH.r * 0.4)}" fill="${K.INK}" stroke="none"/>`,
      { x: a.x, y: a.y, u: U, k, kind: 'lineDot', id });
  }
  // kBase = 底與軸牌出現後第幾格、kR = 折線第 0 點出現後第幾格(<0 未出現)、kF = 平線第 0 點、kKnee = 轉折黃牌
  function chart(pal, kBase, kR, kF, kKnee) {
    let s = Ch.sheet(rect(-CH.w / 2, -CH.h / 2, CH.w, CH.h, pal.pad) + rect(-CH.w / 2, CH.h / 2 - CH.th, CH.w, CH.th, K.INK),
      { x: CH.x + CH.w / 2, y: CH.y + CH.h / 2, u: U, k: kBase, kind: 'lineBase', id: 'cb', wide: true });
    const yl = Ch.plate('開心度', FS), xl = Ch.plate('年收入(美元)', FS);
    s += Ch.sheet(yl.svg, { x: CH.x + 24 + yl.w / 2, y: CH.y + 24 + yl.h / 2, rot: -1, u: U, k: kBase, kind: 'sheet', id: 'cy', wide: true });
    s += Ch.sheet(xl.svg, { x: CH.x + CH.w - 24 - xl.w / 2, y: BASE - CH.th - 24 - xl.h / 2, rot: 1, u: U, k: kBase, kind: 'sheet', id: 'cx', wide: true });
    const kp = (i) => (i < RISE.length ? kR - i : kF - (i - RISE.length));
    let segs = '', dots = '';
    PTS.forEach((p, i) => {
      const k = kp(i);
      if (k < 0) return;
      if (i > 0 && kp(i - 1) >= 0) segs += seg(p, PTS[i - 1], k, 'cs' + i);
      if (i === 0 || i === PTS.length - 1) dots += dot(p, k, 'cd' + i, false, pal);
    });
    if (kKnee >= 0) {
      const kn = PTS[RISE.length - 1], tp = Ch.plate('7.5 萬美元', FS, { fill: K.YELLOW });
      dots += dot(kn, kKnee, 'cdk', true, pal);
      dots += Ch.sheet(tp.svg, { x: kn.x, y: kn.y - CH.r - 16 - tp.h / 2, rot: -1.5, u: U, k: kKnee, kind: 'sheet', id: 'ck', wide: true });
    }
    return s + segs + dots;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const at = (i, w) => wordK(L[i], w);
    let s = '';

    // 來源牌:句24–26 = 2010 年論文,句27 = 2021 年論文(句23 沒有)
    if (k >= F[1] && k < F[4]) s += Ch.srcTag(SRC_A, { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src', k: k - F[1] });
    if (k >= F[4]) s += Ch.srcTag(SRC_B, { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src', k: k - F[4] });

    // ===== 句23:笑臉計量表 =====
    const MT = { x: 1110, y: 450, box: 520 }, kM = F[0], kMo = k - F[1];
    {
      const wob = [0.5, 0.56, 0.5, 0.44], v = k >= kM + 4 && kMo < 0 ? wob[Math.floor((k - kM - 4) / 2) % 4] : 0.5;
      s += piece(iconPx({ svg: PS.meter(pal, { v }), w: PS.LIST.meter.w, h: PS.LIST.meter.h }, MT.box), { x: MT.x, y: MT.y, kind: 'prop', id: 'meter' }, k - kM, kMo);
      const p = Ch.plate('開心度', 64);
      s += piece(p.svg, { x: MT.x, y: 770, rot: -1, kind: 'sheet', id: 'meterL' }, k - kM - 1, kMo);
    }

    // ===== 句24:兩位學者、45 萬份問卷(句25 起退場) =====
    {
      const kO = k - F[2];
      const kD = at(1, '2010'), kC1 = at(1, '兩位'), kC2 = kC1 + 2, kN = Math.max(at(1, '諾貝爾'), kC2 + 1), kS = at(1, '四十五萬份');
      if (k >= kD) s += gone(Ch.dateTag({ x: 1400, y: 300, top: '論文', main: '2010', size: 220, rot: -2, k: k - kD, pal, id: 'd10' }), 1400, 300, kO);
      [['康納曼', 630, kC1, -1.5], ['迪頓', 1000, kC2, 1.5]].forEach((c, i) => {
        s += piece(card(pal, c[0]), { x: c[1], y: 440, rot: c[3], kind: 'card', id: 'card' + i }, k - c[2], kO);
      });
      const nb = Ch.plate('後來都拿諾貝爾經濟學獎', FS, { fill: K.YELLOW });
      s += piece(nb.svg, { x: 810, y: 740, rot: -1, kind: 'sheet', id: 'nobel' }, k - kN, kO);
      [[-30, -6], [0, 0], [30, 6]].forEach((o, i) => {
        s += piece(iconPx({ svg: PS.survey(pal), w: PS.LIST.survey.w, h: PS.LIST.survey.h }, 220), { x: 1690 + o[0], y: 310 - Math.abs(o[1]) , rot: o[1], kind: 'prop', id: 'sv' + i }, k - kS - 1 - i, kO);
      });
      if (k >= kS) s += gone(Ch.bigNum({ x: 1535, y: 590, num: '45 萬', unit: '份', note: '美國人的問卷', fs: 150, rot: -1, k: k - kS, kNote: k - kS - 2, id: 'n45' }), 1535, 660, kO);
    }

    // ===== 句25–26:折線圖、價牌、對話泡(句27 起退場) =====
    {
      const kO = k - F[4];
      const kBase = F[2] + 2, kR = Math.max(kBase + 2, at(2, '年收入')), kKnee = Math.max(kR + RISE.length, at(2, '七萬五千')),
        kF = Math.max(kKnee + 2, at(2, '不太會'));
      if (k >= kBase) {
        let c = chart(pal, k - kBase, k - kR, k - kF, k - kKnee >= 0 && k >= kKnee ? k - kKnee : -1);
        const flatY = yOf(VMAX), fs = 70, h = fs * 1.7, ty = flatY + 8 + h / 2 + 0.36 * fs;
        if (k >= F[3]) c += Ch.priceFlip({ x: 1130, y: ty, from: '快樂的價格?', fs, rot: -2, k: k - F[3], pal, id: 'tag' });
        s += gone(c, 930, 500, kO);
      }
      const kb = at(3, '傳得很廣');
      [[1570, 300, 'bl', 1.5], [1690, 510, null, -1.5], [1570, 710, null, 1]].forEach((b, i) => {
        if (k < kb + 3 * i) return;
        s += gone(Ch.bubble(['快樂的', '價格?'], { x: b[0], y: b[1], tail: b[2], rot: b[3], k: k - kb - 3 * i, id: 'bb' + i }), b[0], b[1], kO);
      });
    }

    // ===== 句27:基林斯沃斯、手機通知、三萬多人 =====
    if (k >= F[4]) {
      const kD = F[4] + 2, kC = Math.max(F[4] + 2, at(4, '基林斯沃斯')), kPh = Math.max(F[4] + 2, at(4, '手機')), kN = Math.max(F[4] + 2, at(4, '三萬多'));
      s += Ch.dateTag({ x: 1500, y: 330, top: '論文', main: '2021', size: 220, rot: 2, k: k - kD, pal, id: 'd21' });
      s += piece(card(pal, '基林斯沃斯'), { x: 660, y: 440, rot: -1.5, kind: 'card', id: 'cardK' }, k - kC, -1);
      s += piece(iconPx({ svg: PT.phone(pal, { screen: pal.pad }), w: 100, h: 194 }, 460), { x: 1080, y: 450, kind: 'prop', id: 'phone' }, k - kPh, -1);
      [[330, -2], [430, 1.5], [530, -1]].forEach((b, i) => {
        const kn = kPh + 3 + 7 * i;
        if (k < kn) return;
        const p = Ch.plate('你現在開心嗎?', FS, { chip: pal.main, padX: 0.8 });
        s += Ch.sheet(p.svg, { x: 1080, y: b[0], rot: b[1], u: U, k: k - kn, kind: 'sheet', id: 'nt' + i, wide: true });
      });
      if (k >= kN) s += Ch.bigNum({ x: 1500, y: 700, num: '3 萬多', unit: '人', fs: 150, rot: 1, k: k - kN, id: 'n3' });
    }

    // 鴿子與腳下襯底:句23 doubt、句24 look、句25 normal、句26 doubt、句27 look
    const P = RL.pigeon;
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    const name = k < F[1] ? 'doubt' : k < F[2] ? 'look' : k < F[3] ? 'normal' : k < F[4] ? 'doubt' : 'look';
    s += K.pigeon(pigeonPose(k, name), { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_happy_a', dur: 24.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
