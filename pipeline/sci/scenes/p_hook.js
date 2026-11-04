/* pearl 場景 p_hook(句1–5)開場。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。淺底,鴿子站左下(面向右)。
 * 句1:珍奶杯彈入;「喝下去」處鴿子低頭吸一口(杯子靠近嘴),之後皺成酸臉(閉眼加左右抖),珍珠旁冒「酸」字牌。
 * 句2:上一句退場;話筒彈入,實線對話泡「珍珠有加醋」(詞位)。
 * 句3:上一句退場;日曆牌「隔天」加字牌「總部:是醋酸澱粉」。
 * 句4:上一句退場;三個虛線泡(留言)依序疊出,最大的「沒加醋還會酸?」。
 * 句5:上一句退場;勾選清單三題全部 `q` 狀態(詞位逐題出現)。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入;最後一個元素至少在整段結束前 1.5 秒出現。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const DEF_TXT = ['有人外送了一杯五桐號的珍珠奶茶,喝下去發現珍珠是酸的。', '他打電話去門市問,照他的說法,店員回他珍珠有加醋,所以喝起來會酸酸的。',
    '隔天總部出來道歉,說珍珠裡面加的東西叫醋酸澱粉,跟食用醋不一樣。', '留言區沒有買單,很多人問的是同一件事,沒加醋還會酸,那不就是壞掉了嗎?',
    '所以醋酸澱粉到底算不算醋,正常的珍珠會不會酸,那一杯又有沒有可能是壞的呢?'];
  const DEF = [{ start: 0.05, end: 4.55 }, { start: 4.67, end: 10.47 }, { start: 10.59, end: 16.09 }, { start: 16.21, end: 22.01 }, { start: 22.13, end: 28.33 }];
  const U = 1.43, PU = 1.42;
  const FOOT = { x: 270, y: 820 };
  const CUP = { x: 610, y: 610, s: 1.5 }, TILE = { x: 790, y: 600, size: 170 };
  const PH = { x: 1150, y: 650, s: 2.0 }, B1 = { x: 1400, y: 340, fs: 84 };
  const DATE = { x: 1000, y: 470, size: 260 }, HQ = { x: 1500, y: 470, fs: 64 };
  const BUB = [{ x: 1620, y: 300, fs: 60, t: '不買單', tail: 'bl', kw: '沒有買單', rot: 2, id: 'b0' },
    { x: 1330, y: 560, fs: 84, t: '沒加醋還會酸?', tail: 'bl', kw: '沒加醋', rot: 0, id: 'b1' },
    { x: 1150, y: 300, fs: 60, t: '壞掉了嗎?', tail: 'br', kw: '壞掉', rot: -2, id: 'b2' }];
  const CL = { x: 980, y: 280, w: 600, rowH: 110, gap: 30, fs: 64, kws: ['算不算醋', '會不會酸', '有沒有可能'], labels: ['算不算醋', '正常會酸嗎', '那杯壞了嗎'] };
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end, text: l.text || DEF_TXT[i] };
    });
  }
  const at = (L, i, p) => K.frame(L[i].start + p * (L[i].end - L[i].start));
  const atKw = (L, i, kw) => at(L, i, Math.max(0, L[i].text.indexOf(kw)) / L[i].text.length);
  // 退場:自第 k0 格起 2 格縮小後消失(以 (x,y) 為中心);k0 為 null = 不退場
  const shr = (str, x, y, k, k0) => {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  };
  function prop(pal, name, args, o) {
    const e = PP.LIST[name], p = K.pop(o.q);
    if (p <= 0) return '';
    return K.paper(e.fn(pal, args), { x: o.x, y: o.y, rot: o.rot, scale: o.s, sx: p, sy: p, k: 'prop', id: o.id, wide: e.wide, enter: o.q < 2 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start)), kEnd = K.frame(L[4].end), lim = (v) => Math.min(v, kEnd - 15);
    let s = '';

    // ---- 句1:珍奶杯、吸一口、酸字牌 ----
    const ks = Math.max(atKw(L, 0, '喝下去'), F[0] + 4);
    if (k < F[1] + 2) {
      const q = k - F[0], dx = k < ks ? 0 : Math.max(-40, -20 * (k - ks + 1)), rot = k > ks && k <= ks + 3 ? -6 : 0;
      s += shr(prop(pal, 'cup', {}, { x: CUP.x + dx, y: CUP.y, s: CUP.s, rot, q, id: 'cup' }), CUP.x + dx, CUP.y, k, F[1]);
      const qs = k - (ks + 4), p = K.pop(qs);
      if (p > 0) {
        s += shr(K.tile('酸', { x: TILE.x, y: TILE.y, size: TILE.size, rot: 6, u: U, sx: p, sy: p, id: 'sour', enter: qs < 2 }), TILE.x, TILE.y, k, F[1]);
      }
    }
    // ---- 句2:話筒 + 實線泡 ----
    if (k >= F[1] + 2 && k < F[2] + 2) {
      const q = k - (F[1] + 2), kb = Math.max(atKw(L, 1, '珍珠有加醋'), F[1] + 6);
      s += shr(prop(pal, 'phone', {}, { x: PH.x, y: PH.y, s: PH.s, q, id: 'phone' }), PH.x, PH.y, k, F[2]);
      s += shr(Ch.bubble('珍珠有加醋', { x: B1.x, y: B1.y, fs: B1.fs, tail: 'bl', u: U, k: k - kb, id: 'say' }), B1.x, B1.y, k, F[2]);
    }
    // ---- 句3:日曆牌「隔天」+ 字牌 ----
    if (k >= F[2] + 2 && k < F[3] + 2) {
      const q = k - (F[2] + 2), kp = Math.max(atKw(L, 2, '醋酸澱粉'), F[2] + 7), pl = Ch.plate('總部:是醋酸澱粉', HQ.fs, { fill: K.YELLOW });
      s += shr(Ch.dateTag({ x: DATE.x, y: DATE.y, main: '隔天', size: DATE.size, rot: -3, u: U, k: q, id: 'date' }), DATE.x, DATE.y, k, F[3]);
      s += shr(Ch.sheet(pl.svg, { x: HQ.x, y: HQ.y, rot: 2, u: U, k: k - kp, kind: 'sheet', id: 'hq', wide: true }), HQ.x, HQ.y, k, F[3]);
    }
    // ---- 句4:三個虛線泡 ----
    if (k >= F[3] + 2 && k < F[4] + 2) {
      let prev = F[3] + 2 - 3;
      BUB.forEach((b, j) => {
        let kb = Math.max(atKw(L, 3, b.kw), prev + 3);
        if (j === 2) kb = lim(kb);
        prev = kb;
        s += shr(Ch.bubble(b.t, { x: b.x, y: b.y, fs: b.fs, dashed: true, tail: b.tail, rot: b.rot, u: U, k: k - kb, id: b.id }), b.x, b.y, k, F[4]);
      });
    }
    // ---- 句5:三題清單全部 q ----
    if (k >= F[4] + 2) {
      let prev = F[4] + 2 - 3;
      const items = CL.labels.map((lb, j) => {
        let kb = Math.max(atKw(L, 4, CL.kws[j]), prev + 3);
        if (j === 2) kb = lim(kb);
        prev = kb;
        return { label: lb, state: 'q', k: k - kb };
      });
      s += Ch.checklist({ x: CL.x, y: CL.y, w: CL.w, rowH: CL.rowH, gap: CL.gap, fs: CL.fs, pal, u: U, items, id: 'cl' });
    }

    // ---- 鴿子(左下,面向右) ----
    let pz;
    if (k < F[1]) {
      if (k < ks) pz = K.expr(K.clip('idle', k), 'normal');
      else if (k < ks + 6) pz = K.expr(K.clip('nod', k - ks), 'normal');
      else pz = Object.assign(K.expr(K.clip('idle', k), 'speechless'), { headRot: k % 2 ? 5 : -4, headDy: 3 });
    } else if (k < F[2]) pz = K.expr(K.clip('idle', k), 'normal');
    else if (k < F[3]) pz = K.expr(K.clip('tilt', k - F[2]), 'doubt');
    else if (k < F[4]) pz = K.clip('shrug', k - F[3]);
    else pz = K.expr(K.clip('tilt', k - F[4]), 'think');
    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pz, { flip: 1 }), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_hook', dur: 28.4, render, meta: () => ({ clear: [], noOverlapFrom: 0 }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
