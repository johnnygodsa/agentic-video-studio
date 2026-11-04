/* turtle 場景 §26 t_fails(句 98–103,26.6 秒)沒那麼有用的部分。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句98:兩欄板(左欄灰暗、右欄亮),右欄兩張編號牌「原因一」「原因二」依序彈入。
 * 句99:原因一變亮、原因二變灰,原因一下方彈出「管得到的範圍很小」。
 * 句100:10×10 方格(700px);30% 起逐格上色 12 格,「12%」大字與「14 類商店」依序彈入,來源小牌「報導引用 2024 專案報告」。
 * 句101:大字與小牌退場,其餘 88 格前站著市場攤位,右側空白日曆牌「?」加「傳統市場和攤販」。
 * 句102:「原因二」;左板生活用品四件、右板海底漁網,中間兩支箭頭指向彼此但停在半途,加紅叉。
 * 句103:上下對照圖(contrastPanel 畫法;上沙灘:寶特瓶與吸管;下海底:漁網與釣魚線),「限塑」箭頭只指到上半;70% 處下半標「另一套規定」。
 * 純圖表場景,無鴿子;同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 紙片倍率(與其他 turtle 場景一致)
  const DEF = [{ start: 0.1, end: 2.98 }, { start: 3.1, end: 5.42 }, { start: 5.54, end: 14.24 }, { start: 14.37, end: 17.01 },
    { start: 17.13, end: 19.98 }, { start: 20.09, end: 26.54 }];
  const RED = 'hsl(6 75% 55%)';
  const SAND = 'hsl(42 60% 80%)', SEA = 'hsl(195 55% 45%)';
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const pf = (l, p) => K.frame(p * (l.end - l.start));            // 句內 p 比例處是第幾格(相對句首)
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  // 嵌入圖解紙片:p 為 Ch.sheet 的額外參數(k、rot、id…)
  const iconSheet = (pal, n, o, x, y, box, p) => Ch.sheet(Ch.icon(ic(pal, n, o), 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: n, wide: PT.LIST[n].wide }, p));
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const plateSheet = (str, fs, o, p) => { const q = Ch.plate(str, fs, o); return Ch.sheet(q.svg, Object.assign({ u: U, kind: 'plate', id: str, wide: true }, p)); };
  // 粗箭頭(px):起點 → 尖端。o: {th,hw,hl,fill,k,id}
  function arrow(x0, y0, x1, y1, o) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, px = -uy, py = ux, th = o.th, hw = o.hw, hl = o.hl;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, bx = x1 - ux * hl, by = y1 - uy * hl;
    const pts = [[x0 + px * th / 2, y0 + py * th / 2], [bx + px * th / 2, by + py * th / 2], [bx + px * hw / 2, by + py * hw / 2], [x1, y1],
      [bx - px * hw / 2, by - py * hw / 2], [bx - px * th / 2, by - py * th / 2], [x0 - px * th / 2, y0 - py * th / 2]];
    return Ch.sheet(`<polygon points="${pts.map((p) => `${f(p[0] - cx)},${f(p[1] - cy)}`).join(' ')}" fill="${o.fill}"/>`,
      { x: cx, y: cy, u: U, k: o.k, kind: 'arrow', id: o.id, wide: Math.min(Math.abs(dx), Math.abs(dy)) < 0.33 * Math.max(Math.abs(dx), Math.abs(dy)) });
  }
  const RB = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;   // 帶紙白描邊的底板
  const crossSvg = (len, th) => [45, -45].map((a) => `<g transform="rotate(${a})">${R(-len / 2, -th / 2, len, th, RED)}</g>`).join('');

  // 市場攤位(px,中心在原點,約 560×440):條紋遮陽棚、後板、桌子與水果
  function stallSvg(pal) {
    let s = '';
    for (let i = 0; i < 7; i++) {
      const x = -280 + i * 80;
      s += `<polygon points="${x},-220 ${x + 80},-220 ${x + 90},-120 ${x - 10},-120" fill="${i % 2 ? K.PAPER : pal.main}"/>`;
    }
    s += R(-250, -120, 16, 330, 'hsl(28 45% 30%)') + R(234, -120, 16, 330, 'hsl(28 45% 30%)') + R(-234, -120, 468, 120, pal.pad);
    s += R(-270, 20, 540, 46, 'hsl(28 45% 36%)') + R(-240, 66, 22, 144, 'hsl(28 45% 30%)') + R(218, 66, 22, 144, 'hsl(28 45% 30%)');
    [[-190, 'hsl(6 75% 55%)'], [-100, 'hsl(25 90% 58%)'], [-10, 'hsl(130 45% 45%)'], [80, 'hsl(6 75% 55%)'], [170, 'hsl(48 90% 55%)']].forEach((c) => {
      s += `<circle cx="${c[0]}" cy="-12" r="38" fill="${c[1]}" stroke="none"/>`;
    });
    return s;
  }

  const pts = (a) => a.map((p) => f(p[0]) + ',' + f(p[1])).join(' ');
  function wave(x0, x1, y, amp, n) {
    const a = [];
    for (let i = 0; i <= n; i++) a.push([x0 + (x1 - x0) * i / n, y + (i % 2 ? -amp : amp)]);
    return a;
  }
  // 上下對照圖底(複製自 t_seabed.js contrastPanel 的畫法):上半沙灘(沙粒)、下半海水(鋸齒海平面加紙白線)。中心 (960,466)、1740×730
  function panelBase() {
    const x = 960, y = 466, w = 1740, h = 730, hh = h / 2;
    let sand = `<rect x="${f(-w / 2)}" y="${f(-hh / 2)}" width="${w}" height="${hh}" fill="${SAND}" stroke-linejoin="miter"/>`;
    for (let i = 0; i < 26; i++) {
      sand += `<circle cx="${f(-w / 2 + 40 + K.hash(i * 3.3 + 1) * (w - 80))}" cy="${f(-hh / 2 + 24 + K.hash(i * 6.1 + 2) * (hh - 48))}" r="${f(4 + K.hash(i * 4.7 + 3) * 4)}" fill="hsl(40 42% 68%)" stroke="none"/>`;
    }
    const top = wave(-w / 2, w / 2, -hh / 2, 13, 40);
    let sea = `<polygon points="${pts(top.concat([[w / 2, hh / 2], [-w / 2, hh / 2]]))}" fill="${SEA}" stroke-linejoin="miter"/>`;
    sea += `<polyline points="${pts(top)}" fill="none" stroke="${K.PAPER}" stroke-width="14" stroke-linejoin="round"/>`;
    return Ch.sheet(sand, { x, y: y - hh / 2, u: U, kind: 'prop', id: 'sand' }) + Ch.sheet(sea, { x, y: y + hh / 2, u: U, kind: 'prop', id: 'sea' });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : k < F[5] ? 4 : 5;
    const q = Math.max(0, k - F[ph]);
    const greyI = `hsl(${pal.h} 8% 42%)`, greyF = `hsl(${pal.h} 8% 72%)`;
    let s = '';

    if (ph <= 1) {                                 // 句98–99:兩欄板、右欄亮、編號牌
      s += Ch.twoCol({ pal, u: U, x: 960, y: 450, w: 1740, h: 700, gap: 24, fs: 72, id: 'tc',
        left: { title: '有用的部分', color: `hsl(${pal.h} 10% 88%)`, titleFill: `hsl(${pal.h} 8% 80%)`, titleInk: greyI },
        right: { title: '沒那麼有用', color: pal.pad, titleFill: K.YELLOW, titleInk: K.INK } });
      s += Ch.iconRow({ pal, u: U, x: 519, y: 520, pitch: 270, size: 200, id: 'dim', items: [
        { icon: ic(pal, 'straw'), dim: true }, { icon: ic(pal, 'cup'), dim: true }, { icon: ic(pal, 'bag', { col: 'hsl(40 20% 90%)' }), dim: true }] });
      const kq = ph === 0 ? q : 99;
      s += plateSheet('原因一', 120, ph === 0 ? { fill: pal.main, ink: pal.onMain } : { fill: pal.main, ink: pal.onMain }, { x: 1401, y: 340, rot: -1.5, k: kq - 2, id: 'r1' });
      s += plateSheet('原因二', 120, ph === 0 ? { fill: pal.main, ink: pal.onMain } : { fill: greyF, ink: greyI }, { x: 1401, y: 690, rot: 1.5, k: kq - 7, id: 'r2' });
      if (ph === 1) s += plateSheet('管得到的範圍很小', 64, { fill: K.YELLOW }, { x: 1401, y: 505, rot: -1, k: q - 2, id: 'cap1' });
    } else if (ph === 2 || ph === 3) {             // 句100–101:方格、12%、攤位與空日曆
      const kFill = k - at(L[2], 0.3), kNum = k - at(L[2], 0.3) - 12;
      s += Ch.dotGrid({ pal, u: U, x: 520, y: 450, size: 700, n: 12, per: 1, kFill: ph === 2 ? kFill : 99, id: 'dg' });
      if (ph === 2) {
        s += Ch.bigNum({ pal, u: U, x: 1340, y: 300, num: '12%', fs: 260, k: kNum, id: 'num' });
        s += plateSheet('14 類商店', 80, { fill: K.YELLOW }, { x: 1340, y: 560, rot: -1.5, id: 'shops' });
        s += Ch.srcTag('報導引用 2024 專案報告', { pal, u: U, x: 1830, y: 770, anchor: 'right', fs: 44, k: q - 3, id: 'src' });
      } else {
        s += Ch.sheet(stallSvg(pal), { x: 520, y: 520, u: U, kind: 'stall', id: 'stall' });
        s += Ch.dateTag({ u: U, x: 1340, y: 400, top: '', main: '?', size: 420, rot: -2, id: 'cal' });
        s += plateSheet('傳統市場和攤販', 60, { fill: K.YELLOW }, { x: 1340, y: 740, rot: 1, id: 'mkt' });
      }
    } else if (ph === 4) {                         // 句102:兩板接不起來
      s += plateSheet('原因二', 72, { fill: pal.main, ink: pal.onMain }, { x: 960, y: 200, rot: -1.5, id: 'r2' });
      s += Ch.sheet(RB(-290, -320, 580, 640, pal.pad), { x: 380, y: 450, u: U, kind: 'col', id: 'L' });
      s += plateSheet('生活用品', 72, { fill: K.YELLOW }, { x: 380, y: 190, rot: -1.5, id: 'tL' });
      [['bag', { col: 'hsl(40 20% 90%)' }, 270, 370, 200], ['cup', {}, 490, 370, 200], ['straw', {}, 270, 600, 220], ['cutlery', {}, 490, 600, 220]].forEach((c, j) => {
        s += iconSheet(pal, c[0], c[1], c[2], c[3], c[4], { k: q - j, id: 'L' + j });
      });
      s += Ch.sheet(RB(-290, -320, 580, 640, SEA), { x: 1540, y: 450, u: U, kind: 'col', id: 'R' });
      s += plateSheet('海底漁網', 72, { fill: K.YELLOW }, { x: 1540, y: 190, rot: 1.5, id: 'tR' });
      s += iconSheet(pal, 'net', {}, 1540, 500, 520, { k: q - 9, id: 'net' });
      s += arrow(690, 450, 900, 450, { th: 30, hw: 90, hl: 70, fill: pal.main, k: q - 16, id: 'aL' });
      s += arrow(1230, 450, 1020, 450, { th: 30, hw: 90, hl: 70, fill: pal.main, k: q - 16, id: 'aR' });
      s += Ch.sheet(crossSvg(90, 26), { x: 960, y: 450, u: U, k: q - 21, kind: 'cross', id: 'x' });
    } else {                                       // 句103:上下對照圖
      s += panelBase();
      s += iconSheet(pal, 'bottle', {}, 700, 276, 320, { id: 'bottle' });
      s += iconSheet(pal, 'straw', {}, 1100, 286, 633, { rot: 84, id: 'straw' });
      s += plateSheet('沙灘 喝完的飲料', 64, { fill: K.YELLOW }, { x: 1539, y: 177, rot: -1.5, id: 'tSand' });
      s += plateSheet('限塑', 72, { fill: K.YELLOW }, { x: 250, y: 190, rot: -2, k: q - pf(L[5], 0.1), id: 'lim' });
      s += arrow(110, 330, 580, 330, { th: 36, hw: 100, hl: 80, fill: pal.main, k: q - pf(L[5], 0.14), id: 'limA' });
      s += iconSheet(pal, 'net', {}, 612, 662, 480, { k: q - pf(L[5], 0.38), id: 'net' });
      s += iconSheet(pal, 'fishline', {}, 1080, 684, 300, { k: q - pf(L[5], 0.5), id: 'fishline' });
      s += plateSheet('另一套規定', 72, { fill: K.YELLOW }, { x: 1539, y: 546, rot: 1.5, k: q - pf(L[5], 0.7), id: 'other' });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_fails', dur: 26.6, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
