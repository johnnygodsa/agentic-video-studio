/* turtle 場景 §11 t_sheet(句 37–40,21.8 秒)淨灘記錄表。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 佈景:沙灘與海面色塊(無 data-k 的底色,不入外框檢查)。鴿子在左下,記錄表在 x 520–1820(不蓋到鴿子)。
 * 句37:鴿子走進來;待查清單(第二列已打勾)彈入,右邊多一根橫放的吸管加「?」。
 * 句38:記錄表攤開(場景內自己畫:5 欄 × 4 列共 20 格,十九類加最後一格空白;1300×614,等比不拉伸),格子逐格出現,
 *       左上「十九格」;寶特瓶格逐筆畫出一個「正」字(字高 97、筆畫粗 16)。
 * 句39:牙刷格與針筒格亮品牌黃,兩格下方括框加「醫療/個人衛生用品」。
 * 句40:括框與標籤退場,只留牙刷格亮著並加墨色粗圈,下方小牌「自己一格」;鴿子 surprised。
 * 同時在動的非文字元素 ≤ 2 組(鴿子 + 一組);記錄表為單片紙。格內類別名稱 36–44px 是這張表允許的小字。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 270, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.04, end: 7.15 }, { start: 7.27, end: 13.21 }, { start: 13.34, end: 17.3 }, { start: 17.43, end: 21.75 }];
  const TB = { x0: 520, y0: 86, w: 1300, h: 614, cols: 5, rows: 4, pad: 5 };   // 記錄表外框(px)與格距
  const CW = TB.w / TB.cols, CH = TB.h / TB.rows;
  // 十九類:projects\turtle\icc_recent.csv 表頭第 7–25 欄(去掉「＊」),順序照表頭。[名稱分行, PropsTurtle 小圖, 轉角];沒有小圖的只放名稱
  const CATS = [[['寶特瓶'], 'bottle', 90], [['塑膠瓶蓋'], 'cap'], [['其他飲料瓶', '與食物容器']], [['非食物的', '瓶罐與容器']], [['塑膠提袋'], 'bag'],
    [['食品包裝袋']], [['吸管'], 'straw', 90], [['外帶飲料杯'], 'cup'], [['免洗餐具'], 'cutlery', 90], [['鐵鋁罐']],
    [['鋁箔包', '或利樂包']], [['玻璃瓶']], [['釣魚用具'], 'hook'], [['漁業浮球、', '浮筒、', '漁船防碰墊']], [['漁網與繩子'], 'net'],
    [['菸蒂']], [['牙刷'], 'toothbrush'], [['針筒、針頭'], 'syringe'], [['打火機']]];
  if (CATS.length !== 19) throw new Error('t_sheet 類別數核對失敗');
  const I_BOTTLE = 0, I_BRUSH = 16, I_SYR = 17;
  const ZHENG = [[0, 0, 18, 3], [7.5, 0, 3, 18], [9, 8, 8, 3], [2, 8, 3, 10], [0, 15, 18, 3]];   // 「正」五筆(18 單位見方)
  const ZS = 5.4;                                  // 正字倍率:字高 97px、筆畫粗 16px
  const f = (x) => +(+x).toFixed(2);
  const np = (k) => (k < 0 ? -1 : k === 0 ? 2 : 3);   // 大塊與貼近字幕帶的紙片不過衝:第 0 格 0.95 倍,之後原大
  const T = (s, x, y, size) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${K.INK}" stroke="none">${s}</text>`;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (L, i, frac) => K.frame(L[i].start + frac * (L[i].end - L[i].start));

  // 第 i 格在畫面上的中心 px
  const cellXY = (i) => ({ x: TB.x0 + ((i % TB.cols) + 0.5) * CW, y: TB.y0 + (Math.floor(i / TB.cols) + 0.5) * CH });

  // 記錄表內容(px,中心在原點)。n:已出現幾格(0–20);hi:亮品牌黃的格;soft:淡色提示的格;strokes:寶特瓶格的正字已畫幾筆
  function tableSvg(pal, n, hi, soft, strokes) {
    const cx0 = TB.x0 + TB.w / 2, cy0 = TB.y0 + TB.h / 2, iw = CW - 2 * TB.pad, ih = CH - 2 * TB.pad;
    const fit = (name, x, y, bw, bh, rot) => {     // 小圖縮到 bw×bh 內(rot 90 = 橫放)
      const d = PT.LIST[name], w = rot ? d.h : d.w, h = rot ? d.w : d.h, sc = Math.min(bw / w, bh / h);
      return `<g transform="translate(${f(x)} ${f(y)}) rotate(${rot || 0})">${Ch.icon({ svg: d.fn(pal, {}), w: d.w, h: d.h }, 0, 0, sc * Math.max(d.w, d.h))}</g>`;
    };
    let c = `<rect x="${-TB.w / 2}" y="${-TB.h / 2}" width="${TB.w}" height="${TB.h}" fill="hsl(${pal.h} 30% 45%)" stroke-linejoin="miter"/>`;
    for (let i = 0; i < Math.min(n, 20); i++) {
      const p = cellXY(i), x = p.x - cx0, y = p.y - cy0;
      c += `<rect x="${f(x - iw / 2)}" y="${f(y - ih / 2)}" width="${f(iw)}" height="${f(ih)}" fill="${hi.includes(i) ? K.YELLOW : i === soft ? pal.pad : K.PAPER}" stroke="none"/>`;
      if (i >= CATS.length) continue;              // 第 20 格空白
      const nm = CATS[i][0], ic = CATS[i][1], rot = CATS[i][2];
      if (i === I_BOTTLE) {                        // 寶特瓶格:左邊名稱與小圖,右邊畫正字
        c += T(nm[0], x - 58, y - 42, 36) + fit(ic, x - 60, y + 25, 116, 80, rot);
        const ox = x + 62 - 9 * ZS, oy = y + 3 - 9 * ZS;
        ZHENG.slice(0, strokes).forEach((z) => {
          c += `<rect x="${f(ox + z[0] * ZS)}" y="${f(oy + z[1] * ZS)}" width="${f(z[2] * ZS)}" height="${f(z[3] * ZS)}" fill="${K.INK}" stroke="none"/>`;
        });
      } else if (ic) {                             // 名稱在上、小圖在下
        c += T(nm[0], x, y - 42, 36) + fit(ic, x, y + 25, 216, 80, rot);
      } else {                                     // 只有名稱:置中、字放大
        const fs = nm.length === 3 ? 38 : 44, lh = fs * 1.18;
        nm.forEach((s, j) => { c += T(s, x, y + (j - (nm.length - 1) / 2) * lh, fs); });
      }
    }
    return c;
  }

  function pigeonPose(k, reacts, expr, walkQ) {
    if (walkQ != null && walkQ < 12) return K.expr(K.clip('walk', walkQ), expr);
    for (const r of reacts) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (r.loop ? k >= r.k0 : k >= r.k0 && k < r.k0 + n) return K.expr(K.clip(r.clip, k - r.k0), r.expr || expr);
    }
    return K.expr(K.clip('idle', k), expr);
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;
    const q = k - F[ph];

    // 佈景:海面、浪花、沙灘(底色,不帶 data-k)
    let s = `<rect x="0" y="0" width="1920" height="480" fill="hsl(195 50% 80%)"/><rect x="0" y="480" width="1920" height="600" fill="hsl(42 55% 85%)"/>`;
    let foam = '0,470';
    for (let x = 0; x <= 1920; x += 60) foam += ` ${x + 30},${x % 120 === 0 ? 452 : 490}`;
    s += `<polygon points="${foam} 1920,500 0,500" fill="${K.PAPER}" opacity=".85"/>`;

    // 鴿子:句37 開頭走進來
    const walkQ = k < 12 ? k : null;
    const px = k < 12 ? FOOT.x - (12 - k) * 30 : FOOT.x;
    s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 380, h: 36, u: U, pal });
    const reacts = [{ k0: F[0] + 14, clip: 'tilt', expr: 'doubt' }, { k0: F[1] + at(L, 1, 0.3) - F[1], clip: 'write', loop: true, expr: 'look' },
      { k0: F[3] + 14, clip: 'shock', expr: 'surprised' }];
    // 句39 起寫字動作停止(只有 [1] 的 loop 到句39 前)
    const rs = ph >= 2 ? reacts.filter((r) => !r.loop) : reacts;
    s += K.pigeon(Object.assign({}, pigeonPose(k, rs, 'look', walkQ), { flip: 1 }), { x: px, y: FOOT.y, scale: U, id: 'main', enter: k < 14 });

    const icn = (name, opts, x, y, box, o) => Ch.sheet(Ch.icon({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h }, 0, 0, box),
      Object.assign({ x, y, u: U, kind: 'prop', id: name, wide: PT.LIST[name].wide }, o));

    if (ph === 0) {                                // 句37:待查清單 + 吸管 + 「?」
      const q0 = k - F[0] - 14;
      s += Ch.checklist({ pal, u: U, x: 520, y: 130, w: 760, rowH: 130, gap: 36, fs: 64, id: 'cl', items: [
        { label: '付錢就安全?', state: 'empty', k: q0 }, { label: '都送去燒?', state: 'check', k: q0 - 2, kState: 99 },
        { label: '為了省錢?', state: 'empty', k: q0 - 4 }] });
      s += icn('straw', {}, 1540, 361, 520, { rot: 90, k: k - at(L, 0, 0.4), id: 'straw' });
      s += K.tile('?', { x: 1700, y: 200, size: 200, rot: 6, u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(k - at(L, 0, 0.55)), sy: K.pop(k - at(L, 0, 0.55)),
        id: 'q', enter: k - at(L, 0, 0.55) < 2 });
    } else {
      // 記錄表(單片紙):句38 格子逐格出現(每格 2 格)、寶特瓶格畫正字;句39 牙刷格、針筒格亮黃;句40 只留牙刷格
      const qs = k - F[1];
      const n = Math.min(20, 2 + qs * 2);
      const strokes = ph === 1 ? Math.max(0, Math.min(5, Math.floor((k - at(L, 1, 0.32)) / 4) + 1)) : 5;
      const kSyr = at(L, 2, 0.5) - F[2];
      const hi = ph === 1 ? [] : ph === 2 ? (q >= 2 ? (q >= kSyr ? [I_BRUSH, I_SYR] : [I_BRUSH]) : []) : [I_BRUSH];
      s += Ch.sheet(tableSvg(pal, n, hi, ph === 1 ? I_BOTTLE : -1, strokes),
        { x: TB.x0 + TB.w / 2, y: TB.y0 + TB.h / 2, u: U, k: np(qs), kind: 'prop', id: 'tallySheet' });
      // 左上:「十九格」(句38 起一直在)
      const p19 = Ch.plate('十九格', 96, { fill: K.YELLOW });
      s += Ch.sheet(p19.svg, { x: 290, y: 185, rot: -2, u: U, k: qs - 12, kind: 'note', id: 'n19', wide: true });
      const cb = cellXY(I_BRUSH), cs = cellXY(I_SYR), yb = TB.y0 + TB.h;
      if (ph === 2) {                              // 兩格下方的括框加標籤
        const x0 = cb.x - CW / 2, x1 = cs.x + CW / 2, w = x1 - x0, bw = 14;
        s += Ch.sheet(`<rect x="${f(-w / 2)}" y="-7" width="${f(w)}" height="${bw}" fill="${K.INK}"/>` +
          `<rect x="${f(-w / 2)}" y="-19" width="${bw}" height="26" fill="${K.INK}"/><rect x="${f(w / 2 - bw)}" y="-19" width="${bw}" height="26" fill="${K.INK}"/>`,
          { x: (x0 + x1) / 2, y: yb + 19, u: U, k: q - (at(L, 2, 0.58) - F[2]), kind: 'bracket', id: 'br', wide: true });
        const pl = Ch.plate('醫療/個人衛生用品', 56);
        s += Ch.sheet(pl.svg, { x: (x0 + x1) / 2, y: 784, u: U, k: np(q - (at(L, 2, 0.62) - F[2])), kind: 'note', id: 'med', wide: true });
      }
      if (ph === 3) {                              // 牙刷格墨色粗圈 + 小牌
        const ring = (col, sw) => `<rect x="-136" y="-84" width="272" height="168" rx="44" fill="none" stroke="${col}" stroke-width="${sw}"/>`;
        s += Ch.sheet(ring(K.PAPER, 24) + ring(K.INK, 14), { x: cb.x, y: cb.y, rot: -1, u: U, k: q, kind: 'ring', id: 'ring', wide: true });
        const p1 = Ch.plate('自己一格', 58, { fill: K.YELLOW });
        s += Ch.sheet(p1.svg, { x: cb.x, y: 784, rot: -1.5, u: U, k: np(q - 8), kind: 'note', id: 'one', wide: true });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_sheet', dur: 21.8, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
