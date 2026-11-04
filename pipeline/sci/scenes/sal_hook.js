/* salary 場景 sal_hook(句 1–5)開場。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–4。
 * 版面沿用 PropsSalary.RANK_LAYOUT 的鴿子欄(腳底固定、面向右),左上固定來源牌。
 * 句1:鴿子 think、拿薪資袋;頭上冒思考泡(兩顆小泡 → 雲朵,內有模糊數字),「?」牌彈在泡角。
 * 句2:思考泡縮掉;手機(Dcard 貼文,不畫商標)句首彈入、「Dcard 貼文」來源牌;詞「台大」學士帽小圖彈入;詞「有人覺得」同學對話泡「年薪一百多萬的公司 不用考慮」。
 * 句3:原 PO 泡(黃)「一百萬也願意做」句首彈入;詞「你是不是」虛線泡「你是不是家裡很有錢?」彈入、鴿子 surprised(shock 驚跳後留 surprised)。
 * 句4:薪資袋縮掉、鴿子 angry 並捲袖子(翅膀每 2 格交替抬放)。
 * 句5:手機、帽、泡與來源牌整組縮掉、資料夾「主計總處」(底邊固定)彈入;詞「主計總處」前蓋下移(4 格)打開、排名表彈出、薪資段來源牌彈入;
 *     詞「算出來」(不早於打開後 6 格)墨底黃字「?」牌彈在表上,之後靜止,位置與大小同片頭(intro)的「?」牌:中心 (1119,567)、邊長 280、u=2、旋轉 3°。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSalary || require('../props_salary.js'),
    PT = Wn.PropsTurtle || require('../props_turtle.js');
  const RL = PS.RANK_LAYOUT, U = 1.4, PU = RL.pigeon.scale;
  const DEF = [
    { start: 0.0, end: 2.79, text: '你一年賺多少?先在心裡偷偷想一下。' },
    { start: 2.91, end: 10.06, text: '有一個台大研究所的學生在 Dcard 發文,說同學聊到找工作,有人覺得年薪只有一百多萬的公司根本不用考慮。' },
    { start: 10.18, end: 16.115, text: '發文的人說年薪一百萬的工作他也願意做,結果被同學笑,你是不是家裡很有錢才講得出這種話。' },
    { start: 16.235, end: 19.07, text: '我第一眼看到也覺得這位同學有點欠罵。' },
    { start: 19.19, end: 24.915, text: '可是年薪一百萬在台灣排第幾,主計總處每年都會算,算出來那位同學其實沒講錯多少。' }];
  const f = (x) => +(+x).toFixed(2);
  const EXIT = [0.7, 0.35];                                     // 縮掉:2 格後消失
  const THINK = { x: 760, y: 290, dots: [[330, 462, 16], [410, 415, 26]], q: { x: 1040, y: 160, size: 110 } };
  const SLIP = { x: 385, y: 690, box: 190, rot: 8 };
  const PHONE = { x: 800, y: 450, s: 3.2, rot: -2 };
  const CAP = { x: 420, y: 270, box: 270, rot: -8 };
  const BUB = { fs: 56, b1: { x: 1400, y: 215 }, b2: { x: 1390, y: 470 }, b3: { x: 1400, y: 685 } };
  const FOLD = { x: 739, w: 760, backTop: 340, bot: 826, cx: 1119, tab: [739, 296, 280], label: { x: 905, y: 770, fs: 56 } };
  const FRONT_TOP = [380, 440, 500, 560, 585];                  // 蓋下移的格序(-1 = 未開 = 第 0 項)
  const TABLE = { x: 1119, y: 395, w: 500, h: 410, rot: -1 };
  const QMARK = { x: 1119, y: 567, size: 280, rot: 3, u: 2 };   // 與 intro.js 的 wordmarkPos 第 6 張牌一致

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || d.text };
    });
  }
  // 詞的起始字索引 ÷ 句長 × 句長秒數 + start → 第幾格
  const wordK = (l, w) => { const i = Math.max(0, l.text.indexOf(w)); return K.frame(l.start + i / l.text.length * (l.end - l.start)); };

  const rect = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const rectN = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke="none"/>`;
  const circN = (x, y, r, fill) => `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${fill}" stroke="none"/>`;
  const text = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  // 以 (cx,cy) 為中心縮放一組已畫好的紙片(縮掉、整組彈入用)
  const zoom = (svg, cx, cy, s) => (s <= 0 ? '' : `<g transform="translate(${f(cx)} ${f(cy)}) scale(${f(s)}) translate(${f(-cx)} ${f(-cy)})">${svg}</g>`);
  const zoomOut = (svg, cx, cy, kOut) => (kOut < 0 ? svg : kOut >= EXIT.length ? '' : zoom(svg, cx, cy, EXIT[kOut]));
  // 以絕對 px 座標畫的紙片(不彈入;彈入由 zoom 包)
  const absSheet = (content, id, kind) => Ch.sheet(content, { x: 0, y: 0, u: U, kind: kind || 'sheet', id, wide: true });

  // 鴿子:idle 呼吸、面向右;expr 為名稱或表情物件;extra 覆寫欄位
  function pigeonPose(k, expr, extra) {
    const p = K.clip('idle', k), e = typeof expr === 'string' ? K.P.EXPR[expr] : expr;
    return Object.assign({}, p, e, { lid: Math.max(e.lid, p.lid > 0.5 ? p.lid : 0), flip: 1 }, extra || {});
  }
  // 驚跳:shock 片段但翅膀收小、尾巴不擺(原本會超出左側 80px 安全邊界)
  function shockPose(i) {
    const p = K.clip('shock', i);
    return Object.assign({}, p, { flip: 1, wing: p.wing * 0.4, wlen: 1, tail: 0 });
  }
  const ANGRY = { lid: 0.45, lidTilt: -18, pdx: -3, pdy: 5, ps: 1, beak: 0 };

  // 句1:思考泡(kk = 出現後第幾格):兩顆小泡 → 雲朵(內為模糊數字)→ 「?」牌
  function thought(pal, kk) {
    let s = '';
    THINK.dots.forEach((d, i) => {
      s += Ch.sheet(`<circle cx="0" cy="0" r="${d[2]}" fill="${K.PAPER}" stroke="${K.INK}" stroke-width="5"/>`,
        { x: d[0], y: d[1], u: U, k: kk - i, kind: 'bubble', id: 'td' + i });
    });
    const C = [[-210, 15, 105], [-90, -30, 125], [90, -30, 120], [215, 15, 100], [0, 40, 115]];
    let c = '<filter id="salBlur" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="9"/></filter>';
    C.forEach((o) => { c += circN(o[0], o[1], o[2] + 7, K.INK); });
    C.forEach((o) => { c += circN(o[0], o[1], o[2], K.PAPER); });
    c += `<g filter="url(#salBlur)">${text('??? 萬', 0, 15, 150, K.INK)}</g>`;
    s += Ch.sheet(c, { x: THINK.x, y: THINK.y, rot: -1, u: U, k: kk - 2, kind: 'bubble', id: 'think' });
    const q = K.pop(kk - 5);
    if (q > 0) s += K.tile('?', { x: THINK.q.x, y: THINK.q.y, size: THINK.q.size, rot: 8, u: U, fill: K.INK, ink: K.YELLOW, sx: q, sy: q, id: 'tq', enter: kk - 5 < 2 });
    return s;
  }

  // 手機貼文(Dcard,不畫商標):手機外框加灰色假字的貼文畫面
  function phoneContent(pal) {
    const C = PT.C;
    let c = PT.LIST.phone.fn(pal, { screen: K.PAPER });
    c += circN(-26, -62, 9, pal.main) + rectN(-12, -68, 30, 6, C.greyD) + rectN(-12, -58, 20, 5, C.greyL);
    c += rectN(-32, -42, 64, 8, K.INK) + rectN(-32, -28, 50, 8, K.INK);
    [[-8, 64], [4, 62], [16, 40]].forEach((r) => { c += rectN(-32, r[0], r[1], 6, C.greyL); });
    c += rectN(-34, 34, 68, 2, C.greyL);
    [[46, 40], [60, 52]].forEach((r) => { c += circN(-26, r[0], 6, pal.pad) + rectN(-14, r[0] - 3, r[1], 6, C.greyL); });
    return `<g transform="scale(${PHONE.s})" stroke-width="${f(4 * U / PHONE.s)}">${c}</g>`;
  }

  // 資料夾:返回 {main:背板+前板+標籤(整組以底邊中心彈入), table}
  function folder(pal, kk, kOpen) {
    const C = PS.C, r = FOLD, ft = FRONT_TOP[Math.max(0, Math.min(FRONT_TOP.length - 1, kOpen))];
    let back = `<polygon points="${r.tab[0]},${r.backTop} ${r.tab[0]},${r.tab[1] + 14} ${r.tab[0] + 14},${r.tab[1]} ${r.tab[0] + r.tab[2] - 24},${r.tab[1]}` +
      ` ${r.tab[0] + r.tab[2]},${r.backTop}" fill="${C.kraftD}"/>` + rect(r.x, r.backTop, r.w, r.bot - r.backTop, C.kraftD);
    let front = rect(r.x, ft, r.w, r.bot - ft, C.kraft) + rectN(r.x, ft, r.w, 8, C.kraftD);
    const pl = Ch.plate('主計總處', r.label.fs, { fill: K.PAPER });
    front += `<g transform="translate(${r.label.x} ${r.label.y})">${pl.svg}</g>`;
    return { back: absSheet(back, 'fback', 'folder'), front: absSheet(front, 'ffront', 'folder') };
  }

  // 排名表(中心在原點):標題色帶「薪資排名」+ 五列灰色假資料(不揭曉數字)
  function tableContent(pal) {
    const w = TABLE.w, h = TABLE.h, C = PT.C;
    let c = rect(-w / 2, -h / 2, w, h, K.PAPER) + rectN(-w / 2, -h / 2, w, 100, pal.main) + text('薪資排名', 0, -h / 2 + 50, 60, pal.onMain);
    [300, 250, 330, 220, 270].forEach((bw, i) => {
      const y = -52 + i * 62;
      c += circN(-200, y, 18, pal.main) + rectN(-165, y - 12, bw, 24, C.greyL);
    });
    return c;
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 135 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const kCap = Math.max(wordK(L[1], '台大'), F[1] + 2), kB1 = Math.max(wordK(L[1], '有人覺得'), kCap + 3), kB3 = Math.max(wordK(L[2], '你是不是'), F[2] + 3);
    const kOpen = Math.max(wordK(L[4], '主計總處'), F[4] + 4), kQ = Math.max(wordK(L[4], '算出來'), kOpen + 6);
    const P = RL.pigeon;
    let s = '';

    // 句5:資料夾與排名表(畫在最底層)
    if (k >= F[4]) {
      const fd = folder(pal, k - F[4], k >= kOpen ? k - kOpen : -1);
      s += zoom(fd.back, FOLD.cx, FOLD.bot, K.pop(k - F[4]));
      if (k >= kOpen) s += Ch.sheet(tableContent(pal), { x: TABLE.x, y: TABLE.y, rot: TABLE.rot, u: U, k: k - kOpen, kind: 'sheet', id: 'table' });
      s += zoom(fd.front, FOLD.cx, FOLD.bot, K.pop(k - F[4]));
      if (k >= kOpen) s += Ch.srcTag(RL.src.text, { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, k: k - kOpen, id: 'src2' });
      if (k >= kQ) {
        const q = K.pop(k - kQ);
        s += K.tile('?', { x: QMARK.x, y: QMARK.y, size: QMARK.size, rot: QMARK.rot, u: QMARK.u, fill: K.INK, ink: K.YELLOW, sx: q, sy: q, id: 'wq', enter: k - kQ < 2 });
      }
    }

    // 句2–4:手機、帽、泡與來源牌(句5 起整組縮掉)
    if (k >= F[1] && k < F[4] + EXIT.length) {
      let g = Ch.sheet(phoneContent(pal), { x: PHONE.x, y: PHONE.y, rot: PHONE.rot, u: U, k: k - F[1], kind: 'phone', id: 'phone' });
      g += Ch.srcTag('Dcard 貼文', { x: RL.src.x, y: RL.src.y, anchor: 'left', fs: RL.src.fs, pal, k: k - F[1], id: 'src' });
      if (k >= kCap) g += Ch.sheet(Ch.icon({ svg: PS.LIST.gradcap.fn(pal), w: PS.LIST.gradcap.w, h: PS.LIST.gradcap.h }, 0, 0, CAP.box),
        { x: CAP.x, y: CAP.y, rot: CAP.rot, u: U, k: k - kCap, kind: 'prop', id: 'cap' });
      g += Ch.bubble(['年薪一百多萬的公司', '不用考慮'], { x: BUB.b1.x, y: BUB.b1.y, fs: BUB.fs, tail: 'bl', rot: -1.5, k: k - kB1, id: 'b1' });
      g += Ch.bubble('一百萬也願意做', { x: BUB.b2.x, y: BUB.b2.y, fs: BUB.fs, tail: 'bl', rot: 1, fill: K.YELLOW, k: k - F[2], id: 'b2' });
      g += Ch.bubble('你是不是家裡很有錢?', { x: BUB.b3.x, y: BUB.b3.y, fs: BUB.fs, tail: 'bl', rot: -1, dashed: true, k: k - kB3, id: 'b3' });
      s += zoomOut(g, 1000, 480, k - F[4]);
    }

    // 句1:思考泡(句2 起縮掉)
    if (k < F[1] + EXIT.length) s += zoomOut(thought(pal, k - F[0]), 700, 330, k - F[1]);

    // 鴿子與腳下襯底
    s += K.ground({ x: P.x + 20, y: P.y + 4, w: 300, h: 22, u: U, pal });
    let pose;
    if (k < F[1]) pose = pigeonPose(k, 'think');
    else if (k < F[2]) pose = pigeonPose(k, 'look');
    else if (k < F[3]) pose = k < kB3 ? pigeonPose(k, 'look') : k - kB3 < 8 ? shockPose(k - kB3) : pigeonPose(k, 'surprised');
    else if (k < F[4]) pose = pigeonPose(k, ANGRY, { wing: Math.floor((k - F[3]) / 2) % 2 ? 150 : 120, wlen: 1.15, headRot: 2 });
    else pose = pigeonPose(k, 'look');
    s += K.pigeon(pose, { x: P.x, y: P.y, scale: PU, id: 'main', enter: false });

    // 句1–3:鴿子手上的薪資袋(句4 起縮掉;跟著驚跳離地)
    if (k < F[3] + EXIT.length) {
      const hop = (pose.hop || 0) * PU;
      s += zoomOut(Ch.sheet(Ch.icon({ svg: PS.LIST.payslip.fn(pal), w: PS.LIST.payslip.w, h: PS.LIST.payslip.h }, 0, 0, SLIP.box),
        { x: SLIP.x, y: SLIP.y - hop, rot: SLIP.rot, u: U, k: k - F[0], kind: 'prop', id: 'slip' }), SLIP.x, SLIP.y, k - F[3]);
    }
    return K.wrap(pal, s);
  }

  const Scene = { name: 'sal_hook', dur: 25, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
