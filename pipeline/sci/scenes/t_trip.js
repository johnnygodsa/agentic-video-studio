/* turtle 場景 §8 t_trip(句 23–28,24 秒)退房之後。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句23:垃圾桶(牙刷插在裡面)特寫,上方「?」。
 * 句24:桶縮成路線第一站,三站逐站亮(房間垃圾桶→房務推車→垃圾車),垃圾車逐格開走。
 * 句25:大數字「1,210 萬公噸」加說明加來源「環境部」。
 * 句26:比例條回收 58.6%、焚化 36.6%、掩埋 3.6% 依序長出(其他 1.1% 灰色小段)。
 * 句27:牙刷走到回收段前被擋下、回收段變灰;剩下的段被拉出來放大成新的一條。
 * 句28:新的一條標「焚化 88.5%」加「將近九成」加「自算」;牙刷滑向焚化爐。
 * 字牌一律用 Charts(px 紙片,描邊一致);同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PT = Wn.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                  // 鴿子倍率(高約 325px = 30%);全場紙片共用
  const FOOT = { x: 300, y: 810 };                 // 鴿子腳底落點(面向右)
  const DEF = [{ start: 0.06, end: 2.15 }, { start: 2.27, end: 5.96 }, { start: 6.08, end: 11.43 }, { start: 11.54, end: 17.05 },
    { start: 17.18, end: 21.64 }, { start: 21.77, end: 23.95 }];
  const BAR = { x: 1380, w: 900, h: 130 };        // 第一條比例條(水平範圍 930–1830)
  const BAR2 = { x: 1280, w: 1100 };               // 新的一條(730–1830)
  const BIN = { x: 720, y: 560, box: 470 };        // 句23 的大垃圾桶(縮放 2.87)
  const BRUSH = { box: 560, rot: -28, hx: 20, hy: -120 };   // 句23 牙刷(長 540):握柄端落在桶內(桶心 +hx, +hy)

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  // 房務推車(場景內自畫,單位繪製、中心在原點,同 PropsTurtle 畫風)
  function cartSvg(pal) {
    const R = (x, y, w, h, fill, rx) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"${rx ? ` rx="${rx}"` : ''} fill="${fill}"/>`;
    const dark = 'hsl(200 10% 38%)', bag = 'hsl(40 20% 96%)';
    return `<circle cx="-30" cy="-22" r="36" fill="${bag}"/><circle cx="34" cy="-30" r="30" fill="${bag}"/>` +
      R(-92, -72, 10, 110, dark, 3) + R(-92, -72, 54, 10, dark, 3) + R(-86, 22, 176, 14, dark, 4) + R(-90, 36, 180, 28, pal.main, 6) +
      `<circle cx="-56" cy="70" r="16" fill="${K.INK}"/><circle cx="56" cy="70" r="16" fill="${K.INK}"/>`;
  }
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // 鴿子:有反應片段就播,否則呼吸待機
  function pigeonPose(k, reacts, expr) {
    for (const r of reacts) {
      const n = K.P.CLIPS[r.clip].frames.length;
      if (k >= r.k0 && k < r.k0 + n) return K.expr(K.clip(r.clip, k - r.k0), r.expr || expr);
    }
    return K.expr(K.clip('idle', k), expr);
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const grey = `hsl(${pal.h} 8% 72%)`;
    // 圖解(PropsTurtle)嵌進 px 紙片:box = 最長邊 px
    const icn = (name, opts, x, y, box, o) => Ch.sheet(Ch.icon({ svg: PT.LIST[name].fn(pal, opts), w: PT.LIST[name].w, h: PT.LIST[name].h }, 0, 0, box),
      Object.assign({ x, y, u: U, kind: 'prop', id: name, wide: PT.LIST[name].wide }, o));
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    const reacts = [{ k0: F[0] + 2, clip: 'tilt', expr: 'doubt' }, { k0: F[2] + 2, clip: 'nod' }, { k0: F[4] + 14, clip: 'shrug' }];
    const ph = k < F[1] ? 0 : k < F[2] ? 1 : k < F[3] ? 2 : k < F[4] ? 3 : k < F[5] ? 4 : 5;
    s += K.pigeon(Object.assign({}, pigeonPose(k, reacts, 'look'), { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    if (ph === 0) {                                // 句23:垃圾桶特寫(牙刷畫在桶之前,桶蓋住握柄端)
      const q = k - F[0], hl = BRUSH.box * 0.49, rad = BRUSH.rot * Math.PI / 180;
      s += icn('toothbrush', {}, BIN.x + BRUSH.hx + hl * Math.cos(rad), BIN.y + BRUSH.hy + hl * Math.sin(rad), BRUSH.box,
        { rot: BRUSH.rot, k: q - 2, id: 'brushIn' });
      s += icn('bin', {}, BIN.x, BIN.y, BIN.box, {});
      s += K.tile('?', { x: 1700, y: 300, size: 220, rot: 6, u: U, fill: K.INK, ink: K.YELLOW, sx: K.pop(q), sy: K.pop(q), id: 'q', enter: q < 2 });
    } else if (ph === 1) {                         // 句24:路線
      const q = k - F[1], y = 660, ys = 420;
      const stops = [{ x: 700, label: '房間垃圾桶', kOn: q }, { x: 1130, label: '房務推車', kOn: q - 12 }, { x: 1560, label: '垃圾車', kOn: q - 24 }]
        .map((p) => Object.assign(p, { y, labelSide: 'down' }));
      s += Ch.route({ pal, u: U, fs: 56, r: 28, th: 16, stops, id: 'rt' });
      s += icn('bin', {}, 700, ys, 300, {});
      s += Ch.sheet(Ch.icon({ svg: cartSvg(pal), w: 200, h: 150 }, 0, 0, 300), { x: 1130, y: ys, u: U, k: q - 12, kind: 'prop', id: 'cart' });
      const dq = q - 28, dx = dq < 0 ? 0 : Math.min(10, dq + 1) * 10;     // 第 28 格起逐格開走
      s += icn('truck', { spin: dq < 0 ? 0 : dq * 40 }, 1560 + dx, ys, 330, { k: q - 24, id: 'truck' });
    } else if (ph === 2) {                         // 句25:大數字
      const q = k - F[2];
      s += Ch.bigNum({ pal, u: U, x: 1200, y: 330, num: '1,210', unit: '萬公噸', note: '2025 年 台灣一般垃圾', fs: 260, id: 'num' });
      s += Ch.srcTag('環境部', { pal, u: U, x: 1200, y: 668, anchor: 'center', k: q - 8, id: 'src' });
    } else if (ph === 3 || ph === 4) {             // 句26–27:比例條
      const q = k - F[ph], q4 = ph === 4 ? q : -1;
      const grayed = q4 >= 14, pulled = q4 >= 26;
      const kk = (a) => (ph === 4 ? 99 : q - a);
      const seg = (value, label, text, color, side, a, hide) => ({ value, label, text, color, side, k: hide ? -1 : kk(a) });
      s += Ch.ratioBar({ pal, u: U, x: BAR.x, y: 400, w: BAR.w, h: BAR.h, fs: 56, id: 'rb', segs: [
        seg(58.6, '回收', '58.6%', grayed ? grey : pal.main, 'up', -99, false),
        seg(36.6, '焚化', '36.6%', K.YELLOW, 'up', 18, pulled),
        seg(3.6, '掩埋', '3.6%', pal.pad, 'down', 36, pulled),
        seg(1.1, null, null, grey, 'down', 40, pulled)] });
      if (!pulled) {
        const p = Ch.plate('其他 1.1%', 56, { chip: grey });
        s += Ch.sheet(p.svg, { x: BAR.x + BAR.w / 2 - p.w / 2, y: 621, u: U, k: kk(40), kind: 'ratioL', id: 'rb3', wide: true });
      }
      const n = ph === 4 ? clamp(Math.floor((q - 4) / 2) + 1, 0, 4) : 0;   // 牙刷在條左邊,句27 逐格走向回收段
      s += icn('toothbrush', {}, 380 + n * 55, 400, 560, { id: 'brush' });
      if (ph === 3) {
        s += Ch.srcTag('環境部', { pal, u: U, x: 1830, y: 760, anchor: 'right', id: 'src' });
      } else {
        s += Ch.sheet(`<circle cx="0" cy="0" r="70" fill="hsl(6 75% 55%)"/><rect x="-48" y="-13" width="96" height="26" fill="${K.PAPER}" stroke="none"/>`,
          { x: 925, y: 400, u: U, k: q - 14, kind: 'sign', id: 'stop' });
        if (pulled) {                              // 剩下的段被拉出來放大(4 格變形)
          const st = q - 26, b = st === 0 ? [1644, 372, 600] : st <= 2 ? [1540, 560, 620] : st === 3 ? [1435, 790, 630] : [BAR2.x, BAR2.w, 640];
          s += Ch.ratioBar({ pal, u: U, x: b[0], y: b[2], w: b[1], h: BAR.h, fs: 56, id: 'rb2', segs: [
            { value: 36.6, color: K.YELLOW }, { value: 3.6, color: pal.pad }, { value: 1.1, color: grey }] });
        }
      }
    } else {                                       // 句28:新的一條
      const q = k - F[5];
      s += Ch.ratioBar({ pal, u: U, x: BAR2.x, y: 640, w: BAR2.w, h: BAR.h, fs: 56, id: 'rb2', segs: [
        { value: 36.6, label: '焚化', text: '88.5%', color: K.YELLOW, side: 'down' }, { value: 3.6, color: pal.pad }, { value: 1.1, color: grey }] });
      const tile = Ch.plate('將近九成', 72, { fill: K.YELLOW });
      s += Ch.sheet(tile.svg, { x: 1217, y: 500, rot: -1.5, u: U, k: q - 1, kind: 'note', id: 'nine', wide: true });
      s += Ch.srcTag('自算', { pal, u: U, x: 1830, y: 530, anchor: 'right', k: q - 1, id: 'self' });
      s += icn('incinerator', { tall: 0.2, restaurant: false }, 1650, 160, 500, { k: q, id: 'burner' });
      const n = clamp(q - 2, 0, 6);                // 牙刷逐格滑向爐口
      s += icn('toothbrush', {}, 790 + n * 75, 360, 560, { id: 'brush' });
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_trip', dur: 24, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
