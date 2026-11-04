/* turtle 場景 §5 t_rule_b(句 14–16,固定鏡頭)。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句14:名單板(六樣備品)彈入;拖鞋站在板外;鴿子指它;小海龜在另一側與拖鞋對看,什麼事也沒發生。
 * 句15:舊物退場;櫃檯彈入、鴿子走到櫃檯前;對話泡(牙刷);櫃檯遞出牙刷;價牌「收不收 飯店決定」;來源小牌「環境部」。
 * 句16:舊物退場;公告紙兩個空欄位「收錢」「海龜」;飯店貼上兩張便條(硬幣、海龜);鴿子指便條。
 * 事件都在該句 start 後依句長比例出現;同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), Ch = W.Charts || require('../charts.js'), PT = W.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT0 = { x: 300, y: 800 }, WALK_N = 10, WALK_DX = 31;
  const DEF = [{ start: 0, end: 4.1 }, { start: 4.2, end: 8.6 }, { start: 8.7, end: 14.2 }];
  const f = (x) => +(+x).toFixed(2);
  const OUT = [0.7, 0.35];                          // 退場縮小兩格

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const ic = (pal, n, o) => ({ svg: PT.LIST[n].fn(pal, o), w: PT.LIST[n].w, h: PT.LIST[n].h });
  const prop = (pal, n, o, p) => K.paper(PT.LIST[n].fn(pal, o), Object.assign({ k: 'prop', id: n, wide: PT.LIST[n].wide, scale: U }, p));
  // 退場:kOut 為退場起始格;回傳 null = 已消失,否則包上縮放群組的函式
  function shrink(k, kOut, cx, cy) {
    if (kOut == null || k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  const popAt = (k, kIn) => { const kk = k - kIn; return { kk, p: K.pop(kk), enter: kk < 2 }; };

  // ---------- 句14 ----------
  const BOARD = { x: 1250, y: 345, w: 1120, h: 380 }, SLIP = { x: 1130, y: 685, sc: 1.3 }, HATCH = { x: 1500, y: 684, sc: 2.05 };
  // 板上六樣備品:[名, 旋轉, 縮放](細長的斜放,每個高約 150px)
  const BOARD_ITEMS = [['toothbrush', -35, 0.857], ['toothpaste', -35, 0.84], ['comb', -35, 0.885], ['razor', 0, 0.707], ['foam', 0, 0.694], ['showerCap', 0, 1.36]];
  function board(pal, kk) {
    const b = BOARD, q = Ch.plate('名單', 56, { fill: pal.main, ink: pal.onMain });
    let c = `<rect x="${-b.w / 2}" y="${-b.h / 2}" width="${b.w}" height="${b.h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<g transform="translate(${-b.w / 2 + q.w / 2} ${-b.h / 2 - 24})">${q.svg}</g>`;
    BOARD_ITEMS.forEach(([n, rot, sc], i) => {
      const cx = (i % 3 - 1) * 330, cy = (Math.floor(i / 3) - 0.5) * 190;
      c += `<g transform="translate(${cx} ${cy}) rotate(${rot}) scale(${sc})" stroke-width="${f(5 / sc)}">${PT.LIST[n].fn(pal)}</g>`;
    });
    return Ch.sheet(c, { x: b.x, y: b.y, u: U, k: kk, kind: 'board', id: 'list', rot: -1 });
  }

  // ---------- 句15 ----------
  const COUNTER = { x: 1430, y: 575, sc: 2.3 }, BUB = { x: 860, y: 250 }, TAG = { x: 1525, y: 280 }, SRC = { x: 1815, y: 795 }, BR15 = 2.3;
  const HAND = [[1380, 485], [1330, 505], [1270, 535], [1210, 565], [1160, 595], [1130, 610]];   // 櫃檯遞出的牙刷路徑

  // ---------- 句16 ----------
  const PAPER16 = { x: 1280, y: 270, w: 1080, h: 360, rowH: 96, gap: 12, fs: 72 };
  const STICKY = [{ x: 1130, y: 650, rot: -5, n: 'coin' }, { x: 1520, y: 650, rot: 6, n: 'turtle' }];

  const face = (p) => Object.assign({}, p, { flip: 1 });

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const sec = k < F[1] ? 0 : k < F[2] ? 1 : 2;
    // 事件格
    const e14 = { board: F[0], slip: at(L[0], 0.25), point: at(L[0], 0.32), hatch: at(L[0], 0.6) };
    const e15 = { counter: F[1], bub: at(L[1], 0.25), hand: at(L[1], 0.45), tag: at(L[1], 0.68), src: at(L[1], 0.82) };
    const e16 = { paper: F[2], q1: F[2] + 3, s1: at(L[2], 0.36), s2: at(L[2], 0.55), point: at(L[2], 0.72) };
    const kWalk = k - F[1], fx = FOOT0.x + WALK_DX * Math.min(Math.max(kWalk, 0), WALK_N) * (sec >= 1 ? 1 : 0);
    const FOOT = { x: fx, y: FOOT0.y };

    // 鴿子姿勢
    let pose;
    if (sec === 0) pose = k >= e14.point ? K.expr(K.clip('point', k - e14.point), 'look') : K.expr(K.clip('idle', k), k >= e14.slip ? 'doubt' : 'look');
    else if (sec === 1) {
      if (kWalk < WALK_N) pose = K.expr(K.clip('walk', kWalk), 'normal');
      else if (k >= e15.hand + HAND.length && k < e15.hand + HAND.length + 6) pose = K.expr(K.clip('nod', k - e15.hand - HAND.length), 'normal');
      else if (k >= e15.bub && k < e15.bub + 12) pose = K.expr(K.clip('talk', k - e15.bub), 'talkA');
      else pose = K.expr(K.clip('idle', k), 'normal');
    } else pose = k >= e16.point ? K.expr(K.clip('point', k - e16.point), 'look') : K.expr(K.clip('idle', k), 'look');

    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(face(pose), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // ----- 句14 的物件(句15 開頭退場) -----
    const o14 = shrink(k, F[1], 960, 450);
    if (sec <= 1 && o14 && k >= e14.board) {
      let g = '';
      const kb = k - e14.board;
      g += board(pal, kb);
      const sl = popAt(k, e14.slip);
      if (sl.kk >= 0) g += prop(pal, 'slipper', {}, { x: SLIP.x, y: SLIP.y, scale: SLIP.sc, sx: sl.p, sy: sl.p, rot: 4, id: 'slipper', enter: sl.enter });
      const ha = popAt(k, e14.hatch);
      if (ha.kk >= 0) g += prop(pal, 'hatchling', { ang: -90 }, { x: HATCH.x, y: HATCH.y, scale: HATCH.sc, sx: ha.p, sy: ha.p, id: 'hatchling', enter: ha.enter });
      s += o14(g);
    }

    // ----- 句15 的物件(句16 開頭退場) -----
    const o15 = shrink(k, F[2], 1100, 520);
    if (sec >= 1 && sec <= 2 && o15 && k >= e15.counter) {
      let g = '';
      const c = popAt(k, e15.counter);
      g += prop(pal, 'counter', {}, { x: COUNTER.x, y: COUNTER.y, scale: COUNTER.sc, sx: c.p, sy: c.p, id: 'counter', enter: c.enter });
      const kt = k - e15.tag;                                    // 價牌
      if (kt >= 0) {
        const q = Ch.plate('收不收 飯店決定', 72, { fill: K.PAPER });
        g += Ch.sheet(q.svg + `<rect x="${f(-q.w / 2)}" y="${f(-q.h / 2)}" width="${f(q.w)}" height="14" fill="${pal.main}" stroke="none"/>`,
          { x: TAG.x, y: TAG.y, u: U, k: kt, kind: 'priceTag', id: 'tag', rot: -3, wide: true });
      }
      const kh = k - e15.hand, hi = Math.min(Math.max(kh, 0), HAND.length - 1);   // 遞出的牙刷
      if (kh >= 0) g += prop(pal, 'toothbrush', {}, { x: HAND[hi][0], y: HAND[hi][1], rot: -12 - 3 * hi, scale: BR15, id: 'handed', enter: false });
      s += o15(g);
      const kbub = k - e15.bub;                                  // 對話泡 + 牙刷(泡留到句16 退場)
      if (kbub >= 0) {
        let bb = Ch.bubble(['　　　　　　　　', '　'], { x: BUB.x, y: BUB.y, fs: 72, tail: 'bl', u: U, k: kbub, id: 'ask', rot: -2 });
        if (kbub >= 1) bb += prop(pal, 'toothbrush', {}, { x: BUB.x, y: BUB.y, rot: -2, scale: BR15, id: 'ask', enter: kbub < 3 });
        s += o15(bb);
      }
      if (k >= e15.src) s += o15(Ch.srcTag('環境部', { x: SRC.x, y: SRC.y, anchor: 'right', pal, u: U, k: k - e15.src, id: 'src' }));
    }

    // ----- 句16 -----
    if (sec === 2) {
      const P = PAPER16;
      const cl = Ch.checklist({ x: P.x - P.w / 2 + 40, y: P.y - P.h / 2 + 138, w: P.w - 80, rowH: P.rowH, gap: P.gap, fs: P.fs, pal, u: U, id: 'blank',
        items: [{ label: '收錢', state: 'empty', k: k - e16.paper }, { label: '海龜', state: 'empty', k: k - e16.q1 }] });
      const ph = P.h;
      const kp = k - e16.paper;
      if (kp >= 0) {
        const hd = Ch.plate('公告', 72, { fill: pal.main, ink: pal.onMain });
        s += Ch.sheet(`<rect x="${-P.w / 2}" y="${-ph / 2}" width="${P.w}" height="${ph}" fill="${pal.pad}" stroke-linejoin="miter"/>` +
          `<g transform="translate(0 ${-ph / 2 + 10 + hd.h / 2})">${hd.svg}</g>`, { x: P.x, y: P.y, u: U, k: kp, kind: 'paper16', id: 'notice', rot: 0 });
        s += cl;
      }
      STICKY.forEach((st, i) => {
        const kk = k - (i ? e16.s2 : e16.s1);
        if (kk < 0) return;
        const sz = 290, d = ic(pal, st.n, st.n === 'turtle' ? { headUp: false } : {});
        s += Ch.sheet(`<rect x="${-sz / 2}" y="${-sz / 2}" width="${sz}" height="${sz}" fill="${K.YELLOW}" stroke-linejoin="miter"/>` + Ch.icon(d, 0, 0, sz * 0.78),
          { x: st.x, y: st.y, u: U, k: kk, kind: 'sticky', id: st.n, rot: st.rot });
      });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_rule_b', dur: 14.4, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
