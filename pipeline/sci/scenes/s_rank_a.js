/* salary 場景 s_rank_a(句 6–8)十等份。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–2。
 * 版面用 PropsSalary.RANK_LAYOUT(十等份階梯在右側 x 420–1800,鴿子在左欄、腳底固定、面向右);實際只有 9 根(D1–D9)。
 * 結束狀態 = s_rank_b 開頭:九根柱、只有第 5 根(黃)有數值 54.6、左上固定來源牌、鴿子 look;句8 的灰柱與標牌在句末前收掉。
 * 句6:九個剪影(不畫臉)由矮到高從句首每隔 2 格一個站上基線;詞「切成」位置起,剪影由左至右每格一個換成同位置的柱(柱每格一根),x 軸標籤隨柱出現。
 * 句7:句首 D5 轉黃、黃牌「中間那個人」+ 引線彈入;詞「54.6」位置 D5 數值牌彈入;句末(句8 前 3 格)黃牌與引線縮掉。
 * 句8:句首 D5 柱前面、往右偏半根柱寬彈出同寬灰柱(46.8,比 D5 矮)、鴿子 sad;次格黃牌「未滿 30 歲 46.8 萬」在灰柱正上方、引線走 D5/D6 的縫落到灰柱頂;句末前 1.6 秒起三件依序縮掉、鴿子回 look。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale;
  const DEF = [
    { start: 0.035, end: 4.79, text: '主計總處把全台灣的上班族照一年的薪水從低排到高,再切成十等份。' },
    { start: 4.91, end: 9.435, text: '排在最中間的那個人,一年領 54.6 萬,還不到一百萬的六成。' },
    { start: 9.555, end: 14.57, text: '如果只看未滿三十歲的人,中間那個人一年只領 46.8 萬,又更少了。' }];
  const f = (x) => +(+x).toFixed(2);
  const OUT = [0.85, 0.5, 0.2];                                  // 縮掉:第 0、1、2 格的縮放,之後不畫
  const SAD = { lid: 0.65, lidTilt: -18, pdx: -3, pdy: 6, ps: 1, beak: 0 };   // 沒有現成 sad 表情:眼半閉、眼尾下垂
  const PITCH = RL.chart.w / RL.vals.length, BW = PITCH * 0.74;      // 與 Charts.decileRow 同:柱距、柱寬
const THIN = { w: BW, x: RL.chart.x + PITCH * 4.5 + BW / 2, lx: RL.chart.x + PITCH * 5 + 5, v: 46.8 };   // 灰柱:同寬、疊在 D5 前面往右偏半根;引線走 D5 與 D6 的縫
  const FIG = { hMin: 130, hMax: 260, wr: 0.46 };                // 剪影高度範圍與寬高比

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  // 詞的起始字索引 ÷ 句長 × 句長秒數 + start → 第幾格
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  // 以 px 繪製的紙片(同 Charts.sheet,但 sx、sy 可自訂)
  const paperPx = (content, o) => K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
    { x: o.x, y: o.y, rot: o.rot, scale: U, sx: o.sx, sy: o.sy, k: o.kind, id: o.id, enter: o.enter, wide: true });
  // 會彈入、也會縮掉的紙片:kIn = 出現後第幾格(<0 未出現)、kOut = 開始縮後第幾格(<0 未縮)
  function piece(content, o, kIn, kOut) {
    let p;
    if (kOut >= 0) { if (kOut >= OUT.length) return ''; p = OUT[kOut]; } else { if (kIn < 0) return ''; p = K.pop(kIn); }
    return paperPx(content, Object.assign({}, o, { sx: o.sx == null ? p : p * o.sx, sy: p, enter: kOut >= 0 || kIn < 2 }));
  }

  // 剪影:腳底在原點(縮放以腳底為準),H = 總高;頭 + 圓肩身體
  function figure(H) {
    const w = H * FIG.wr, bt = -H + 0.36 * H, rr = 0.18 * H, r = 0.16 * H;
    return `<circle cx="0" cy="${f(-H + r)}" r="${f(r)}" fill="${K.INK}"/>` +
      `<path d="M${f(-w / 2)} 0 V${f(bt + rr)} Q${f(-w / 2)} ${f(bt)} ${f(-w / 2 + rr)} ${f(bt)} H${f(w / 2 - rr)} Q${f(w / 2)} ${f(bt)} ${f(w / 2)} ${f(bt + rr)} V0 Z" fill="${K.INK}"/>`;
  }

  // 鴿子:idle 呼吸(眨眼格保留)、面向右(flip)、表情只換眼
  function pigeonPose(k, e) {
    const p = K.clip('idle', k);
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const C = RL.chart, n = RL.vals.length;
    const pitch = C.w / n, yBot = C.y + C.h, cx = (i) => C.x + pitch * (i + 0.5);
    const yOf = (v) => yBot - (yBot - (C.y + Ch.FS_LABEL * 1.62 + 16)) * v / C.max;
    let s = '';

    // 來源牌(全場)
    s += Ch.srcTag(RL.src.text, { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, id: 'src' });

    // 句6:剪影站上基線,詞「切成」起逐根換成柱
    const kSwap = Math.max(wordK(L[0], '切成'), F[0] + 20);
    const grey = `hsl(${pal.h} 8% 72%)`;
    if (k < kSwap) s += Ch.sheet(rect(-C.w / 2 - 12, -7, C.w + 24, 14, K.INK), { x: C.x + C.w / 2, y: yBot - 7, u: U, k: k - F[0], kind: 'figBase', id: 'figB', wide: true });
    for (let i = 0; i < n; i++) {
      if (k >= kSwap + i) continue;
      const H = FIG.hMin + (FIG.hMax - FIG.hMin) * (RL.vals[i] - RL.vals[0]) / (RL.vals[n - 1] - RL.vals[0]);
      const p = K.pop(k - F[0] - 2 * i);
      if (p <= 0) continue;
      s += paperPx(figure(H), { x: cx(i), y: yBot - 4, sx: p, sy: p, kind: 'figure', id: 'fig' + i, enter: k - F[0] - 2 * i < 2 });
    }

    // 句7:引線與黃牌「中間那個人」(引線在柱與數值牌之下)
    const kOut7 = k - (F[2] - 3), k7 = k - F[1];
    const mid = Ch.plate('中間那個人', 72, { fill: K.YELLOW });
    s += piece(rect(-7, -80, 14, 160, K.INK), { x: cx(4), y: 475, kind: 'leader', id: 'ld7' }, k7, kOut7);

    // 句8:灰柱的引線
    const kOut8 = k - Math.max(F[2] + 25, K.frame(L[2].end - 1.6)), k8 = k - F[2];
    const thinTop = yOf(THIN.v), thinH = yBot - thinTop;
    const call = Ch.plate('未滿 30 歲 46.8 萬', Ch.FS_LABEL, { fill: K.YELLOW });
    const ldTop = 345, ldH = thinTop - ldTop;
    s += piece(rect(-7, -ldH / 2, 14, ldH, K.INK), { x: THIN.lx, y: ldTop + ldH / 2, kind: 'leader', id: 'ld8' }, k8 - 1, kOut8 - 1);

    // 十等份階梯:柱換成後每格一根(最後一根出現 8 格後穩定);句7 起 D5 黃、數值牌在詞「54.6」位置
    const k54 = wordK(L[1], '54.6');
    const numKs = RL.vals.map(() => -1);
    if (k >= k54) numKs[4] = k - k54;
    if (k >= kSwap) {
      s += Ch.decileRow({ x: C.x, y: C.y, w: C.w, h: C.h, max: C.max, pal, id: 'dr', vals: RL.vals, hiIdx: k >= F[1] ? [4] : [], numKs,
        k: k - kSwap, kStep: 1 });
    }

    // 黃牌與灰柱(在階梯之上)
    s += piece(mid.svg, { x: cx(4), y: 335, rot: -1.5, kind: 'sheet', id: 'mid' }, k7, kOut7);
    s += piece(rect(-THIN.w / 2, -thinH / 2, THIN.w, thinH, grey), { x: THIN.x, y: thinTop + thinH / 2, kind: 'thin', id: 'thin' }, k8, kOut8);
    s += piece(call.svg, { x: THIN.x, y: ldTop - call.h / 2 + 4, rot: 1, kind: 'sheet', id: 'call' }, k8 - 1, kOut8 - 1);

    // 鴿子(句8 sad;其餘 look)與腳下襯底
    const P = RL.pigeon, sad = k >= F[2] && !(kOut8 >= 0);
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    s += K.pigeon(pigeonPose(k, sad ? SAD : K.P.EXPR.look), { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_rank_a', dur: 14.6, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
