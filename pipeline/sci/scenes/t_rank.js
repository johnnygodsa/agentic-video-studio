/* turtle 場景 §12 t_rank(句 41–44,24.1 秒)排行(全片最重要的圖表)。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 純圖表場景,不放鴿子。數字來源 projects\turtle\icc_recent.csv 第 7–25 欄(十九類)逐欄加總,已核對:
 * 寶特瓶 93,203、塑膠瓶蓋 54,413、吸管 23,974、牙刷 1,433、針筒針頭 894、總計 386,079。
 * 版面:內容佔 x 100–1820、y 90–838(字幕帶以上全用)。
 * 句41:資料卡 2×2 逐項彈入,依欄出現(左欄 荒野保護協會 愛海小旅行、2024 年底–2026 年 10 月;右欄 575 場、386,079 件),第一張就佔寬六成。
 * 句42:前三名大列逐條長出(寶特瓶、瓶蓋、吸管),三種色相;每列 = 名稱牌(圖示 + 名稱)、長條、數值牌。
 * 句43:十九條窄條佔左側 x 100–1150 逐條出現(其餘灰),牙刷那列變品牌黃加墨框;右側「第 18 名」「牙刷 1,433 支」,箭頭指向牙刷列。
 * 句44:只留吸管與牙刷兩條(長度照 23,974:1,433),下方大字「16 倍以上」。
 * 窄條的名稱與數字 29px 是全片唯一允許的小字。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;
  const DEF = [{ start: 0.07, end: 9.7 }, { start: 9.81, end: 15.67 }, { start: 15.79, end: 20.91 }, { start: 21.04, end: 23.06 }];
  // 十九類件數(由大到小);核對:總和必須是 386,079
  const DATA = [['寶特瓶', 93203], ['塑膠瓶蓋', 54413], ['吸管', 23974], ['玻璃瓶', 22313], ['免洗餐具', 22312], ['塑膠提袋', 22126],
    ['菸蒂', 19757], ['其他飲料瓶與食物容器', 17671], ['外帶飲料杯', 15857], ['食品包裝袋', 15844], ['非食物的瓶罐與容器', 14820],
    ['漁業浮球、浮筒、漁船防碰墊', 12609], ['鋁箔包或利樂包', 12568], ['鐵鋁罐', 11390], ['釣魚用具', 9978], ['漁網與繩子', 9102],
    ['打火機', 5815], ['牙刷', 1433], ['針筒、針頭', 894]];
  const TOTAL = 386079;
  if (DATA.reduce((a, d) => a + d[1], 0) !== TOTAL || DATA.length !== 19) throw new Error('t_rank 數字核對失敗');
  const BAR_COL = ['hsl(205 75% 52%)', 'hsl(32 92% 55%)', 'hsl(350 75% 58%)'];   // 寶特瓶藍、瓶蓋橙、吸管紅:三種色相
  const GROW = [0.25, 0.5, 0.75, 0.9, 1];
  const X0 = 100, X1 = 1820;                       // 內容左右界
  const SRC = '荒野保護協會 開放資料 自算';
  const f = (x) => +(+x).toFixed(2);
  const fmt = (n) => String(n).replace(/\B(?=(\d{3})+$)/g, ',');
  const R = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"${ex || ''}/>`;
  const T = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="${anchor || 'middle'}"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (L, i, frac) => K.frame(L[i].start + frac * (L[i].end - L[i].start));
  const grow = (k) => (k < 0 ? 0 : GROW[Math.min(k, GROW.length - 1)]);
  const np = (k) => (k < 0 ? -1 : k === 0 ? 2 : 3);   // 貼近字幕帶的大牌不過衝:第 0 格 0.95 倍,之後原大

  // 句41 兩行字卡(px,中心在原點):紙白底、左側主色條、墨色字靠左
  function card2(l1, l2, fs, pal) {
    const chip = fs * 0.3, w = Math.max(Ch.tw(l1, fs), Ch.tw(l2, fs)) + fs * 0.9 + chip, lh = fs * 1.28, h = 2 * lh + fs * 0.5;
    const tx = -w / 2 + chip + fs * 0.45;
    return { w, h, svg: R(-w / 2, -h / 2, w, h, K.PAPER) + R(-w / 2, -h / 2, chip, h, pal.main, ' stroke="none"') +
      T(l1, tx, -lh / 2, fs, K.INK, 'start') + T(l2, tx, lh / 2, fs, K.INK, 'start') };
  }

  // 大列(句42、44;每列三片紙):名稱牌(圖示 + 名稱)、長條、數值牌;佔滿 X0–X1。
  // o: {y(第一列上緣),rowH,gap,chars(名稱最多幾字),max,id,rows:[{label,value,g(長條長出比例),color,hi,icon,k}]}
  const BR = { icon: 140, fs: 72, nfs: 110, gx: 14 };
  function bigRows(o) {
    const lead = BR.icon + 24, labelW = lead + o.chars * BR.fs + 22;
    const valW = Math.max(...o.rows.map((r) => Ch.tw(fmt(r.value), BR.nfs))) + 44;
    const barMax = X1 - X0 - labelW - valW - 2 * BR.gx, bh = o.rowH * 0.8, bx = X0 + labelW + BR.gx;
    let s = '';
    o.rows.forEach((r, i) => {
      if (r.k < 0) return;
      const cy = o.y + i * (o.rowH + o.gap) + o.rowH / 2, len = Math.max(12, barMax * r.value / o.max * (r.g == null ? 1 : r.g));
      s += Ch.sheet(R(-labelW / 2, -o.rowH / 2, labelW, o.rowH, r.hi ? K.YELLOW : K.PAPER) + Ch.icon(r.icon, -labelW / 2 + 12 + BR.icon / 2, 0, BR.icon) +
        T(r.label, -labelW / 2 + lead, 0, BR.fs, K.INK, 'start'), { x: X0 + labelW / 2, y: cy, u: U, k: r.k, kind: 'rowL', id: o.id + i });
      s += Ch.sheet(R(-len / 2, -bh / 2, len, bh, r.color), { x: bx + len / 2, y: cy, u: U, k: r.k, kind: 'rowB', id: o.id + i, wide: len / bh > 3 });
      s += Ch.sheet(R(-valW / 2, -bh / 2, valW, bh, r.hi ? K.INK : K.PAPER) + T(fmt(r.value), 0, 0, BR.nfs, r.hi ? K.YELLOW : K.INK),
        { x: bx + len + BR.gx + valW / 2, y: cy, u: U, k: r.k, kind: 'rowV', id: o.id + i });
    });
    return s;
  }

  // 窄條一列(句43;單片紙):名稱牌 + 長條 + 數字牌;px 絕對座標,紙片中心取整列外框中心。十九列佔 x 100–1150、y 92–830
  const NR = { x0: X0, lw: 398, bx: 506, bmax: 517, y0: 110, pitch: 39, h: 35, fs: 29 };
  const rowEnd = (i) => NR.bx + Math.max(12, NR.bmax * DATA[i][1] / DATA[0][1]) + 8 + Ch.tw(fmt(DATA[i][1]), NR.fs) + 16;
  function narrowRow(i, pal, k, opt) {
    const d = DATA[i], cy = NR.y0 + i * NR.pitch, len = Math.max(12, NR.bmax * d[1] / DATA[0][1]);
    const txt = fmt(d[1]), vw = Ch.tw(txt, NR.fs) + 16, xe = rowEnd(i), cx = (NR.x0 + xe) / 2;
    const grey = `hsl(${pal.h} 8% 72%)`, col = opt.hi ? K.YELLOW : i < 3 ? BAR_COL[i] : grey;
    const rx = (x) => x - cx;
    const c = R(rx(NR.x0), -NR.h / 2, NR.lw, NR.h, opt.hi ? K.YELLOW : K.PAPER) + T(d[0], rx(NR.x0 + 10), 0, NR.fs, K.INK, 'start') +
      R(rx(NR.bx), -NR.h / 2, len, NR.h, col) + R(rx(NR.bx + len + 8), -NR.h / 2, vw, NR.h, opt.hi ? K.INK : K.PAPER) +
      T(txt, rx(NR.bx + len + 8 + vw / 2), 0, NR.fs, opt.hi ? K.YELLOW : K.INK) +
      (opt.hi ? R(rx(NR.x0), -NR.h / 2, xe - NR.x0, NR.h, 'none', ` stroke="${K.INK}" stroke-width="7"`) : '');   // 整列一圈墨色框
    return Ch.sheet(c, { x: cx, y: cy, u: U, k, kind: 'nrow', id: 'r' + i, wide: true });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;
    const q = k - F[ph];
    const icn = (name, opts) => ({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h });
    const src = (y, kk) => Ch.srcTag(SRC, { pal, u: U, x: X1 - 5, y, anchor: 'right', k: kk, id: 'src' });
    let s = '';

    if (ph === 0) {                                // 句41:資料卡 2×2,依欄出現(左欄:來源名、日期;右欄:575 場、386,079 件)
      const kk = [at(L, 0, 0), at(L, 0, 0.3), at(L, 0, 0.55), at(L, 0, 0.78)].map((a) => k - a);
      const NFS = 190, UFS = NFS * 0.38, bigW = (num, unit) => Ch.tw(num, NFS) + Ch.tw(unit, UFS) + NFS * 0.08 + NFS * 0.5;
      const yB = 824 - NFS * 1.3 / 2;              // 下排中心:數字牌下緣貼 y 824
      const c1 = card2('荒野保護協會', '愛海小旅行', 144, pal), c2 = card2('2024 年底–', '2026 年 10 月', 82, pal);
      s += Ch.sheet(c1.svg, { x: X0 + c1.w / 2, y: 100 + c1.h / 2, rot: -1, u: U, k: kk[0], kind: 'card', id: 'c1' });
      s += Ch.sheet(c2.svg, { x: X0 + c2.w / 2, y: 824 - c2.h / 2, rot: -1, u: U, k: np(kk[1]), kind: 'card', id: 'c2' });   // 下排貼近字幕帶:不過衝
      s += Ch.bigNum({ pal, u: U, x: X1 - bigW('575', '場') / 2, y: 100 + NFS * 0.65, num: '575', unit: '場', fs: NFS, rot: 1, k: kk[2], id: 'n575' });
      s += Ch.bigNum({ pal, u: U, x: X1 - bigW('386,079', '件') / 2, y: yB, num: '386,079', unit: '件', fs: NFS, rot: -1, k: np(kk[3]), id: 'n386' });
      s += src(450, k - at(L, 0, 0.85));
    } else if (ph === 1) {                         // 句42:前三名(y 140–799)
      const st = [0, at(L, 1, 0.3) - F[1], at(L, 1, 0.58) - F[1]], names = ['寶特瓶', '瓶蓋', '吸管'];
      s += bigRows({ y: 140, rowH: 205, gap: 22, chars: 3, max: DATA[0][1], id: 'top', rows: [0, 1, 2].map((i) => ({
        label: names[i], value: DATA[i][1], g: grow(q - st[i]), color: BAR_COL[i], icon: icn(['bottle', 'cap', 'straw'][i], {}), k: q - st[i] })) });
      s += src(760, 99);
    } else if (ph === 2) {                         // 句43:十九條(左)加「第 18 名」「牙刷 1,433 支」(右)
      for (let i = 0; i < 19; i++) s += narrowRow(i, pal, q - i, { hi: i === 17 && q >= 20 });
      s += src(122, 99);
      const cyB = NR.y0 + 17 * NR.pitch, tip = rowEnd(17) + 34;
      const pa = Ch.plate('第 18 名', 190, { fill: K.YELLOW, padX: 0.4 }), pb = Ch.plate('牙刷 1,433 支', 120, { fill: K.INK, ink: K.YELLOW, padX: 0.5 });
      const xb = X1 - pb.w, hl = (xb + 10 - tip) / 2;          // 箭頭:從下方字牌左緣指向牙刷列(尾端藏在字牌後)
      s += Ch.sheet(`<polygon points="${f(-hl)},0 ${f(-hl + 80)},-34 ${f(-hl + 80)},-9 ${f(hl)},-9 ${f(hl)},9 ${f(-hl + 80)},9 ${f(-hl + 80)},34" fill="${K.INK}"/>`,
        { x: tip + hl, y: cyB, u: U, k: q - 30, kind: 'arrow', id: 'toBrush', wide: true });
      s += Ch.sheet(pa.svg, { x: X1 - pa.w / 2, y: 365, rot: -1, u: U, k: q - 22, kind: 'big', id: 'rank18' });
      s += Ch.sheet(pb.svg, { x: X1 - pb.w / 2, y: 834 - pb.h / 2, u: U, k: np(q - 26), kind: 'big', id: 'brush', wide: true });
    } else {                                       // 句44:吸管與牙刷兩條(y 100–512),16 倍以上(y 560–820)
      s += bigRows({ y: 100, rowH: 195, gap: 22, chars: 2, max: DATA[2][1], id: 'two', rows: [
        { label: '吸管', value: DATA[2][1], color: BAR_COL[2], icon: icn('straw', {}), k: q },
        { label: '牙刷', value: DATA[17][1], color: K.YELLOW, hi: true, icon: icn('toothbrush', {}), k: q - 3 }] });
      s += src(479, 99);
      const fs = 200, w = Ch.tw('16 倍以上', fs) + fs * 0.8, h = fs * 1.25;
      s += Ch.sheet(R(-w / 2, -h / 2, w, h, K.YELLOW) + T('16 倍以上', 0, 0, fs, K.INK),
        { x: 960, y: 688, rot: -1, u: U, k: np(q - 8), kind: 'big', id: 'x16', wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_rank', dur: 24.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
