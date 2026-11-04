/* turtle 封面(靜態一張,1920x1080 算圖後縮成 1280x720)。主色滿版底、品牌黃字牌「牙刷 害海龜?」、無言的海龜、牙刷、懷疑的鴿子。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PT = (typeof window !== 'undefined' && window.PropsTurtle) || require('../props_turtle.js');
  const U = 2;
  function render(t, params) {
    const pal = K.palette((params || {}).hue);
    const ic = (name, o) => ({ svg: PT.LIST[name].fn(pal, o || {}), w: PT.LIST[name].w, h: PT.LIST[name].h });
    let s = `<rect width="1920" height="1080" fill="${pal.main}"/>`;
    s += K.paper(`<circle r="300" fill="${pal.bg}"/>`, { x: 1500, y: 520, scale: U, k: 'spot', id: 'spot' });
    s += Ch.sheet(Ch.icon(ic('turtle', { expr: 'speechless' }), 0, 0, 740), { x: 1520, y: 400, u: U, kind: 'prop', id: 'turtle', wide: true });
    s += `<g transform="rotate(-14 1490 800)">` + Ch.sheet(Ch.icon(ic('toothbrush'), 0, 0, 660), { x: 1490, y: 800, u: U, kind: 'prop', id: 'brush', wide: true }) + `</g>`;
    const T = (ch, x, y, rot, q) => K.tile(ch, { x, y, size: 300, rot, u: U, fill: q ? K.INK : K.YELLOW, ink: q ? K.YELLOW : K.INK, id: 't' + x });
    s += T('牙', 250, 250, -3) + T('刷', 560, 240, 2);
    s += T('害', 250, 590, 2) + T('海', 560, 600, -2) + T('龜', 870, 590, 3) + T('?', 1150, 620, 8, true);
    s += K.pigeon(Object.assign({}, K.expr(K.clip('tilt', 5), 'doubt'), { flip: 1 }), { x: 300, y: 1060, scale: 1.25, id: 'p' });
    return K.wrap(pal, s);
  }
  const Scene = { name: 't_thumb', dur: 0.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
