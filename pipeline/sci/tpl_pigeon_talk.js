/* 模板 pigeon_talk(F4-0c):鴿子放大當主角(面向右),對話泡在鴿子前方、圖解在鴿子另一側。
 * data: {expr: 名|[每句表情], clip, bubbles:[{text,at?,word?,dashed?}], props:[{lib,name,params,at?,word?,x?,y?,u?}], out?:{at,word?}}
 * text = 字串(\n 換行)或陣列,≤ 2 行;泡泡同時 ≤ 2:第 i+2 個出現前 3 格,第 i 個縮掉(位置 = 槽 i % 2,不補間)。
 * props:lib = window 上的圖解庫名(PropsSalary,或簡寫 salary),name = LIST 的鍵;未給 x,y 時依序直排在鴿子另一側(縮放取放得下的最大值,上限 uMax)。
 * 觸發:泡泡與圖解各自依 at/word,省略則依序分配;觸發順序須與陣列順序相同。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判,F4-0c 實測】:pg 鴿子腳底落點與倍率(規格原值 橫 u3.2/x700、直 u3/y1150;橫 u3.2 頭頂會進上邊距、直 u3 泡泡區放不下兩個兩行泡,改小;直式鴿子靠右)、
  // gapX/gapY 內容與鴿子外框的間距、bub 泡泡字級範圍與槽距、prop 圖解縮放上限與間距
  const LAYOUT = {
    landscape: { pg: { x: 700, y: 812, u: 3.1 }, gapX: 40, gapY: 24, bub: { fsMax: 80, fsMin: 56, gap: 32 }, prop: { uMax: 1.6, gap: 32, minW: 120 } },
    portrait: { pg: { x: 655, y: 1286, u: 2.2 }, gapX: 24, gapY: 24, bub: { fsMax: 80, fsMin: 60, gap: 24 }, prop: { uMax: 1.6, gap: 24, minW: 120 } },
  };
  const LY = LAYOUT[C.LAY];
  // 鴿子(flip 面向右)各片段 × 全部表情的外框聯集(單位,相對腳底;含描邊,不含陰影;F4-0c 實測)。turn 會改 flip,不列入
  const BOX = {
    idle: [-106, -231, 126, 3], blink: [-106, -226, 126, 3], nod: [-106, -229, 139, 3], tilt: [-106, -234, 126, 3],
    talk: [-106, -226, 126, 3], write: [-105, -218, 155, 5], shrug: [-110, -226, 136, 3], point: [-106, -229, 146, 3],
    point_out: [-106, -229, 139, 3], write_out: [-106, -229, 153, 4], walk: [-108, -228, 126, 8], shock: [-119, -275, 139, 3],
    hop: [-111, -259, 131, 3],
  };
  const SLACK = 12;                                 // 紙片傾斜、陰影與描邊的預留(px)
  const ROT = [-1.5, 1.5];                          // 兩個槽的泡泡傾斜
  const OVER = 1.15, SHADOW = 8;                    // K.pop 彈入過衝倍率、陰影下緣(px):字幕帶檢查用
  const BOT = 64;                                   // 泡泡區、圖解區下緣離字幕帶(留給過衝與陰影)

  const pgBox = (clip) => {
    const b = BOX[clip || 'idle'], P = LY.pg;
    return b && { x0: P.x + b[0] * P.u, y0: P.y + b[1] * P.u, x1: P.x + b[2] * P.u, y1: P.y + b[3] * P.u };
  };
  const linesOf = (b) => (Array.isArray(b.text) ? b.text : String(b.text == null ? '' : b.text).split('\n')).map(String);
  function libOf(n) {
    if (!n) return null;
    const s = String(n);
    return Wn[s] || Wn['Props' + s[0].toUpperCase() + s.slice(1)] || null;
  }
  const propOf = (p) => { const L = libOf(p.lib); return (L && L.LIST && L.LIST[p.name]) || null; };
  // 泡泡尺寸(同 Charts.bubble):半寬 a、本體半高 b、尾巴長 th
  const bubDim = (ls, fs) => ({ a: (Math.max(...ls.map((l) => Ch.tw(l, fs))) + fs * 1.5) / 2, b: (ls.length * fs * 1.3 + fs * 0.9) / 2, th: fs * 0.9 });

  // 幾何:泡泡區(鴿子前方:橫式右側、直式上方)、圖解區(鴿子另一側:左側)、字級、每個泡泡與圖解的位置與外框
  function geo(d) {
    const pb = pgBox(d.clip), bubs = d.bubbles || [], props = d.props || [], M = K.L.margin;
    const R = K.L.W - M[2] - SLACK, yMax = K.L.SUB_BAND[0] - BOT;
    const BZ = K.portrait ? { x0: M[0] + SLACK, x1: R, y0: 120, y1: pb.y0 - LY.gapY - SLACK }
      : { x0: pb.x1 + LY.gapX + SLACK, x1: R, y0: 120, y1: yMax };
    const PZ = { x0: M[0] + SLACK, x1: pb.x0 - LY.gapX - SLACK, y0: K.portrait ? pb.y0 : 120, y1: yMax };
    const ls = bubs.map(linesOf), slotN = [0, 1].map((s) => Math.max(0, ...ls.filter((_, i) => i % 2 === s).map((l) => l.length)));
    const size = (fs) => {
      const hs = slotN.map((n) => (n ? n * fs * 1.3 + fs * 0.9 + fs * 0.9 + 2 * SLACK : 0));
      return { hs, H: hs[0] + hs[1] + (hs[1] ? LY.bub.gap : 0), W: Math.max(0, ...ls.map((l) => 2 * bubDim(l, fs).a + 2 * SLACK)) };
    };
    let fs = LY.bub.fsMax;
    while (fs > LY.bub.fsMin && (size(fs).H > BZ.y1 - BZ.y0 || size(fs).W > BZ.x1 - BZ.x0)) fs -= 2;
    const z = size(fs), top = BZ.y0 + (BZ.y1 - BZ.y0 - z.H) / 2;
    const slotTop = [top, top + z.hs[0] + LY.bub.gap];
    const B = ls.map((l, i) => {
      const s = i % 2, dm = bubDim(l, fs), cx = K.portrait ? (BZ.x0 + BZ.x1) / 2 : BZ.x0 + SLACK + dm.a, cy = slotTop[s] + SLACK + dm.b;
      return { lines: l, s, cx, cy, dm, box: { x0: cx - dm.a - SLACK, y0: cy - dm.b - SLACK, x1: cx + dm.a + SLACK, y1: cy + dm.b + dm.th + SLACK } };
    });
    const auto = props.filter((p) => p.x == null || p.y == null).length, cellH = auto ? (PZ.y1 - PZ.y0 - (auto - 1) * LY.prop.gap) / auto : 0;
    let ai = 0;
    const Pp = props.map((p) => {
      const it = propOf(p);
      if (!it) return null;
      let x = p.x, y = p.y, u = p.u;
      if (x == null || y == null) {
        const fit = Math.min(LY.prop.uMax, (PZ.x1 - PZ.x0 - 2 * SLACK) / it.w, (cellH - 2 * SLACK) / it.h);
        u = u || fit; x = (PZ.x0 + PZ.x1) / 2; y = PZ.y0 + ai * (cellH + LY.prop.gap) + cellH / 2; ai++;
      }
      u = u || 1;
      const hw = it.w * u / 2 + SLACK, hh = it.h * u / 2 + SLACK;
      return { it, x, y, u, box: { x0: x - hw, y0: y - hh, x1: x + hw, y1: y + hh } };
    });
    return { pb, BZ, PZ, fs, z, B, Pp };
  }

  // 觸發格:泡泡、圖解各自依序分配;泡泡 i 在第 i+2 個出現前 3 格縮掉
  function trigs(L, d) {
    const Kb = C.assign(L, d.bubbles || []), Kp = C.assign(L, d.props || []);
    const Ko = Kb.map((_, i) => (i + 2 < Kb.length ? Kb[i + 2] - 3 : null));
    return { Kb, Kp, Ko };
  }

  function drawPigeon(t, L, d, pal) {
    const k = K.frame(t), P = LY.pg;
    let li = 0;
    L.forEach((l, i) => { if (t + 1e-6 >= l.start) li = i; });
    const name = Array.isArray(d.expr) ? d.expr[li] : d.expr || 'normal';
    const p = K.clip(d.clip || 'idle', k), e = K.P.EXPR[name] || K.P.EXPR.normal;
    const pose = Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
    return K.ground({ x: P.x + 10, y: P.y + 4, w: 150 * P.u, h: 11 * P.u, u: 1.4, pal }) + K.pigeon(pose, { x: P.x, y: P.y, scale: P.u, id: 'talk' });
  }

  function render(t, params) {
    const d = params.data || {}, L = C.lines(params), k = K.frame(t), pal = K.palette(params.hue), G = geo(d), T = trigs(L, d);
    const ko = C.outK(L, d.out), minK = (a, b) => (a == null ? b : b == null ? a : Math.min(a, b));
    let s = '';
    (d.props || []).forEach((p, i) => {
      const g = G.Pp[i], kk = k - T.Kp[i], q = K.pop(kk);
      if (!g || q <= 0) return;
      const el = K.paper(g.it.fn(pal, p.params || {}), { x: g.x, y: g.y, scale: g.u, sx: q, sy: q, k: 'prop', id: 'prop' + i, enter: kk < 2, wide: g.it.wide });
      s += C.exitWrap(el, k, ko, g.x, g.y);
    });
    G.B.forEach((b, i) => {
      const bb = d.bubbles[i], tail = K.portrait ? (b.cx < LY.pg.x ? 'br' : 'bl') : 'bl';
      const el = Ch.bubble(b.lines, { x: b.cx, y: b.cy, fs: G.fs, dashed: !!bb.dashed, tail, rot: ROT[b.s], k: k - T.Kb[i], id: 'bub' + i });
      s += C.exitWrap(el, k, minK(T.Ko[i], ko), b.cx, b.cy);
    });
    return K.wrap(pal, drawPigeon(t, L, d, pal) + s);
  }

  // 兩框的距離:水平 dx、垂直 dy(負 = 該軸重疊)
  const sep = (a, b) => ({ dx: Math.max(a.x0 - b.x1, b.x0 - a.x1), dy: Math.max(a.y0 - b.y1, b.y0 - a.y1) });

  function check(params) {
    const d = params.data || {}, e = C.checkLines(params);
    if (e.length) return e;
    const L = C.lines(params), bubs = d.bubbles || [], props = d.props || [];
    if (d.hide || (d.pigeon && d.pigeon.hide)) e.push('pigeon_talk 不能藏鴿子');
    e.push(...C.checkPigeon(L, { expr: d.expr, clip: d.clip }));
    if (d.clip && K.P.CLIPS[d.clip] && !BOX[d.clip]) e.push(`clip「${d.clip}」不適用 pigeon_talk(可用 ${Object.keys(BOX).join('/')})`);
    if (!bubs.length && !props.length) e.push('bubbles 與 props 都是空的');
    bubs.forEach((b, i) => {
      const ls = linesOf(b);
      if (!ls.join('')) e.push(`bubbles[${i}] 缺 text`);
      if (ls.length > 2) e.push(`bubbles[${i}] ${ls.length} 行,上限 2 行`);
      e.push(...C.checkTrig(L, b.at, b.word, `bubbles[${i}]`));
    });
    if (props.length > 3) e.push(`props ${props.length} 個,上限 3 個`);
    props.forEach((p, i) => {
      if (!libOf(p.lib)) e.push(`props[${i}].lib「${p.lib}」不存在`);
      else if (!propOf(p)) e.push(`props[${i}].name「${p.name}」不在 ${p.lib}.LIST`);
      e.push(...C.checkTrig(L, p.at, p.word, `props[${i}]`));
    });
    e.push(...C.checkTrig(L, d.out && d.out.at, d.out && d.out.word, 'out'));
    if (e.length) return e;
    const G = geo(d), T = trigs(L, d), M = K.L.margin, pb = G.pb;
    // 鴿子本身:頭頂不進上邊距、腳底陰影不進字幕帶
    if (pb.y0 < M[1] || pb.y1 + 6 * LY.pg.u > K.L.SUB_BAND[0]) e.push(`clip「${d.clip || 'idle'}」鴿子外框 y ${Math.round(pb.y0)}–${Math.round(pb.y1)} 超出上邊距或進字幕帶`);
    // 觸發須依陣列順序;被擠掉的泡泡至少完整停 1 秒
    [['bubbles', T.Kb], ['props', T.Kp]].forEach(([n, Ks]) => Ks.forEach((x, i) => { if (i && x < Ks[i - 1]) e.push(`${n}[${i}] 觸發早於 ${n}[${i - 1}],請照出現順序排`); }));
    T.Ko.forEach((x, i) => { if (x != null && x - (T.Kb[i] + C.FULL) < 10) e.push(`bubbles[${i}] 被 bubbles[${i + 2}] 擠掉前只完整停 ${((x - T.Kb[i] - C.FULL) / 10).toFixed(1)} 秒(< 1)`); });
    if (G.z.W > G.BZ.x1 - G.BZ.x0) e.push(`泡泡寬 ${Math.round(G.z.W)}px 超出泡泡區 ${Math.round(G.BZ.x1 - G.BZ.x0)}px(字級已降到 ${G.fs})`);
    if (G.z.H > G.BZ.y1 - G.BZ.y0) e.push(`泡泡高 ${Math.round(G.z.H)}px 超出泡泡區 ${Math.round(G.BZ.y1 - G.BZ.y0)}px(字級已降到 ${G.fs})`);
    if (props.some((p) => p.x == null || p.y == null) && G.PZ.x1 - G.PZ.x0 < LY.prop.minW) e.push(`圖解區寬只有 ${Math.round(G.PZ.x1 - G.PZ.x0)}px`);
    // 外框:不出邊距、不進字幕帶、與鴿子外框間距 ≥ gapX(水平分開)或 gapY(垂直分開)
    const els = G.B.map((b, i) => [`bubbles[${i}]`, b.box, b.cy]).concat(G.Pp.map((p, i) => [`props[${i}]`, p.box, p.y]));
    els.forEach(([n, b, cy]) => {
      if (b.x0 < M[0] || b.y0 < M[1] || b.x1 > K.L.W - M[2] || cy + (b.y1 - cy) * OVER + SHADOW > K.L.SUB_BAND[0]) e.push(`${n} 外框 (${Math.round(b.x0)},${Math.round(b.y0)})–(${Math.round(b.x1)},${Math.round(b.y1)}) 超出邊距或彈入時進字幕帶`);
      const g = sep(b, pb);
      if (g.dx < LY.gapX && g.dy < LY.gapY) e.push(`${n} 壓到鴿子(水平距 ${Math.round(g.dx)}、垂直距 ${Math.round(g.dy)}px)`);
    });
    const last = Math.max(...T.Kb.concat(T.Kp)), ko = C.outK(L, d.out);
    e.push(...C.checkHold(last, ko == null ? Math.round(params.dur * 10) : ko));
    return e;
  }

  const API = { LAYOUT, BOX, render, check };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).pigeon_talk = API;
})();
