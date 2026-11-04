/* snack 場景 s_cpi_b(句 29–32)主計總處外食費細項中段(接 s_cpi_a 結尾)。render(t, params);params: {hue, dur, lines:[{idx,text,start,end}]},場景內索引 0–3。
 * 開場:畫面同 s_cpi_a 結尾(幼兒園、午餐灰條、咖啡飲料黃條,x 430–1840、max 40;右上來源牌、右下「自算」牌;討論榜不帶過來,鴿子仍在左下)。
 * 開頭:兩條灰條退場(3 格),咖啡飲料條落到最下一列(第 5 列);之後由下而上一列一列加條(共 6 列版面:y 116 起、列距 116;最上一列留給來源牌)。
 * 句29:中式米食 28.1%(滷肉飯圖)在句首後 0.6 秒出現;中式麵食 30.1%(水餃、牛肉麵圖)在「水餃」詞出現;圖貼在長條起點。
 * 句30:官方名稱大牌(蓋在圖表上)句首彈入;鴿子在「括號」詞指向括號那行(黃底)。
 * 句31:大牌退場、鴿子收手;其他家外食物 30.6%(攤車圖)長出來。
 * 句32:上方三條各上移一列(2 格滑動),西式速食 23.7%(漢堡圖)插在咖啡飲料之上;鴿子歪頭。最後事件後靜止到 dur。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const K = Wn.Kit || require('../kit.js'), Ch = Wn.Charts || require('../charts.js'), PS = Wn.PropsSnack || require('../props_snack.js');
  const TXT = ['滷肉飯這類算在中式米食,漲了 28.1%,水餃和牛肉麵算在中式麵食,是 30.1% 左右。',
    '雞排、臭豆腐這種攤子上的東西,官方的名字叫其他家外食物,括號裡還很認真地寫了鹽酥雞、蚵仔麵線、臭豆腐等。',
    '這一項漲了 30.6%,夜市的主力差不多都在這裡。', '對了,西式速食只漲 23.7% 而已,這十年漢堡薯條漲得比鹽酥雞還少。'];
  const DEF = [{ start: 0.08, end: 7.61 }, { start: 7.73, end: 15.84 }, { start: 15.96, end: 19.735 }, { start: 19.855, end: 25.41 }];
  const U = 1.43, PU = 1.36;                          // 紙片倍率、鴿子倍率(高約 309px)
  const FOOT = { x: 245, y: 820 };
  const BARS = { x: 430, w: 1410, rowH: 104, gap: 12, labelW: 590, y0: 116, pitch: 116 };   // 與 s_cpi_a 同:x 430、列高 104、標籤欄 590
  const slotTop = (s) => BARS.y0 + s * BARS.pitch;
  const EXIT = [3, 1, 0];                             // 退場 = 彈入逆序(k 索引)
  const SHIFT = [0, 40, 90, 116];                     // 上移一列的逐格位移(px)
  const OFF = { name: '其他家外食物', note: '（鹽酥雞、蚵仔麵線、臭豆腐等）', fs1: 100, fs2: 72, h: 250, y: 555 };
  const ICON_BOX = 92;
  const f = (x) => +(+x).toFixed(2);
  const R = (x, y, w, h, fill) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="${fill}" stroke-linejoin="miter"/>`;
  const T = (s, x, y, size, fill) => `<text x="${f(x)}" y="${f(y)}" font-family="GenSen" font-size="${size}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;
  const DUM = { label: '', value: 19.3, text: '19.3%', k: -1 };     // 讓每次單條呼叫的長條最大長度與 s_cpi_a 相同(數值牌字寬取最大者)

  function lines(params) {
    const L = (params && params.lines) || [];
    return DEF.map((d, i) => {
      const l = L[i] || {};
      return { start: l.start != null && isFinite(l.start) ? +l.start : d.start, end: l.end != null && isFinite(l.end) ? +l.end : d.end,
        text: l.text || TXT[i] };
    });
  }

  // 一條長條(單獨呼叫 hbars 以便各自上下移動):top = 該列上緣 y
  function bar(pal, b, top, id) {
    return Ch.hbars({ pal, x: BARS.x, y: top, w: BARS.w, rowH: BARS.rowH, gap: BARS.gap, labelW: BARS.labelW, fs: 60, numFs: 72, max: 40, id, bars: [b, DUM] });
  }
  // 食物小圖:貼在長條起點(標籤欄右緣 + gx 之後),icons = [LIST 名稱…]
  function foodIcons(pal, names, top, k, id) {
    let s = '';
    names.forEach((n, i) => {
      const L = PS.LIST[n], ic = { svg: L.fn(pal, { sign: '' }), w: L.w, h: L.h };
      s += Ch.sheet(Ch.icon(ic, 0, 0, ICON_BOX), { x: BARS.x + BARS.labelW + 18 + 12 + ICON_BOX / 2 + i * (ICON_BOX + 8), y: top + BARS.rowH / 2, u: U,
        k, kind: 'icon', id: id + i });
    });
    return s;
  }

  function pigeonPose(k, F, kBr, base) {
    const lean = { headDx: -10, headRot: -6, headDy: 2 };
    let p;
    if (k < 7) p = Object.assign(K.expr(base, 'doubt'), lean);            // 接 s_cpi_a 結尾的前傾看
    else if (k < kBr) p = K.expr(base, 'normal');
    else if (k < F[2]) p = K.clip('point', Math.min(k - kBr, 5));         // 句30:指向括號
    else if (k < F[2] + 3) p = K.clip('point_out', k - F[2]);             // 句31:收手
    else if (k < F[3]) p = K.expr(base, 'normal');
    else if (k < F[3] + 6) p = K.expr(K.clip('tilt', k - F[3]), 'look');  // 句32:歪頭
    else p = K.expr(base, 'normal');
    return Object.assign({}, p, { flip: 1 });
  }

  function render(t, params) {
    const pal = K.palette((params || {}).hue == null ? 24 : params.hue), k = K.frame(t), L = lines(params);
    const F = L.map((l) => K.frame(l.start));
    const tK = (i, w) => K.frame(L[i].start + Math.max(0, L[i].text.indexOf(w)) / L[i].text.length * (L[i].end - L[i].start));
    const kRice = 6, kNoodle = tK(0, '水餃'), kBr = tK(1, '括號'), kOut = F[2], kOther = F[2] + 3, kShift = F[3] + 1, kFast = kShift + 2;
    const sh = () => (k < kShift ? 0 : SHIFT[Math.min(k - kShift, 3)]);        // 上方三條的上移位移
    let s = '';

    // 咖啡飲料(黃):開頭在第 3 列,灰條退場後落到第 5 列
    if (k < 3) s += bar(pal, { label: '在外點用之咖啡飲料', value: 19.3, text: '19.3%', hi: true }, slotTop(3), 'cpiC');
    else s += bar(pal, { label: '在外點用之咖啡飲料', value: 19.3, text: '19.3%', hi: true, k: k - 3 }, slotTop(5), 'cpiC5');
    if (k < 3) {                                                                 // 兩條灰條退場
      s += bar(pal, { label: '學生營養午餐', value: 17.5, text: '17.5%', grey: true, k: EXIT[k] }, slotTop(4), 'cpiG1');
      s += bar(pal, { label: '幼兒園點心費', value: 7.2, text: '7.2%', grey: true, k: EXIT[k] }, slotTop(5), 'cpiG2');
    }
    // 由下而上加條(未上移時:米食第 4 列、麵食第 3 列、其他第 2 列;句32 各上移一列)
    if (k >= kRice) {
      const top = slotTop(4) - sh(), q = k - kRice;
      s += bar(pal, { label: '中式米食', value: 28.1, text: '28.1%', k: q }, top, 'cpiR');
      s += foodIcons(pal, ['braisedPorkRice'], top, q, 'icR');
    }
    if (k >= kNoodle) {
      const top = slotTop(3) - sh(), q = k - kNoodle;
      s += bar(pal, { label: '中式麵食', value: 30.1, text: '30.1%', k: q }, top, 'cpiN');
      s += foodIcons(pal, ['dumplings', 'beefNoodle'], top, q, 'icN');
    }
    if (k >= kOther) {
      const top = slotTop(2) - sh(), q = k - kOther;
      s += bar(pal, { label: '其他家外食物', value: 30.6, text: '30.6%', k: q }, top, 'cpiO');
      s += foodIcons(pal, ['stall'], top, q, 'icO');
    }
    if (k >= kFast) {
      const top = slotTop(4), q = k - kFast;
      s += bar(pal, { label: '西式速食', value: 23.7, text: '23.7%', k: q }, top, 'cpiF');
      s += foodIcons(pal, ['burger'], top, q, 'icF');
    }

    // 句30:官方名稱大牌(蓋在圖表上),句31 開頭退場
    if (k >= F[1] && k < F[2] + 3) {
      const pk = k < F[2] ? k - F[1] : EXIT[k - F[2]];
      const w = Ch.tw(OFF.note, OFF.fs2) + 110, h = OFF.h;
      if (w > 1230) throw new Error('s_cpi_b 大牌過寬:' + w);
      const chip = 24, c = R(-w / 2, -h / 2, w, h, K.PAPER) + R(-w / 2, -h / 2, chip, h, pal.main).replace('stroke-linejoin="miter"', 'stroke="none"') +
        T(OFF.name, chip / 2, -58, OFF.fs1, K.INK) + R(-w / 2 + chip + 20, 10, w - chip - 40, 100, K.YELLOW) + T(OFF.note, chip / 2, 60, OFF.fs2, K.INK);
      s += Ch.sheet(c, { x: 1215, y: OFF.y, u: U, k: pk, kind: 'sheet', id: 'official', wide: true });
    }

    s += Ch.srcTag('主計總處 消費者物價指數', { pal, x: 1830, y: 120, anchor: 'right', k: 99, id: 'src' });
    const sp = Ch.plate('自算', 56, { fill: K.YELLOW, padX: 0.8 });
    s += Ch.sheet(sp.svg, { x: 1740, y: 780, u: U, k: 99, kind: 'src', id: 'self', wide: true });

    s += K.ground({ x: FOOT.x + 20, y: FOOT.y + 4, w: 340, h: 22, u: U, pal });
    s += K.pigeon(pigeonPose(k, F, kBr, K.clip('idle', k)), { x: FOOT.x, y: FOOT.y, scale: PU, id: 'main' });
    return K.wrap(pal, s);
  }

  const Scene = { name: 's_cpi_b', dur: 25.5, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
