/* turtle 場景 §22 t_light_a(句 80–84,19.5 秒)揭曉:燈。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句80:回到走廊(同 t_hook 牆面):左側鴿子、中間墨底黃字「?」牌、右側海龜告示、左上牙刷;鴿子約 45% 處歪頭。
 * 句81:「?」牌逐格壓扁、燈泡逐格展開;夜空紙片鋪上(蓋掉告示與牙刷),右側飯店(高約 550)彈入,20 扇窗戶逐格亮起。
 * 句82:硬切到夜晚的沙灘橫切面:左邊海(月亮在上)、中間沙灘、右邊是沙灘後方的陸地;沙堆逐個鼓起,小海龜(6 隻,各約 125px)逐隻冒出。
 * 句83:海面出現亮帶(逐格畫出);小海龜先轉向左、再全部朝海逐格爬。
 * 句84:陸地上的小房子一棟棟彈入並亮燈(品牌黃光暈);每亮一棟,海面亮帶就更暗一階。
 * 時序:每個事件在該句 start 之後依句長比例出現;同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 330, y: 800 };                  // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.075, end: 3.935 }, { start: 4.055, end: 6.745 }, { start: 6.865, end: 10.465 }, { start: 10.585, end: 16.43 }, { start: 16.55, end: 19.41 }];
  const NOTICE = { x: 1570, y: 450, w: 520, h: 660 };
  const BRUSH = { x: 440, y: 250, u: 2.5 };
  const Q = { x: 960, y: 470, size: 260, u: 2 };    // 「?」牌位置(同 t_hook)
  const BULB = { x: 960, y: 497, s: 2.3 };          // 燈泡中心(內容中心 y ≈ 497 - 13.5 * s 的上方,與「?」牌同位置)
  const HOTEL = { x: 1540, y: 430, box: 560 };
  const NIGHT = 'hsl(170 45% 14%)';
  // 沙灘橫切面
  const NT = 6, TSIZE = 136, SHIFT = 200, ROW_Y = [660, 752];
  const SHORE = 600;                                // 海岸 x(小海龜爬到這附近)
  const HOUSES = [{ x: 1420, y: 530 }, { x: 1590, y: 524 }, { x: 1752, y: 532 }], HBOX = 168;
  const BAND = ['hsl(50 85% 80%)', 'hsl(50 55% 62%)', 'hsl(190 40% 46%)', 'hsl(205 55% 36%)'];   // 亮帶四階:愈亮愈多房子前
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const iconSheet = (pal, n, o, x, y, box, p) => Ch.sheet(Ch.icon(ic(pal, n, o), 0, 0, box), Object.assign({ x, y, u: U, kind: 'prop', id: n, wide: PT.LIST[n].wide }, p));
  const absSheet = (content, cx, cy, o) => Ch.sheet(`<g transform="translate(${f(-cx)} ${f(-cy)})">${content}</g>`, Object.assign({ x: cx, y: cy, u: U }, o));
  const poly = (pts, fill) => `<polygon points="${pts.map((p) => f(p[0]) + ',' + f(p[1])).join(' ')}" fill="${fill}"/>`;
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const txt = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  // ---------- 走廊(句80–81) ----------
  function noticeSheet(pal) {
    const w = NOTICE.w, h = NOTICE.h;
    const c = `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="80" fill="${pal.main}" stroke="none"/>` +
      `<circle cx="0" cy="${-h / 2 + 40}" r="18" fill="${PT.C.red}"/>` +
      Ch.icon(ic(pal, 'turtle', {}), 0, -70, 420) + txt('一次性備品', 0, 160, 76, K.INK) + txt('會傷害海龜', 0, 250, 76, K.INK);
    return Ch.sheet(c, { x: NOTICE.x, y: NOTICE.y, u: U, kind: 'notice', id: 'notice' });
  }
  function brush(pal) {
    const e = PT.LIST.toothbrush;
    return K.paper(e.fn(pal, {}), { x: BRUSH.x, y: BRUSH.y, rot: -8, scale: BRUSH.u, k: 'prop', id: 'brush', wide: e.wide });
  }
  function hallSky(k) {
    let c = '<rect x="-868" y="-334" width="1736" height="668" fill="' + NIGHT + '" stroke-linejoin="miter"/>';
    for (let i = 0; i < 46; i++) {
      const x = -840 + K.hash(i * 3.1 + 1) * 1680, y = -320 + K.hash(i * 7.7 + 2) * 640, r = 2.5 + K.hash(i * 5.3 + 3) * 4;
      c += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return Ch.sheet(c, { x: 960, y: 426, u: U, k, kind: 'sky', id: 'sky' });
  }
  // 窗戶亮起順序:固定洗牌(hash)
  const WIN_ORDER = Array.from({ length: 20 }, (_, i) => i).sort((a, b) => K.hash(a * 2.3 + 9) - K.hash(b * 2.3 + 9));
  const winLit = (n) => { const v = new Array(20).fill(0); for (let i = 0; i < n; i++) v[WIN_ORDER[i]] = 1; return v; };

  function pigeonPose(k, F, kTilt, kShock) {
    let p;
    if (k < kTilt) p = K.clip('idle', k);
    else if (k < kTilt + 6) p = K.expr(K.clip('tilt', k - kTilt), 'doubt');
    else if (k < kShock) p = K.expr(K.clip('idle', k), 'doubt');
    else if (k < kShock + 8) p = K.clip('shock', k - kShock);
    else p = K.expr(K.clip('idle', k), 'surprised');
    return Object.assign({}, p, { flip: 1 });
  }

  function hall(pal, k, F, L) {
    const kFlip = F[1] + 1, j = k - kFlip;                         // 翻面起算格
    const kSky = kFlip + 8, kHotel = kSky + 3;
    const kTilt = F[0] + Math.max(10, at(L[0], 0.45) - F[0]);
    const kw0 = kHotel + 2, kw1 = Math.max(kw0 + 8, at(L[1], 0.93));
    let s = `<rect x="0" y="800" width="1920" height="280" fill="${pal.pad}"/><rect x="0" y="790" width="1920" height="12" fill="hsl(${pal.h} 45% 62%)"/>`;
    if (k < kSky + 4) { s += noticeSheet(pal) + brush(pal); }
    if (k >= kSky) s += hallSky(k - kSky);
    if (k >= kHotel) {
      const nl = k < kw0 ? 0 : Math.min(20, Math.ceil((k - kw0 + 1) * 20 / (kw1 - kw0 + 1)));
      s += iconSheet(pal, 'hotel', { lit: winLit(nl) }, HOTEL.x, HOTEL.y, HOTEL.box, { id: 'hotel', k: k - kHotel });
    }
    // 「?」牌 → 燈泡(逐格壓扁再展開)
    const SQ = [0.62, 0.3, 0.1], EX = [0.15, 0.5, 0.9, 1.1];
    if (j < 3) {
      const sx = j < 0 ? 1 : SQ[j];
      s += K.tile('?', { x: Q.x, y: Q.y, size: Q.size, rot: -3, u: Q.u, fill: K.INK, ink: K.YELLOW, sx, sy: 1, id: 'q' });
    } else {
      const sx = j - 3 < EX.length ? EX[j - 3] : 1;
      s += K.paper(`<g stroke-width="${f(5 / BULB.s)}">${PT.LIST.bulb.fn(pal, { on: true, rays: true })}</g>`,
        { x: BULB.x, y: BULB.y, scale: BULB.s, sx, sy: 1, k: 'prop', id: 'bulb', enter: j - 3 < 2 });
    }
    s += K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(pigeonPose(k, F, kTilt, kFlip), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });
    return s;
  }

  // ---------- 夜晚沙灘橫切面(句82–84) ----------
  function sky() {
    let c = R(-875, -375, 1750, 750, NIGHT).replace('stroke="none"', 'stroke-linejoin="miter"');
    for (let i = 0; i < 44; i++) {
      c += `<circle cx="${f(-850 + K.hash(i * 3.1 + 1) * 1700)}" cy="${f(-360 + K.hash(i * 7.7 + 2) * 500)}" r="${f(2.5 + K.hash(i * 5.3 + 3) * 4)}"` +
        ` fill="${i % 3 ? K.PAPER : K.YELLOW}" stroke="none"/>`;
    }
    return Ch.sheet(c, { x: 960, y: 460, u: U, kind: 'sky', id: 'sky' });
  }
  // 海:bandRows = 亮帶畫出幾列(0–7),bandCol = 亮帶顏色
  function sea(bandRows, bandCol) {
    const top = [[85, 590], [140, 570], [200, 590], [260, 570], [320, 590], [380, 570], [440, 590], [500, 570], [560, 595]];
    const pts = top.concat([[610, 625], [590, 690], [612, 760], [585, 835], [85, 835]]);
    let c = poly(pts, 'hsl(205 55% 30%)');
    [[150, 640], [450, 650], [170, 790], [470, 770]].forEach((p) => { c += R(p[0] - 50, p[1] - 6, 100, 12, 'hsl(205 55% 40%)'); });
    for (let i = 0; i < bandRows; i++) c += R(300 - (80 + 22 * i) / 2, 610 + i * 33, 80 + 22 * i, 17, bandCol);
    return absSheet(c, 348, 702, { kind: 'sea', id: 'sea' });
  }
  function sand() {
    const pts = [[560, 608], [800, 598], [1300, 602], [1335, 835], [585, 835], [600, 760], [585, 690]];
    let c = poly(pts, 'hsl(38 42% 50%)');
    [[860, 820], [1180, 822], [1000, 618]].forEach((p) => { c += R(p[0] - 50, p[1] - 5, 100, 10, 'hsl(38 42% 42%)'); });
    return absSheet(c, 960, 716, { kind: 'sand', id: 'sand', wide: true });
  }
  function land() {
    let c = poly([[1300, 602], [1835, 598], [1835, 835], [1335, 835]], 'hsl(130 22% 26%)') + R(1300, 598, 535, 18, 'hsl(130 28% 38%)');
    [[1420, 700], [1600, 760], [1750, 690], [1500, 810]].forEach((p) => { c += R(p[0] - 45, p[1] - 6, 90, 12, 'hsl(130 22% 20%)'); });
    return absSheet(c, 1580, 716, { kind: 'land', id: 'land', wide: true });
  }
  const tBase = (i) => ({ x: 780 + 96 * i + (K.hash(i * 3 + 1) - 0.5) * 20, y: ROW_Y[i % 2] + (K.hash(i * 3 + 2) - 0.5) * 10 });
  const hatch = (pal, x, y, ang, kk) => Ch.sheet(Ch.icon(ic(pal, 'hatchling', { ang }), 0, 0, TSIZE), { x, y, u: U, kind: 'prop', id: 'hatch', k: kk });

  function beach(pal, k, F, L) {
    const N82 = K.frame(L[2].end) - F[2], N83 = K.frame(L[3].end) - F[3];
    const kBand = F[3];
    const kHouse = HOUSES.map((_, i) => at(L[4], 0.06 + 0.32 * i));
    const lit = kHouse.filter((h) => k >= h + 2).length;
    const kCrawl = F[3] + 5, T = N83 - 9;
    const bandRows = k < kBand ? 0 : Math.min(7, 2 * (k - kBand) + 2);

    let s = sky() + sea(bandRows, BAND[lit]) + sand() + land();
    s += iconSheet(pal, 'moon', {}, 300, 215, 200, { id: 'moon' });
    // 沙堆與洞
    for (let i = 0; i < NT; i++) {
      const b = tBase(i), kE = F[2] + 2 + Math.floor(i * (N82 * 0.75) / NT), j = k - (kE - 3);
      if (j < 0) continue;
      if (j < 3) s += `<ellipse cx="${f(b.x)}" cy="${f(b.y + 34)}" rx="${[44, 56, 64][j]}" ry="${[10, 20, 28][j]}" fill="hsl(38 42% 58%)"/>`;
      else s += `<ellipse cx="${f(b.x)}" cy="${f(b.y + 34)}" rx="56" ry="15" fill="hsl(38 40% 34%)"/>`;
    }
    // 小海龜
    const TURN = [-35, -70, -90];
    for (let i = 0; i < NT; i++) {
      const b = tBase(i), kE = F[2] + 2 + Math.floor(i * (N82 * 0.75) / NT);
      if (k < kE) continue;
      const prog = Math.max(0, Math.min(1, (k - kCrawl) / T)), moving = prog > 0 && prog < 1;
      const kt = k - (F[3] + 1 + (i % 3));
      let ang = kt < 0 ? 0 : TURN[Math.min(kt, 2)];
      if (moving) ang += ((k + i) % 2) ? 7 : -7;
      s += hatch(pal, b.x - SHIFT * prog, b.y, ang, k - kE);
    }
    // 光暈(全部在房子之下)與房子
    HOUSES.forEach((h, i) => {
      const kh = k - kHouse[i];
      if (kh < 2) return;
      const hp = K.pop(kh - 2);
      s += `<g opacity=".38"><circle cx="${h.x}" cy="${h.y - 6}" r="${f(150 * hp)}" fill="${K.YELLOW}"/></g>` +
        `<g opacity=".55"><circle cx="${h.x}" cy="${h.y - 6}" r="${f(95 * hp)}" fill="${K.YELLOW}"/></g>`;
    });
    HOUSES.forEach((h, i) => {
      const kh = k - kHouse[i];
      if (kh < 0) return;
      s += Ch.sheet(Ch.icon(ic(pal, 'house', { lit: kh >= 2 }), 0, 0, HBOX), { x: h.x, y: h.y, u: U, kind: 'prop', id: 'house' + i, k: kh });
    });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    return K.wrap(pal, k < F[2] ? hall(pal, k, F, L) : beach(pal, k, F, L));
  }

  const Scene = { name: 't_light_a', dur: 19.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
