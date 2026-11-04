/* 模板 thumb(F4-1):ChannelC自製封面,靜態單格 1920x1080,規格 channel\發片資料_規則.md §4.1。只有橫式;t 與 lines 都不用。
 * data: {lines:[主,副,補](合計 ≤13 字), hi?:行索引 0–2(黃底色帶 + 墨字,預設 2), expr:鴿子表情名, prop?:{lib,name,params?}, side?:'left'|'right'(鴿子所在側,預設 left), hue?}
 * 物件只有三個:襯底圓、認真鴿(朝向字那一側)、prop(選填,抱在鴿子前);另一側 40% 留給三行字。
 * 字:主黃(hi 行改黃底墨字)、副紙白、補紙白;墨色描邊 12px + 右下陰影;底色 H 160–250 時紙白行改暖橘。
 * 版面幾何檢查(安全區、右下角淨空、字與鴿子/prop 重疊、鴿子佔高)在 make_thumb.py 用算圖後的外框量;這裡的 check 只擋資料錯誤與放不下。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const C = (Wn.Tpl && Wn.Tpl.common) || require('./tpl_common.js'), K = C.K, Ch = C.Ch;
  // 版面常數【判】(依 §4.1):字級目標(主 236 = 畫面高 22%;副 55%;補 46%)、字級下限(縮成 320 寬後 33/18/15px)、
  // 描邊 12px 加右下陰影 (8,9)、字區 40% 寬、行距、安全區四邊 5%、右下角 15% 淨空
  const LAYOUT = {
    fsTarget: [236, 130, 108], fsFloor: [200, 110, 90], maxChars: 13,
    stroke: 12, shadow: [8, 9], gap: 30, bandPadX: 0.8, bandH: 1.45, lineH: 1.15,
    zone: { right: [952, 1812], left: [108, 968] },
    safe: [96, 54, 1824, 1026], clear: [1632, 918, 1920, 1080],
    pigeon: { scale: 3.0, y: 975, xLeft: 500, xRight: 1420, yRight: 905 },   // 鴿子在右時整體上抬 70px,外框底緣 ≤918 才不進右下角淨空
    circle: { r: 440, cy: 590, xLeft: 540, xRight: 1380 },
    prop: { dx: 80, y: 765, yRight: 695, maxW: 420, maxH: 330 },
    warm: '#FF7A3D', warmHue: [160, 250],
  };
  const LY = LAYOUT;
  const len = (s) => [...String(s || '')].length;
  const libOf = (n) => { if (!n) return null; const s = String(n); return Wn[s] || Wn['Props' + s[0].toUpperCase() + s.slice(1)] || null; };
  const propOf = (p) => { const L = libOf(p && p.lib); return (L && L.LIST && L.LIST[p.name]) || null; };

  // 每行字級:取 ≤ 目標且寬度放得進字區的最大值(步進 2);主行縮小時副、補的目標跟著按比例縮
  function sizes(d) {
    const Ls = d.lines || [], zone = LY.zone[d.side === 'right' ? 'left' : 'right'], zw = zone[1] - zone[0], hi = d.hi == null ? 2 : d.hi;
    const wOf = (i, fs) => Ch.tw(Ls[i], fs) + (i === hi ? fs * LY.bandPadX + 24 : 2 * LY.stroke + LY.shadow[0]);
    const fit = (i, t) => { let fs = t; while (fs > 40 && wOf(i, fs) > zw) fs -= 2; return fs; };
    const main = fit(0, LY.fsTarget[0]), k = main / LY.fsTarget[0];
    return [main, fit(1, Math.round(LY.fsTarget[1] * k)), fit(2, Math.round(LY.fsTarget[2] * k))];
  }

  function render(t, params) {
    const d = params.data || {}, hue = d.hue != null ? d.hue : params.hue, pal = K.palette(hue), hi = d.hi == null ? 2 : d.hi;
    const right = d.side === 'right', zone = LY.zone[right ? 'left' : 'right'], cx = (zone[0] + zone[1]) / 2, fs = sizes(d);
    const cool = hue >= LY.warmHue[0] && hue <= LY.warmHue[1];
    const FILL = [K.YELLOW, cool ? LY.warm : K.PAPER, cool ? LY.warm : K.PAPER];
    const hs = fs.map((f, i) => f * (i === hi ? LY.bandH : LY.lineH)), H = hs[0] + hs[1] + hs[2] + 2 * LY.gap;
    let y = 540 - H / 2, s = `<circle cx="${right ? LY.circle.xRight : LY.circle.xLeft}" cy="${LY.circle.cy}" r="${LY.circle.r}" fill="${pal.pad}"/>`;
    // 鴿子朝向字區;prop 抱在鴿子前方偏字區側
    const px = right ? LY.pigeon.xRight : LY.pigeon.xLeft, dir = right ? -1 : 1;
    s += K.pigeon(K.expr({ flip: right ? 0 : 1, wing: -40, wlen: 1.2 }, d.expr), { x: px, y: right ? LY.pigeon.yRight : LY.pigeon.y, scale: LY.pigeon.scale, id: 'p' });
    const it = d.prop && propOf(d.prop);
    if (it) {
      const sc = Math.min(LY.prop.maxW / it.w, LY.prop.maxH / it.h);
      s += K.paper(it.fn(pal, d.prop.params || {}), { x: px + dir * LY.prop.dx, y: right ? LY.prop.yRight : LY.prop.y, rot: -6, scale: sc, k: 'prop', id: 'prop', wide: it.wide });
    }
    // 三行字
    (d.lines || []).forEach((txt, i) => {
      const cy = y + hs[i] / 2, f = fs[i];
      y += hs[i] + LY.gap;
      if (i === hi) {
        const bw = Ch.tw(txt, f) + f * LY.bandPadX, bh = hs[i];
        s += K.paper(`<rect x="${-bw / 2}" y="${-bh / 2}" width="${bw}" height="${bh}" fill="${K.YELLOW}" stroke="${K.INK}" stroke-width="${LY.stroke}" stroke-linejoin="miter"/>` +
          `<text x="0" y="0" font-family="GenSen" font-size="${f}" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">${txt}</text>`,
          { x: cx, y: cy, rot: -2, scale: 1, k: 'plate', id: 'tl' + i, wide: true });
        return;
      }
      const tx = (dx, dy, fl) => `<text x="${cx + dx}" y="${cy + dy}" font-family="GenSen" font-size="${f}" text-anchor="middle" dominant-baseline="central"` +
        ` fill="${fl}" stroke="${K.INK}" stroke-width="${LY.stroke * 2}" stroke-linejoin="round" paint-order="stroke">${txt}</text>`;
      s += `<g data-k="thumbtext" data-id="tl${i}" data-u="1">${tx(LY.shadow[0], LY.shadow[1], K.INK)}${tx(0, 0, FILL[i])}</g>`;
    });
    return K.wrap(pal, s);
  }

  function check(params) {
    const d = params.data || {}, e = [];
    if (K.portrait) return ['thumb 只有橫式'];
    const Ls = d.lines;
    if (!Array.isArray(Ls) || Ls.length !== 3 || Ls.some((x) => !len(x))) return ['lines 必須是三行非空字串'];
    const n = Ls.reduce((a, x) => a + len(x), 0);
    if (n > LY.maxChars) e.push(`三行合計 ${n} 字,上限 ${LY.maxChars}`);
    if (d.hi != null && [0, 1, 2].indexOf(d.hi) < 0) e.push(`hi「${d.hi}」只能是 0、1、2`);
    if (d.side != null && ['left', 'right'].indexOf(d.side) < 0) e.push(`side「${d.side}」只能是 left 或 right`);
    if (!d.expr || !K.P.EXPR[d.expr]) e.push(`expr「${d.expr}」不在表情組:${Object.keys(K.P.EXPR).join('、')}`);
    if (d.prop) {
      if (!libOf(d.prop.lib)) e.push(`prop.lib「${d.prop.lib}」不存在`);
      else if (!propOf(d.prop)) e.push(`prop.name「${d.prop.name}」不在 ${d.prop.lib}.LIST`);
    }
    if (e.length) return e;
    if (len(Ls[0]) < 2 || len(Ls[0]) > 4) e.push(`警告:主文字 ${len(Ls[0])} 字(§4.1 建議 2–4 字)`);
    if (Ls.some((x) => /[?？]/.test(x))) e.push('警告:含問號(§4.1 優先不用問號)');
    sizes(d).forEach((f, i) => { if (f < LY.fsFloor[i]) e.push(`第 ${i + 1} 行「${Ls[i]}」放進字區後字級只剩 ${f}px,低於下限 ${LY.fsFloor[i]}px,請縮短字`); });
    return e;
  }

  const API = { LAYOUT, sizes, render, check };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') (window.Tpl = window.Tpl || {}).thumb = API;
})();
