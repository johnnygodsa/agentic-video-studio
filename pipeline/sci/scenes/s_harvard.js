/* salary 場景 s_harvard(句 18–22)兩個世界。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 接在 s_twist 之後:開頭畫面 = s_twist 末格(台灣輪廓、台灣角落的小圈、「身邊那一圈」「全台灣」牌、「示意圖」來源牌、鴿子在左欄),
 * 句首第 1 格起整組(台灣、小圈、兩張牌)縮小退場、舊來源牌退場,第 3 格換新來源牌「哈佛雜誌 1996 報導」與問卷板。
 * 版面沿用 PropsSalary.RANK_LAYOUT 的鴿子(左欄、腳底固定、面向右);舞台 x 420–1840。
 * 句18:問卷板彈入;詞「257」黃牌「哈佛公衛學院 257 人」;詞「很怪」問卷板晃一下(3 格)。
 * 句19:句首問卷板與牌退場 → 左地球「世界一」;詞「你賺」你的柱(2)、詞「其他人」別人的柱(1)、詞「兩倍」黃牌「兩倍」。
 * 句20:句首右地球「世界二」;詞「再多一倍」你的柱(4)與黃牌「多一倍」;詞「其他人都」別人的柱(更高)、鴿子 doubt。
 * 句21:句首比例條(只標「將近一半選這個」,不寫百分比)彈入;詞「第一個世界」左地球旁打勾。
 * 句22:句首整個舞台縮小退場 → 天秤彈入(右盤下沉);詞「哈佛」「台大生」兩盤上方牌依序彈入;詞「沒那麼」天秤逐格擺平、鴿子 shrug。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale;
  const DEF = [
    { start: 0.01, end: 6.31, text: '九零年代,哈佛的公共衛生學院找了 257 個老師、學生和職員填問卷,裡面有一題很怪。' },
    { start: 6.43, end: 8.935, text: '第一個世界,你賺的錢是其他人的兩倍。' },
    { start: 9.055, end: 13.93, text: '第二個世界,你賺的錢比第一個世界再多一倍,可是其他人都賺得比你多。' },
    { start: 14.05, end: 18.625, text: '結果將近一半的人選第一個世界,寧願自己少賺,也要贏過旁邊的人。' },
    { start: 18.745, end: 22.97, text: '連哈佛的人都這樣選,台大生嫌一百萬太少,好像也沒那麼奇怪吧。' }];
  const f = (x) => +(+x).toFixed(2);
  const OUT = [1.1, 0.55];                                           // 小件退場:兩格(放大一點再縮小),第三格消失
  const GOUT = [0.8, 0.45];                                          // 整組退場:只縮不放(放大會出邊距)
  const SRC_OLD = '示意圖 不是統計資料', SRC_NEW = '哈佛雜誌 1996 報導';
  const RING = { x: 1110, y: 540, to: { x: 1330, y: 358 }, sc: 0.11 };
  const PERSON = [[560, 430], [1660, 430], [800, 360], [1420, 360], [700, 700], [1520, 700]];
  const TW = { x: 1300, y: 510, u: 2.18 };
  const FS = Ch.FS_LABEL, BASE = 725, BW = 110, UNIT = 70, GY = 560;  // 長條基線 y、柱寬、每 1 份的高度、地球中心 y
  const W1 = { gx: 620, b1: 850, b2: 1010 }, W2 = { gx: 1330, b1: 1570, b2: 1730 };
  const SUR = { x: 1110, y: 470, box: 440, plY: 770 };
  const RB = { x: 1110, y: 205, w: 760, h: 80 };
  const CHK = { x: 775, y: 440 };
  const SCL = { x: 1110, y: 520, s: 2 };                             // 天秤:icon box 700 → 縮放 2
  const SHAKE = [-5, 5, -3, 0];
  const TILT = [1, 0.6, 0.25, 0];

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
  // 以 px 繪製的紙片(中心 o.x,o.y):k = 出現後第幾格(省略 = 已出現)、kx = 退場後第幾格(省略或 <0 = 未退場)
  function sh(content, o) {
    const k = o.k == null ? 99 : o.k, kx = o.kx == null ? -1 : o.kx;
    const p = kx >= 0 ? OUT[kx] || 0 : K.pop(k);
    if (p <= 0) return '';
    const s = o.s == null ? 1 : o.s;
    return K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
      { x: o.x, y: o.y, rot: o.rot, scale: U, sx: p * s, sy: p * s, k: o.kind, id: o.id, enter: k < 2 || kx >= 0, wide: o.wide !== false });
  }
  const plate = (s, fs, o) => Ch.plate(s, fs, o);
  // 整組縮小退場:kx<0 原樣、0–1 縮、≥2 消失
  function group(s, kx, cx, cy) {
    if (kx < 0) return s;
    const p = GOUT[kx];
    return p ? `<g transform="translate(${cx} ${cy}) scale(${p}) translate(${-cx} ${-cy})">${s}</g>` : '';
  }

  function pigeonPose(k, name) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }
  const shrugPose = (kc) => Object.assign({}, K.clip('shrug', kc), { flip: 1 });

  // 來源牌(左上固定)
  function srcLeft(pal, s, k, kx, id) {
    const q = plate(s, Ch.FS_SRC, { chip: pal.main, padX: 0.8 });
    return sh(q.svg, { x: RL.src.x + q.w / 2, y: RL.src.y, k, kx, kind: 'src', id });
  }

  // ---------- 開頭:s_twist 末格 ----------
  function oldStage(pal) {
    let s = K.paper(PT.taiwan(pal, { fill: pal.main }), { x: TW.x, y: TW.y, scale: TW.u, k: 'prop', id: 'tw' });
    const c = RING.to, sc = RING.sc, rx = 620 * sc, ry = 240 * sc;
    const d = `M ${f(-rx)} 0 a ${f(rx)} ${f(ry)} 0 1 0 ${f(2 * rx)} 0 a ${f(rx)} ${f(ry)} 0 1 0 ${f(-2 * rx)} 0 Z`;
    s += sh(`<path d="${d}" fill="none" stroke="${K.INK}" stroke-width="5" stroke-dasharray="8 5.6"/>`, { x: c.x, y: c.y, kind: 'ring', id: 'ring' });
    PERSON.forEach((q, i) => {
      const body = `<circle cx="0" cy="-50" r="28" fill="${K.INK}"/><path d="M -52 62 Q -52 -18 0 -18 Q 52 -18 52 62 Z" fill="${K.INK}"/>`;
      s += sh(body, { x: c.x + sc * (q[0] - RING.x), y: c.y + sc * (q[1] - RING.y), s: sc, kind: 'person', id: 'p' + i });
    });
    const p1 = plate('身邊那一圈', FS, { fill: K.YELLOW, padX: 1 }), x1 = 1000 + p1.w / 2, y1 = 340, mx = (x1 + 1256) / 2, my = (y1 + 356) / 2;
    s += sh(`<path d="M ${f(x1 - mx)} ${f(y1 - my)} L ${f(1256 - mx)} ${f(356 - my)}" fill="none" stroke="${K.INK}" stroke-width="6" stroke-linecap="round"/>`,
      { x: mx, y: my, kind: 'conn', id: 'conn' });
    s += sh(p1.svg, { x: 1000, y: 330, rot: -1.5, kind: 'sheet', id: 'near' });
    const p2 = plate('全台灣', FS, { fill: K.YELLOW, padX: 1 });
    s += sh(p2.svg, { x: 1590, y: 520, rot: 1.5, kind: 'sheet', id: 'all' });
    return s;
  }

  // ---------- 一個世界:地球加兩根柱(你、別人);k* = 出現後第幾格(<0 = 未出現) ----------
  function world(pal, v, W, hs, kG, kB1, kB2) {
    let s = sh(Ch.icon({ svg: PS.globe(pal, { sign: v === 1 ? '世界一' : '世界二', v }), w: 210, h: 306 }, 0, 0, 460), { x: W.gx, y: GY, k: kG, kind: 'prop', id: 'g' + v });
    const grey = `hsl(${pal.h} 8% 72%)`, wBase = W.b2 - W.b1 + BW + 60;
    s += sh(rect(-wBase / 2, -7, wBase, 14, K.INK), { x: (W.b1 + W.b2) / 2, y: BASE - 7, k: kG, kind: 'base', id: 'base' + v });
    [[W.b1, hs[0], pal.main, '你', kB1, 'a'], [W.b2, hs[1], grey, '別人', kB2, 'b']].forEach((b) => {
      const h = b[1] * UNIT;
      s += sh(rect(-BW / 2, -h / 2, BW, h, b[2]), { x: b[0], y: BASE - h / 2, k: b[4], kind: 'bar', id: `bar${v}${b[5]}`, wide: h / BW > 3 });
      const lb = plate(b[3], FS, { padX: 1 });
      s += sh(lb.svg, { x: b[0], y: BASE + 16 + lb.h / 2, k: b[4], kind: 'barL', id: `barL${v}${b[5]}` });
    });
    return s;
  }

  // 天秤兩盤上方牌的位置(依傾斜算,與 PS.scale 幾何一致:臂長 110、傾角 12°、整體下移 22、樞軸 y=-100)
  function panXY(tilt, side) {
    const a = tilt * 12 * Math.PI / 180, ex = 110 * Math.cos(a), ey = 110 * Math.sin(a);
    return { x: SCL.x + side * ex * SCL.s, y: SCL.y + (-78 + side * ey) * SCL.s - 75 };
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const KX = F[0] + 1, KSur = F[0] + 3;                              // 開頭舊畫面退場、問卷板與新來源牌
    const KPl = Math.max(wordK(L[0], '257'), KSur + 5), KWei = Math.max(wordK(L[0], '很怪'), KPl + 5);
    const KG1 = F[1] + 2, KB1 = Math.max(wordK(L[1], '你賺'), KG1 + 3), KBo1 = Math.max(wordK(L[1], '其他人'), KB1 + 4), K2x = Math.max(wordK(L[1], '兩倍'), KBo1 + 4);
    const KG2 = F[2], KB2 = Math.max(wordK(L[2], '再多一倍'), KG2 + 3), KP2 = KB2 + 3, KBo2 = Math.max(wordK(L[2], '其他人都'), KP2 + 4);
    const KR = F[3], KCk = Math.max(wordK(L[3], '第一個世界'), KR + 5);
    const KSc = F[4] + 3, KT1 = Math.max(wordK(L[4], '哈佛'), KSc + 3), KT2 = Math.max(wordK(L[4], '台大生'), KT1 + 4), KBal = Math.max(wordK(L[4], '沒那麼'), KT2 + 5);
    let s = '';

    // 來源牌
    if (k < KX + 2) s += srcLeft(pal, SRC_OLD, 99, k - KX, 'srcOld');
    if (k >= KSur) s += srcLeft(pal, SRC_NEW, k - KSur, -1, 'src');

    // 開頭舊畫面(台灣、小圈、兩張牌)整組縮小退場
    if (k < KX + 2) s += group(oldStage(pal), k - KX, RING.x, RING.y);

    // 舞台:句18 問卷板 → 句19–21 兩個世界與比例條(句22 整組退場)
    const kS = k - F[4];
    let stage = '';
    if (k >= KSur && k < F[1] + 2) {
      const kx = k - F[1];
      const sw = k >= KWei && k - KWei < SHAKE.length ? SHAKE[k - KWei] : 0;
      stage += sh(Ch.icon({ svg: PS.survey(pal), w: 170, h: 222 }, 0, 0, SUR.box), { x: SUR.x, y: SUR.y, rot: sw, k: k - KSur, kx, kind: 'prop', id: 'survey' });
      if (k >= KPl) {
        const p = plate('哈佛公衛學院 257 人', 64, { fill: K.YELLOW, padX: 1 });
        stage += sh(p.svg, { x: SUR.x, y: SUR.plY, rot: -1, k: k - KPl, kx, kind: 'sheet', id: 'surL' });
      }
    }
    if (k >= KG1) stage += world(pal, 1, W1, [2, 1], k - KG1, k - KB1, k - KBo1);
    if (k >= K2x) {
      const p = plate('兩倍', FS, { fill: K.YELLOW, padX: 1 });
      stage += sh(p.svg, { x: 960, y: 500, rot: -1.5, k: k - K2x, kind: 'sheet', id: 'x2' });
    }
    if (k >= KG2) stage += world(pal, 2, W2, [4, 5.5], k - KG2, k - KB2, k - KBo2);
    if (k >= KP2) {
      const p = plate('多一倍', FS, { fill: K.YELLOW, padX: 1 });
      stage += sh(p.svg, { x: 1560, y: 378, rot: 1.5, k: k - KP2, kind: 'sheet', id: 'x2b' });
    }
    if (k >= KR) {
      const grey = `hsl(${pal.h} 8% 72%)`;
      stage += Ch.ratioBar({ x: RB.x, y: RB.y, w: RB.w, h: RB.h, fs: FS, pal, k: k - KR, id: 'rb',
        segs: [{ value: 47, label: '將近一半選這個', side: 'down', color: pal.main }, { value: 53, color: grey }] });
    }
    if (k >= KCk) {
      const c = `<circle cx="0" cy="0" r="62" fill="hsl(140 60% 40%)"/><path d="M -30 4 L -9 27 L 32 -24" fill="none" stroke="${K.PAPER}" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>`;
      stage += sh(c, { x: CHK.x, y: CHK.y, rot: -4, k: k - KCk, kind: 'sheet', id: 'ok' });
    }
    s += group(stage, k >= F[4] ? kS : -1, 1110, 560);

    // 句22:天秤與兩盤牌
    if (k >= KSc) {
      const tilt = k >= KBal ? TILT[Math.min(k - KBal, TILT.length - 1)] : 1;
      s += sh(Ch.icon({ svg: PS.scale(pal, { tilt }), w: 350, h: 240 }, 0, 0, 700), { x: SCL.x, y: SCL.y, k: k - KSc, kind: 'prop', id: 'scale' });
      if (k >= KT1) {
        const p = plate('哈佛的人', FS, { fill: K.YELLOW, padX: 1 }), q = panXY(tilt, -1);
        s += sh(p.svg, { x: q.x, y: q.y, rot: -1.5, k: k - KT1, kind: 'sheet', id: 'hv' });
      }
      if (k >= KT2) {
        const p = plate('台大生', FS, { fill: K.YELLOW, padX: 1 }), q = panXY(tilt, 1);
        s += sh(p.svg, { x: q.x, y: q.y, rot: 1.5, k: k - KT2, kind: 'sheet', id: 'tu' });
      }
    }

    // 鴿子(左欄):句20 後半 doubt、句22 起 look,詞「沒那麼」shrug
    const P = RL.pigeon;
    const name = k >= KBal ? 'normal' : k >= F[4] ? 'look' : k >= KBo2 ? 'doubt' : k >= F[1] ? 'normal' : 'look';
    const pose = k >= KBal ? shrugPose(k - KBal) : pigeonPose(k, name);
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    s += K.pigeon(pose, { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_harvard', dur: 24, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
