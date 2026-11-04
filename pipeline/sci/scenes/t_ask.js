/* turtle 場景 §3 t_ask(句 5–10)網紅的三個質疑,固定鏡頭。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 右側大手機、鴿子在左下。句5:手機彈入,20% 處螢幕上彈出告示縮圖。
 * 句6/7/8:對話泡一/二/三依序彈入(泡帶左半圖,右半圖在 45–55% 彈入;句7 的叉在 75%);句9:鴿子點頭,三個泡各亮黃一下。
 * 句10:三個泡縮掉,待查清單三列依序彈入(10/25/40%),55% 鴿子開始寫;場景最後 0.4 秒清單分兩格收到左上角。
 * 同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PT = (typeof window !== 'undefined' && window.PropsTurtle) || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 290, y: 800 };                  // 鴿子腳底落點(面向右:flip)
  const DUR = 23.6;
  const DEF = [{ start: 0.07, end: 3.81 }, { start: 3.93, end: 9.715 }, { start: 9.835, end: 15.235 }, { start: 15.355, end: 17.605 },
    { start: 17.725, end: 19.765 }, { start: 19.885, end: 23.54 }];
  const PHONE = { x: 1640, y: 440, box: 680 };
  const BUB = [{ x: 757, y: 203, w: 1286 }, { x: 980, y: 451, w: 840 }, { x: 1050, y: 699, w: 700 }];   // 對話泡中心與寬(高 230);右緣 1400 貼手機,泡二三避開鴿子
  const BH = 230;
  const LIST = [{ x: 540, y: 140, w: 1120, rowH: 130, gap: 32, fs: 72 }, { x: 330, y: 120, w: 760, rowH: 104, gap: 20, fs: 62 },
    { x: 100, y: 100, w: 560, rowH: 84, gap: 14, fs: 56 }];
  const SHRINK = [0.7, 0.4];
  const LABELS = ['付錢就安全?', '都送去燒?', '為了省錢?'];
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (L, i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  // 以倍率 sc 繪製的紙片(內容以 px,中心在 x,y);sc<=0 不畫
  function sh(content, o) {
    if (o.sc <= 0) return '';
    const u = o.u || U;
    return K.paper(`<g transform="scale(${(1 / u).toFixed(5)})" stroke-width="${f(4 * u)}">${content}</g>`,
      { x: o.x, y: o.y, scale: u, sx: o.sc, sy: o.sc, k: o.kind, id: o.id, enter: o.enter, wide: o.wide });
  }
  const popSh = (content, o, k) => sh(content, Object.assign({ sc: K.pop(k), enter: k < 2 }, o));

  // 一排(中心 cx 相對於泡中心):items [{w, draw(cx)}]
  function row(items, cx, gap) {
    let x = cx - (items.reduce((a, i) => a + i.w, 0) + gap * (items.length - 1)) / 2, s = '';
    items.forEach((i) => { s += i.draw(x + i.w / 2); x += i.w + gap; });
    return s;
  }
  const arrow = () => ({ w: 56, draw: (c) => `<polygon points="${c - 28},-8 ${c + 6},-8 ${c + 6},-22 ${c + 28},0 ${c + 6},22 ${c + 6},8 ${c - 28},8" fill="${K.INK}"/>` });
  const plus = () => ({ w: 40, draw: (c) => `<rect x="${c - 20}" y="-5" width="40" height="10" fill="${K.INK}" stroke="none"/><rect x="${c - 5}" y="-20" width="10" height="40" fill="${K.INK}" stroke="none"/>` });
  const prop = (pal, name, box, w, o, rot) => ({ w, draw: (c) => (rot ? `<g transform="rotate(${rot} ${c} 0)">` : '<g>') + Ch.icon(ic(pal, name, o || {}), c, 0, box) + '</g>' });
  const crossX = (c, size) => [45, -45].map((a) => `<rect x="${c - size / 2}" y="-11" width="${size}" height="22" fill="${PT.C.red}" transform="rotate(${a} ${c} 0)"/>`).join('');

  // 對話泡本體:圓角紙片加墨色內框,右側小尖角朝手機
  function bubbleBody(w, fill) {
    const a = w / 2, b = BH / 2, r = 40;
    const d = `M ${-a + r} ${-b} H ${a - r} Q ${a} ${-b} ${a} ${-b + r} V ${b - 110} L ${a + 40} ${b - 58} L ${a} ${b - 48} V ${b - r} Q ${a} ${b} ${a - r} ${b}` +
      ` H ${-a + r} Q ${-a} ${b} ${-a} ${b - r} V ${-b + r} Q ${-a} ${-b} ${-a + r} ${-b} Z`;
    return `<path d="${d}" fill="${fill}"/><rect x="${-a + 14}" y="${-b + 14}" width="${w - 28}" height="${BH - 28}" rx="28" fill="none" stroke="${K.INK}" stroke-width="8"/>`;
  }

  // 各泡內容(左半 / 右半 / 叉)
  function contents(pal) {
    const brushI = (w) => prop(pal, 'toothbrush', w, w);
    return [
      { left: row([brushI(220), arrow(), prop(pal, 'turtle', 220, 220, { expr: 'speechless' }, 180)], -360, 14),
        right: row([brushI(190), plus(), prop(pal, 'coin', 120, 120), arrow(), prop(pal, 'turtle', 220, 220)], 255, 10), cross: '' },
      { left: row([prop(pal, 'bag', 150, 111), arrow(), prop(pal, 'incinerator', 190, 135)], -234, 14),
        right: row([prop(pal, 'bag', 150, 111), arrow(), prop(pal, 'turtle', 220, 220, { headUp: true })], 160, 10),
        cross: crossX(160, 200) },
      { left: row([prop(pal, 'coin', 130, 130), plus(), { w: 200, draw: (c) => txt('省錢', c, 0, 88, K.INK) }], 0, 14), right: '', cross: '' },
    ];
  }

  function thumb(pal, sc) {
    const c = `<rect x="-115" y="-155" width="230" height="310" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="-115" y="-155" width="230" height="40" fill="${pal.main}" stroke="none"/>` + Ch.icon(ic(pal, 'turtle', {}), 0, -45, 200) +
      `<rect x="-85" y="40" width="170" height="16" fill="${K.INK}" stroke="none"/><rect x="-85" y="72" width="170" height="14" fill="${PT.C.grey}" stroke="none"/>` +
      `<rect x="-85" y="102" width="110" height="14" fill="${PT.C.grey}" stroke="none"/>`;
    return sh(c, { x: PHONE.x, y: PHONE.y - 4 * PHONE.box / 194, sc, enter: sc < 1, kind: 'thumb', id: 'thumb' });
  }

  function pigeonPose(k, F, kWrite) {
    let p;
    if (k >= F[4] && k < F[4] + 6) p = K.expr(K.clip('nod', k - F[4]), 'look');
    else if (k >= kWrite && k < kWrite + 3) p = K.clip('write_out', 2 - (k - kWrite));
    else if (k >= kWrite + 3) p = K.clip('write', k - kWrite - 3);
    else p = K.expr(K.clip('idle', k), 'look');
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), P = params || {};
    const F = L.map((l) => K.frame(l.start));
    const kEnd = Math.round((P.dur != null && isFinite(P.dur) ? +P.dur : DUR) * K.FPS);
    const C = contents(pal);
    const kShow = [F[1], F[2], F[3]];
    const kRight = [at(L, 1, 0.55), at(L, 2, 0.45), -1];
    const kCross = at(L, 2, 0.75);
    const kHi = [at(L, 4, 0.05), at(L, 4, 0.35), at(L, 4, 0.65)];
    const kRow = [at(L, 5, 0.1), at(L, 5, 0.25), at(L, 5, 0.4)], kWrite = at(L, 5, 0.55);
    let s = '';

    // 手機與螢幕上的告示縮圖
    // 句 10 起手機連同縮圖與泡一起縮掉,讓出位置給待查清單
    const gone = k >= F[5] ? (k - F[5] < SHRINK.length ? SHRINK[k - F[5]] : 0) : -1, kT = k - at(L, 0, 0.2);
    s += sh(Ch.icon(ic(pal, 'phone', { screen: pal.pad }), 0, 0, PHONE.box), { x: PHONE.x, y: PHONE.y, sc: gone >= 0 ? gone : K.pop(k - F[0]),
      enter: gone >= 0 || k - F[0] < 2, kind: 'phone', id: 'phone' });
    if (kT >= 0) s += thumb(pal, gone >= 0 ? gone : K.pop(kT));

    // 三個對話泡
    for (let i = 0; i < 3; i++) {
      const kb = k - kShow[i];
      if (kb < 0) continue;
      let sc = K.pop(kb), enter = kb < 2;
      if (k >= F[5]) { const j = k - F[5]; sc = j < SHRINK.length ? SHRINK[j] : 0; enter = true; }
      const lit = k >= kHi[i] && k < kHi[i] + 4 && k < F[5];
      const o = { x: BUB[i].x, y: BUB[i].y, sc, enter, kind: 'bubble', id: 'bubble' + i, wide: BUB[i].w / BH > 3 };
      s += sh(bubbleBody(BUB[i].w, lit ? K.YELLOW : K.PAPER) + C[i].left, o);
      if (C[i].right && k >= kRight[i]) {
        const kr = k - kRight[i], scr = k >= F[5] ? sc : K.pop(kr);
        s += sh(C[i].right, { x: BUB[i].x, y: BUB[i].y, sc: scr, enter: enter || kr < 2, kind: 'bubbleR', id: 'bubbleR' + i, wide: true });
      }
      if (C[i].cross && k >= kCross) {
        const kx = k - kCross, scx = k >= F[5] ? sc : K.pop(kx);
        s += sh(C[i].cross, { x: BUB[i].x, y: BUB[i].y, sc: scx, enter: enter || kx < 2, kind: 'cross', id: 'cross' + i, wide: true });
      }
    }

    // 待查清單:三列依序彈入,最後 0.4 秒收到左上角
    const kC = kEnd - 4, st = k >= kC + 2 ? 2 : k >= kC ? 1 : 0, S = LIST[st];
    s += Ch.checklist({ x: S.x, y: S.y, w: S.w, rowH: S.rowH, gap: S.gap, fs: S.fs, pal, u: U, id: 'todo',
      items: LABELS.map((label, i) => ({ label, state: 'empty', k: k - kRow[i] })) });

    s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 380, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, F, kWrite), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_ask', dur: DUR, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
