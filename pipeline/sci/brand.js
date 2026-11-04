/* 「ChannelC」品牌圖(大頭貼、Banner)純函式:Brand.draw(name) 回傳 {w,h,svg}。
 * name: avatar_A | avatar_B | banner_A | banner_B。groups(data-g):bg 底色、deco 裝飾(僅 banner,低不透明)、
 * 其餘為內容(a_char、b_l1、b_l2、logo、sub、flask),make_brand.py 逐組顯示後量墨跡外框。不用亂數,裝飾位置全固定。
 * 字型:GenSen(源泉圓體 Heavy)。色:品牌黃 / 墨 / 紙白(同 kit.js)。 */
(function () {
  const Y = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7', FONT = 'GenSen';
  const f = (n) => Math.round(n * 100) / 100;
  const text = (s, x, y, fs, fill, anchor) =>
    `<text x="${f(x)}" y="${f(y)}" font-family="${FONT}" font-size="${f(fs)}" fill="${fill}" text-anchor="${anchor || 'middle'}" dominant-baseline="central">${s}</text>`;
  // 印章方框:黃色描邊、墨色底,旋轉 rot 度;box = 外緣邊長(含描邊)
  function stamp(cx, cy, box, sw, ch, rot) {
    const s = box - sw;
    return `<g transform="rotate(${rot} ${f(cx)} ${f(cy)})"><rect x="${f(cx - s / 2)}" y="${f(cy - s / 2)}" width="${f(s)}" height="${f(s)}" rx="${f(box * 0.04)}" fill="${INK}" stroke="${Y}" stroke-width="${f(sw)}" stroke-linejoin="round"/>` +
      text(ch, cx, cy + box * 0.01, box * 0.72, Y) + '</g>';
  }
  // 手繪線條:燒瓶(含可選小鬼魂)、鬼魂、問號、符咒外框;皆以中心與尺寸 s 定位
  const ln = (c, w, extra) => `fill="none" stroke="${c}" stroke-width="${f(w)}" stroke-linecap="round" stroke-linejoin="round"${extra || ''}`;
  function ghostPath(cx, cy, g, c, w, fill) {
    const P = (x, y) => `${f(cx + x * g)} ${f(cy + y * g)}`;
    const d = `M ${P(-0.5, 0.6)} L ${P(-0.5, -0.1)} C ${P(-0.5, -0.6)} ${P(0.5, -0.6)} ${P(0.5, -0.1)} L ${P(0.5, 0.6)} ` +
      `Q ${P(0.375, 0.45)} ${P(0.25, 0.6)} Q ${P(0.125, 0.75)} ${P(0, 0.6)} Q ${P(-0.125, 0.45)} ${P(-0.25, 0.6)} Q ${P(-0.375, 0.75)} ${P(-0.5, 0.6)} Z`;
    return `<path d="${d}" ${fill ? `fill="${fill}" stroke="${c}" stroke-width="${f(w)}" stroke-linejoin="round"` : ln(c, w)}/>` +
      `<circle cx="${f(cx - 0.17 * g)}" cy="${f(cy - 0.08 * g)}" r="${f(0.07 * g)}" fill="${fill ? INK : c}"/><circle cx="${f(cx + 0.17 * g)}" cy="${f(cy - 0.08 * g)}" r="${f(0.07 * g)}" fill="${fill ? INK : c}"/>` +
      `<ellipse cx="${f(cx)}" cy="${f(cy + 0.12 * g)}" rx="${f(0.07 * g)}" ry="${f(0.09 * g)}" fill="${fill ? INK : c}"/>`;
  }
  function flask(cx, cy, s, c, w, ghost) {
    const P = (x, y) => `${f(cx + x * s)} ${f(cy + y * s)}`;
    const d = `M ${P(-0.15, -0.5)} L ${P(-0.15, -0.15)} L ${P(-0.45, 0.4)} Q ${P(-0.5, 0.5)} ${P(-0.4, 0.5)} L ${P(0.4, 0.5)} Q ${P(0.5, 0.5)} ${P(0.45, 0.4)} L ${P(0.15, -0.15)} L ${P(0.15, -0.5)}`;
    let o = `<path d="${d}" ${ln(c, w)}/><path d="M ${P(-0.22, -0.5)} L ${P(0.22, -0.5)}" ${ln(c, w)}/>`;
    o += `<path d="M ${P(-0.36, 0.22)} Q ${P(-0.18, 0.14)} ${P(0, 0.22)} Q ${P(0.18, 0.3)} ${P(0.36, 0.22)}" ${ln(c, w * 0.7)}/>`;   // 液面
    if (ghost) o += ghostPath(cx, cy + 0.17 * s, 0.36 * s, ghost, w * 0.8, null);
    else o += `<circle cx="${f(cx - 0.12 * s)}" cy="${f(cy + 0.36 * s)}" r="${f(0.04 * s)}" ${ln(c, w * 0.6)}/><circle cx="${f(cx + 0.1 * s)}" cy="${f(cy + 0.32 * s)}" r="${f(0.06 * s)}" ${ln(c, w * 0.6)}/>`;
    return o;
  }
  // 符咒紙條:直長條紙(下緣鋸齒)、上方小圈、中間彎曲筆畫(不寫字);h = 紙高
  function talisman(cx, cy, h, c, w) {
    const hw = h * 0.2, P = (x, y) => `${f(cx + x * h)} ${f(cy + y * h)}`;
    let o = `<path d="M ${P(-0.2, -0.5)} L ${P(0.2, -0.5)} L ${P(0.2, 0.5)} L ${P(0.1, 0.45)} L ${P(0, 0.5)} L ${P(-0.1, 0.45)} L ${P(-0.2, 0.5)} Z" ${ln(c, w)}/>`;
    o += `<circle cx="${f(cx)}" cy="${f(cy - 0.4 * h)}" r="${f(0.05 * h)}" ${ln(c, w)}/>`;
    o += `<path d="M ${P(-0.12, -0.28)} L ${P(0.12, -0.28)}" ${ln(c, w * 0.8)}/>`;
    o += `<path d="M ${P(-0.1, -0.2)} C ${P(0.16, -0.16)} ${P(-0.16, -0.06)} ${P(0.1, -0.02)}" ${ln(c, w)}/>`;
    o += `<path d="M ${P(0.1, 0.02)} C ${P(-0.16, 0.06)} ${P(0.16, 0.16)} ${P(-0.1, 0.2)}" ${ln(c, w)}/>`;
    o += `<path d="M ${P(0, -0.24)} Q ${P(0.05, 0.05)} ${P(-0.04, 0.34)}" ${ln(c, w * 0.8)}/>`;
    o += `<path d="M ${P(-0.12, 0.36)} Q ${P(0, 0.3)} ${P(0.12, 0.38)}" ${ln(c, w * 0.7)}/>`;
    return o;
  }
  const qmark = (x, y, fs, rot, c) => `<g transform="rotate(${rot} ${x} ${y})">${text('?', x, y, fs, c)}</g>`;
  // 方格紙紋:間距 80,細線
  function grid(W, H, c) {
    let o = '';
    for (let x = 0; x <= W; x += 80) o += `<line x1="${x}" y1="0" x2="${x}" y2="${H}" stroke="${c}" stroke-width="2"/>`;
    for (let y = 0; y <= H; y += 80) o += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="${c}" stroke-width="2"/>`;
    return o;
  }

  const SAFE = { x: 507, y: 508.5, w: 1546, h: 423 };   // YouTube 2560x1440 Banner 全裝置安全區(水平垂直置中)
  const G = (name, inner, extra) => `<g data-g="${name}"${extra || ''}>${inner}</g>`;

  function avatar(name) {
    const W = 800, H = 800, cx = 400, cy = 400;
    let body;
    if (name === 'avatar_A') body = G('a_char', stamp(cx, cy, 450, 28, 'C', -6));
    else {
      const fs = 160, lh = 168;
      const l1 = `<text x="${cx}" y="${cy - lh / 2}" font-family="${FONT}" font-size="${fs}" text-anchor="middle" dominant-baseline="central"><tspan fill="${Y}">不</tspan><tspan fill="${PAPER}">科學</tspan></text>`;
      body = G('b_l1', l1) + G('b_l2', text('頻道', cx, cy + lh / 2, fs, PAPER));
    }
    return { w: W, h: H, svg: G('bg', `<rect width="${W}" height="${H}" fill="${INK}"/>`) + body };
  }

  function banner(name) {
    const W = 2560, H = 1440, left = name === 'banner_B', cy = SAFE.y + SAFE.h / 2;
    const bg = G('bg', `<rect width="${W}" height="${H}" fill="${INK}"/>`);
    // 裝飾:全部落在安全區外,不透明度 ≤ 0.15,位置固定
    const C = PAPER;
    const deco = G('deco',
      grid(W, H, C) +
      flask(250, 230, 230, C, 7, null) + flask(1720, 1215, 150, C, 6, C) +
      qmark(2290, 230, 300, 12, C) + qmark(1010, 215, 150, -10, C) + qmark(330, 1190, 190, 8, C) +
      talisman(2290, 1160, 340, C, 6) + talisman(760, 1200, 240, C, 5) +
      ghostPath(2330, 620, 150, C, 6, null) + ghostPath(1560, 215, 90, C, 5, null) + ghostPath(215, 640, 120, C, 6, null),
      ' opacity="0.13"');
    // Logo:印章「C」+「範例頻道」;fs = 字級,box = 印章邊長
    const fs = left ? 190 : 220, box = left ? 214 : 250, gap = left ? 20 : 24, subFs = left ? 66 : 76;
    const total = box + gap + fs * 5, x0 = left ? SAFE.x + 14 : W / 2 - total / 2;
    const lc = left ? 671 : 665, sc = left ? 857 : 882;
    const logo = G('logo', stamp(x0 + box / 2, lc, box, left ? 12 : 14, 'C', -6) + text('範例頻道', x0 + box + gap, lc, fs, PAPER, 'start'));
    const sx = left ? x0 + 4 : W / 2;
    const sub = G('sub', text('認真研究那些有趣的事', sx, sc, subFs, PAPER, left ? 'start' : 'middle'));
    let extra = '';
    if (left) extra = G('flask', flask(1885, cy + 4, 300, PAPER, 8, Y));
    return { w: W, h: H, svg: bg + deco + logo + sub + extra, safe: SAFE };
  }

  window.Brand = { SAFE, draw: (name) => (name.startsWith('avatar') ? avatar(name) : banner(name)) };
})();
