/* turtle 場景 §7 t_brush_b(句 20–22,固定鏡頭)。render(t, params) 回傳完整 <svg> 內容;params: {hue, dur, lines:[{idx,text,start,end}]}。
 * 句20:大數字牌「2003」加「麻省理工 調查」;問卷紙彈入。(右上「?」記號沿用上一場,開場即在)
 * 句21:舊物退場;五個選項小圖逐一彈入;頒獎台彈入;牙刷掉上第一名、汽車掉上第二名(原位小圖變淡)。
 * 句22:舊物退場;漱口杯彈入,冠軍牙刷掉進杯子;兩個月亮依序彈入;垃圾桶彈入,牙刷跳進垃圾桶;「?」記號彈出。垃圾桶留在畫面右側給下一場。
 * 事件都在該句 start 後依句長比例出現;同時在動的非文字元素 ≤ 2 組。 */
(function () {
  const W = typeof window !== 'undefined' ? window : {};
  const K = W.Kit || require('../kit.js'), Ch = W.Charts || require('../charts.js'), PT = W.PropsTurtle || require('../props_turtle.js');
  const U = 1.43;                                   // 鴿子倍率(高約 325px);全場紙片共用
  const FOOT = { x: 330, y: 800 };
  const DEF = [{ start: 0, end: 5.9 }, { start: 6.0, end: 10.4 }, { start: 10.5, end: 14.6 }];
  const YEAR = { x: 520, y: 235 }, SURVEY = { x: 1350, y: 440, w: 580, h: 640 };
  const OPT_X = [308, 633, 962, 1184, 1436], OPT_Y = 175, OPT_FS = 60;
  const POD = { x: 1130, y: 800, w: 960, h: 150 };
  const CUP = { x: 700, y: 630, w: 230, h: 340 }, BRUSH_IN = { x: 793, y: 444, rot: -72, sc: 2.4 };
  const MOON = [{ x: 1050, y: 260, rot: -8 }, { x: 1370, y: 260, rot: 6 }], MOON_SC = 2.0;
  const BIN = { x: 1600, y: 600, sc: 2.4 }, BIN_BRUSH = { x: 1600, y: 470, rot: -84 };
  const FALL_N = 6;
  const OUT = [0.7, 0.35];                          // 退場縮小兩格
  const f = (x) => +(+x).toFixed(2);

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end };
    });
  }
  const at = (l, p) => K.frame(l.start + p * (l.end - l.start));
  const prop = (pal, n, o, p) => K.paper(PT.LIST[n].fn(pal, o), Object.assign({ k: 'prop', id: n, wide: PT.LIST[n].wide, scale: U }, p));
  function shrink(k, kOut, cx, cy) {
    if (kOut == null || k < kOut) return (s) => s;
    const j = k - kOut;
    if (j >= OUT.length) return null;
    return (s) => `<g transform="translate(${f(cx)} ${f(cy)}) scale(${OUT[j]}) translate(${f(-cx)} ${f(-cy)})">${s}</g>`;
  }
  const face = (p) => Object.assign({}, p, { flip: 1 });
  // 五個選項小圖:[名, 名稱, 旋轉, 縮放](縮放讓每個高約 150–158px;牙刷斜放才不會扁成一條線)
  const OPTS = [['toothbrush', '牙刷', -40, 0.85], ['car', '汽車', 0, 1.45], ['computer', '電腦', 0, 1.05], ['phone', '手機', 0, 0.8], ['microwave', '微波爐', 0, 1.2]];
  function optItem(pal, i, k, dim) {
    const [n, label, rot, sc] = OPTS[i];
    const lp = Ch.plate(label, OPT_FS);
    return Ch.sheet(`<g transform="rotate(${rot}) scale(${sc})" stroke-width="${f(5 / sc)}"${dim ? ' opacity=".4"' : ''}>${PT.LIST[n].fn(pal)}</g>`,
        { x: OPT_X[i], y: OPT_Y, u: U, k, kind: 'icon', id: 'opt' + i }) +
      Ch.sheet(lp.svg, { x: OPT_X[i], y: OPT_Y + 80 + 16 + lp.h / 2, u: U, k, kind: 'iconL', id: 'opt' + i, wide: true });
  }

  // 問卷紙(px,中心在原點):主色頁首加五列「勾選框 + 灰色橫條」
  function survey(pal) {
    const s = SURVEY;
    let c = `<rect x="${-s.w / 2}" y="${-s.h / 2}" width="${s.w}" height="${s.h}" fill="${K.PAPER}" stroke-linejoin="miter"/>` +
      `<rect x="${-s.w / 2}" y="${-s.h / 2}" width="${s.w}" height="96" fill="${pal.main}" stroke="none"/>` +
      `<rect x="${-s.w / 2 + 40}" y="${-s.h / 2 + 34}" width="${s.w - 160}" height="28" fill="${pal.onMain}" stroke="none"/>`;
    for (let i = 0; i < 5; i++) {
      const y = -s.h / 2 + 170 + i * 92;
      c += `<rect x="${-s.w / 2 + 40}" y="${y - 22}" width="44" height="44" fill="none" stroke="${K.INK}" stroke-width="7"/>` +
        `<rect x="${-s.w / 2 + 112}" y="${y - 9}" width="${s.w - 190 - (i % 2) * 70}" height="18" fill="hsl(200 8% 62%)" stroke="none"/>`;
    }
    return c;
  }

  // 漱口杯(px,中心在原點):淺藍杯身、杯口加一圈、杯底一點水
  function cup(pal) {
    const w = CUP.w, h = CUP.h;
    return `<polygon points="${-w / 2},${-h / 2} ${w / 2},${-h / 2} ${w / 2 - 22},${h / 2} ${-w / 2 + 22},${h / 2}" fill="hsl(195 70% 84%)" stroke-linejoin="round"/>` +
      `<polygon points="${-w / 2 + 6},${h * 0.1} ${w / 2 - 6},${h * 0.1} ${w / 2 - 24},${h / 2 - 4} ${-w / 2 + 24},${h / 2 - 4}" fill="hsl(195 70% 70%)" stroke="none"/>` +
      `<rect x="${-w / 2 - 8}" y="${-h / 2 - 12}" width="${w + 16}" height="26" rx="8" fill="${K.PAPER}"/>`;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue), k = K.frame(t), L = lines(params), F = L.map((l) => K.frame(l.start));
    const sec = k < F[1] ? 0 : k < F[2] ? 1 : 2;
    const e20 = { year: F[0], survey: at(L[0], 0.4), tilt: at(L[0], 0.42) };
    const e21 = { opt: F[1], pod: at(L[1], 0.3), brush: at(L[1], 0.4), car: at(L[1], 0.68) };
    const e22 = { cup: F[2], brush: F[2] + 3, m1: at(L[2], 0.2), m2: at(L[2], 0.4), bin: at(L[2], 0.46), fall: at(L[2], 0.52), out: at(L[2], 0.68) };

    // 鴿子姿勢
    let pose;
    if (sec === 0) pose = k >= e20.tilt && k < e20.tilt + 6 ? K.expr(K.clip('tilt', k - e20.tilt), 'look') : K.expr(K.clip('idle', k), 'look');
    else if (sec === 1) pose = K.expr(K.clip('idle', k), 'look');
    else pose = K.expr(K.clip('idle', k), k >= e22.m2 ? 'doubt' : 'look');
    let s = K.ground({ x: FOOT.x + 10, y: FOOT.y + 6, w: 400, h: 36, u: U, pal });
    s += K.pigeon(face(pose), { x: FOOT.x, y: FOOT.y, scale: U, id: 'main' });

    // ----- 句20:大數字牌 + 問卷紙(句21 開頭退場) -----
    const o20 = shrink(k, F[1], 960, 420);
    if (sec === 0 || (sec === 1 && o20)) {
      let g = '';
      g += Ch.bigNum({ x: YEAR.x, y: YEAR.y, num: '2003', note: '麻省理工 調查', fs: 160, u: U, k: k - e20.year, rot: -2, id: 'year' });
      const ks = k - e20.survey;
      if (ks >= 0) g += Ch.sheet(survey(pal), { x: SURVEY.x, y: SURVEY.y, u: U, k: ks, kind: 'survey', id: 'survey', rot: 3 });
      s += o20(g);
    }

    // ----- 句21:五個選項 + 頒獎台 + 掉上台的牙刷與汽車(句22 開頭退場) -----
    const o21 = shrink(k, F[2], 1000, 480);
    if (sec === 1 || (sec === 2 && o21)) {
      let g = '';
      const kb = k - e21.brush, kc = k - e21.car;
      OPTS.forEach((_, i) => {
        const ki = k - (e21.opt + 2 * i);
        if (ki >= 0) g += optItem(pal, i, ki, (i === 0 && kb >= 0) || (i === 1 && kc >= 0));
      });
      const kp = k - e21.pod;
      g += Ch.podium({ x: POD.x, y: POD.y, w: POD.w, h: POD.h, pal, u: U, id: 'pod', places: [{ k: kp }, { k: kp }, { k: kp }] });
      const pos = Ch.podiumPos(POD);
      const dropOn = (kk, n, o, tx, ty, id) => {                // 從上方掉到台面,壓扁回彈
        const d = K.drop(kk);
        if (!d) return '';
        return prop(pal, n, o.o, { x: tx, y: ty + d.dy * 140, rot: o.rot, scale: o.sc, sx: d.sx, sy: d.sy, id, enter: !!d.enter });
      };
      g += dropOn(kb, 'toothbrush', { o: {}, rot: -84, sc: 1.15 }, pos[0].x, pos[0].top - 135, 'champ');
      g += dropOn(kc, 'car', { o: {}, rot: 0, sc: 1.4 }, pos[1].x, pos[1].top - 76, 'car');
      s += o21(g);
    }

    // ----- 句22:漱口杯、牙刷、月亮、垃圾桶 -----
    if (sec === 2) {
      // 牙刷:先掉進杯子,再於第二個月亮之後弧線跳進垃圾桶(畫在杯子與垃圾桶之下,下半被蓋住)
      const kf = k - e22.fall;
      let br = null;
      if (kf >= 0) {
        const i = Math.min(kf, FALL_N - 1), q = i / (FALL_N - 1);
        br = { x: BRUSH_IN.x + (BIN_BRUSH.x - BRUSH_IN.x) * q, y: BRUSH_IN.y + (BIN_BRUSH.y - BRUSH_IN.y) * q - 70 * Math.sin(Math.PI * q),
          rot: BRUSH_IN.rot + (BIN_BRUSH.rot - BRUSH_IN.rot) * q + 90 * Math.sin(Math.PI * q), enter: false };
      } else if (k - e22.brush >= 0) {
        const d = K.drop(k - e22.brush);
        br = { x: BRUSH_IN.x, y: BRUSH_IN.y + d.dy * 200, rot: BRUSH_IN.rot, sx: d.sx, sy: d.sy, enter: !!d.enter };
      }
      if (br) s += prop(pal, 'toothbrush', {}, { x: br.x, y: br.y, rot: br.rot, scale: BRUSH_IN.sc, sx: br.sx, sy: br.sy, id: 'champ', enter: br.enter });
      const kcup = k - e22.cup;
      if (kcup >= 0) s += Ch.sheet(cup(pal), { x: CUP.x, y: CUP.y, u: U, k: kcup, kind: 'cup', id: 'cup' });
      MOON.forEach((m, i) => {
        const km = k - (i ? e22.m2 : e22.m1);
        if (km < 0) return;
        const p = K.pop(km);
        s += prop(pal, 'moon', {}, { x: m.x, y: m.y, rot: m.rot, scale: MOON_SC, sx: p, sy: p, id: 'moon' + i, enter: km < 2 });
      });
      const kbin = k - e22.bin;
      if (kbin >= 0) {
        const p = K.pop(kbin);
        s += prop(pal, 'bin', {}, { x: BIN.x, y: BIN.y, scale: BIN.sc, sx: p, sy: p, id: 'bin', enter: kbin < 2 });
      }
    }

    // ----- 右上「?」記號:沿用上一場,開場即在;句22 後段彈出 -----
    s += Ch.triviaMark({ u: U, kOut: k >= e22.out && sec === 2 ? k - e22.out : -1 });
    return K.wrap(pal, s);
  }

  const Scene = { name: 't_brush_b', dur: 14.8, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
