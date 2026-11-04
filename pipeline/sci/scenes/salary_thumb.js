/* salary 封面(靜態一張,1920x1080),依 channel\發片資料_規則.md §4.1。底:主題色相 H=135 的品牌淺底加一個襯底圓;
 * 物件只有三個:襯底圓、驚訝(表情組最誇張的 surprised)的認真鴿(左,高約畫面 60%+)、千元鈔一疊。
 * 右側 40% 三行字「100萬」(品牌黃)、「贏過八成」(紙白)、「台大卻後半段」(墨字黃底色帶);墨色描邊 12px 加右下陰影。
 * 安全區:四邊 5%;右下角 x>1632 且 y>918 淨空。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const PS = (typeof window !== 'undefined' && window.PropsSalary) || require('../props_salary.js');
  const PIG = { x: 500, y: 975, scale: 3.1 };
  const TXT = {   // 右側三行:中心 x/y、字級(主 236;副 55%=130;補 46%=108)
    l1: { s: '100萬', x: 1420, y: 280, fs: 236 },
    l2: { s: '贏過八成', x: 1420, y: 535, fs: 130 },
    l3: { s: '台大卻後半段', x: 1420, y: 745, fs: 108 },
  };
  const INK = K.INK;
  const strokeText = (o, fill, sw, shadow) => {
    const t = (dx, dy, fl, st) => `<text x="${o.x + dx}" y="${o.y + dy}" font-family="GenSen" font-size="${o.fs}" text-anchor="middle" dominant-baseline="central"` +
      ` fill="${fl}" stroke="${st}" stroke-width="${sw}" stroke-linejoin="round" paint-order="stroke">${o.s}</text>`;
    return `<g data-k="thumbtext" data-id="${o.id}" data-u="1">${shadow ? t(8, 9, INK, INK) : ''}${t(0, 0, fill, INK)}</g>`;
  };

  function render(t, params) {
    const pal = K.palette(135);
    let s = `<rect width="1920" height="1080" fill="${pal.bg}"/><circle cx="540" cy="590" r="440" fill="${pal.pad}"/>`;
    // 鴿子(朝右、驚訝)與抱著的一疊千元鈔
    const pose = K.expr({ flip: 1, wing: -40, wlen: 1.2 }, 'surprised');
    s += K.pigeon(pose, { x: PIG.x, y: PIG.y, scale: PIG.scale, id: 'p' });
    if (!(params && params.nobills)) {
      const bx = 580, by = 765, bs = 1.3;
      [[-10, 26, -8], [8, 14, -5], [-4, 2, -9], [10, -10, -4], [0, -22, -7]].forEach(([dx, dy, r], i) => {
        s += K.paper(PS.bill(pal, {}), { x: bx + dx * 2, y: by + dy * 2, rot: r, scale: bs, k: 'prop', id: 'bill' + i, wide: true });
      });
    }
    // 右側三行字
    s += strokeText(Object.assign({ id: 'l1' }, TXT.l1), K.YELLOW, 24, true);
    s += strokeText(Object.assign({ id: 'l2' }, TXT.l2), K.PAPER, 22, true);
    const l3 = TXT.l3, bw3 = l3.fs * 6 + l3.fs * 0.8, bh3 = l3.fs * 1.45;
    s += K.paper(`<rect x="${-bw3 / 2}" y="${-bh3 / 2}" width="${bw3}" height="${bh3}" fill="${K.YELLOW}" stroke="${INK}" stroke-width="12" stroke-linejoin="miter"/>` +
      `<text x="0" y="0" font-family="GenSen" font-size="${l3.fs}" text-anchor="middle" dominant-baseline="central" fill="${INK}" stroke="none">${l3.s}</text>`,
      { x: l3.x, y: l3.y, rot: -2, scale: 1, k: 'plate', id: 'l3', wide: true });
    return K.wrap(pal, s);
  }
  const Scene = { name: 'salary_thumb', dur: 0.1, render, meta: () => ({ clear: [[1632, 918, 1920, 1080]] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
