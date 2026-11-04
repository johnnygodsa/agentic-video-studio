/* pearl 場景 p_end(句 35–39)收尾三問。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。淺底,鴿子站左下。
 * 句35:標題牌「想問你三件事」(右上)。
 * 句36–38:三題各在句首逐題彈出(編號牌 1、2、3 + 短句牌):打電話問還是倒掉 / 有加醋你信嗎 / 只驗原料能接受嗎。
 * 句39:鴿子舉翅指向右(point 片段),翅尖旁留言框「留言」彈出;之後靜止到結束。
 * 全部元件留在原位不退場。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js');
  const DEF_TXT = ['最後想問你三件事。', '你喝到酸的珍珠,會打電話去問店家,還是直接倒掉?', '店員跟你說珍珠有加醋的時候,你會相信嗎?',
    '總部只驗原料,這樣的交代你能不能接受?', '留言跟我說吧,記得寫上理由。'];
  const DEF = (() => { let t = 0.08; return DEF_TXT.map((s) => { const d = { start: t, end: t + s.length / 6.5 }; t = d.end + 0.12; return d; }); })();
  const U = 1.43, PU = 1.45;                           // 紙片倍率、鴿子倍率
  const FOOT = { x: 270, y: 805 };
  const TITLE = { x: 1362, y: 195, fs: 100 };
  const ROW = { left: 1000, ys: [380, 540, 700], tile: 110, gap: 20, fs: 66 };
  const QS = ['打電話問還是倒掉', '有加醋你信嗎', '只驗原料能接受嗎'];
  const BOX = { x: 740, y: 520, w: 400, h: 120, fs: 84 };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    let s = '';

    // 句35:標題牌
    if (k >= F[0]) {
      const pl = Ch.plate('想問你三件事', TITLE.fs, { fill: K.YELLOW, ink: K.INK });
      s += Ch.sheet(pl.svg, { x: TITLE.x, y: TITLE.y, rot: -2, u: U, k: k - F[0], kind: 'title', id: 'title', wide: true });
    }
    // 句36–38:編號牌 + 短句牌
    QS.forEach((q, i) => {
      const k0 = F[i + 1];
      if (k < k0) return;
      const pl = Ch.plate(q, ROW.fs, { fill: K.PAPER, ink: K.INK }), y = ROW.ys[i], p = K.pop(k - k0);
      s += K.tile(String(i + 1), { x: ROW.left + ROW.tile / 2, y, size: ROW.tile, rot: i % 2 ? 3 : -3, u: U, sx: p, sy: p, id: 'n' + i, enter: k - k0 < 2 });
      s += Ch.sheet(pl.svg, { x: ROW.left + ROW.tile + ROW.gap + pl.w / 2, y, rot: i % 2 ? -1 : 1, u: U, k: k - k0 - 1, kind: 'q', id: 'q' + i, wide: true });
    });
    // 句39:留言框
    const kb = F[4] + 4;
    if (k >= kb) {
      const w = BOX.w, h = BOX.h;
      const c = `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="30" fill="${K.PAPER}"/>` +
        `<polygon points="${-w / 2 + 2},-16 ${-w / 2 - 46},12 ${-w / 2 + 2},36" fill="${K.PAPER}"/>` +
        `<text x="0" y="4" font-family="GenSen" font-size="${BOX.fs}" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">留言</text>`;
      s += Ch.sheet(c, { x: BOX.x, y: BOX.y, rot: -2, u: U, k: k - kb, kind: 'prop', id: 'msgBox' });
    }

    // 鴿子站左下;句39 舉翅指向留言框
    const pose = k >= F[4] ? K.clip('point', k - F[4]) : K.expr(K.clip('idle', k), 'normal');
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 400, h: 26, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_end', dur: 18, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
