/* 香蕉樣片 場景一:開場鉤子 6.7 秒(固定鏡頭,4 句)。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句1 鴿子(左,高約 45%)idle,句中歪頭加 think → 句2 彎香蕉彈入、鴿子 doubt 歪頭 → 句3 虛線直香蕉彈入、鴿子 point
 * → 句4 兩根香蕉縮到右上角、三張「研究」紙一格一張掉下疊起、鴿子收手換記錄板 write。
 * 同時在動的非文字元素 ≤ 2 組(鴿子、香蕉彈入/縮小、紙片掉落兩兩錯開)。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const U = 2.15;                                  // 鴿子倍率(高約 488px = 45%);全場紙片共用
  const FOOT = { x: 440, y: 800 };                 // 鴿子腳底落點(面向右:flip)
  const DEF = [{ start: 0, end: 1.71 }, { start: 1.83, end: 3.07 }, { start: 3.19, end: 4.39 }, { start: 4.51, end: 6.52 }];
  const LEN = 620, WMAX = 84;                      // 香蕉中心線長、最粗處(px)
  const C_BIG = { x: 1290, y: 390 }, S_BIG = { x: 1290, y: 660 };         // 彎/直香蕉(大)
  const C_SMALL = { x: 1640, y: 185 }, S_SMALL = { x: 1640, y: 285 };     // 縮小後(右上角)
  const SHRINK = [0.48, 0.4];                      // 縮小兩格:過衝 → 定位
  const STACK = [{ x: 1100, y: 740, rot: -3 }, { x: 1240, y: 630, rot: 2 }, { x: 1380, y: 520, rot: -1.5 }];
  const CARD_FS = 80, DROP_PX = 380;
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
  // 香蕉紙片內容(單位 = px / u)。o: {len,h0,turn,pow,wmax,wscale,u,pal,anchor:'center'|'start',ghost,stem}
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
    // 不可見外框:確保濾鏡範圍(橫/直的中心線外框寬或高為 0)並供舞台量外框
    let s = `<rect x="${f(bx0)}" y="${f(by0)}" width="${f(bx1 - bx0)}" height="${f(by1 - by0)}" fill="none" stroke="none"/>`;
    const brown = `hsl(${o.pal.h} 45% 22%)`;
    const line = (a, b, w, col) => {
      const A = q(a), B = q(b);
      return `<line x1="${f(A[0])}" y1="${f(A[1])}" x2="${f(B[0])}" y2="${f(B[1])}" stroke="${col}" stroke-width="${f(w / u)}" stroke-linecap="round" fill="none"/>`;
    };
    const poly = (P, extra) => `<polygon points="${P.map((p) => q(p).map(f).join(',')).join(' ')}" ${extra}/>`;
    if (o.ghost) {                                 // 假想的直香蕉:淡色加墨色虛線外框
      const sd = sides(pts, ws), sw = sides([se, pts[0]], [stem * 0.8, stem * 0.8]);
      const dash = `stroke="${K.INK}" stroke-width="${f(6 / u)}" stroke-dasharray="${f(16 / u)} ${f(12 / u)}" stroke-linejoin="round"`;
      s += poly(sw.L.concat(sw.R.slice().reverse()), `fill="${K.PAPER}" ${dash}`);
      s += poly(sd.L.concat(sd.R.slice().reverse()), `fill="hsl(${o.pal.h} 75% 88%)" ${dash}`);
      return s;
    }
    s += line(se, pts[0], 30 + 28, K.PAPER) + line(se, pts[0], 30 + 20, K.INK) + line(se, pts[0], 30, brown);
    let a = '', b = '', c = '';
    for (let i = 0; i < n; i++) {
      const w = (ws[i] + ws[i + 1]) / 2;
      a += line(pts[i], pts[i + 1], w + 28, K.PAPER); b += line(pts[i], pts[i + 1], w + 20, K.INK); c += line(pts[i], pts[i + 1], w, o.pal.main);
    }
    const T = q(pts[n]);
    return s + a + b + c + `<circle cx="${f(T[0])}" cy="${f(T[1])}" r="${f(Math.max(5, o.wmax * (o.wscale == null ? 1 : o.wscale) * 0.2) / u)}" fill="${brown}"/>`;
  }

  // 紙牌(紙白底加墨色字,頂端一條主色紙帶):o: {x,y,fs,u,rot,sx,sy,id,enter,pal}
  function card(str, o) {
    const u = o.u, fs = o.fs / u, w = str.length * fs + fs * 1.1, h = fs * 1.62;
    const c = `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(fs * 0.22)}" fill="${o.pal.main}" stroke="none"/>` +
      `<text x="0" y="${f(fs * 0.1)}" font-family="GenSen" font-size="${f(fs)}" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">${str}</text>`;
    return K.paper(c, { x: o.x, y: o.y, rot: o.rot, scale: u, sx: o.sx, sy: o.sy, k: 'card', id: o.id, enter: o.enter, wide: true });
  }

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: isFinite(l.start) && l.start != null ? +l.start : d.start, end: isFinite(l.end) && l.end != null ? +l.end : d.end };
    });
  }

  const face = (p) => Object.assign({}, p, { flip: 1 });          // 面向右

  function pigeonPose(k, F) {
    const a = k - F[3];
    if (k < F[1]) {                                                // 句1:idle,句中歪頭加 think
      const kt = k - (F[0] + 6);
      if (kt < 0) return K.clip('idle', k);
      return K.expr(kt < 6 ? K.clip('tilt', kt) : K.clip('idle', k), 'think');
    }
    if (k < F[2]) return K.expr(K.clip('tilt', Math.min(k - F[1], 3)), 'doubt');   // 句2:歪頭 doubt 看香蕉
    if (k < F[3]) return K.clip('point', k - F[2]);                // 句3:指過去
    if (a < 2) return K.clip('point', 5);                          // 句4:先停住讓香蕉縮、紙掉
    if (a < 5) return K.clip('point_out', a - 2);
    if (a === 5) return K.clip('write_out', 1);
    if (a === 6) return K.clip('write_out', 0);
    return K.clip('write', a - 7);
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 520, h: 40, u: U, pal });
    s += K.pigeon(face(pigeonPose(k, F)), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    const kc = k - F[1], ks = k - F[2], kr = k - F[3];
    const shrunk = kr >= 0, sc = shrunk ? SHRINK[Math.min(kr, SHRINK.length - 1)] : 1;
    const big = { u: U, pal, wmax: WMAX * sc, len: LEN * sc, anchor: 'center' };
    if (kc >= 0) {                                                 // 彎香蕉(主色,墨色粗外框)
      const p = shrunk ? C_SMALL : C_BIG, pp = shrunk ? 1 : K.pop(kc);
      s += K.paper(banana(Object.assign({ h0: 46, turn: -92, pow: 1 }, big)),
        { x: p.x, y: p.y, scale: U, sx: pp, sy: pp, k: 'banana', id: 'curved', enter: !shrunk && kc < 2 });
    }
    if (ks >= 0) {                                                 // 直香蕉(同長,淡色虛線 = 假想)
      const p = shrunk ? S_SMALL : S_BIG, pp = shrunk ? 1 : K.pop(ks);
      s += K.paper(banana(Object.assign({ h0: 0, turn: 0, pow: 1, ghost: true, stem: 36 * sc }, big)),
        { x: p.x, y: p.y, scale: U, sx: pp, sy: pp, k: 'banana', id: 'straight', enter: !shrunk && ks < 2 });
    }
    STACK.forEach((st, i) => {                                     // 三張「研究」紙,一格一張,從上掉下疊起
      const d = K.drop(k - (F[3] + 1 + i));
      if (!d) return;
      const h = CARD_FS * 1.62;
      s += card('研究', { x: st.x, y: st.y + d.dy * DROP_PX + (1 - d.sy) * h / 2, fs: CARD_FS, u: U, rot: st.rot, sx: d.sx, sy: d.sy,
        id: 'r' + i, enter: !!d.enter, pal });
    });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'banana_hook', dur: 6.7, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
