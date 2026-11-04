/* pearl 封面(靜態一張,1920x1080)。主色滿版底、左側特大手搖杯加傾倒的醋瓶與琥珀水滴、右上兩行字牌「珍珠 加醋?」、右下嫌惡的鴿子(避開右下角片長標籤)。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PP = (typeof window !== 'undefined' && window.PropsPearl) || require('../props_pearl.js');
  const U = 2;
  const FS = 250;                                   // 字牌字級(px)
  const CUP = { x: 380, y: 622, h: 756 }, VIN = { x: 800, y: 239, h: 486, rot: -100 };
  const PIG = { x: 1340, y: 1008, scale: 1.65 };
  function render(t, params) {
    const pal = K.palette((params || {}).hue);
    const ic = (name, o) => ({ svg: PP.LIST[name].fn(pal, o || {}), w: PP.LIST[name].w, h: PP.LIST[name].h });
    const byH = (name, h, o) => Ch.icon(ic(name, o), 0, 0, h * Math.max(PP.LIST[name].w, PP.LIST[name].h) / PP.LIST[name].h);   // 以高度定大小
    let s = `<rect width="1920" height="1080" fill="${pal.main}"/>`;
    s += K.paper(`<circle r="330" fill="${pal.bg}"/>`, { x: 1470, y: 640, scale: U, k: 'spot', id: 'spot' });
    // 手搖杯、醋瓶、琥珀水滴
    s += Ch.sheet(byH('cup', CUP.h, { ice: true }), { x: CUP.x, y: CUP.y, u: U, kind: 'prop', id: 'cup', wide: true });
    s += Ch.sheet(byH('vinegar', VIN.h), { x: VIN.x, y: VIN.y, u: U, rot: VIN.rot, kind: 'prop', id: 'vinegar', wide: true });
    const drop = (x, y, sc, rot, id) => K.paper(
      `<path d="M 0 -26 Q 17 2 15 13 A 15 15 0 1 1 -15 13 Q -17 2 0 -26 Z" fill="hsl(38 95% 52%)"/><ellipse cx="-6" cy="12" rx="3.4" ry="6.5" fill="hsl(44 100% 80%)" stroke="none"/>`,
      { x, y, scale: sc, rot, k: 'drop', id });
    s += drop(556, 318, 1.4, 8, 'd1') + drop(542, 358, 1.6, 4, 'd2') + drop(528, 396, 1.8, 0, 'd3');
    // 右上兩行字牌
    const plate = (str, w, x, y, rot, fill, id) => K.paper(
      `<rect x="${-w / U / 2}" y="${-FS * 1.0 / U / 2}" width="${w / U}" height="${FS * 1.0 / U}" fill="${fill}" stroke="${K.INK}" stroke-width="5" stroke-linejoin="miter"/>` +
      `<text x="0" y="0" font-family="GenSen" font-size="${FS / U}" text-anchor="middle" dominant-baseline="central" fill="${K.INK}" stroke="none">${str}</text>`,
      { x, y, rot, scale: U, k: 'plate', id, wide: true });
    s += plate('珍珠', 560, 1524, 199, -2.5, K.PAPER, 'l1');
    s += plate('加醋?', 700, 1455, 470, 2.5, K.YELLOW, 'l2');
    // 嫌惡的鴿子
    const pose = Object.assign({}, K.expr(K.clip('tilt', 5), 'doubt'), { flip: 0 });
    s += K.pigeon(pose, { x: PIG.x, y: PIG.y, scale: PIG.scale, id: 'p' });
    return K.wrap(pal, s);
  }
  const Scene = { name: 'p_thumb', dur: 0.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
