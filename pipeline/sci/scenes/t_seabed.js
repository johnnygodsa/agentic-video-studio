/* turtle 場景 §20 t_seabed(句 74–76,15.0 秒)兩個戰場。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 純圖表場景,不放鴿子。
 * 句74:海的剖面(海水大色塊加海底垃圾:漁網、釣魚線、魚鉤、塑膠袋、寶特瓶、飲料杯),比例條「漁網漁具 約六成」加小牌「報導指出 2019」。
 * 句75:淨灘記錄表(漁業浮球、釣魚用具、漁網與繩子三格亮黃),右邊大字「約 8%」加「漁業三格合計」加小牌「自算」。
 * 句76:上下對照圖 contrastPanel(上半沙灘:寶特瓶與吸管;下半海底:漁網與釣魚線;中間一條海平面線),定格到結尾。
 * contrastPanel(pal, o) 供 t_fails 重畫同一張圖(場景檔不互相載入,請複製函式):
 *   o: {x,y(整張圖中心,預設 960,466), w,h(預設 1740×730), u(預設 1.43), k(兩塊色塊,預設 99 = 已出現),
 *       kBottle,kStraw,kLabTop,kNet,kLine,kLabBot(各元素出現後第幾格;省略 = 同 k)}
 *   每個 k 的意義:<0 不畫;省略/99 = 已完全出現;其餘為彈入後第幾格。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率;全場紙片共用(此場景無鴿子,僅決定描邊粗細)
  const DEF = [{ start: 0.07, end: 5.615 }, { start: 5.735, end: 10.655 }, { start: 10.775, end: 14.97 }];
  const SEA = 'hsl(195 55% 45%)', SAND = 'hsl(42 60% 80%)';
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const pts = (a) => a.map((p) => f(p[0]) + ',' + f(p[1])).join(' ');
  // 圖解紙片:Ch.icon 縮到 box 見方內
  const icn = (pal, name, opts, x, y, box, o) => Ch.sheet(Ch.icon({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h }, 0, 0, box),
    Object.assign({ x, y, u: U, kind: 'prop', id: name, wide: PT.LIST[name].wide }, o));
  // 橫向鋸齒線(波浪):x0→x1,中線 y,振幅 amp,n 段
  function wave(x0, x1, y, amp, n) {
    const a = [];
    for (let i = 0; i <= n; i++) a.push([x0 + (x1 - x0) * i / n, y + (i % 2 ? -amp : amp)]);
    return a;
  }

  // ---------- 句74:海的剖面(海水加海底) ----------
  function seaProfile(pal, o) {
    const w = o.w, h = o.h, top = -h / 2;
    let c = `<rect x="${f(-w / 2)}" y="${f(top)}" width="${w}" height="${h}" fill="${SEA}" stroke-linejoin="miter"/>`;
    c += `<polygon points="${pts([[-w / 2, top], [w / 2, top]].concat(wave(w / 2, -w / 2, top + 34, 9, 28)))}" fill="hsl(195 62% 66%)" stroke="none"/>`;
    const bed = [[-w / 2, h / 2]];
    for (let i = 0; i <= 24; i++) bed.push([-w / 2 + w * i / 24, h / 2 - 60 - K.hash(i * 2.9 + 4) * 30]);
    bed.push([w / 2, h / 2]);
    c += `<polygon points="${pts(bed)}" fill="hsl(40 42% 60%)" stroke="none"/>`;
    return Ch.sheet(c, { x: o.x, y: o.y, u: U, k: o.k, kind: 'prop', id: 'sea' });
  }
  const SEA_PANEL = { x: 960, y: 305, w: 1720, h: 430 };
  const PILE = [['net', {}, 330, 400, 340], ['fishline', {}, 640, 410, 260], ['hook', {}, 880, 390, 240],
    ['bag', {}, 1130, 390, 260], ['bottle', {}, 1370, 390, 260], ['cup', {}, 1590, 390, 250]];
  function s74(pal, L, k) {
    let s = seaProfile(pal, Object.assign({ k: 99 }, SEA_PANEL));
    PILE.forEach((p, i) => { s += icn(pal, p[0], p[1], p[2], p[3], p[4], { k: k - at(L[0], 0.04 + 0.07 * i) }); });
    const bar = { pal, u: U, x: 960, y: 690, w: 1500, h: 90, fs: 60, id: 'rb' };
    s += Ch.ratioBar(Object.assign(bar, { segs: [
      { value: 6, label: '漁網漁具', text: '約六成', color: pal.main, side: 'up', k: k - at(L[0], 0.5) },
      { value: 4, label: '其他', color: `hsl(${pal.h} 8% 72%)`, side: 'up', k: k - at(L[0], 0.58) }] }));
    return s + Ch.srcTag('報導指出 2019', { x: 1825, y: 800, anchor: 'right', pal, u: U, k: k - at(L[0], 0.72), id: 'src74' });
  }

  // ---------- 句75:淨灘記錄表加「約 8%」 ----------
  const SHEET = { x: 680, y: 440, sx: 3.3, sy: 2.0 };
  const FISH = [11, 14, 15];                       // 漁業浮球、釣魚用具、漁網與繩子(t_rank 十九類的索引)
  function s75(pal, L, k) {
    const hi = k >= at(L[1], 0.22) ? FISH : [];
    const svg = PT.LIST.tallySheet.fn(pal, { n: 19, hi, tally: [] });
    let s = Ch.sheet(`<g transform="scale(${SHEET.sx} ${SHEET.sy})" stroke-width="${f(5 / 2.45)}">${svg}</g>`,
      { x: SHEET.x, y: SHEET.y, u: U, kind: 'prop', id: 'tallySheet' });
    const kn = k - at(L[1], 0.42);
    s += Ch.bigNum({ x: 1550, y: 330, num: '約8%', fs: 170, note: '漁業三格合計', noteFs: 56, u: U, k: kn, kNote: kn - 2, id: 'n8' });
    return s + Ch.srcTag('自算', { x: 1550, y: 640, anchor: 'center', pal, u: U, k: k - at(L[1], 0.7), id: 'src75' });
  }

  // ---------- 句76:上下對照圖(沙灘/海底) ----------
  // 圖內元素大小:寶特瓶高 312、吸管長 633 粗 45、漁網 480×320、釣魚線 300×174
  function contrastPanel(pal, o) {
    o = o || {};
    const x = o.x == null ? 960 : o.x, y = o.y == null ? 466 : o.y, w = o.w || 1740, h = o.h || 730, u = o.u || U;
    const kd = (v) => (v == null ? (o.k == null ? 99 : o.k) : v);
    const kp = o.k == null ? 99 : o.k, hh = h / 2;
    // 上半:沙灘(沙色大色塊,幾點沙粒)
    let sand = `<rect x="${f(-w / 2)}" y="${f(-hh / 2)}" width="${w}" height="${hh}" fill="${SAND}" stroke-linejoin="miter"/>`;
    for (let i = 0; i < 26; i++) {
      sand += `<circle cx="${f(-w / 2 + 40 + K.hash(i * 3.3 + 1) * (w - 80))}" cy="${f(-hh / 2 + 24 + K.hash(i * 6.1 + 2) * (hh - 48))}" r="${f(4 + K.hash(i * 4.7 + 3) * 4)}" fill="hsl(40 42% 68%)" stroke="none"/>`;
    }
    // 下半:海水(頂端鋸齒 = 海平面)加紙白海平面線
    const top = wave(-w / 2, w / 2, -hh / 2, 13, 40);
    let sea = `<polygon points="${pts(top.concat([[w / 2, hh / 2], [-w / 2, hh / 2]]))}" fill="${SEA}" stroke-linejoin="miter"/>`;
    sea += `<polyline points="${pts(top)}" fill="none" stroke="${K.PAPER}" stroke-width="14" stroke-linejoin="round"/>`;
    let s = Ch.sheet(sand, { x, y: y - hh / 2, u, k: kp, kind: 'prop', id: 'sand' }) + Ch.sheet(sea, { x, y: y + hh / 2, u, k: kp, kind: 'prop', id: 'sea' });
    const yt = y - hh / 2 - 8, yb = y + hh / 2 + 14, lx = x + w * 0.31;
    s += icn(pal, 'bottle', {}, x - w * 0.34, yt, 320, { k: kd(o.kBottle), id: 'bottle' });
    s += icn(pal, 'straw', {}, x + w * 0.0, yt + 10, 633, { rot: 84, k: kd(o.kStraw), id: 'straw' });
    const lt = Ch.plate('沙灘 喝完的飲料', 64, { fill: K.YELLOW }), lb = Ch.plate('海底 廢棄漁網', 64, { fill: K.YELLOW });
    s += Ch.sheet(lt.svg, { x: lx + 40, y: y - h / 2 + 76, rot: -1.5, u, k: kd(o.kLabTop), kind: 'note', id: 'labTop', wide: true });
    s += icn(pal, 'net', {}, x - w * 0.2, yb, 480, { k: kd(o.kNet), id: 'net' });
    s += icn(pal, 'fishline', {}, x + w * 0.12, yb + 22, 300, { k: kd(o.kLine), id: 'fishline' });
    s += Ch.sheet(lb.svg, { x: lx + 40, y: y + 80, rot: 1.5, u, k: kd(o.kLabBot), kind: 'note', id: 'labBot', wide: true });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    let s = '';
    if (k < F[1]) s = s74(pal, L, k);
    else if (k < F[2]) s = s75(pal, L, k);
    else {
      s = contrastPanel(pal, { kBottle: k - at(L[2], 0.1), kStraw: k - at(L[2], 0.26), kLabTop: k - at(L[2], 0.36),
        kNet: k - at(L[2], 0.52), kLine: k - at(L[2], 0.64), kLabBot: k - at(L[2], 0.74) });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_seabed', dur: 15, render, contrastPanel, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
