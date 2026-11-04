/* salary 場景 s_twist(句 13–17)換一群人。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 接在 s_rank_b 之後:開頭畫面 = s_rank_b 末格(襯底紙蓋住階梯、12 格日曆、「100 萬 ÷ 12 個月」牌、「自算」牌、鴿子在左欄),
 * 第 0–1 格日曆、兩張牌、襯底紙一起縮掉(這兩格階梯整個不畫,不會有半張襯底紙蓋柱子);第 2–3 格九根柱一起退場;第 4 格起長出一根「研究所」柱
 * (查證檔只有中間值 109.9,沒有十分位數,所以只畫這一根)。
 * 版面沿用 PropsSalary.RANK_LAYOUT(階梯基線與縮放不變,「100 萬」橫線位置不動)。
 * 句13:日曆收掉 → 階梯退場;詞「中間值」學士帽落到柱上;詞「109.9」黃牌「109.9 萬」;詞「比一百萬」柱轉黃(超過橫線)。
 * 句14:句首虛線(柱頂中間線)向右畫出;詞「後半段」牌彈入在「100 萬」橫線下方。
 * 句15:句首銀行與「金融保險業」牌彈入;詞「110.6」大數字卡彈入。
 * 句16:舞台逐件退場,鴿子移到圈中央,同一格起虛線圈與第一個小人彈入,其餘小人逐個彈入,每人頭上「100多萬」牌(示意,來源牌改「示意圖」)。
 * 句17:鴿子回左欄、小牌退場、台灣輪廓彈入;詞「身邊那一圈人」那一圈縮小移進台灣的一角並出「身邊那一圈」牌;詞「全台灣」出「全台灣」牌。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale, C = RL.chart;
  const DEF = [
    { start: 0.06, end: 6.08, text: '可是只看研究所畢業的人,一年薪水的中間值已經是 109.9 萬,比一百萬還多。' },
    { start: 6.2, end: 9.02, text: '在研究所這一群裡,年薪一百萬排在後半段。' },
    { start: 9.14, end: 13.225, text: '金融保險業的中間值是 110.6 萬,跟研究所那群人差不多。' },
    { start: 13.345, end: 19.195, text: '我自己是覺得啦,那位同學每天看到的台大研究所同學和學長姐,薪水多半就落在這一帶。' },
    { start: 19.315, end: 22.99, text: '他嫌一百萬太少,比的是身邊那一圈人,不是全台灣。' }];
  const f = (x) => +(+x).toFixed(2);
  const OUT = [1.1, 0.55];                                           // 退場:兩格(放大一點再縮小),第三格消失
  const COVER = { x: 1113, y: 509, w: 1434, h: 658 }, COVER_OUT = [0.8, 0.4];
  const CELL = { w: 200, h: 210, gapX: 29, gapY: 18, x0: 440.5, y0: 368 };
  const SRC_OLD = RL.src.text, SRC_NEW = '主計總處 113 年 全年總薪資中位數(含獎金 稅前 不含公部門與學校)', SRC_DEMO = '示意圖 不是統計資料';
  // 階梯幾何(同 Charts.decileRow:fs 56、柱距 = w/9、柱寬 = 0.74 柱距)
  const FS = Ch.FS_LABEL, tagH = FS * 1.62, yBot = C.y + C.h, yTop = C.y + tagH + 16, n = RL.vals.length, pitch = C.w / n, bw = pitch * 0.74;
  const yOf = (v) => yBot - (yBot - yTop) * v / C.max;
  const BAR = { x: 760, w: 190 };                                    // 研究所柱(自己畫,不佔十等份的位置)
  const GROW = [0.3, 0.55, 0.75, 0.9, 1.04, 1];                      // 長高每格佔 109.9 的比例(末格回到 1)
  const MID = 109.9;
  const BANK = { x: 1490, y: 570, box: 230, lab: 740 }, BIG = { x: 1490, y: 282 };
  // 一圈人:ring 圓心、橢圓半徑、每人位置(身體中心)
  const RING = { x: 1110, y: 540, rx: 620, ry: 240, to: { x: 1330, y: 358 }, end: 0.11 };
  const PERSON = [[560, 430], [1660, 430], [800, 360], [1420, 360], [700, 700], [1520, 700]];
  const PIG_MID = { x: 1110, y: 690 };
  const TW = { x: 1300, y: 510, u: 2.18 };
  const SHRINK = [1, 0.78, 0.52, 0.32, 0.18, 0.11];

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
  // 以 px 繪製的紙片(中心 o.x,o.y):k = 出現後第幾格(省略 = 已出現)、kx = 退場後第幾格(省略或 <0 = 未退場)、p 直接指定縮放、s 額外倍率
  function sh(content, o) {
    const k = o.k == null ? 99 : o.k, kx = o.kx == null ? -1 : o.kx;
    const p = o.p != null ? o.p : kx >= 0 ? (o.out || OUT)[kx] || 0 : K.pop(k);
    if (p <= 0) return '';
    const s = o.s == null ? 1 : o.s;
    return K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
      { x: o.x, y: o.y, rot: o.rot, scale: U, sx: p * s, sy: p * s, k: o.kind, id: o.id, enter: k < 2 || kx >= 0 || !!o.enter, wide: o.wide !== false });
  }
  const plate = (s, fs, o) => Ch.plate(s, fs, o);

  function pigeonPose(k, name) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }
  // 鴿子加腳下襯底:p = 縮放(0 = 不畫)
  function pigeonAt(pal, k, x, y, p, name, id) {
    if (p <= 0) return '';
    return K.ground({ x: x + 20, y: y + 4, w: 300 * p, h: 22 * p, u: U, pal }) +
      K.pigeon(pigeonPose(k, name), { x, y, scale: PU * p, id, enter: p !== 1 });
  }

  // 來源小牌(左上固定);k = 出現後第幾格
  function srcLeft(pal, s, k, id) {
    const q = plate(s, Ch.FS_SRC, { chip: pal.main, padX: 0.8 });
    return sh(q.svg, { x: RL.src.x + q.w / 2, y: RL.src.y, k, kind: 'src', id });
  }

  // ---------- 句13 前:接 s_rank_b 末格的日曆、襯底紙 ----------
  function calendar(pal, k, ke) {
    let s = '';
    for (let i = 0; i < 12; i++) {
      const kx = k - ke;
      if (kx >= 2) continue;
      const col = i % 6, row = Math.floor(i / 6), cx = CELL.x0 + CELL.w / 2 + col * (CELL.w + CELL.gapX), cy = CELL.y0 + CELL.h / 2 + row * (CELL.h + CELL.gapY);
      const w = CELL.w, h = CELL.h;
      const c = rect(-w / 2, -h / 2, w, h, K.PAPER) + rect(-w / 2, -h / 2, w, 62, pal.main) + text(`${i + 1} 月`, 0, -h / 2 + 31, FS, pal.onMain) +
        Ch.icon({ svg: PS.bill(pal), w: 320, h: 140 }, 0, -3, 150) + text('8 萬多', 0, 70, FS, K.INK);
      s += sh(c, { x: cx, y: cy, rot: i % 2 ? 1 : -1, kx, kind: 'calCell', id: 'cal' + i });
    }
    return s;
  }

  // ---------- 十等份階梯(舊畫面):九根柱在 kB 一起退場 ----------
  function ladder(pal, k, kB) {
    let bars = '', nums = '', xl = '';
    const cuts = [];
    RL.vals.forEach((v, i) => {
      const kx = k - kB;
      if (kx >= 2) return;
      const cx = C.x + pitch * (i + 0.5), top = Math.min(yOf(v), yBot - 12), bh = yBot - top, hi = i === 8;
      bars += sh(rect(-bw / 2, -bh / 2, bw, bh, hi ? K.YELLOW : `hsl(${pal.h} 8% 72%)`), { x: cx, y: top + bh / 2, kx, kind: 'decileBar', id: 'dr' + i, wide: bh / bw > 3 });
      if (i === 4 || i === 7 || i === 8) {
        const p = plate(String(v), FS, hi ? { padX: 0.3, fill: K.INK, ink: K.YELLOW } : { padX: 0.3 });
        nums += sh(p.svg, { x: cx, y: top - 16 - p.h / 2, kx, kind: 'decileNum', id: 'dr' + i });
        if (i === 7) cuts.push([cx - p.w / 2 - 16, cx + p.w / 2 + 16, kx]);
      }
      const l = plate('D' + (i + 1), FS, { padX: 0.3 });
      xl += sh(l.svg, { x: cx, y: yBot + 16 + l.h / 2, kx, kind: 'decileX', id: 'dr' + i });
    });
    return { bars, nums, xl, cuts: cuts.filter((c) => c[2] < 2) };
  }

  // 「100 萬」橫線(線被數值牌切斷:與 decileRow 同規則);回傳 {line, label}
  function marker(pal, kx, cuts) {
    const my = yOf(100);
    let a = C.x - 12, line = '', j = 0;
    const segs = [];
    cuts.slice().sort((p, q) => p[0] - q[0]).concat([[C.x + C.w + 12, 0]]).forEach((c) => { if (c[0] - a >= 40) segs.push([a, c[0]]); a = Math.max(a, c[1]); });
    segs.forEach((g) => { line += sh(rect(-(g[1] - g[0]) / 2, -6, g[1] - g[0], 12, K.INK), { x: (g[0] + g[1]) / 2, y: my, kx, kind: 'decileMk', id: 'drM' + j++ }); });
    const p = plate('100 萬', FS, { fill: K.INK, ink: K.YELLOW });
    return { line, label: sh(p.svg, { x: C.x + p.w / 2, y: my - 14 - p.h / 2, rot: -1.5, kx, kind: 'decileMkL', id: 'drML' }) };
  }

  // 虛線(柱頂中間線):x0→x1,k = 出現後第幾格(4 格伸長)
  function dashed(x0, x1, y, k, kx) {
    const fr = [0.25, 0.5, 0.75, 1][Math.max(0, Math.min(3, k))];
    if (k < 0 || kx >= 0) return '';
    const e = x0 + (x1 - x0) * fr;
    return sh(`<path d="M ${f(x0)} ${f(y)} H ${f(e)}" fill="none" stroke="${K.INK}" stroke-width="8" stroke-dasharray="26 18" stroke-linecap="butt"/>`,
      { x: 0, y: 0, p: 1, kind: 'midLine', id: 'mid', enter: k < 1 });
  }

  // 一圈小人:s = 縮放(1 → 0.11)、c = 圓心;rows:每人 k
  function person(pal) {
    return `<circle cx="0" cy="-50" r="28" fill="${K.INK}"/><path d="M -52 62 Q -52 -18 0 -18 Q 52 -18 52 62 Z" fill="${K.INK}"/>`;
  }
  function ring(pal, k, kR, sc, c, kxTag, tagPos) {
    let s = '';
    const rel = (p) => ({ x: c.x + sc * (p[0] - RING.x), y: c.y + sc * (p[1] - RING.y) });
    // 虛線橢圓(畫在小人後面)
    const ke = k - kR;
    if (ke >= 0) {
      const rx = RING.rx * sc * (ke < 2 ? K.pop(ke) : 1), ry = RING.ry * sc * (ke < 2 ? K.pop(ke) : 1);
      const d = `M ${f(c.x - rx)} ${f(c.y)} a ${f(rx)} ${f(ry)} 0 1 0 ${f(2 * rx)} 0 a ${f(rx)} ${f(ry)} 0 1 0 ${f(-2 * rx)} 0 Z`;
      const sw = Math.max(5, 8 * sc), dl = Math.max(8, 30 * sc);
      s += sh(`<path d="${d}" fill="none" stroke="${K.INK}" stroke-width="${f(sw)}" stroke-dasharray="${f(dl)} ${f(dl * 0.7)}"/>`, { x: 0, y: 0, p: 1, kind: 'ring', id: 'ring', enter: ke < 2 });
    }
    PERSON.forEach((q, i) => {
      const kin = k - (kR + 3 * i);
      if (kin < 0) return;
      const r = rel(q);
      s += sh(person(pal), { x: r.x, y: r.y, k: kin, s: sc, kind: 'person', id: 'p' + i });
      const tg = plate('100多萬', FS, { padX: 0.3 });
      if (kxTag < 2) s += sh(tg.svg, { x: r.x, y: r.y - 133, k: kin - 1, kx: kxTag, kind: 'tag', id: 'tg' + i, rot: i % 2 ? 1.5 : -1.5 });
    });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const KE = 0, KB = KE + 2, KG = KB + 2;                         // 日曆與襯底紙一起退場、階梯九根柱一起退場、研究所柱開始長高
    const KCap = Math.max(wordK(L[0], '中間值'), KG + 7), KNum = Math.max(wordK(L[0], '109.9'), KCap + 5), KOver = Math.max(wordK(L[0], '比一百萬'), KNum + 5);
    const KMid = F[1], KBack = Math.max(wordK(L[1], '後半段'), KMid + 5);
    const KBank = F[2], KBig = Math.max(wordK(L[2], '110.6'), KBank + 3);
    const KC3 = F[3];                                                 // 句16:舞台逐件退場
    const KPc = KC3 + 6, KR = KPc;                       // 鴿子到圈中央、虛線圈、第一個小人同一格
    const KP4 = F[4];                                  // 句17
    const KShr = Math.max(wordK(L[4], '身邊那一圈人'), KP4 + 8), KAll = Math.max(wordK(L[4], '全台灣'), KShr + 8);
    const kx = (a) => k - a;                                          // 自 a 起退場後第幾格(<0 = 尚未)
    let s = '';

    // 來源牌:階梯段沿用舊字,研究所柱出現起換新字;句16 起改「示意圖」
    if (k < KG) s += srcLeft(pal, SRC_OLD, 99, 'src');
    else if (k < KC3) s += srcLeft(pal, SRC_NEW, k - KG, 'src');
    else s += srcLeft(pal, SRC_DEMO, k - KC3, 'src');

    // 階梯基線(整段留到句16 退場)
    const stair = k >= KB;                                            // 襯底紙還在縮的兩格,階梯整個不畫
    if (stair) s += sh(rect(-C.w / 2 - 12, -7, C.w + 24, 14, K.INK), { x: C.x + C.w / 2, y: yBot - 7, kx: kx(KC3 + 5), kind: 'decileBase', id: 'drB' });

    // 舊階梯
    const L0 = stair ? ladder(pal, k, KB) : { bars: '', nums: '', xl: '', cuts: [] };
    s += L0.bars;

    // 研究所柱:自 KG 起逐格長高;KOver 起轉黃(超過 100 萬線)
    const kg = k - KG, kBarX = kx(KC3 + 3);
    if (kg >= 0 && kBarX < 2) {
      const v = MID * GROW[Math.min(kg, GROW.length - 1)], top = Math.min(yOf(v), yBot - 12), bh = yBot - top;
      s += sh(rect(-BAR.w / 2, -bh / 2, BAR.w, bh, k >= KOver ? K.YELLOW : pal.main), { x: BAR.x, y: top + bh / 2, k: kg, kx: kBarX, kind: 'gradBar', id: 'gb', wide: bh / BAR.w > 3 });
    }

    // 「100 萬」橫線與牌(整段不動,句16 退場)
    const mk = stair ? marker(pal, kx(KC3 + 4), L0.cuts) : { line: '', label: '' };
    s += mk.line;
    // 句14:虛線(中間線)
    if (k >= KMid) s += dashed(BAR.x + BAR.w / 2, 1150, yOf(MID), k - KMid, kx(KC3 + 1));
    s += L0.nums + L0.xl + mk.label;

    // 研究所柱:底下標籤、頂上學士帽與數值牌
    if (kg >= 0 && kBarX < 2) {
      const lb = plate('研究所 中間值', FS, { padX: 1 });
      s += sh(lb.svg, { x: BAR.x, y: yBot + 16 + lb.h / 2, k: kg, kx: kBarX, kind: 'decileX', id: 'gbL' });
    }
    const kc = k - KCap, kCapX = kx(KC3 + 2);
    if (kc >= 0 && kCapX < 2) {
      const d = K.drop(kc), capH = 99, yc = yOf(MID) + 6 + d.dy * 300 - capH / 2;
      s += sh(Ch.icon({ svg: PS.gradcap(pal), w: 226, h: 140 }, 0, 0, 160), { x: BAR.x, y: yc, p: kCapX >= 0 ? OUT[kCapX] || 0 : 1, kind: 'prop', id: 'cap', enter: kc < 2 });
    }
    if (k >= KNum && kCapX < 2) {
      const p = plate(`${MID} 萬`, FS, { padX: 0.3, fill: K.INK, ink: K.YELLOW });
      s += sh(p.svg, { x: BAR.x, y: yOf(MID) - 99 - 12 - p.h / 2 + 6, rot: -1, k: k - KNum, kx: kCapX, kind: 'gradNum', id: 'gbN' });
    }

    // 句14:「後半段」牌(在 100 萬橫線下方)
    if (k >= KBack && kx(KC3 + 1) < 2) {
      const p = plate('後半段', FS, { fill: K.YELLOW, padX: 1 });
      s += sh(p.svg, { x: 1000, y: yOf(100) + 6 + 16 + p.h / 2, rot: 1.5, k: k - KBack, kx: kx(KC3 + 1), kind: 'sheet', id: 'back' });
    }

    // 句15:銀行、牌、大數字
    if (k >= KBank && kx(KC3) < 2) {
      s += sh(Ch.icon({ svg: PS.bank(pal), w: 290, h: 236 }, 0, 0, BANK.box), { x: BANK.x, y: BANK.y, k: k - KBank, kx: kx(KC3), kind: 'prop', id: 'bank' });
      const p = plate('金融保險業', FS, { fill: K.YELLOW, padX: 1 });
      s += sh(p.svg, { x: BANK.x, y: BANK.lab, rot: -1.5, k: k - KBank - 1, kx: kx(KC3), kind: 'sheet', id: 'bankL' });
    }
    if (k >= KBig && kx(KC3) < 2) {
      const fs = 150, ufs = 57, ug = 12, nw = Ch.tw('110.6', fs), uw = Ch.tw('萬元', ufs) + ug, w = nw + uw + fs * 0.5, h = fs * 1.3, x0 = -w / 2 + fs * 0.25;
      const c = rect(-w / 2, -h / 2, w, h, K.YELLOW) + text('110.6', x0 + nw / 2, 0, fs, K.INK) + text('萬元', x0 + nw + ug + (uw - ug) / 2, fs * 0.36 - ufs * 0.42, ufs, K.INK);
      s += sh(c, { x: BIG.x, y: BIG.y, rot: 1, k: k - KBig, kx: kx(KC3), kind: 'bigNum', id: 'big' });
    }

    // 句16–17:一圈人
    let sc = 1, cc = { x: RING.x, y: RING.y };
    if (k >= KShr) {
      const q = Math.min(k - KShr, SHRINK.length - 1);
      sc = SHRINK[q];
      const tpos = (1 - sc) / (1 - RING.end);
      cc = { x: RING.x + (RING.to.x - RING.x) * tpos, y: RING.y + (RING.to.y - RING.y) * tpos };
    }
    // 台灣輪廓(句17 開頭彈入;畫在小人後面)
    const kTw = k - (KP4 + 3);
    if (kTw >= 0) {
      const p = [0.55, 0.9, 1][Math.min(kTw, 2)];               // 大張紙不過衝(過衝會壓進字幕帶)
      s += K.paper(PT.taiwan(pal, { fill: pal.main }), { x: TW.x, y: TW.y, scale: TW.u, sx: p, sy: p, k: 'prop', id: 'tw', enter: kTw < 2 });
    }
    if (k >= KR) s += ring(pal, k, KR, sc, cc, kx(KP4 + 1), null);

    // 句17:牌
    if (k >= KShr + 6) {
      const p = plate('身邊那一圈', FS, { fill: K.YELLOW, padX: 1 });
      s += sh(`<path d="M ${f(1000 + p.w / 2)} 340 L 1256 356" fill="none" stroke="${K.INK}" stroke-width="6" stroke-linecap="round"/>`, { x: 0, y: 0, p: 1, kind: 'conn', id: 'conn', enter: k - KShr - 6 < 1 });
      s += sh(p.svg, { x: 1000, y: 330, rot: -1.5, k: k - KShr - 6, kind: 'sheet', id: 'near' });
    }
    if (k >= KAll) {
      const p = plate('全台灣', FS, { fill: K.YELLOW, padX: 1 });
      s += sh(p.svg, { x: 1590, y: 520, rot: 1.5, k: k - KAll, kind: 'sheet', id: 'all' });
    }

    // 蓋住階梯的襯底紙與日曆(句13 開頭由 s_rank_b 接過來,逐步退場)
    if (k < KE + 2) {
      const ec = kx(KE);
      s += sh(rect(-COVER.w / 2, -COVER.h / 2, COVER.w, COVER.h, pal.pad), { x: COVER.x, y: COVER.y, kx: ec, out: COVER_OUT, kind: 'cover', id: 'cover' });
      {
        const tp = plate('100 萬 ÷ 12 個月', 84, { fill: K.YELLOW }), kt = kx(KE);
        s += sh(tp.svg, { x: COVER.x, y: 270, rot: -1, kx: kt, kind: 'sheet', id: 'calT' });
        const sp = plate('自算', Ch.FS_SRC, { chip: pal.main, padX: 0.8 });
        s += sh(sp.svg, { x: 1836 - sp.w / 2, y: RL.src.y, kx: kt, kind: 'src', id: 'self' });
      }
      s += calendar(pal, k, KE);
    }

    // 鴿子:句13–15 在左欄;句16 起圈中央;句17 回左欄
    const leftP = k < KC3 + 3 ? 1 : k < KC3 + 5 ? OUT[k - KC3 - 3] : k >= KP4 + 4 ? K.pop(k - KP4 - 4) : 0;
    const midP = k < KPc ? 0 : k >= KP4 ? (OUT[k - KP4] || 0) : K.pop(k - KPc);
    const P = RL.pigeon;
    s += pigeonAt(pal, k, P.x, P.y, leftP, k >= KP4 + 4 ? 'look' : 'normal', 'main');
    s += pigeonAt(pal, k, PIG_MID.x, PIG_MID.y, midP, 'look', 'mid');
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_twist', dur: 24.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
