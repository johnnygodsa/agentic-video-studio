/* 模板 bars(F4-0b):標題牌 + 橫向排行長條(Charts.hbars)+ 來源牌。
 * data: {title?, unit?, src?, bars:[{label,value,text?,icon?,at?,word?,grey?}], hi:[i], max?, out?:{at,word?}, pigeon?}
 * 數值牌字 = text,省略 = value + unit。hi:該列標籤黃底、數值墨底黃字(單一焦點),其餘主色,grey 灰條。
 * 來源牌:有標題且放得下時放標題同一列右端(不另佔高度),否則放最後一條下方 srcGap、靠左對齊長條群組(算進群組高)。
 * 少條數:字級上限放大(橫 96/直 88),群組高仍 < 內容區 45% 時再加高列高(上限 stretchR × 字級)。觸發:標題在第 0 句開頭;各條依 at/word,省略則依序分配。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判】:max 條數、fsMax/fsMin 標籤與數值字級範圍(實際由 C.fitBlock 取最大值)、rowR 列高 ÷ 字級、gapR 列距 ÷ 列高、
  // minBar 最長條至少幾 px、maxW 群組寬上限、titleGap 標題牌與長條間距、srcFs 來源牌字級、srcGap 來源牌離最後一條、gapX 標籤/長條/數值間距(同 hbars 預設)、
  // minFill 群組高至少佔內容區高的比例、stretchR 為補足 minFill 而加高的列高 ÷ 字級上限
  const LAYOUT = {
    landscape: { max: 6, fsMax: 96, fsMin: 56, rowR: 1.25, gapR: 0.15, minBar: 300, maxW: 1300, titleGap: 24, srcFs: 40, srcGap: 24, gapX: 18, minFill: 0.45, stretchR: 1.6 },
    portrait: { max: 5, fsMax: 88, fsMin: 60, rowR: 1.25, gapR: 0.15, minBar: 200, maxW: 836, titleGap: 24, srcFs: 40, srcGap: 24, gapX: 18, minFill: 0.45, stretchR: 1.6 },
  };
  const LY = LAYOUT[C.LAY];
  const inset = (A) => Object.assign({}, A, { x0: A.x0 + 12, x1: A.x1 - 12 });   // 左右各讓 12px 給描邊與陰影

  // 幾何:群組 = 標題列(標題牌 + 來源牌)+ 長條,在內容區垂直置中、水平置中;字級取放得下的最大值
  function geo(d) {
    const A0 = C.area(d.pigeon && d.pigeon.hide), bars = d.bars || [], n = Math.max(1, bars.length);
    const tb = d.title ? C.titleBox(d.title) : null, srcH = LY.srcFs * 1.62;
    const srcW = d.src ? Ch.plate(d.src, LY.srcFs, { padX: 0.8 }).w + LY.srcFs * 0.36 : 0;
    const below = !!(d.src && (!tb || tb.w + srcW + 40 > Math.min(A0.x1 - A0.x0 - 24, LY.maxW))), srcBlock = below ? LY.srcGap + srcH : 0;   // 標題列放不下(或沒標題)就放最後一條下方
    const A = inset(A0), head = tb ? tb.h + LY.titleGap : 0;
    const str = (b) => (b.text != null ? String(b.text) : `${b.value}${d.unit || ''}`), hasIcon = bars.some((b) => b.icon);
    const size = (fs) => {
      const rowH = fs * LY.rowR, gap = rowH * LY.gapR, lead = hasIcon ? rowH + 4 : fs * 0.4;
      const labelW = lead + Math.max(0, ...bars.map((b) => Ch.tw(b.label || '', fs))) + fs * 0.4;
      const valW = Math.max(0, ...bars.map((b) => Ch.tw(str(b), fs) + fs * 0.7));
      return { rowH, gap, labelW, valW, need: labelW + valW + 2 * LY.gapX + LY.minBar, H: n * rowH + (n - 1) * gap };
    };
    const headW = tb ? tb.w + (d.src && !below ? srcW + 40 : 0) : 0;
    const F = C.fitBlock(A, { fsMax: LY.fsMax, fsMin: LY.fsMin, hOf: (fs) => head + size(fs).H + srcBlock, wOf: (fs) => Math.max(size(fs).need, headW) });
    const z = size(F.fs), w = Math.min(A.x1 - A.x0, LY.maxW), x = F.cx - w / 2;
    const want = (A0.y1 - A0.y0) * LY.minFill;      // 少條數:加高列高讓群組高 ≥ 內容區 minFill(列高上限 stretchR × 字級),再重新置中
    if (F.h < want) {
      z.rowH = Math.min(F.fs * LY.stretchR, z.rowH + (want - F.h) / (n + (n - 1) * LY.gapR));
      z.gap = z.rowH * LY.gapR; z.H = n * z.rowH + (n - 1) * z.gap;
      F.h = head + z.H + srcBlock; F.top = A.y0 + 12 + (A.y1 - A.y0 - 24 - F.h) / 2; F.cy = F.top + F.h / 2;
    }
    return Object.assign(z, { A0, A, F, fs: F.fs, tb, x, w, top: F.top + head, str, headW, srcW, fill: F.h / (A0.y1 - A0.y0),
      titlePos: tb && { x: x + tb.w / 2, y: F.top + tb.h / 2 },
      src: d.src && (below ? { x: x, y: F.top + head + z.H + LY.srcGap + srcH / 2, anchor: 'left' } : { x: x + w, y: F.top + tb.h / 2, anchor: 'right' }) });
  }

  function render(t, params) {
    const d = params.data || {}, L = C.lines(params), k = K.frame(t), pal = K.palette(params.hue), G = geo(d);
    const bars = d.bars || [], Ks = C.assign(L, bars), hi = d.hi || [], k0 = C.trig(L, 0, null, 0);
    let s = C.title(d.title, k - k0, G.titlePos);
    s += Ch.hbars({ x: G.x, y: G.top, w: G.w, rowH: G.rowH, gap: G.gap, gapX: LY.gapX, fs: G.fs, numFs: G.fs, labelW: G.labelW, max: d.max, pal, id: 'tb',
      bars: bars.map((b, i) => ({ label: b.label, value: +b.value, text: G.str(b), icon: b.icon ? C.iconOf(b.icon, pal) : null,
        grey: !!b.grey, hi: hi.indexOf(i) >= 0, k: k - Ks[i] })) });
    if (G.src) s += Ch.srcTag(d.src, { x: G.src.x, y: G.src.y, anchor: G.src.anchor, fs: LY.srcFs, pal, k: k - (d.title ? k0 : Ks[0]), id: 'src' });
    s = C.exitWrap(s, k, C.outK(L, d.out), G.F.cx, G.F.cy);
    return K.wrap(pal, s + C.pigeon(t, L, d.pigeon, pal));
  }

  function check(params) {
    const d = params.data || {}, e = C.checkLines(params);
    if (e.length) return e;
    const L = C.lines(params), bars = d.bars || [];
    if (!bars.length) e.push('bars 是空的');
    if (bars.length > LY.max) e.push(`bars ${bars.length} 條,${C.LAY} 上限 ${LY.max}`);
    bars.forEach((b, i) => {
      if (!b.label) e.push(`bars[${i}] 缺 label`);
      if (!isFinite(b.value) || +b.value < 0) e.push(`bars[${i}].value「${b.value}」不是 ≥0 的數字`);
      if (b.icon && !C.iconOf(b.icon)) e.push(`bars[${i}].icon「${b.icon}」找不到(格式 片名.圖解名)`);
      e.push(...C.checkTrig(L, b.at, b.word, `bars[${i}]`));
    });
    if (d.max != null && (!isFinite(d.max) || bars.some((b) => +b.value > +d.max))) e.push(`max=${d.max} 不是數字或小於某條的 value`);
    (d.hi || []).forEach((i) => { if (!bars[i]) e.push(`hi 索引 ${i} 不存在`); });
    e.push(...C.checkTrig(L, d.out && d.out.at, d.out && d.out.word, 'out'), ...C.checkPigeon(L, d.pigeon));
    if (e.length) return e;
    const G = geo(d), aw = G.A.x1 - G.A.x0;
    if (G.headW > aw) e.push(`標題加來源牌寬 ${Math.round(G.headW)}px 超出內容區 ${aw}px`);
    if (d.src && G.srcW > aw) e.push('src 太長,超出內容區');
    if (G.need > G.w) e.push(`標籤加數值太寬:最長條只剩 ${Math.round(G.w - G.need + LY.minBar)}px(下限 ${LY.minBar})`);
    if (G.F.h > G.A.y1 - G.A.y0 - 24) e.push(`可用高度不足:群組高 ${Math.round(G.F.h)}px > 內容區 ${Math.round(G.A.y1 - G.A.y0 - 24)}px(字級已降到下限 ${LY.fsMin})`);
    const ko = C.outK(L, d.out);
    e.push(...C.checkHold(Math.max(...C.assign(L, bars)), ko == null ? Math.round(params.dur * 10) : ko));
    return e;
  }

  const API = { LAYOUT, render, check, geo };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).bars = API;
})();
