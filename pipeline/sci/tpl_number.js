/* 模板 number(F4-0):大數字卡(Charts.bigNum)或翻價牌(Charts.priceFlip)+ 說明牌 + 來源牌。
 * data: {num, unit?, note?(≤16 字;放不下一行時拆兩行), src?, at?, word?, flip?:{from,to,at?,word?}, out?:{at,word?}, pigeon?}
 * 有 flip 時畫價牌(from → to,單位用 unit),num 可省略。觸發:數字卡在 at/word(預設第 0 句開頭),說明牌晚 3 格;翻牌預設第 1 句開頭。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判】:fsMax/fsMin 數字字級範圍、flipMax/flipMin 價牌字級範圍(實際字級由 C.fitBlock 取放得進內容區的最大值);
  // noteFs 說明;gap 數字卡與說明牌間距、lineGap 說明兩行間距;srcFs 來源牌
  const LAYOUT = {
    landscape: { fsMax: 300, fsMin: 150, flipMax: 220, flipMin: 100, noteFs: 64, gap: 28, lineGap: 10, srcFs: 40, noteMax: 16 },
    portrait: { fsMax: 260, fsMin: 150, flipMax: 180, flipMin: 100, noteFs: 64, gap: 22, lineGap: 8, srcFs: 40, noteMax: 16 },
  };
  const LY = LAYOUT[C.LAY];
  const NOTE_DELAY = 3;

  // 說明拆行:放得下就一行,否則在最接近中間的標點或空格後拆(沒有就從中間拆)
  function noteLines(note, maxW) {
    if (!note) return [];
    if (Ch.tw(note, LY.noteFs) + LY.noteFs <= maxW) return [note];
    const cs = [...note], mid = cs.length / 2;
    let cut = Math.round(mid), best = 1e9;
    cs.forEach((ch, i) => { if (/[,、 ,]/.test(ch) && Math.abs(i + 1 - mid) < best) { best = Math.abs(i + 1 - mid); cut = i + 1; } });
    return [cs.slice(0, cut).join('').trim(), cs.slice(cut).join('').trim()];
  }
  // 幾何:數字卡(群組 = 數字卡 + 說明牌)在內容區(有來源牌時扣掉來源牌)置中,字級取放得下的最大值
  function geo(d) {
    const A0 = C.area(d.pigeon && d.pigeon.hide), unit = d.unit ? ' ' + d.unit : '', srcH = LY.srcFs * 1.62, srcTop = A0.y1 - srcH;
    const A = d.src ? Object.assign({}, A0, { y1: srcTop - 16 }) : A0;
    const nl = noteLines(d.note, A.x1 - A.x0), ph = LY.noteFs * 1.62;
    const noteH = nl.length ? LY.gap + nl.length * ph + (nl.length - 1) * LY.lineGap : 0;
    const card = (fs) => {
      if (d.flip) return { w: Math.max(Ch.tw(String(d.flip.from) + unit, fs), Ch.tw(String(d.flip.to) + unit, fs)) + fs, h: fs * 3.3, up: fs * 0.4 };   // h = 翻牌後 2.9 倍 + 吊繩 0.4 倍(翻牌前後不動)
      const ufs = Math.max(Ch.FS_LABEL, fs * 0.38);
      return { w: Ch.tw(String(d.num), fs) + (d.unit ? Ch.tw(d.unit, ufs) + fs * 0.08 : 0) + fs * 0.5, h: fs * 1.3, up: 0 };
    };
    const F = C.fitBlock(A, { fsMax: d.flip ? LY.flipMax : LY.fsMax, fsMin: d.flip ? LY.flipMin : LY.fsMin,
      hOf: (fs) => card(fs).h + noteH, wOf: (fs) => card(fs).w + 80 });   // +80:傾斜與陰影的餘裕,不然價牌碰邊距
    const c = card(F.fs), cardCy = F.top + c.up + (c.h - c.up) / 2, ny = F.top + c.h + LY.gap + ph / 2;
    const notes = nl.map((s, i) => ({ s, w: Ch.tw(s, LY.noteFs) + LY.noteFs, y: ny + i * (ph + LY.lineGap) }));
    return { A, fs: F.fs, cx: F.cx, cy: F.cy, cardCy, w: c.w, h: c.h, top: F.top, notes, bottom: F.top + F.h,
      src: { x: A0.x0 + 20, y: A0.y1 - srcH / 2 }, srcTop };
  }

  function times(d, L) {
    const kNum = C.trig(L, d.at, d.word, 0);
    const kFlip = d.flip ? C.trig(L, d.flip.at, d.flip.word, Math.min(1, L.length - 1)) : null;
    const last = Math.max(d.note ? kNum + NOTE_DELAY : kNum, kFlip == null ? -1 : kFlip);
    return { kNum, kFlip, last };
  }

  function render(t, params) {
    const d = params.data || {}, L = C.lines(params), k = K.frame(t), pal = K.palette(params.hue), G = geo(d), T = times(d, L);
    let s = '';
    if (d.src) s += Ch.srcTag(d.src, { x: G.src.x, y: G.src.y, anchor: 'left', fs: LY.srcFs, pal, k: k - T.kNum, id: 'src' });
    if (d.flip) {
      s += Ch.priceFlip({ x: G.cx, y: G.cardCy, from: d.flip.from, to: d.flip.to, unit: d.unit, fs: G.fs, pal, rot: -1.5,
        k: k - T.kNum, kFlip: k >= T.kFlip ? k - T.kFlip : -1, id: 'flip' });
    } else {
      s += Ch.bigNum({ x: G.cx, y: G.cardCy, num: String(d.num), unit: d.unit, fs: G.fs, pal, rot: -1.5, k: k - T.kNum, id: 'num' });
    }
    G.notes.forEach((n, i) => {
      s += Ch.sheet(Ch.plate(n.s, LY.noteFs).svg, { x: G.cx, y: n.y, rot: i ? 1 : -1.5, k: k - T.kNum - NOTE_DELAY - i, kind: 'note', id: 'note' + i, wide: true });
    });
    s = C.exitWrap(s, k, C.outK(L, d.out), G.cx, G.cy);
    return K.wrap(pal, s + C.pigeon(t, L, d.pigeon, pal));
  }

  function check(params) {
    const d = params.data || {}, e = C.checkLines(params);
    if (e.length) return e;
    const L = C.lines(params);
    if (d.flip) {
      if (d.flip.from == null || d.flip.to == null) e.push('flip 需要 from 與 to');
      e.push(...C.checkTrig(L, d.flip.at, d.flip.word, 'flip'));
    } else if (d.num == null || d.num === '') e.push('缺 num(或 flip)');
    e.push(...C.checkTrig(L, d.at, d.word, 'data'), ...C.checkTrig(L, d.out && d.out.at, d.out && d.out.word, 'out'), ...C.checkPigeon(L, d.pigeon));
    if (e.length) return e;
    if (d.note && [...d.note].length > LY.noteMax) e.push(`note ${[...d.note].length} 字,上限 ${LY.noteMax}`);
    const G = geo(d), cw = G.A.x1 - G.A.x0;
    if (G.w > cw) e.push(`數字卡寬 ${Math.round(G.w)}px 超出內容區 ${cw}px`);
    G.notes.forEach((n) => { if (n.w > cw) e.push(`說明「${n.s}」寬 ${Math.round(n.w)}px 超出內容區`); });
    const floor = d.src ? G.srcTop - 16 : G.A.y1;
    if (G.bottom > floor) e.push(`說明牌下緣 ${Math.round(G.bottom)} 超過 ${Math.round(floor)}(內容區或來源牌)`);
    if (d.src && Ch.tw(d.src, LY.srcFs) + LY.srcFs * 1.2 > cw) e.push('src 太長,超出內容區');
    const T = times(d, L), ko = C.outK(L, d.out);
    if (T.kFlip != null && T.kFlip < T.kNum) e.push('flip 觸發早於數字卡出現');
    e.push(...C.checkHold(T.last, ko == null ? Math.round(params.dur * 10) : ko));
    return e;
  }

  const API = { LAYOUT, render, check };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).number = API;
})();
