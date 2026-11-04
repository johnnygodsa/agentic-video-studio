/* turtle 場景 §9 t_tower(句 29–32,17.5 秒)無用知識:煙囪旋轉餐廳。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句29:右上「?」記號彈入;焚化爐(煙囪矮)在畫面下方。
 * 句30:煙囪逐格長高(滿高約畫面 60%),左側高度尺標「120 公尺」,頂端圓盤餐廳出現並逐格旋轉,日曆牌「2000 年元旦」。
 * 句31:獎牌「全世界第一間」加來源「臺北市環保局」(餐廳持續旋轉)。
 * 句32:換成頒獎台,只有焚化爐站第一名,第二、三名灰色空著;鴿子聳肩;段落結尾「?」記號彈出。
 * 字牌用 Charts(px 紙片);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 300, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.07, end: 2.68 }, { start: 2.8, end: 8.51 }, { start: 8.62, end: 13.37 }, { start: 13.49, end: 17.46 }];
  const TOWER = { x: 900, y: 500, s: 1.65 };       // 焚化爐:icon 縮放 1.65(煙囪高 392 單位 ≈ 647px = 60%),底邊 y=830
  const GROW = 24, REST_AT = 30, ROT_EVERY = 3;    // 句30:長高格數、餐廳出現格、每幾格轉一格
  const RULER_X = 620, TALL0 = 0.18;               // 尺標中心 x;句29 煙囪起始高度比例

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  function pigeonPose(k, reacts, expr) {
    for (const r of reacts) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (k >= r.k0 && k < r.k0 + n) return K.expr(K.clip(r.clip, k - r.k0), r.expr || expr);
    }
    return K.expr(K.clip('idle', k), expr);
  }

  // 高度尺標(px 紙片,中心 RULER_X,y 170–830):直尺、上下刻度、向煙囪頂端的虛線
  function rulerSvg() {
    let c = `<rect x="-8" y="-330" width="16" height="660" fill="${K.INK}" stroke="none"/>` +
      `<rect x="-35" y="-330" width="70" height="12" fill="${K.INK}" stroke="none"/><rect x="-35" y="318" width="70" height="12" fill="${K.INK}" stroke="none"/>`;
    for (let i = 0; i < 9; i++) c += `<rect x="${44 + i * 44}" y="-327" width="26" height="8" fill="${K.INK}" stroke="none"/>`;
    return c;
  }

  // 獎牌(黃圓加兩條紅絲帶,圓內「第一」),中心在原點
  function medalSvg() {
    const rib = (d) => `<polygon points="${[[-70, 40], [-15, 40], [-5, 175], [-42, 148], [-75, 178]].map((p) => `${d * p[0]},${p[1]}`).join(' ')}" fill="hsl(6 75% 55%)"/>`;
    return rib(1) + rib(-1) + `<circle cx="0" cy="0" r="115" fill="${K.YELLOW}"/><circle cx="0" cy="0" r="90" fill="none" stroke="${K.INK}" stroke-width="7"/>` +
      `<text x="0" y="0" font-family="GenSen" font-size="110" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">第一</text>`;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kEnd = Math.round(((params && params.dur) || 17.5) * K.FPS);
    const grey = `hsl(${pal.h} 8% 82%)`;
    const icn = (name, opts, x, y, box, o) => Ch.sheet(Ch.icon({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h }, 0, 0, box),
      Object.assign({ x, y, u: U, kind: 'prop', id: name, wide: PT.LIST[name].wide }, o));
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : 3;

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    const reacts = [{ k0: F[0] + 2, clip: 'tilt', expr: 'think' }, { k0: F[3] + 22, clip: 'shrug' }];
    s += K.pigeon(Object.assign({}, pigeonPose(k, reacts, 'look'), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // 無用知識「?」:句29 彈入,段落結尾退場
    s += Ch.triviaMark({ u: U, k: k - F[0], kOut: k - (kEnd - 4) });

    const box = PT.LIST.incinerator.h * TOWER.s;
    if (ph <= 2) {
      const q = k - F[1];
      const tall = ph === 0 ? TALL0 : TALL0 + (1 - TALL0) * Math.min(1, q / GROW);
      const kR = F[1] + REST_AT, restaurant = k >= kR;
      const rot = restaurant ? Math.floor((k - kR) / ROT_EVERY) : 0;
      // 焚化爐與尺標不彈入(整座高約 660px,彈入過衝會壓到字幕帶),焚化爐從第 0 格就在
      s += icn('incinerator', { tall, rot, restaurant }, TOWER.x, TOWER.y, box, {});
      if (ph >= 1 && q >= GROW - 2) {
        s += Ch.sheet(rulerSvg(), { x: RULER_X, y: 500, u: U, kind: 'ruler', id: 'ruler', wide: false });
      }
      if (ph >= 1) {
        const p = Ch.plate('120 公尺', 72);
        s += Ch.sheet(p.svg, { x: RULER_X - 50 - p.w / 2, y: 380, rot: -1.5, u: U, k: q - GROW, kind: 'rulerL', id: 'ruler', wide: true });
      }
      if (ph === 1) {
        s += Ch.dateTag({ pal, u: U, x: 1520, y: 500, top: '2000 年', main: '元旦', size: 260, rot: 2, k: q - 46, id: 'date' });
      } else if (ph === 2) {
        const r = k - F[2];
        s += Ch.sheet(medalSvg(), { x: 1560, y: 420, rot: -3, u: U, k: r, kind: 'medal', id: 'medal' });
        const p = Ch.plate('全世界第一間', 64, { fill: K.YELLOW });
        s += Ch.sheet(p.svg, { x: 1560, y: 671, rot: 1.5, u: U, k: r - 3, kind: 'medalL', id: 'medal', wide: true });
        s += Ch.srcTag('臺北市環保局', { pal, u: U, x: 1830, y: 790, anchor: 'right', k: r - 6, id: 'src' });
      }
    } else {                                       // 句32:頒獎台
      const q = k - F[3], PD = { x: 1280, y: 800, w: 1100, h: 300 }, on = q >= 6;
      // 三階台一開始就在(灰);第 6 格第一名亮黃,焚化爐站上去並出現名牌
      s += Ch.podium(Object.assign({ pal, u: U, fs: 56, id: 'pd', places: [
        { color: on ? K.YELLOW : grey }, { color: grey }, { color: grey }] }, PD));
      const top = Ch.podiumPos(PD)[0], sc = 0.74;
      if (on) {
        s += icn('incinerator', { tall: 1, rot: Math.floor((k - F[1] - REST_AT) / ROT_EVERY) }, top.x, top.top - 200 * sc, PT.LIST.incinerator.h * sc, { k: q - 6, id: 'burnerSmall' });
        const p = Ch.plate('北投焚化廠', 56);
        s += Ch.sheet(p.svg, { x: top.x, y: 142, rot: -1.5, u: U, k: q - 6, kind: 'podiumL', id: 'pd1', wide: true });
      }
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_tower', dur: 17.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
