/* turtle 場景 §10 t_power(句 33–36,18.2 秒)燒垃圾發電。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句33:爐口火焰,牙刷滑進爐口(被爐身蓋住),煙囪頂端閃電逐格升出。
 * 句34:大數字「34 億度」加來源「環境部」;一排房子出現後逐棟亮燈;「約 83 萬戶 用一年」。
 * 句35:牙刷→小閃電→電風扇,葉片逐格轉半圈後停住。
 * 句36:待查清單三列,第二列「都送去燒?」打勾,加註「牙刷:大部分是」;鴿子點頭。
 * 字牌用 Charts(px 紙片);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 300, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.08, end: 1.76 }, { start: 1.89, end: 8.76 }, { start: 8.88, end: 14.07 }, { start: 14.2, end: 18.11 }];
  const BURNER = { x: 1350, y: 370, s: 2.3 };      // 句33 焚化爐(icon 縮放 2.3,底邊 y=830)
  const HOUSES = 6;

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  function pigeonPose(k, reacts, expr) {
    for (const r of reacts) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (k >= r.k0 && k < r.k0 + n) return K.expr(K.clip(r.clip, k - r.k0), r.expr || expr);
    }
    return K.expr(K.clip('idle', k), expr);
  }

  // 火焰(兩個樣子逐格交替),中心在原點
  function flameSvg(v, sc) {
    const a = v ? [[0, -72], [28, -28], [42, 12], [34, 46], [10, 66], [-10, 66], [-34, 46], [-42, 12], [-24, -22], [-12, -50]]
      : [[-6, -66], [20, -34], [40, 8], [36, 46], [12, 66], [-12, 66], [-34, 46], [-40, 12], [-18, -26], [-24, -44]];
    const pts = (m) => a.map((p) => `${(p[0] * m * sc).toFixed(1)},${((p[1] * m + (m < 1 ? 14 : 0)) * sc).toFixed(1)}`).join(' ');
    return `<polygon points="${pts(1)}" fill="hsl(14 90% 55%)"/><polygon points="${pts(0.55)}" fill="${K.YELLOW}" stroke="none"/>`;
  }
  // 閃電(黃,中心在原點)
  const bolt = (sc) => `<g transform="scale(${sc})"><polygon points="-20,-92 32,-92 8,-22 44,-22 -30,96 -6,10 -42,10" fill="#FFD23F"/></g>`;
  // 向右的粗箭頭(主色)
  // (長 200、桿粗 30、箭頭寬 90)
  const arrowSvg = (col) => `<polygon points="-100,-15 40,-15 40,-45 100,0 40,45 40,15 -100,15" fill="${col}"/>`;

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const icn = (name, opts, x, y, box, o) => Ch.sheet(Ch.icon({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h }, 0, 0, box, o && o.dim),
      Object.assign({ x, y, u: U, kind: 'prop', id: name, wide: PT.LIST[name].wide }, o));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    const reacts = [{ k0: F[3] + 14, clip: 'nod' }];
    s += K.pigeon(Object.assign({}, pigeonPose(k, reacts, ph >= 2 ? 'smug' : 'look'), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (ph === 0) {                                // 句33:爐口火焰、牙刷進去、閃電出來
      const q = k - F[0];
      // 牙刷從第 0 格就在爐左(畫在爐身之前,滑進爐身後被蓋住);第 4 格起每格右移 100px,到第 7 格停,第 9 格消失
      s += icn('truck', {}, 720, 580, 340, { id: 'truck' });                // 送垃圾來的垃圾車(靜止,墊在左側)
      if (q < 9) s += icn('toothbrush', {}, 775 + clamp(q - 4, 0, 3) * 100, 770, 560, { id: 'brush' });   // 第 9 格起進了爐子,不再畫
      s += icn('incinerator', { tall: 0.35, restaurant: false }, BURNER.x, BURNER.y, PT.LIST.incinerator.h * BURNER.s, {});
      s += Ch.sheet(flameSvg(q % 2, 1.3), { x: 1120, y: 722, u: U, k: q, kind: 'flame', id: 'flame' });
      if (q >= 11) {                               // 閃電在煙囪右側逐格升起
        const y = [420, 420, 360, 360, 300][Math.min(4, q - 11)];
        s += Ch.sheet(bolt(1.2), { x: 1700, y, rot: 8, u: U, k: q - 11, kind: 'bolt', id: 'bolt' });
      }
    } else if (ph === 1) {                         // 句34:34 億度、一排房子逐棟亮燈
      const q = k - F[1];
      s += Ch.sheet(bolt(1.9), { x: 620, y: 340, rot: 8, u: U, kind: 'bolt', id: 'bolt' });
      s += Ch.bigNum({ pal, u: U, x: 1250, y: 262, num: '34', unit: '億度', fs: 260, id: 'num' });
      s += Ch.srcTag('環境部', { pal, u: U, x: 1830, y: 470, anchor: 'right', k: q - 4, id: 'src' });
      const items = [];
      for (let i = 0; i < HOUSES; i++) {
        items.push({ icon: { svg: PT.LIST.house.fn(pal, { lit: q >= 44 + 3 * i }), w: PT.LIST.house.w, h: PT.LIST.house.h }, k: q - 30 - 2 * i });
      }
      s += Ch.iconRow({ pal, u: U, x: 1260, y: 600, pitch: 190, size: 170, items, id: 'house' });
      const p = Ch.plate('約 83 萬戶 用一年', 64, { fill: K.YELLOW });
      s += Ch.sheet(p.svg, { x: 1240, y: 765, rot: -1.5, u: U, k: q - 46, kind: 'note', id: 'households', wide: true });
    } else if (ph === 2) {                         // 句35:牙刷→小閃電→電風扇(斜向下三站;後兩站先暗後亮)
      const q = k - F[2];
      const arr = (x, y, a) => Ch.sheet(arrowSvg(pal.main), { x, y, rot: 35, u: U, k: q - a, kind: 'arrow', id: 'a' + a });
      s += icn('toothbrush', {}, 800, 250, 560, { id: 'brush' });
      s += arr(1170, 335, 8);
      s += Ch.sheet(Ch.icon({ svg: bolt(1), w: 86, h: 188 }, 0, 0, 225, q < 8), { x: 1340, y: 450, rot: 8, u: U, kind: 'bolt', id: 'bolt' });
      s += arr(1500, 560, 20);
      s += icn('fan', { ang: clamp(q - 28, 0, 6) * 30 }, 1710, 640, 330, { dim: q < 20, id: 'fan' });
    } else {                                       // 句36:待查清單
      const q = k - F[3];
      s += Ch.checklist({ pal, u: U, x: 700, y: 200, w: 1130, rowH: 140, gap: 30, fs: 72, id: 'cl', items: [
        { label: '付錢就安全?', state: 'empty' }, { label: '都送去燒?', state: 'check', kState: q - 14 }, { label: '為了省錢?', state: 'empty' }] });
      const p = Ch.plate('牙刷:大部分是', 64, { fill: K.YELLOW });
      s += Ch.sheet(p.svg, { x: 1555, y: 440, rot: -2, u: U, k: q - 18, kind: 'note', id: 'mostly', wide: true });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_power', dur: 18.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
