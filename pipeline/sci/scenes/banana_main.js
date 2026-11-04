/* 香蕉樣片 場景二:答案 6.5 秒(固定鏡頭,2 句)。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句5:莖、往下箭頭彈入,小香蕉從莖往下垂著逐格變長(鴿子小一點站左下,高約 30%)。
 * 句6:句首停止變長;約 30% 處尾端 6 格往上彎成彎香蕉;約 50% 處太陽彈入、箭頭換成往上彎;60% 前完成,之後只留鴿子 nod 一次。
 * 同時在動的非文字元素 ≤ 2 組(鴿子 + 香蕉長/彎、或太陽 + 箭頭彈入)。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 400, y: 800 };                 // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0, end: 1.98 }, { start: 2.10, end: 5.46 }];
  const STEM = { x: 900, y: 250, w: 540, h: 54 };  // 橫的莖
  const B0 = { x: 900, y: 282 };                   // 香蕉起點(蒂頭藏在莖後)
  const LEN = 480, WMAX = 84, TURN = -150, BEND_POW = 1.4;
  const G0 = 0.12, K_GROW = 3, K_GROW_END = 19;    // 長度比例:第 3 格起逐格變長,第 19 格(1.9 秒)長滿
  const BEND = [0.15, 0.35, 0.6, 0.82, 0.95, 1];   // 彎曲參數逐格(6 格)
  const ARROW = { x: 1460, y: 540 }, ARROW_LABEL = { x: 1460, y: 730 };
  const SUN = { x: 1600, y: 265 };
  const f = (x) => +(+x).toFixed(2);
  const RAD = Math.PI / 180;

  // ---------- 香蕉(參數式:中心線 + 墨色寬線疊主色窄線) ----------
  // 中心線:heading(s) = h0 + turn * s^pow(度,y 向下);回傳 n+1 個點(px)
  function spine(o) {
    const n = o.n || 24, pts = [[0, 0]];
    let x = 0, y = 0;
    for (let i = 0; i < n; i++) {
      const s = (i + 0.5) / n, h = (o.h0 + o.turn * Math.pow(s, o.pow || 1)) * RAD;
      x += Math.cos(h) * o.len / n; y += Math.sin(h) * o.len / n; pts.push([x, y]);
    }
    return pts;
  }
  const girth = (s) => 0.38 + 0.62 * Math.pow(Math.sin(Math.PI * s), 0.7);      // 兩端細、中段粗
  function sides(pts, ws) {                        // 沿中心線兩側偏移
    const L = [], R = [];
    pts.forEach((p, i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      const tx = b[0] - a[0], ty = b[1] - a[1], d = Math.hypot(tx, ty) || 1, nx = -ty / d, ny = tx / d;
      L.push([p[0] + nx * ws[i] / 2, p[1] + ny * ws[i] / 2]); R.push([p[0] - nx * ws[i] / 2, p[1] - ny * ws[i] / 2]);
    });
    return { L, R };
  }
  // 香蕉紙片內容(單位 = px / u)。o: {len,h0,turn,pow,wmax,wscale,u,pal,anchor:'center'|'start',stem}
  function banana(o) {
    const u = o.u, pts = spine(o), n = pts.length - 1, stem = o.stem == null ? 36 : o.stem;
    const ws = pts.map((_, i) => o.wmax * (o.wscale == null ? 1 : o.wscale) * girth(i / n));
    const h0 = o.h0 * RAD, se = [pts[0][0] - Math.cos(h0) * stem, pts[0][1] - Math.sin(h0) * stem];
    const all = pts.concat([se]);
    const x0 = Math.min(...all.map((p) => p[0])), x1 = Math.max(...all.map((p) => p[0]));
    const y0 = Math.min(...all.map((p) => p[1])), y1 = Math.max(...all.map((p) => p[1]));
    const off = o.anchor === 'start' ? pts[0] : [(x0 + x1) / 2, (y0 + y1) / 2];
    const q = (p) => [(p[0] - off[0]) / u, (p[1] - off[1]) / u];
    const m = ws.reduce((a, b) => Math.max(a, b), 0) / 2 + 16;
    const [bx0, by0] = q([x0 - m, y0 - m]), [bx1, by1] = q([x1 + m, y1 + m]);
    // 不可見外框:確保濾鏡範圍(直的中心線外框寬或高為 0)並供舞台量外框
    let s = `<rect x="${f(bx0)}" y="${f(by0)}" width="${f(bx1 - bx0)}" height="${f(by1 - by0)}" fill="none" stroke="none"/>`;
    const brown = `hsl(${o.pal.h} 45% 22%)`;
    const line = (a, b, w, col) => {
      const A = q(a), B = q(b);
      return `<line x1="${f(A[0])}" y1="${f(A[1])}" x2="${f(B[0])}" y2="${f(B[1])}" stroke="${col}" stroke-width="${f(w / u)}" stroke-linecap="round" fill="none"/>`;
    };
    s += line(se, pts[0], 30 + 28, K.PAPER) + line(se, pts[0], 30 + 20, K.INK) + line(se, pts[0], 30, brown);
    let a = '', b = '', c = '';
    for (let i = 0; i < n; i++) {
      const w = (ws[i] + ws[i + 1]) / 2;
      a += line(pts[i], pts[i + 1], w + 28, K.PAPER); b += line(pts[i], pts[i + 1], w + 20, K.INK); c += line(pts[i], pts[i + 1], w, o.pal.main);
    }
    const T = q(pts[n]);
    return s + a + b + c + `<circle cx="${f(T[0])}" cy="${f(T[1])}" r="${f(Math.max(5, o.wmax * (o.wscale == null ? 1 : o.wscale) * 0.2) / u)}" fill="${brown}"/>`;
  }

  // 箭頭多邊形(單位 = px / u):沿中心線 {len,h0,turn} 的粗箭頭,尖端在終點;置中於原點
  function arrow(o) {
    const u = o.u, pts = spine(Object.assign({ n: 20, pow: 1 }, o)), n = pts.length - 1;
    const m = Math.max(1, Math.round(n * o.headL / o.len)), k = n - m;
    const sd = sides(pts.slice(0, k + 1), pts.slice(0, k + 1).map(() => o.shaft));
    const hd = sides([pts[k], pts[n]], [o.headW, o.headW]);
    const poly = sd.L.concat([hd.L[0], pts[n], hd.R[0]], sd.R.slice().reverse());
    const xs = poly.map((p) => p[0]), ys = poly.map((p) => p[1]);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    return `<polygon points="${poly.map((p) => `${f((p[0] - cx) / u)},${f((p[1] - cy) / u)}`).join(' ')}" fill="${o.fill}" stroke-linejoin="round"/>`;
  }

  // 紙牌(紙白底加墨色字,頂端一條主色紙帶):o: {x,y,fs,u,rot,sx,sy,id,enter,pal}
  function card(str, o) {
    const u = o.u, fs = o.fs / u, w = str.length * fs + fs * 1.1, h = fs * 1.62;
    const c = `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(fs * 0.22)}" fill="${o.pal.main}" stroke="none"/>` +
      `<text x="0" y="${f(fs * 0.1)}" font-family="GenSen" font-size="${f(fs)}" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">${str}</text>`;
    return K.paper(c, { x: o.x, y: o.y, rot: o.rot, scale: u, sx: o.sx, sy: o.sy, k: 'card', id: o.id, enter: o.enter, wide: true });
  }

  // 太陽:品牌黃圓加 12 條放射紙條(整組同一片紙)
  function sun(u) {
    let s = '';
    for (let i = 0; i < 12; i++) {
      s += `<g transform="rotate(${i * 30})"><rect x="${f(-12 / u)}" y="${f(-170 / u)}" width="${f(24 / u)}" height="${f(52 / u)}" fill="${K.YELLOW}"/></g>`;
    }
    return s + `<circle cx="0" cy="0" r="${f(92 / u)}" fill="${K.YELLOW}"/>`;
  }

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  const face = (p) => Object.assign({}, p, { flip: 1 });          // 面向右

  function pigeonPose(k, F, kBendEnd, kNod) {
    if (k < F[1]) return K.expr(K.clip('idle', k), 'look');        // 句5:站著看
    const kt = k - F[1];
    if (kt < 6) return K.expr(K.clip('tilt', kt), 'look');         // 句6 開頭:歪頭
    if (k <= kBendEnd) return K.expr(K.clip('idle', k), 'look');   // 彎曲中:呼吸
    if (k >= kNod && k < kNod + 6) return K.expr(K.clip('nod', k - kNod), 'look');
    return K.expr(K.clip('idle', 0), 'look');                      // 之後靜止
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kBend = K.frame(L[1].start + 0.3 * (L[1].end - L[1].start)), kBendEnd = kBend + BEND.length - 1;
    const kSun = K.frame(L[1].start + 0.5 * (L[1].end - L[1].start)), kNod = Math.max(kBendEnd, kSun + 3) + 2;

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(face(pigeonPose(k, F, kBendEnd, kNod)), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // 香蕉:長度逐格增加到滿,句6 時尾端往上彎
    const g = k < F[0] + K_GROW ? G0 : Math.min(1, G0 + (1 - G0) * (k - F[0] - K_GROW) / (K_GROW_END - K_GROW));
    const kb = k - kBend, bend = kb < 0 ? 0 : BEND[Math.min(kb, BEND.length - 1)];
    s += K.paper(banana({ u: U, pal, len: LEN * g, wmax: WMAX, wscale: 0.55 + 0.45 * g, h0: 90, turn: TURN * bend, pow: BEND_POW,
      anchor: 'start' }), { x: B0.x, y: B0.y, scale: U, k: 'banana', id: 'main' });

    // 莖(深色紙片,畫在香蕉之上蓋住蒂頭)
    const kst = k - F[0], ps = K.pop(kst);
    const w = STEM.w / U, h = STEM.h / U;
    s += K.paper(`<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" fill="hsl(${pal.h} 45% 22%)" stroke-linejoin="miter"/>`,
      { x: STEM.x, y: STEM.y, rot: -1, scale: U, sx: ps, sy: ps, k: 'stem', id: 'stem', enter: kst < 2, wide: true });

    // 箭頭:句5 往下;句6 約 50% 換成往上彎
    const up = k >= kSun, ka = up ? k - kSun : kst;
    const pa = K.pop(ka), a = up ? { len: 300, h0: 30, turn: -120, label: '往上' } : { len: 210, h0: 90, turn: 0, label: '往下' };
    s += K.paper(arrow({ u: U, len: a.len, h0: a.h0, turn: a.turn, shaft: 58, headW: 138, headL: 80, fill: pal.main }),
      { x: ARROW.x, y: ARROW.y, rot: up ? 0 : 0, scale: U, sx: pa, sy: pa, k: 'arrow', id: a.label, enter: ka < 2 });
    s += card(a.label, { x: ARROW_LABEL.x, y: ARROW_LABEL.y, fs: 64, u: U, rot: -1.5, sx: pa, sy: pa, id: a.label + 'L', enter: ka < 2, pal });

    // 太陽(約 50% 彈入)
    if (up) s += K.paper(sun(U), { x: SUN.x, y: SUN.y, scale: U, sx: pa, sy: pa, k: 'sun', id: 'sun', enter: ka < 2 });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'banana_main', dur: 6.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
