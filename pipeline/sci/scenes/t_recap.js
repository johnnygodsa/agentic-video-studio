/* turtle 場景 §29 t_recap(句 116–120,17.4 秒)整理。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句116:記錄板(第 18 格亮黃)加大字牌「整理一下」。鴿子本場不出現。
 * 句117–120:2×2 四格紙白卡(各 800×340),句首彈入;未輪到的三格先以淡色空卡佔位。
 *   ① 牙刷→焚化爐→閃電 ② 大字「第18名」加「誰的?」小牌 ③ 小海龜與亮燈泡 ④ 吸管與塑膠袋加向下箭頭。
 * 句內多個圖依句長比例逐一彈入;最後一格最後一個圖在 50% 處,之後停留。同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 紙片倍率(同鴿子場景)
  const DEF = [{ start: 0.09, end: 1.79 }, { start: 1.92, end: 5.54 }, { start: 5.67, end: 10.33 }, { start: 10.45, end: 13.33 }, { start: 13.45, end: 17.36 }];
  const CARD = { w: 780, h: 330 };
  const POS = [{ x: 480, y: 250 }, { x: 1440, y: 250 }, { x: 480, y: 650 }, { x: 1440, y: 650 }];   // 卡片中心
  const OUT = [0.7, 0.35];                         // 退場縮小兩格
  const RED = 'hsl(6 75% 55%)';
  const TALLY = [3, 5, 2, 7, 1, 4, 2, 0, 6, 3, 1, 2, 0, 5, 1, 2, 4, 1, 2];   // 記錄表上的筆畫示意(不代表數字)
  const f = (x) => +(+x).toFixed(2);
  const now = (k) => (k < 0 ? -1 : 3);            // 大紙片直接以原尺寸出現(不過衝,免得出界)

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const poly = (pts, fill) => `<polygon points="${pts.map((p) => f(p[0]) + ',' + f(p[1])).join(' ')}" fill="${fill}"/>`;
  function shrink(k, kOut, cx, cy) {
    if (k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  // 卡片內的圖:中心相對於卡中心 (dx,dy),box 為見方 px
  const inCard = (c, content, dx, dy, k, kind, id, wide) => Ch.sheet(content, { x: c.x + dx, y: c.y + dy, u: U, k, kind, id, wide });
  const propIn = (pal, c, n, o, dx, dy, box, k, rot, id) => {
    const g = Ch.icon(ic(pal, n, o), 0, 0, box);
    return inCard(c, rot ? `<g transform="rotate(${rot})">${g}</g>` : g, dx, dy, k, 'prop', id || n, PT.LIST[n].wide);
  };
  const chevron = () => poly([[-22, -26], [4, -26], [28, 0], [4, 26], [-22, 26], [2, 0]], K.INK);

  // 卡片本體(紙白底加頂端主色帶)與空卡佔位
  function cardBody(pal, c, k) {
    return Ch.sheet(`<rect x="${-CARD.w / 2}" y="${-CARD.h / 2}" width="${CARD.w}" height="${CARD.h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-CARD.w / 2}" y="${-CARD.h / 2}" width="${CARD.w}" height="22" fill="${pal.main}" stroke="none"/>`, { x: c.x, y: c.y, u: U, k: now(k), kind: 'card', id: 'card', wide: true });
  }
  function emptyCard(pal, c, k) {
    return Ch.sheet(`<rect x="${-CARD.w / 2}" y="${-CARD.h / 2}" width="${CARD.w}" height="${CARD.h}" fill="${pal.pad}" stroke-linejoin="miter"/>` +
      `<rect x="${-CARD.w / 2 + 16}" y="${-CARD.h / 2 + 16}" width="${CARD.w - 32}" height="${CARD.h - 32}" fill="none" stroke="hsl(${pal.h} 40% 62%)" stroke-width="7" stroke-dasharray="26 18"/>`,
    { x: c.x, y: c.y, u: U, k: now(k), kind: 'slot', id: 'slot', wide: true });
  }

  // 句116:記錄板(第 18 格高亮)加大字牌
  const SHEET = { x: 560, y: 460, box: 700 }, TITLE = { x: 1380, y: 460, fs: 150 };
  function s116(pal, k0, k1) {
    const st = ic(pal, 'tallySheet', { hi: 17, tally: TALLY });
    let s = Ch.sheet(Ch.icon(st, 0, 0, SHEET.box), { x: SHEET.x, y: SHEET.y, u: U, k: now(k0), kind: 'prop', id: 'sheet' });
    const pl = Ch.plate('整理一下', TITLE.fs, { fill: K.YELLOW });
    return s + Ch.sheet(pl.svg, { x: TITLE.x, y: TITLE.y, rot: -2, u: U, k: k1, kind: 'tag', id: 'recap', wide: true });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    let s = '';

    // 句116(到句117 開頭退場)
    const out = shrink(k, F[1], 1000, 460);
    if (out) s += out(s116(pal, k - F[0], k - at(L[0], 0.35)));

    if (k >= F[1]) {
      // 空卡佔位(②③④):句117 開頭一起出現,輪到時被紙白卡蓋掉
      for (let i = 1; i < 4; i++) if (k < F[i + 1] + 2) s += emptyCard(pal, POS[i], k - F[1]);
      // ① 牙刷→焚化爐→閃電
      let c = POS[0];
      s += cardBody(pal, c, k - F[1]);
      s += propIn(pal, c, 'toothbrush', {}, -285, 0, 230, k - F[1], -20, 'brush');
      s += inCard(c, chevron(), -138, 5, k - at(L[1], 0.2), 'arrow', 'a1');
      s += propIn(pal, c, 'incinerator', { restaurant: false }, 0, 8, 250, k - at(L[1], 0.3), 0, 'burner');
      s += inCard(c, chevron(), 140, 5, k - at(L[1], 0.5), 'arrow', 'a2');
      s += inCard(c, Ch.icon({ svg: poly([[25, -120], [-55, 12], [-8, 12], [-30, 120], [58, -30], [8, -30], [55, -120]], K.YELLOW), w: 130, h: 240 }, 0, 0, 240),
        285, 8, k - at(L[1], 0.6), 'prop', 'bolt');

      // ② 第18名 + 誰的?
      if (k >= F[2]) {
        c = POS[1];
        s += cardBody(pal, c, k - F[2]);
        const big = Ch.plate('第18名', 130, { fill: K.YELLOW });
        s += inCard(c, big.svg, 0, -38, k - F[2], 'tag', 'rank', true);
        const who = Ch.plate('誰的?', 64, { fill: pal.main, ink: pal.onMain });
        s += inCard(c, who.svg, 175, 100, k - at(L[2], 0.5), 'tag', 'whose', true);
      }
      // ③ 小海龜與亮著的燈
      if (k >= F[3]) {
        c = POS[2];
        s += cardBody(pal, c, k - F[3]);
        s += propIn(pal, c, 'hatchling', { ang: 20 }, -175, 14, 240, k - F[3], 0, 'hatch');
        s += propIn(pal, c, 'bulb', { rays: true }, 190, 14, 250, k - at(L[3], 0.4), 0, 'bulb');
      }
      // ④ 吸管與塑膠袋加向下箭頭
      if (k >= F[4]) {
        c = POS[3];
        s += cardBody(pal, c, k - F[4]);
        s += propIn(pal, c, 'straw', {}, -255, 6, 250, k - F[4], 0, 'straw');
        s += propIn(pal, c, 'bag', {}, -35, 6, 240, k - at(L[4], 0.2), 0, 'bag');
        s += inCard(c, Ch.icon({ svg: poly([[-30, -120], [30, -120], [30, 10], [70, 10], [0, 120], [-70, 10], [-30, 10]], RED), w: 140, h: 240 }, 0, 0, 240),
          255, 6, k - at(L[4], 0.5), 'arrow', 'down');
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_recap', dur: 17.4, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
