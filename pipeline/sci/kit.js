/* ChannelC:場景共用工具(剪紙拼貼)。純函式,不依賴 DOM;需先載入 pigeon.js。
 * 畫面橫式 1920x1080(直式 1080x1920 見 LAYOUT)。頓感:時間一律先取整格(frame/step,每秒 10 格)再算,不補間。
 * 每個物件是一片紙(paper):紙白描邊 4 單位、硬邊陰影;單位 = 鴿子的 300 座標,
 * 以 scale(下稱 u)等比放大,同一場景的紙片共用鴿子的 u。
 * 外層 <g> 帶 data-k / data-id / data-u / data-enter(進場中),供舞台量外框做檢查。
 * 禁用 Math.random / Date / 計時器 / CSS 動畫;要亂數用 hash(n)。 */
(function () {
  const P = (typeof window !== 'undefined' && window.Pigeon) || require('./pigeon.js');
  // ---------- 版面常數(橫/直兩組) ----------
  // margin = [左,上,右,下] 紙片外框離畫面邊的下限;sub = 字幕(make_film 的 ASS 與此一致):cy 墨跡垂直中心、cx 水平中心、
  // fs libass Fontsize、maxW 每段字幕上限(全形字);title = 標題字級(字牌邊長 tile = 字標第二列四張要放進左右邊界內,直式因此比橫式小;副標 labelFs 直式 1.25 倍);pigeon = 吉祥物預設 {x,y 腳底落點,u 倍率}。
  // 橫式 = 既有成片數值,不可改。直式(Shorts 1080x1920)的數值是【判】,待 Shorts 實測修正:
  // 右邊界 ≥140(避開右側按鈕)、下邊界 ≥320(避開標題區),字級約橫式 1.25 倍,字幕帶在下方約 1/4 以上,吉祥物置中偏下。
  const LAYOUT = {
    landscape: { W: 1920, H: 1080, SAFE: 80, margin: [80, 80, 80, 80], SUB_BAND: [850, 1000],
      sub: { cx: 960, cy: 924, fs: 85, maxW: 18 }, title: { tile: 280, labelFs: 60 }, pigeon: { x: 1621, y: 800, u: 2 } },
    portrait: { W: 1080, H: 1920, SAFE: 80, margin: [80, 120, 140, 320], SUB_BAND: [1320, 1480],
      sub: { cx: 535, cy: 1400, fs: 106, maxW: 11 }, title: { tile: 200, labelFs: 75 }, pigeon: { x: 540, y: 1260, u: 2.5 } },
  };
  // 依 window.__PARAMS.portrait(render_clip.py 注入)選組;Node 下預設橫式
  const PORTRAIT = typeof window !== 'undefined' && !!(window.__PARAMS && window.__PARAMS.portrait);
  const L = LAYOUT[PORTRAIT ? 'portrait' : 'landscape'];
  const W = L.W, H = L.H, FPS = P.POSE_FPS, SAFE = L.SAFE, SUB_BAND = L.SUB_BAND;
  const YELLOW = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7';
  // pap:鴿子與方形紙片;papw:扁長紙片(濾鏡範圍以外框百分比計,扁的要放寬)
  const DEFS = P.PAP_DEFS + '<filter id="papw" x="-30%" y="-150%" width="160%" height="400%">' +
    '<feDropShadow dx="5" dy="6" stdDeviation="0" flood-color="#1B1414" flood-opacity=".45"/></filter>';
  const f = (x) => +(+x).toFixed(2);

  // ---------- 時間與亂數 ----------
  const frame = (t) => Math.floor(t * FPS + 1e-6);          // 第幾格
  const step = (t) => frame(t) / FPS;                        // 取整格後的秒數
  const hash = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

  // ---------- 配色 ----------
  function hslLum(h, s, l) {
    s /= 100; l /= 100;
    const a = s * Math.min(l, 1 - l);
    const ch = (n) => {
      const k = (n + h / 30) % 12, c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * ch(0) + 0.7152 * ch(8) + 0.0722 * ch(4);
  }
  function palette(h) {
    h = h == null ? 46 : +h;
    return {
      h, bg: `hsl(${h} 35% 93%)`, pad: `hsl(${h} 60% 82%)`, main: `hsl(${h} 85% 55%)`, text: `hsl(${h} 90% 40%)`,
      onMain: hslLum(h, 85, 55) > 0.19 ? INK : PAPER,        // 主色牌上的字:取對比高的
      yellow: YELLOW, ink: INK, paper: PAPER,
    };
  }

  // ---------- 逐格表 ----------
  // 彈入:k 為出現後第幾格(0 起);k<0 尚未出現
  const POP = [0.6, 1.15, 0.95, 1];
  const pop = (k) => (k < 0 ? 0 : POP[Math.min(k, POP.length - 1)]);
  // 掉落:dy 為距離落點的比例(負值在上方),sx/sy 壓扁回彈(底邊固定)
  const DROP = [
    { dy: -0.62, sx: 0.94, sy: 1.08, enter: true }, { dy: -0.24, sx: 0.92, sy: 1.12, enter: true },
    { dy: 0, sx: 1.22, sy: 0.72 }, { dy: -0.04, sx: 0.93, sy: 1.1 }, { dy: 0, sx: 1.05, sy: 0.95 },
    { dy: 0, sx: 1, sy: 1 },
  ];
  const drop = (k) => (k < 0 ? null : DROP[Math.min(k, DROP.length - 1)]);

  // ---------- 紙片 ----------
  // content 以「單位」繪製;o: {x,y,rot,scale,sx,sy,k,id,enter,wide}
  function paper(content, o) {
    o = o || {};
    const s = o.scale == null ? 1 : o.scale, sx = o.sx == null ? 1 : o.sx, sy = o.sy == null ? 1 : o.sy;
    const attrs = `data-k="${o.k || 'paper'}" data-id="${o.id || ''}" data-u="${f(s)}"` + (o.enter ? ' data-enter="1"' : '');
    return `<g ${attrs} transform="translate(${f(o.x || 0)} ${f(o.y || 0)}) rotate(${f(o.rot || 0)}) scale(${f(s * sx)} ${f(s * sy)})"` +
      ` filter="url(#${o.wide ? 'papw' : 'pap'})" stroke="${PAPER}" stroke-width="4" stroke-linejoin="round">${content}</g>`;
  }

  const txt = (s, size, fill) => `<text x="0" y="0" font-family="GenSen" font-size="${f(size)}" text-anchor="middle"` +
    ` dominant-baseline="central" fill="${fill}" stroke="none">${s}</text>`;

  // 單字紙牌:o: {x,y,size(px),rot,u,fill,ink,sx,sy,anchor:'center'|'bottom',id,enter}
  function tile(ch, o) {
    const u = o.u || o.size / 100, a = o.size / u;
    const sx = o.sx == null ? 1 : o.sx, sy = o.sy == null ? 1 : o.sy;
    const y = o.y + (o.anchor === 'bottom' ? (1 - sy) * o.size / 2 : 0);
    const c = `<rect x="${f(-a / 2)}" y="${f(-a / 2)}" width="${f(a)}" height="${f(a)}" fill="${o.fill || YELLOW}" stroke-linejoin="miter"/>` +
      txt(ch, a * 0.74, o.ink || INK);
    return paper(c, { x: o.x, y, rot: o.rot, scale: u, sx, sy, k: 'tile', id: o.id, enter: o.enter });
  }

  // 紙白底條加墨色字(副標):o: {x,y,fs(px),u,rot,id}
  function label(s, o) {
    const u = o.u || 1, fs = o.fs / u, w = s.length * fs + fs * 1.1, h = fs * 1.62;
    const c = `<rect x="${f(-w / 2)}" y="${f(-h / 2)}" width="${f(w)}" height="${f(h)}" fill="${PAPER}" stroke-linejoin="miter"/>` + txt(s, fs, INK);
    return paper(c, { x: o.x, y: o.y, rot: o.rot, scale: u, k: 'label', id: o.id, wide: true });
  }

  // 腳下的襯底紙片:o: {x,y(中心),w,h(px),u,pal}
  const GROUND = [[-0.5, 0.1], [-0.42, -0.5], [0.38, -0.42], [0.5, -0.05], [0.44, 0.5], [-0.4, 0.42]];
  function ground(o) {
    const u = o.u || 1, pts = GROUND.map(([x, y]) => `${f(x * o.w / u)},${f(y * o.h / u)}`).join(' ');
    return paper(`<polygon points="${pts}" fill="${o.pal.pad}"/>`, { x: o.x, y: o.y, scale: u, k: 'ground', id: o.id, wide: true });
  }

  // ---------- 鴿子 ----------
  const clip = (name, i) => { const c = P.CLIPS[name], n = c.frames.length; return c.frames[c.loop ? ((i % n) + n) % n : Math.max(0, Math.min(i, n - 1))]; };
  const expr = (pose, name) => Object.assign({}, pose, P.EXPR[name]);
  // o: {x,y(腳底落點 px),scale,enter}
  function pigeon(pose, o) {
    const s = o.scale, fx = pose.flip ? 132 : 168;
    return `<g data-k="pigeon" data-id="${o.id || ''}" data-u="${f(s)}"${o.enter ? ' data-enter="1"' : ''}` +
      ` transform="translate(${f(o.x - fx * s)} ${f(o.y - 280 * s)}) scale(${f(s)})">${P.pigeonSVG(pose)}</g>`;
  }

  // ---------- 字標 ----------
  const WORD = ['知', '道', '又', '怎', '樣'], ROTS = [-2.5, 1.5, -1, 3, -2, 3];
  // 六張牌的中心 x(o: {cx,size,gap})
  const wordmarkXs = (o) => ROTS.map((_, i) => o.cx + (i - 2.5) * (o.size + (o.gap || 0)));
  // 六張牌的中心 {x,y}。單列:同 wordmarkXs;rows:2 → 第一列「範例」、第二列「頻道」,左對齊,
  // cx 為第二列(四張)的水平中心,cy 為兩列合計的垂直中心,列距 = 牌邊長 × 1.12
  function wordmarkPos(o) {
    if (o.rows !== 2) return wordmarkXs(o).map((x) => ({ x, y: o.cy }));
    const pitch = o.size + (o.gap || 0), x0 = o.cx - 1.5 * pitch, rp = o.size * 1.12;
    return ROTS.map((_, i) => (i < 2 ? { x: x0 + i * pitch, y: o.cy - rp / 2 } : { x: x0 + (i - 2) * pitch, y: o.cy + rp / 2 }));
  }
  // 「ChannelC」五張品牌黃牌逐張彈入(每張隔 1 格)加固定墨底黃字「?」牌。
  // o: {cx,cy,size,gap,u,rows:1|2,soft,q:'pop'|'drop',qAt,dropSeq}:qAt 為「?」出現的秒數(預設接在第五張後);
  // drop 從上方掉下壓扁回彈;dropSeq 為 DROP 表的格序(預設全 6 格),可縮短回彈
  function wordmark(tSince, o) {
    const k0 = frame(tSince), ps = wordmarkPos(o);
    const popOf = (k) => (o.soft == null || k < 0 ? pop(k) : 1 + (pop(k) - 1) * o.soft);   // soft:彈入過衝縮放比例(1=原樣)
    let s = '';
    WORD.forEach((ch, i) => {
      const sc = popOf(k0 - i);
      if (sc > 0) s += tile(ch, { x: ps[i].x, y: ps[i].y, size: o.size, rot: ROTS[i], u: o.u, sx: sc, sy: sc, id: 'w' + i });
    });
    const kq = k0 - (o.qAt == null ? WORD.length : frame(o.qAt));
    const q = { x: ps[5].x, y: ps[5].y, size: o.size, rot: ROTS[5], u: o.u, fill: INK, ink: YELLOW, id: 'wq' };
    if (o.q === 'drop') {
      const d = o.dropSeq ? (kq < 0 ? null : DROP[o.dropSeq[Math.min(kq, o.dropSeq.length - 1)]]) : drop(kq);
      if (d) s += tile('?', Object.assign(q, { y: q.y + d.dy * (q.y + o.size), sx: d.sx, sy: d.sy, anchor: 'bottom', enter: d.enter }));
    } else {
      const sc = popOf(kq);
      if (sc > 0) s += tile('?', Object.assign(q, { sx: sc, sy: sc }));
    }
    return s;
  }

  // 完整 <svg> 內容:defs、底色、紙片
  const wrap = (pal, content) => `<defs>${DEFS}</defs><rect width="${W}" height="${H}" fill="${pal.bg}"/>${content}`;

  const API = { P, W, H, L, LAYOUT, portrait: PORTRAIT, FPS, SAFE, SUB_BAND, YELLOW, INK, PAPER, DEFS, frame, step, hash, palette, pop, drop,
    paper, tile, label, ground, clip, expr, pigeon, wordmark, wordmarkXs, wordmarkPos, wrap };
  if (typeof module !== 'undefined') module.exports = API;
  if (typeof window !== 'undefined') window.Kit = API;
})();
