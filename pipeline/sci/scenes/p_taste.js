/* pearl 場景 p_taste(句19–24)正常煮出來會不會酸。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–5。
 * 鴿子站右下、面向左;句23 末段往左走到袋子旁,句24 推著袋子走回工廠。
 * 句19:題目牌「正常煮出來會酸嗎」加冒熱氣的大鍋。
 * 句20:大鍋退場,大字黃牌「照道理不會」。
 * 句21:上一組退場。一排五樣食物(麵、冷凍食品、火腿香腸、魚丸、水餃)依詞位逐一彈入,下方來源牌「味丹產品目錄」。
 * 句22:五樣上方逐一彈出黃牌「不酸」。
 * 句23:上一組退場。沒洗的原料袋冒醋味波浪線加牌「醋味」;「專利」詞位來源牌「澱粉廠專利」;「工廠」詞位小工廠(水龍頭滴水);
 *       「原料做完」詞位洗乾淨的原料袋加牌「洗乾淨」。
 * 句24:除工廠與沒洗的袋子外全退場;鴿子推著沒洗的袋子一格 14px 走回工廠,黃牌「出廠前就該處理」。
 * 退場一律 2 格縮小,新的一組在退場後 2 格才彈入。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PP = Wn.PropsPearl || require('../props_pearl.js');
  const TXT = ['那加了醋酸澱粉的珍珠,照正常流程煮出來會酸嗎?', '照道理講,它煮出來是不會酸的。',
    '它本來就沒有要拿來調味,做澱粉的味丹在產品目錄上寫,醋酸澱粉會用在麵、冷凍食品、火腿香腸、魚丸跟水餃裡面。', '這些東西你大概都吃過,應該沒有哪一樣吃起來是酸的吧。',
    '我唯一找到會有醋味的狀況,寫在澱粉工廠的專利裡面,原料做完如果沒有洗乾淨,殘留的醋酸會讓澱粉帶一股醋味。', '那是原料出廠以前就應該處理掉的事情,輪不到客人用嘴巴幫忙檢查。'];
  const U = 1.4, PU = 1.38, FOOT_Y = 820, FOOT0 = 1500;
  const Q = { x: 800, y: 250, fs: 90 }, POT = { x: 800, y: 560, u: 1.0 }, ANS = { x: 800, y: 560, fs: 140 };
  const ROW = { x: 690, y: 308, pitch: 250, size: 200, fs: 60 }, SRC1 = { x: 690, y: 640 }, NOT = { fs: 60 };
  const FAC = { x: 300, y: 400, u: 1.3 }, DROP = { x: 451, y: 550 };
  const BAG = { y: 660, u: 1.3, x0: 1000, x1: 612, step: 14 }, CLEAN = { x: 610, y: 660, labY: 430, labX: 645 };
  const WAV = { x: 1000, y: 462 }, SMELL = { x: 1000, y: 335, fs: 72 }, SRC2 = { x: 1100, y: 150 }, FIX = { x: 960, y: 150, fs: 80 };
  const PUSH_OFF = 302;                                    // 鴿子腳底 x = 袋子 x + 此值(鴿子身體左緣離袋右緣留一點空)
  const FOODS = [['noodle', '麵', '麵、'], ['frozen', '冷凍', '冷凍食品'], ['sausage', '香腸', '火腿香腸'], ['fishball', '魚丸', '魚丸'], ['dumpling', '水餃', '水餃']];
  const f = (x) => +(+x).toFixed(2);

  const DEF = (() => { let t = 0.08; return TXT.map((s) => { const d = s.length / 6.5, o = { start: +t.toFixed(2), end: +(t + d).toFixed(2) }; t += d + 0.12; return o; }); })();
  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: typeof l.text === 'string' && l.text ? l.text : TXT[i] };
    });
  }
  const kwF = (l, kw) => { const i = l.text.indexOf(kw), r = i < 0 ? 0 : i / l.text.length; return K.frame(Math.round((l.start + r * (l.end - l.start)) * 10) / 10); };
  function shr(str, x, y, k, k0) {
    if (!str) return '';
    const s = k0 == null || k < k0 ? 1 : (k - k0 < 2 ? [0.6, 0.3][k - k0] : 0);
    if (s >= 1) return str;
    return s <= 0 ? '' : `<g transform="translate(${f(x)} ${f(y)}) scale(${s}) translate(${f(-x)} ${f(-y)})">${str}</g>`;
  }
  const plate = (txt, fs, o, q, id) => Ch.sheet(Ch.plate(txt, fs, o.style).svg, { x: o.x, y: o.y, rot: o.rot, u: U, k: q, kind: 'sheet', id, wide: true });
  function prop(svg, o, q, id) {
    const p = K.pop(q);
    if (p <= 0) return '';
    return K.paper(svg, { x: o.x, y: o.y, rot: o.rot, scale: o.u, sx: p, sy: p, k: o.kind || 'prop', id, enter: q < 2, wide: o.wide });
  }
  const line = (d, w, col) => `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
  const rope = (d, w, col) => line(d, w + 9, K.PAPER) + line(d, w, col);

  // 醋味波浪線:三條,相位隨格數走
  function waves(k) {
    let s = '';
    [-42, 0, 42].forEach((dx, i) => {
      let d = '';
      for (let j = 0; j <= 10; j++) d += (j ? ' L ' : 'M ') + f(dx + 9 * Math.sin((j + 2 * k + 2 * i) * 0.9)) + ' ' + f(55 - j * 11);
      s += rope(d, 9, 'hsl(30 80% 45%)');
    });
    return s;
  }
  // 水龍頭滴水:三顆水珠依格數往下掉(落在工廠底板前重來)
  function drops(k) {
    let s = '';
    [-7, 0, 7].forEach((dx, i) => { s += `<circle cx="${dx}" cy="${(k * 5 + i * 10) % 30}" r="5" fill="hsl(200 80% 72%)" stroke="none"/>`; });
    return s;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 265 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const Y = { fill: K.YELLOW, ink: K.INK };
    let s = '';

    // ---- 句19–20:題目牌、大鍋、答案牌 ----
    const kSrc = Math.max(kwF(L[2], '產品目錄'), F[2] + 4);   // 題目牌與答案牌留到句21 來源牌出現才退場(中間不留空檔)
    if (k < kSrc) {
      const q = k - F[0];
      let g = plate('正常煮出來會酸嗎', Q.fs, { x: Q.x, y: Q.y, style: {} }, q, 'ask');
      g += shr(prop(PP.pot(pal, {}), { x: POT.x, y: POT.y, u: POT.u }, q - 2, 'pot'), POT.x, POT.y, k, F[1]);
      if (k >= F[1] + 2) g += plate('照道理不會', ANS.fs, { x: ANS.x, y: ANS.y, style: Y, rot: -1.5 }, k - (F[1] + 2), 'ans');
      s += shr(g, 800, 400, k, kSrc - 2);
    }

    // ---- 句21–22:五樣食物、不酸 ----
    if (k >= F[2] + 2 && k < F[4] + 2) {
      const S = F[2] + 2;
      let g = '', prev = S;
      const kk = FOODS.map((fd) => { prev = Math.max(kwF(L[2], fd[2]), prev + 2); return prev; });
      const icons = FOODS.map((fd, i) => { const e = PP.LIST[fd[0]]; return { icon: { svg: e.fn(pal, {}), w: e.w, h: e.h }, label: fd[1], k: k - kk[i] }; });
      g += Ch.iconRow({ x: ROW.x, y: ROW.y, pitch: ROW.pitch, size: ROW.size, fs: ROW.fs, u: U, items: icons, id: 'food' });
      g += Ch.srcTag('味丹產品目錄', { pal, x: SRC1.x, y: SRC1.y, anchor: 'center', u: U, k: k - Math.max(kwF(L[2], '產品目錄'), S + 2), id: 'src1' });
      FOODS.forEach((fd, i) => {
        const cx = ROW.x + (i - 2) * ROW.pitch, py = ROW.y - ROW.size / 2 - 16 - Ch.plate('x', NOT.fs).h / 2;
        g += plate('不酸', NOT.fs, { x: cx, y: py, style: Y }, k - (F[3] + 2 * i), 'no' + i);
      });
      s += shr(g, 690, 400, k, F[4]);
    }

    // ---- 句23–24:工廠、沒洗的袋子;句24 推回工廠 ----
    if (k >= F[4] + 2) {
      const S = F[4] + 2, q = k - S;
      const kFac = Math.max(kwF(L[4], '工廠'), S + 4), kPat = Math.max(kwF(L[4], '專利'), S + 4), kWash = Math.max(kwF(L[4], '原料做完'), kFac + 4);
      const kPush = F[5] + 3, bagX = Math.max(BAG.x1, BAG.x0 - BAG.step * Math.max(0, k - kPush));
      // 工廠(全程)與沒洗的袋子(全程,句24 被推回)
      s += prop(PP.factory(pal, { water: false }), { x: FAC.x, y: FAC.y, u: FAC.u }, k - kFac, 'factory');
      if (k >= kFac + 2) s += prop(drops(k), { x: DROP.x, y: DROP.y, u: 1, kind: 'mark' }, 3, 'drops');
      s += prop(PP.bag(pal, {}), { x: bagX, y: BAG.y, u: BAG.u }, q, 'bagU');
      // 句23 專屬(句24 開頭退場)
      let g = '';
      g += prop(waves(k), { x: WAV.x, y: WAV.y, u: 1, kind: 'mark' }, q - 1, 'wave');
      g += plate('醋味', SMELL.fs, { x: SMELL.x, y: SMELL.y, style: Y }, q - 2, 'smell');
      g += Ch.srcTag('澱粉廠專利', { pal, x: SRC2.x, y: SRC2.y, anchor: 'center', u: U, k: k - kPat, id: 'src2' });
      g += prop(PP.bag(pal, {}), { x: CLEAN.x, y: CLEAN.y, u: BAG.u }, k - kWash, 'bagC');
      g += plate('洗乾淨', 64, { x: CLEAN.labX, y: CLEAN.labY, style: {} }, k - (kWash + 1), 'clean');
      s += shr(g, 900, 450, k, F[5]);
      if (k >= F[5] + 2) s += plate('出廠前就該處理', FIX.fs, { x: FIX.x, y: FIX.y, style: Y }, k - (F[5] + 2), 'fix');
    }

    // ---- 鴿子:右下面向左;句23 末段走到袋子旁,句24 推袋子 ----
    const kWalk = F[5] - 15, kPush = F[5] + 3;
    const footAt = (kk) => {
      if (kk >= kPush) return Math.max(BAG.x1, BAG.x0 - BAG.step * (kk - kPush)) + PUSH_OFF;
      if (kk >= kWalk) return Math.max(BAG.x0 + PUSH_OFF, FOOT0 - 14 * (kk - kWalk));
      return FOOT0;
    };
    const fx = footAt(k), moving = footAt(k - 1) !== fx;
    let pose;
    if (moving) pose = K.clip('walk', k);
    else if (k < F[1]) pose = K.expr(K.clip('idle', k), 'doubt');
    else if (k < F[2]) pose = K.expr(K.clip('idle', k), 'smug');
    else pose = K.clip('idle', k);
    s += K.ground({ x: fx - 20, y: FOOT_Y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(Object.assign({}, pose, { flip: 0 }), { x: fx, y: FOOT_Y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 'p_taste', dur: 30, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
