/* ChannelC:圖表與標記元件(剪紙拼貼)。純函式,回傳 SVG 字串;需先載入 pigeon.js、kit.js。
 * 座標與尺寸一律 px(1920x1080)。每個元件由一到數片紙組成(K.paper:紙白描邊、硬邊陰影,帶 data-k / data-id)。
 * 逐步出現:k = 出現後第幾格(0 起);k<0 不畫;省略 = 已完全出現。進場用 K.pop(k),不補間、不用亂數與時鐘。
 * 字級下限(程式內強制):主要數字 ≥150、標籤 ≥56、來源小牌 ≥40;字型 GenSen;字一律放在紙片上。
 * 共用參數:u(紙片倍率,預設 1.4;決定描邊與陰影粗細,與同場景的鴿子倍率一致即可)、pal(K.palette(h))、id。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('./kit.js');
  const U0 = 1.4, FS_NUM = 150, FS_LABEL = 56, FS_SRC = 40, MK_CLEAR = 22;     // MK_CLEAR:decileRow 數值牌與 marker 線的最小垂直距離 px
  const NS = ' stroke="none"', MITER = ' stroke-linejoin="miter"';
  const f = (x) => +(+x).toFixed(2);
  const dv = (a, b) => (a == null ? b : a);
  const kk = (k) => (k == null ? 99 : k);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

  // ---------- 基礎 ----------
  const rect = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ''}/>`;
  const text = (s, x, y, size, fill, anchor) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}"` +
    ` text-anchor="${anchor || 'middle'}" dominant-baseline="central" fill="${fill}" stroke="none">${esc(s)}</text>`;
  // 估字寬(GenSen Heavy:全形 1em、數字與拉丁字約 0.64em)
  function tw(s, size) {
    let w = 0;
    for (const ch of String(s)) {
      w += ch.codePointAt(0) > 0x2e7f ? 1 : ch === ' ' ? 0.3 : /[.,:;'!|]/.test(ch) ? 0.34 : /[%MWmw]/.test(ch) ? 0.92 : 0.64;
    }
    return w * size;
  }
  // 以 px 繪製的紙片(中心 o.x,o.y);內層把單位換回 px,描邊維持 4u。o: {x,y,rot,u,k,kind,id,wide}
  function sheet(content, o) {
    const u = o.u || U0, k = kk(o.k), p = K.pop(k);
    if (p <= 0) return '';
    return K.paper(`<g transform="scale(${(1 / u).toFixed(5)})" stroke-width="${f(4 * u)}">${content}</g>`,
      { x: o.x, y: o.y, rot: o.rot, scale: u, sx: p, sy: p, k: o.kind, id: o.id, enter: k < 2, wide: o.wide });
  }
  // 字牌內容(中心在原點):回傳 {svg,w,h}。o: {fill,ink,padX(em),chip(左側色條顏色)}
  function plate(s, fs, o) {
    o = o || {};
    const cw = o.chip ? fs * 0.36 : 0, w = tw(s, fs) + fs * dv(o.padX, 1) + cw, h = fs * 1.62;
    return { w, h, svg: rect(-w / 2, -h / 2, w, h, o.fill || K.PAPER, MITER) + (o.chip ? rect(-w / 2, -h / 2, cw, h, o.chip, NS) : '') +
      text(s, cw / 2, 0, fs, o.ink || K.INK) };
  }
  // 嵌入圖解:ic = {svg,w,h}(以單位繪製、中心在原點的紙片內容,如 PropsTurtle.LIST[名])或字串(視為 100×100);縮到 box 見方內
  function icon(ic, cx, cy, box, dim) {
    if (!ic) return '';
    const o = typeof ic === 'string' ? { svg: ic, w: 100, h: 100 } : ic, s = Math.min(box / o.w, box / o.h);
    return `<g transform="translate(${f(cx)} ${f(cy)}) scale(${s.toFixed(4)})" stroke-width="${f(5 / s)}"${dim ? ' opacity=".4"' : ''}>${o.svg}</g>`;
  }

  // ---------- 橫向排行長條 ----------
  // o: {x,y(左上),w(總寬),rowH,gap,gapX,fs,numFs,labelW,max,k,bars:[{label,value,text,icon,color,grey,hi,k}]}
  // 每列三片紙:標籤牌(可含 icon)、長條(長度 = 可用寬 × value/max)、數值牌;hi:標籤黃底、數值墨底黃字;grey:灰條灰字
  function hbars(o) {
    const u = o.u || U0, pal = o.pal, rowH = o.rowH || 100, gap = dv(o.gap, 22), gx = dv(o.gapX, 18);
    const fs = Math.max(FS_LABEL, o.fs || FS_LABEL), nfs = Math.max(FS_LABEL, o.numFs || 64), id = o.id || 'hb';
    const bars = o.bars, lead = bars.some((b) => b.icon) ? rowH + 4 : fs * 0.4;
    const str = (b) => (b.text == null ? String(b.value) : b.text), valW = (b) => tw(str(b), nfs) + nfs * 0.7;
    const labelW = o.labelW || lead + Math.max(...bars.map((b) => tw(b.label, fs))) + fs * 0.4;
    const barMax = o.w - labelW - Math.max(...bars.map(valW)) - 2 * gx, max = o.max || Math.max(...bars.map((b) => b.value));
    const bh = rowH * 0.72, grey = `hsl(${pal.h} 8% 72%)`, greyInk = `hsl(${pal.h} 8% 42%)`;
    let s = '';
    bars.forEach((b, i) => {
      const k = kk(dv(b.k, o.k));
      if (k < 0) return;
      const cy = o.y + i * (rowH + gap) + rowH / 2, len = Math.max(12, barMax * b.value / max), vw = valW(b), ink = b.grey ? greyInk : K.INK;
      const bx = o.x + labelW + gx;
      s += sheet(rect(-labelW / 2, -rowH / 2, labelW, rowH, b.hi ? K.YELLOW : K.PAPER, MITER) +
        icon(b.icon, -labelW / 2 + rowH / 2, 0, rowH - 22, b.grey) + text(b.label, -labelW / 2 + lead, 0, fs, ink, 'start'),
        { x: o.x + labelW / 2, y: cy, u, k, kind: 'hbarL', id: id + i, wide: labelW / rowH > 3 });
      s += sheet(rect(-len / 2, -bh / 2, len, bh, b.grey ? grey : b.color || pal.main, MITER),
        { x: bx + len / 2, y: cy, u, k, kind: 'hbar', id: id + i, wide: len / bh > 3 });
      s += sheet(rect(-vw / 2, -bh / 2, vw, bh, b.hi ? K.INK : K.PAPER, MITER) + text(str(b), 0, 0, nfs, b.hi ? K.YELLOW : ink),
        { x: bx + len + gx + vw / 2, y: cy, u, k, kind: 'hbarV', id: id + i, wide: vw / bh > 3 });
    });
    return s;
  }

  // ---------- 分段比例條 ----------
  // o: {x,y(中心),w,h,fs,k,segs:[{value,label,text,color,side:'up'|'down',k}]};字牌(左側色條同該段顏色)上下交錯
  function ratioBar(o) {
    const u = o.u || U0, pal = o.pal, w = o.w, h = o.h || 90, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'rb';
    const total = o.segs.reduce((a, g) => a + g.value, 0), cols = [pal.main, K.YELLOW, pal.pad, `hsl(${pal.h} 8% 72%)`];
    let x0 = o.x - w / 2, bar = '', tags = '';
    o.segs.forEach((g, i) => {
      const sw = w * g.value / total, cx = x0 + sw / 2, k = kk(dv(g.k, o.k)), col = g.color || cols[i % cols.length];
      x0 += sw;
      bar += sheet(rect(-sw / 2, -h / 2, sw, h, col, MITER), { x: cx, y: o.y, u, k, kind: 'ratio', id: id + i, wide: sw / h > 3 });
      if (!g.label) return;
      const p = plate(g.label + (g.text ? ' ' + g.text : ''), fs, { chip: col }), up = g.side ? g.side === 'up' : i % 2 === 0;
      const lx = Math.max(o.x - w / 2 + p.w / 2, Math.min(o.x + w / 2 - p.w / 2, cx));
      tags += sheet(p.svg, { x: lx, y: o.y + (up ? -1 : 1) * (h / 2 + 16 + p.h / 2), u, k, kind: 'ratioL', id: id + i, wide: true });
    });
    return bar + tags;
  }

  // ---------- 大數字卡 ----------
  // o: {x,y(數字牌中心),num,unit,note,fs(≥150,預設 220),unitFs,noteFs,fill,ink,rot,k,kNote}
  function bigNum(o) {
    const u = o.u || U0, fs = Math.max(FS_NUM, o.fs || 220), ufs = Math.max(FS_LABEL, o.unitFs || fs * 0.38), id = o.id || 'num';
    const nw = tw(o.num, fs), ug = fs * 0.08, uw = o.unit ? tw(o.unit, ufs) + ug : 0, w = nw + uw + fs * 0.5, h = fs * 1.3, x0 = -w / 2 + fs * 0.25;
    const ink = o.ink || K.INK;
    let c = rect(-w / 2, -h / 2, w, h, o.fill || K.YELLOW, MITER) + text(o.num, x0 + nw / 2, 0, fs, ink);
    if (o.unit) c += text(o.unit, x0 + nw + ug + (uw - ug) / 2, fs * 0.36 - ufs * 0.42, ufs, ink);
    let s = sheet(c, { x: o.x, y: o.y, rot: o.rot, u, k: o.k, kind: 'bigNum', id });
    if (o.note) {
      const p = plate(o.note, Math.max(FS_LABEL, o.noteFs || FS_LABEL));
      s += sheet(p.svg, { x: o.x, y: o.y + h / 2 + 16 + p.h / 2, rot: -1.5, u, k: dv(o.kNote, o.k), kind: 'bigNumL', id, wide: true });
    }
    return s;
  }

  // ---------- 勾選清單 ----------
  // o: {x,y(左上),w,rowH,gap,fs,k,items:[{label,state:'empty'|'check'|'q',k,kState}]};kState = 記號出現後第幾格(預設同列)
  const CHECK = [[-0.5, 0.02], [-0.3, -0.18], [-0.1, 0.08], [0.38, -0.52], [0.58, -0.34], [-0.08, 0.48]];
  function checklist(o) {
    const u = o.u || U0, pal = o.pal, w = o.w, rowH = o.rowH || 100, gap = dv(o.gap, 24), fs = Math.max(FS_LABEL, o.fs || 60), id = o.id || 'cl';
    let rows = '', marks = '';
    o.items.forEach((it, i) => {
      const k = kk(dv(it.k, o.k));
      if (k < 0) return;
      const cx = o.x + w / 2, cy = o.y + i * (rowH + gap) + rowH / 2, b = rowH * 0.62, bx = -w / 2 + rowH / 2, ks = kk(dv(it.kState, k));
      rows += sheet(rect(-w / 2, -rowH / 2, w, rowH, K.PAPER, MITER) + rect(bx - b / 2, -b / 2, b, b, K.INK, NS) +
        rect(bx - b / 2 + 7, -b / 2 + 7, b - 14, b - 14, K.PAPER, NS) + text(it.label, -w / 2 + rowH + fs * 0.1, 0, fs, K.INK, 'start'),
        { x: cx, y: cy, u, k, kind: 'check', id: id + i, wide: w / rowH > 3 });
      if (it.state === 'check') {
        marks += sheet(`<polygon points="${CHECK.map((p) => `${f(p[0] * b * 1.2)},${f(p[1] * b * 1.2)}`).join(' ')}" fill="${pal.text}"/>`,
          { x: cx + bx, y: cy, u, k: ks, kind: 'checkMark', id: id + i });
      } else if (it.state === 'q') {
        marks += sheet(rect(-b / 2, -b / 2, b, b, K.INK, MITER) + text('?', 0, 0, b * 0.78, K.YELLOW),
          { x: cx + bx, y: cy, rot: 5, u, k: ks, kind: 'checkQ', id: id + i });
      }
    });
    return rows + marks;
  }

  // ---------- 一排 icon ----------
  // o: {x,y(整排 icon 的中心),pitch 或 w,size(icon 見方 px),fs,k,items:[{icon,label,dim,k}]};icon 逐一彈入,短標籤在下方
  function iconRow(o) {
    const u = o.u || U0, n = o.items.length, pitch = o.pitch || o.w / n, size = o.size || 160, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'ir';
    let s = '';
    o.items.forEach((it, i) => {
      const k = kk(dv(it.k, o.k)), cx = o.x + (i - (n - 1) / 2) * pitch;
      if (k < 0) return;
      s += sheet(icon(it.icon, 0, 0, size, it.dim), { x: cx, y: o.y, u, k, kind: 'icon', id: id + i });
      if (it.label) {
        const p = plate(it.label, fs);
        s += sheet(p.svg, { x: cx, y: o.y + size / 2 + 16 + p.h / 2, u, k, kind: 'iconL', id: id + i, wide: true });
      }
    });
    return s;
  }

  // ---------- 頒獎台 ----------
  // o: {x,y(台底中心),w,h(第一名台高),fs,k,places:[第一名,第二名,第三名] 各 {label,color,lift,k}};左二、中一、右三
  // podiumPos(o) 回傳三階的 {x,top,w,h}(第一、二、三名),供場景把圖解站上去;lift = 標籤再往上讓出的 px
  function podiumPos(o) {
    const sw = o.w / 3, h = o.h || 260;
    return [[0, 1], [-1, 0.72], [1, 0.5]].map(([dx, r]) => ({ x: o.x + dx * sw, top: o.y - h * r, w: sw, h: h * r }));
  }
  function podium(o) {
    const u = o.u || U0, pal = o.pal, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'pd';
    const cols = [K.YELLOW, pal.main, pal.pad], inks = [K.INK, pal.onMain, K.INK];
    let s = '';
    podiumPos(o).forEach((p, r) => {
      const pl = (o.places || [])[r], k = kk(dv(pl && pl.k, o.k));
      if (!pl || k < 0) return;
      s += sheet(rect(-p.w / 2, -p.h / 2, p.w, p.h, pl.color || cols[r], MITER) + text(String(r + 1), 0, 0, Math.min(p.h * 0.7, p.w * 0.6, 170), inks[r]),
        { x: p.x, y: p.top + p.h / 2, u, k, kind: 'podium', id: id + (r + 1) });
      if (pl.label) {
        const q = plate(pl.label, fs);
        s += sheet(q.svg, { x: p.x, y: p.top - (pl.lift || 0) - 16 - q.h / 2, u, k, kind: 'podiumL', id: id + (r + 1), wide: true });
      }
    });
    return s;
  }

  // ---------- 兩欄板 ----------
  // o: {x,y(中心),w,h,gap,fs,k,left:{title,color,titleFill,titleInk,k},right:{…}};內容由場景自己擺
  // twoColPos(o) 回傳兩欄的 {x,y0,y1,w}(標題牌以下的可用範圍)
  function twoColPos(o) {
    const g = dv(o.gap, 24), cw = (o.w - g) / 2, th = Math.max(FS_LABEL, o.fs || FS_LABEL) * 1.62 + 32;
    return [-1, 1].map((d) => ({ x: o.x + d * (cw + g) / 2, y0: o.y - o.h / 2 + th, y1: o.y + o.h / 2, w: cw }));
  }
  function twoCol(o) {
    const u = o.u || U0, pal = o.pal, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'tc', pos = twoColPos(o);
    let s = '';
    [o.left, o.right].forEach((c, i) => {
      const k = kk(dv(c && c.k, o.k)), p = pos[i];
      if (!c || k < 0) return;
      s += sheet(rect(-p.w / 2, -o.h / 2, p.w, o.h, c.color || (i ? `hsl(${pal.h} 18% 84%)` : pal.pad), MITER),
        { x: p.x, y: o.y, u, k, kind: 'col', id: id + (i ? 'R' : 'L') });
      if (c.title) {
        const q = plate(c.title, fs, { fill: c.titleFill || (i ? K.INK : K.YELLOW), ink: c.titleInk || (i ? K.PAPER : K.INK) });
        s += sheet(q.svg, { x: p.x, y: o.y - o.h / 2 + 16 + q.h / 2, rot: i ? 1.5 : -1.5, u, k, kind: 'colT', id: id + (i ? 'R' : 'L'), wide: true });
      }
    });
    return s;
  }

  // ---------- 10×10 方格佔比 ----------
  // o: {x,y(中心),size,n(0–100 上色格數),color,k,kFill,per};kFill = 開始上色後第幾格,每格多上 per 個(預設一次上完)
  function dotGrid(o) {
    const u = o.u || U0, pal = o.pal, size = o.size || 360, pad = size * 0.07, cell = (size - 2 * pad) / 10, d = cell * 0.8;
    const kf = kk(o.kFill), shown = kf < 0 ? 0 : Math.min(o.n, (kf + 1) * (o.per || 100));
    let c = rect(-size / 2, -size / 2, size, size, K.PAPER, MITER);
    for (let i = 0; i < 100; i++) {
      c += rect(-size / 2 + pad + (i % 10) * cell + (cell - d) / 2, -size / 2 + pad + Math.floor(i / 10) * cell + (cell - d) / 2, d, d,
        i < shown ? o.color || pal.text : `hsl(${pal.h} 14% 82%)`, NS);
    }
    return sheet(c, { x: o.x, y: o.y, rot: o.rot, u, k: o.k, kind: 'dotGrid', id: o.id || 'dg' });
  }

  // ---------- 路線站點 ----------
  // o: {r,th,fs,k,stops:[{x,y,label,labelSide:'up'|'down',k,kOn}]};kOn = 亮起後第幾格(省略 = 已亮,<0 = 未亮,灰色)
  // 線段在後一站出現時出現;兩端都亮才上主色
  function route(o) {
    const u = o.u || U0, pal = o.pal, r = o.r || 28, th = o.th || 16, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'rt';
    const grey = `hsl(${pal.h} 8% 70%)`;
    const st = o.stops.map((p) => ({ p, k: kk(dv(p.k, o.k)), on: kk(p.kOn) }));
    let segs = '', nodes = '', tags = '';
    st.forEach((a, i) => {
      if (a.k < 0) return;
      const b = st[i - 1];
      if (b && b.k >= 0) {
        const dx = a.p.x - b.p.x, dy = a.p.y - b.p.y, L = Math.hypot(dx, dy) || 1, nx = -dy / L * th / 2, ny = dx / L * th / 2;
        const pts = [[-dx / 2 + nx, -dy / 2 + ny], [dx / 2 + nx, dy / 2 + ny], [dx / 2 - nx, dy / 2 - ny], [-dx / 2 - nx, -dy / 2 - ny]];
        segs += sheet(`<polygon points="${pts.map((q) => `${f(q[0])},${f(q[1])}`).join(' ')}" fill="${a.on >= 0 && b.on >= 0 ? pal.main : grey}"/>`,
          { x: (a.p.x + b.p.x) / 2, y: (a.p.y + b.p.y) / 2, u, k: a.k, kind: 'routeSeg', id: id + i, wide: Math.abs(dx) > 3 * Math.abs(dy) });
      }
      nodes += sheet(`<circle cx="0" cy="0" r="${f(r)}" fill="${a.on >= 0 ? K.YELLOW : grey}"/><circle cx="0" cy="0" r="${f(r * 0.4)}" fill="${K.INK}" stroke="none"/>`,
        { x: a.p.x, y: a.p.y, u, k: a.on >= 0 ? Math.min(a.k, a.on) : a.k, kind: 'routeStop', id: id + i });
      if (a.p.label) {
        const q = plate(a.p.label, fs);
        tags += sheet(q.svg, { x: a.p.x, y: a.p.y + (a.p.labelSide === 'up' ? -1 : 1) * (r + 16 + q.h / 2), u, k: a.k, kind: 'routeL', id: id + i, wide: true });
      }
    });
    return segs + nodes + tags;
  }

  // ---------- 來源小牌 ----------
  // srcTag('環境部', {x,y,anchor:'left'|'right'|'center',fs(≥40),pal,rot,k});x 為 anchor 那一側的邊
  function srcTag(s, o) {
    const fs = Math.max(FS_SRC, o.fs || FS_SRC), p = plate(s, fs, { chip: o.pal ? o.pal.main : K.YELLOW, padX: 0.8 });
    const x = o.anchor === 'left' ? o.x + p.w / 2 : o.anchor === 'right' ? o.x - p.w / 2 : o.x;
    return sheet(p.svg, { x, y: o.y, rot: o.rot, u: o.u, k: o.k, kind: 'src', id: o.id || 'src', wide: true });
  }

  // ---------- 無用知識記號 ----------
  // o: {x,y,size(預設 120),rot,k,kOut};預設在右上角安全邊界內;kOut = 開始退場後第幾格(2 格後消失)
  const OUT = [1.15, 0.6];
  function triviaMark(o) {
    o = o || {};
    const size = o.size || 120, k = kk(o.k), ko = dv(o.kOut, -1);
    if (k < 0 || ko >= OUT.length) return '';
    const p = ko >= 0 ? OUT[ko] : K.pop(k);
    return K.tile('?', { x: dv(o.x, K.W - K.SAFE - size / 2 - 12), y: dv(o.y, K.SAFE + size / 2 + 12), size, rot: dv(o.rot, 6), u: o.u || U0,
      fill: K.INK, ink: K.YELLOW, sx: p, sy: p, id: o.id || 'trivia', enter: k < 2 || ko >= 0 });
  }

  // ---------- 對話泡 ----------
  // bubble('一句' 或 ['兩行','文字'], {x,y(泡的中心),fs,dashed,tail:'bl'|'br'|'tl'|'tr'|null,fill,rot,k})
  // 實線 = 說出口的話;dashed 虛線 = 傳言、心裡話
  function bubble(s, o) {
    const lines = Array.isArray(s) ? s : [s], fs = Math.max(FS_LABEL, o.fs || FS_LABEL), lh = fs * 1.3;
    const a = (Math.max(...lines.map((l) => tw(l, fs))) + fs * 1.5) / 2, b = (lines.length * lh + fs * 0.9) / 2, r = Math.min(fs * 0.6, b);
    const tail = o.tail === undefined ? 'bl' : o.tail, th = fs * 0.9, tb = fs * 0.42, sg = tail && tail.indexOf('l') >= 0 ? -1 : 1;
    const tc = sg * Math.max(0, Math.min(a * 0.45, a - r - tb)), tip = tc + sg * fs * 0.6;
    let d = `M ${f(-a + r)} ${f(-b)} H ${f(a - r)} Q ${f(a)} ${f(-b)} ${f(a)} ${f(-b + r)} V ${f(b - r)} Q ${f(a)} ${f(b)} ${f(a - r)} ${f(b)}`;
    if (tail) d += ` H ${f(tc + tb)} L ${f(tip)} ${f(b + th)} L ${f(tc - tb)} ${f(b)}`;
    d += ` H ${f(-a + r)} Q ${f(-a)} ${f(b)} ${f(-a)} ${f(b - r)} V ${f(-b + r)} Q ${f(-a)} ${f(-b)} ${f(-a + r)} ${f(-b)} Z`;
    const inset = fs * 0.17, bw = Math.max(5, fs * 0.09);
    let c = `<path d="${d}" fill="${o.fill || K.PAPER}"${tail && tail.indexOf('t') >= 0 ? ' transform="scale(1 -1)"' : ''}/>` +
      `<rect x="${f(-a + inset)}" y="${f(-b + inset)}" width="${f(2 * (a - inset))}" height="${f(2 * (b - inset))}" rx="${f(Math.max(2, r - inset))}"` +
      ` fill="none" stroke="${K.INK}" stroke-width="${f(bw)}"${o.dashed ? ` stroke-dasharray="${f(fs * 0.34)} ${f(fs * 0.24)}"` : ''}/>`;
    lines.forEach((l, i) => { c += text(l, 0, (i - (lines.length - 1) / 2) * lh, fs, o.ink || K.INK); });
    return sheet(c, { x: o.x, y: o.y, rot: o.rot, u: o.u, k: o.k, kind: 'bubble', id: o.id || 'bubble' });
  }

  // ---------- 日曆牌 ----------
  // o: {x,y(中心),top(上緣色帶的字,如 '2025'),main(大字,如 '1/1'),size(寬 px,預設 220),color,rot,k}
  function dateTag(o) {
    const w = o.size || 220, hh = w * 0.3, h = w * 1.08, tfs = Math.max(FS_SRC, hh * 0.62);
    const mfs = Math.max(FS_LABEL, Math.min(w * 0.5, w * 0.84 / (tw(o.main, 1) || 1)));
    let c = rect(-w / 2, -h / 2, w, h, K.PAPER, MITER) + rect(-w / 2, -h / 2, w, hh, o.color || 'hsl(6 75% 55%)', NS);
    [-1, 1].forEach((d) => { c += `<rect x="${f(d * w * 0.27 - 6)}" y="${f(-h / 2 - 12)}" width="12" height="28" rx="6" fill="${K.INK}" stroke="none"/>`; });
    if (o.top) c += text(o.top, 0, -h / 2 + hh / 2 + 4, tfs, K.PAPER);
    c += text(o.main, 0, hh / 2, mfs, K.INK);
    return sheet(c, { x: o.x, y: o.y, rot: o.rot, u: o.u, k: o.k, kind: 'date', id: o.id || 'date' });
  }

  // ---------- 價牌(吊牌,可翻牌) ----------
  // o: {x,y(中心),from,to,unit,fs(預設 110、下限 56),rot,k,kFlip}
  // kFlip<0 或省略(或沒有 to)= 只顯示 from;kFlip≥0 = 舊價縮小變灰加紅刪除線上移,新價(品牌黃牌)在下半彈出;外框寬度前後相同
  function priceFlip(o) {
    const u = o.u || U0, pal = o.pal, fs = Math.max(FS_LABEL, o.fs || 110), id = o.id || 'pf', k = kk(o.k);
    if (k < 0) return '';
    const unit = o.unit ? ' ' + o.unit : '', fromS = String(o.from) + unit, toS = o.to == null ? null : String(o.to) + unit;
    const kf = toS == null || o.kFlip == null ? -1 : o.kFlip, flipped = kf >= 0;
    const w = Math.max(tw(fromS, fs), toS ? tw(toS, fs) : 0) + fs, h = flipped ? fs * 2.9 : fs * 1.7, rot = o.rot || 0;
    const hy = -h / 2 + fs * 0.26;                                   // 小孔中心
    let c = rect(-w / 2, -h / 2, w, h, K.PAPER, MITER) + `<circle cx="0" cy="${f(hy)}" r="${f(fs * 0.085)}" fill="${K.INK}" stroke="none"/>` +
      `<path d="M 0 ${f(hy)} C ${f(-fs * 0.1)} ${f(hy - fs * 0.3)} ${f(fs * 0.2)} ${f(hy - fs * 0.35)} ${f(fs * 0.12)} ${f(hy - fs * 0.62)}"` +
      ` fill="none" stroke="${K.INK}" stroke-width="6" stroke-linecap="round"/>`;
    if (!flipped) c += text(fromS, 0, fs * 0.15, fs, K.INK);
    else {
      const fo = Math.max(FS_LABEL, fs * 0.55), oy = -h / 2 + fs * 0.55 + fo * 0.5, ow = tw(fromS, fo) + fo * 0.5;
      c += text(fromS, 0, oy, fo, `hsl(${pal.h} 8% 42%)`) + rect(-ow / 2, oy - 4, ow, 8, 'hsl(6 75% 50%)', NS);
    }
    let s = sheet(c, { x: o.x, y: o.y, rot, u, k, kind: 'price', id });
    if (flipped) {
      const ang = rot * Math.PI / 180, dy = h / 2 - fs * 0.805, yw = w - fs * 0.3, yh = fs * 1.45;
      s += sheet(rect(-yw / 2, -yh / 2, yw, yh, K.YELLOW, MITER) + text(toS, 0, 0, fs, K.INK),
        { x: o.x - dy * Math.sin(ang), y: o.y + dy * Math.cos(ang), rot: rot + 2.5, u, k: kf, kind: 'priceNew', id: id + 'N' });
    }
    return s;
  }

  // ---------- 折線圖 ----------
  // o: {x,y(繪圖區左上),w,h,pts:[{label,value,text,k}],min,max,fs(≥56),hi(索引或陣列),title,k,pal}
  // 繪圖區 = 紙白襯底(底部墨色基線);數值牌在點上方、x 軸標籤在基線下方;兩端都出現才畫線段;min/max 省略時取資料並留 10% 邊
  function lineChart(o) {
    const u = o.u || U0, pal = o.pal, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'lc', pts = o.pts, n = pts.length;
    const hi = Array.isArray(o.hi) ? o.hi : o.hi == null ? [] : [o.hi], vals = pts.map((p) => p.value);
    const dmin = Math.min(...vals), dmax = Math.max(...vals), span = dmax - dmin || 1;
    const lo = o.min == null ? dmin - span * 0.1 : o.min, up = o.max == null ? dmax + span * 0.1 : o.max, rng = up - lo || 1;
    const str = (p) => (p.text == null ? String(p.value) : p.text);
    const tags = pts.map((p, i) => plate(str(p), fs, hi.indexOf(i) >= 0 ? { fill: K.INK, ink: K.YELLOW } : {})), labs = pts.map((p) => plate(p.label == null ? '' : p.label, fs));
    const padX = Math.max(...tags.map((p) => p.w), ...labs.map((p) => p.w)) / 2 + 20, r = Math.max(16, fs * 0.3), th = 14;
    const gapY = Math.max(16, fs * 0.25), tagH = fs * 1.62;
    const yTop = o.y + (o.title ? tagH + r + gapY : 0), yBot = o.y + o.h;      // 有標題:資料上緣多留一個數值牌高度,最高點的牌不頂到標題牌
    const P = pts.map((p, i) => ({ x: o.x + (n > 1 ? padX + i * (o.w - 2 * padX) / (n - 1) : o.w / 2), y: yBot - (p.value - lo) / rng * (yBot - yTop),
      k: kk(dv(p.k, o.k)), hi: hi.indexOf(i) >= 0 }));
    let s = sheet(rect(-o.w / 2, -o.h / 2, o.w, o.h, o.pal ? o.pal.pad : K.PAPER, MITER) + rect(-o.w / 2, o.h / 2 - 14, o.w, 14, K.INK, NS),
      { x: o.x + o.w / 2, y: o.y + o.h / 2, u, k: o.k, kind: 'lineBase', id, wide: true });
    let segs = '', dots = '', nums = '', xl = '';
    const placed = [];                                                   // 已放的數值牌 {x0,x1,y0,y1},重疊時往上讓開
    P.forEach((a, i) => {
      if (a.k < 0) return;
      const b = P[i - 1];
      if (b && b.k >= 0) {
        const dx = a.x - b.x, dy = a.y - b.y, L = Math.hypot(dx, dy) || 1, nx = -dy / L * th / 2, ny = dx / L * th / 2;
        const q = [[-dx / 2 + nx, -dy / 2 + ny], [dx / 2 + nx, dy / 2 + ny], [dx / 2 - nx, dy / 2 - ny], [-dx / 2 - nx, -dy / 2 - ny]];
        segs += sheet(`<polygon points="${q.map((v) => `${f(v[0])},${f(v[1])}`).join(' ')}" fill="${K.INK}"/>`,
          { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, u, k: Math.min(a.k, b.k), kind: 'lineSeg', id: id + i, wide: Math.abs(dx) > 3 * Math.abs(dy) });
      }
      dots += sheet(`<circle cx="0" cy="0" r="${f(r)}" fill="${a.hi ? K.YELLOW : pal.main}"/><circle cx="0" cy="0" r="${f(r * 0.4)}" fill="${K.INK}" stroke="none"/>`,
        { x: a.x, y: a.y, u, k: a.k, kind: 'lineDot', id: id + i });
      const t = tags[i];
      let ty = a.y - r - gapY - t.h / 2, tx = a.x;
      if (i > 0 && pts[i].value < pts[i - 1].value) {                       // 前一段線由上往下進來:牌改放右上,避開進來的線
        const b = P[i - 1], d = r + gapY, steep = (b.x ? (a.x - b.x) / Math.max(1, b.y - a.y) : 0);
        tx = a.x + Math.min(t.w / 2, Math.max(0.6 * t.w / 2, t.w / 2 - d * steep + th + 6));
      }
      placed.forEach((q) => { if (Math.abs(tx - (q.x0 + q.x1) / 2) < (t.w + q.x1 - q.x0) / 2 + 8 && ty - t.h / 2 < q.y1 + 8 && ty + t.h / 2 > q.y0 - 8) ty = q.y0 - 12 - t.h / 2; });
      placed.push({ x0: tx - t.w / 2, x1: tx + t.w / 2, y0: ty - t.h / 2, y1: ty + t.h / 2 });
      nums += sheet(t.svg, { x: tx, y: ty, u, k: a.k, kind: 'lineNum', id: id + i, wide: true });
      if (pts[i].label != null) xl += sheet(labs[i].svg, { x: a.x, y: o.y + o.h + 16 + labs[i].h / 2, u, k: a.k, kind: 'lineX', id: id + i, wide: true });
    });
    if (o.title) {
      const p = plate(o.title, fs, { fill: K.YELLOW });
      s += sheet(p.svg, { x: o.x + 16 + p.w / 2, y: o.y - 0.3 * fs - p.h / 2, rot: -1.5, u, k: o.k, kind: 'lineTitle', id: id + 'T', wide: true });
    }
    return s + segs + dots + nums + xl;
  }

  // ---------- 十等份薪資階梯 ----------
  // o: {x,y,w,h(繪圖區左上與寬高,數值牌在柱頂、x 軸標籤在基線下方 ≥107px),vals,texts,labels,hiIdx(索引或陣列,黃柱),max,fs(≥56),title,k,kStep,
  //     marker:{value,label,k,side:'left'|'right'},greyIdx(索引陣列,灰柱),numKs(每根數值牌自己的 k;<0 不畫,省略的索引同柱)}
  // 柱由矮到高(依 vals 順序),標籤預設 D1…Dn;marker = 橫線加墨底黃字牌(預設在左端、線上方),標某個值落在哪兩根之間;
  // k = 全部柱出現後第幾格,kStep = 每根柱晚幾格(第 i 根 k = k − i×kStep);最高柱頂留一個數值牌高度;數值牌與 marker 線垂直距離 < 22px 時 marker 線在牌子處斷開(殘段 < 40px 不畫)
  function decileRow(o) {
    const u = o.u || U0, pal = o.pal, fs = Math.max(FS_LABEL, o.fs || FS_LABEL), id = o.id || 'dr', vals = o.vals, n = vals.length, mk = o.marker;
    const hi = Array.isArray(o.hiIdx) ? o.hiIdx : o.hiIdx == null ? [] : [o.hiIdx], step = o.kStep || 0;
    const txtOf = (i) => (o.texts && o.texts[i] != null ? o.texts[i] : String(vals[i])), labOf = (i) => (o.labels && o.labels[i] != null ? o.labels[i] : 'D' + (i + 1));
    const tagH = fs * 1.62, gapY = 16, yBot = o.y + o.h, yTop = o.y + tagH + gapY, pitch = o.w / n, bw = pitch * 0.74;
    const max = o.max || Math.max(...vals, mk ? mk.value : 0), yOf = (v) => yBot - (yBot - yTop) * v / max;
    const kOf = (i) => (o.k == null ? null : o.k - i * step);
    const base = sheet(rect(-o.w / 2 - 12, -7, o.w + 24, 14, K.INK, NS), { x: o.x + o.w / 2, y: yBot - 7, u, k: o.k, kind: 'decileBase', id: id + 'B', wide: true });
    let s = '', bars = '', nums = '', xl = '';
    const cuts = [], grey = Array.isArray(o.greyIdx) ? o.greyIdx : [];
    vals.forEach((v, i) => {
      const k = kk(kOf(i));
      if (k < 0) return;
      const cx = o.x + pitch * (i + 0.5), top = Math.min(yOf(v), yBot - 12), bh = yBot - top, h = hi.indexOf(i) >= 0;
      bars += sheet(rect(-bw / 2, -bh / 2, bw, bh, grey.indexOf(i) >= 0 ? `hsl(${pal.h} 8% 72%)` : h ? K.YELLOW : pal.main, MITER), { x: cx, y: top + bh / 2, u, k, kind: 'decileBar', id: id + i, wide: bh / bw > 3 });
      const kn = o.numKs && o.numKs[i] != null ? o.numKs[i] : k;
      if (kn >= 0) {
        const p = plate(txtOf(i), fs, h ? { padX: 0.3, fill: K.INK, ink: K.YELLOW } : { padX: 0.3 });
        const lift = p.w > pitch - 4 && i % 2 === 1 ? p.h + 8 : 0;
        const ny = top - gapY - p.h / 2 - lift;
        if (mk) {     // 數值牌與 marker 線(粗 12px)垂直距離 < MK_CLEAR:線在牌子的 x 範圍斷開(牌留在柱頂,不飄到線上)
          const my = yOf(mk.value);
          if (ny + p.h / 2 > my - 6 - MK_CLEAR && ny - p.h / 2 < my + 6 + MK_CLEAR) cuts.push([cx - p.w / 2 - 16, cx + p.w / 2 + 16]);
        }
        nums += sheet(p.svg, { x: cx, y: ny, u, k: kn, kind: 'decileNum', id: id + i, wide: true });
      }
      const l = plate(labOf(i), fs, { padX: 0.3 });
      xl += sheet(l.svg, { x: cx, y: yBot + 16 + l.h / 2, u, k, kind: 'decileX', id: id + i, wide: true });
    });
    s += bars + base;
    let mkLine = '', mkLab = '';
    if (o.title) {
      const p = plate(o.title, fs, { fill: K.YELLOW });
      s += sheet(p.svg, { x: o.x + 16 + p.w / 2, y: o.y - 0.3 * fs - p.h / 2, rot: -1.5, u, k: o.k, kind: 'decileTitle', id: id + 'T', wide: true });
    }
    if (mk) {
      const my = yOf(mk.value), mkk = kk(mk.k == null ? o.k : mk.k);
      let a = o.x - 12;     // 線被數值牌切成幾段(< 40px 的殘段不畫)
      const segs = [];
      cuts.sort((p, q) => p[0] - q[0]).concat([[o.x + o.w + 12, 0]]).forEach((c) => { if (c[0] - a >= 40) segs.push([a, c[0]]); a = Math.max(a, c[1]); });
      segs.forEach((g, j) => { mkLine += sheet(rect(-(g[1] - g[0]) / 2, -6, g[1] - g[0], 12, K.INK, NS), { x: (g[0] + g[1]) / 2, y: my, u, k: mkk, kind: 'decileMk', id: id + 'M' + j, wide: true }); });
      if (mk.label) {
        const p = plate(mk.label, fs, { fill: K.INK, ink: K.YELLOW }), right = mk.side === 'right';
        mkLab = sheet(p.svg, { x: right ? o.x + o.w - p.w / 2 : o.x + p.w / 2, y: my - 6 - 8 - p.h / 2, rot: right ? 1.5 : -1.5, u, k: mkk, kind: 'decileMkL', id: id + 'ML', wide: true });
      }
    }
    return s + mkLine + nums + xl + mkLab;     // 次序:柱 → 標記線 → 數值牌(蓋住線) → x 軸標籤 → 標記牌
  }

  const API = { U0, FS_NUM, FS_LABEL, FS_SRC, tw, sheet, plate, icon, hbars, ratioBar, bigNum, checklist, iconRow, podium, podiumPos,
    twoCol, twoColPos, dotGrid, route, srcTag, triviaMark, bubble, dateTag, priceFlip, lineChart, decileRow };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.Charts = API;
})();
