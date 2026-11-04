/* salary 場景 sal_end(句 40–43)提問收尾。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 開頭乾淨舞台:鴿子在左欄,位置與下一場景 outro 第 0 格相同(腳底 368,800、倍率 2.6、面向右),末格鴿子不動 → 接 outro 不跳位。
 * 句40:兩張空白題卡(色帶「問題一」「問題二」加灰色大「?」)自句首依序彈入(隔 3 格)。
 * 句41:題卡一句首翻面(換黃底)→「一年賺多少才夠用?」;翻完後橫線由左至右畫出(讓人填)加「萬」。
 * 句42:題卡二句首翻面 →「喜歡的工作」「多三成薪水」兩塊牌夾中間天秤,天秤翻完後左右晃動。
 * 句43:兩張題卡 2 格縮小退場;留言框(黃底、「留言」加「記得寫上理由」)彈入,鴿子翅膀指向它,停到結束。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js');
  const U = 1.4, PU = 2.6, FOOT = { x: 368, y: 800 };              // 鴿子:與 outro 相同
  const CARD = { w: 1040, h: 330, x: 1260, ys: [270, 640], strip: 74, fs: 84 };
  const BOX = { x: 1260, y: 530, w: 560, h: 280 };
  const DEF = [
    { start: 0.025, end: 2.54, text: '最後我想問你兩個問題,答案沒有對錯。' },
    { start: 2.66, end: 6.28, text: '你覺得一年賺多少才算夠用,你心裡那條線在哪裡?' },
    { start: 6.4, end: 10.975, text: '如果有一份工作你很喜歡,可是薪水比另一份少三成,你會選哪一個?' },
    { start: 11.095, end: 13.125, text: '留言跟我說吧,記得寫上理由。' }];
  const FLIP = [{ sx: 0.6, back: 1 }, { sx: 0.15, back: 1 }, { sx: 0.15, back: 0 }, { sx: 0.65, back: 0 }, { sx: 1.05, back: 0 }];
  const WING = [[90, 1.1], [150, 1.3], [186, 1.5]];                // 指向留言框(同 s_end 的指向)
  const TILT = [0.55, 0.55, 0.55, 0, -0.55, -0.55, -0.55, 0];     // 天秤晃動:每 3 格換一次
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const rect = (x, y, w, h, fill, ex) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}"${ex || ' stroke="none"'}/>`;
  const text = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  // 以 px 繪製的紙片(中心 o.x,o.y;描邊 4U)
  const paperPx = (content, o) => K.paper(`<g transform="scale(${(1 / U).toFixed(5)})" stroke-width="${f(4 * U)}">${content}</g>`,
    { x: o.x, y: o.y, rot: o.rot, scale: U, sx: o.sx, sy: o.sy, k: o.kind, id: o.id, enter: o.enter, wide: true });
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心)
  const shrink = (str, x, y, k, k0) => {
    const s = k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };

  // 題卡內容(中心在原點):i = 0/1;back = 空白面
  function card(i, back, pal, o) {
    const w = CARD.w, h = CARD.h, st = CARD.strip, cy = st / 2;                  // 本體中心 y
    let c = rect(-w / 2, -h / 2, w, h, back ? K.PAPER : K.YELLOW, ' stroke-linejoin="miter"') + rect(-w / 2, -h / 2, w, st, pal.main) +
      text(i === 0 ? '問題一' : '問題二', 0, -h / 2 + st / 2 + 2, 56, pal.onMain);
    if (back) return c + text('?', 0, cy + 6, 210, pal.pad);
    if (i === 0) {
      c += text('一年賺多少才夠用?', 0, cy - 28, CARD.fs, K.INK);
      const x0 = -380, x1 = x0 + 700 * o.line, yL = cy + 92;
      if (o.line > 0) c += `<path d="M ${x0} ${yL} L ${f(x1)} ${yL}" fill="none" stroke="${K.INK}" stroke-width="9" stroke-linecap="round"/>` + text('萬', 410, yL - 8, 64, K.INK);
    } else {
      const sc = Ch.icon({ svg: PS.scale(pal, { tilt: o.tilt }), w: 350, h: 240 }, 0, cy + 10, 250);
      const chip = (s, x, fill, ink) => { const cw = Ch.tw(s, 60) + 50; return rect(x - cw / 2, cy - 4 - 50, cw, 100, fill, ' stroke-linejoin="miter"') + text(s, x, cy - 2, 60, ink); };
      c += sc + chip('喜歡的工作', -352, K.PAPER, K.INK) + chip('多三成薪水', 352, pal.main, pal.onMain);
    }
    return c;
  }

  // 鴿子:idle 呼吸、面向右、表情只換眼;句43 翅膀逐格抬起指向留言框
  function pigeonPose(k, name, wk) {
    const p = K.clip('idle', k), e = K.P.EXPR[name];
    const o = Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 });
    if (wk >= 0) { const w = WING[Math.min(wk, WING.length - 1)]; o.wing = w[0]; o.wlen = w[1]; }
    return o;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // 兩張題卡
    CARD.ys.forEach((cy, i) => {
      const kApp = F[0] + 3 * i;
      if (k < kApp) return;
      const kF = F[1 + i];
      let back = 1, sx = 1, pk = k - kApp, o = { line: 0, tilt: 0 }, enter = k - kApp < 2;
      if (k >= kF) {
        const q = k - kF, fl = q < FLIP.length ? FLIP[q] : { sx: 1, back: 0 };
        back = fl.back; sx = fl.sx; pk = 9; enter = q < FLIP.length;
        if (i === 0) o.line = Math.max(0, Math.min(1, (k - kF - FLIP.length + 1) / 6));
        else o.tilt = k - kF >= FLIP.length ? TILT[Math.floor((k - kF - FLIP.length) / 3) % TILT.length] : 0;
      }
      const p = K.pop(pk);
      const c = paperPx(card(i, back, pal, o), { x: CARD.x, y: cy, rot: i ? 0.8 : -0.8, sx: p * sx, sy: p, kind: 'card', id: 'card' + i, enter });
      s += shrink(c, CARD.x, cy, k, F[3]);
    });

    // 句43:留言框
    if (k >= F[3] + 2) {
      const kk = k - F[3] - 2, p = K.pop(kk), w = BOX.w, h = BOX.h;
      const c = rect(-w / 2, -h / 2, w, h, K.YELLOW, ' stroke-linejoin="round"') +
        `<polygon points="${-w / 2 + 3},-30 ${-w / 2 - 70},12 ${-w / 2 + 3},50" fill="${K.YELLOW}" stroke-linejoin="round"/>` +
        text('留言', 0, -44, 128, K.INK) + text('記得寫上理由', 0, 76, 60, K.INK);
      s += paperPx(c, { x: BOX.x, y: BOX.y, rot: -1, sx: p, sy: p, kind: 'prop', id: 'msgBox', enter: kk < 2 });
    }

    // 鴿子與腳下襯底(全場固定位置 = outro 第 0 格的位置)
    const wk = k >= F[3] ? k - F[3] : -1;
    const name = k >= F[2] && k < F[3] ? 'think' : 'look';
    s = K.ground({ x: FOOT.x, y: FOOT.y + 6, w: 520, h: 40, u: PU, pal }) + K.pigeon(pigeonPose(k, name, wk), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main', enter: k < 2 }) + s;
    return K.wrap(pal, s);
  }

  const Scene = { name: 'sal_end', dur: 13.2, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
