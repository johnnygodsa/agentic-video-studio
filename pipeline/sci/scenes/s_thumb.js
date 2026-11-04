/* snack 封面(靜態一張,1920x1080 算圖後縮成 1280x720)。主色滿版底、品牌黃字牌「誰漲 最多?」、戴皇冠的「?」牌與三樣小吃、拿 50 元硬幣的驚訝鴿子。 */
(function () {
  const K = (typeof window !== 'undefined' && window.Kit) || require('../kit.js');
  const Ch = (typeof window !== 'undefined' && window.Charts) || require('../charts.js');
  const PS = (typeof window !== 'undefined' && window.PropsSnack) || require('../props_snack.js');
  const U = 2;
  const WING = 150, PX = 300, PY = 1060, PU = 1.25;   // 鴿子翅膀舉起角度、腳底落點、倍率
  function render(t, params) {
    const pal = K.palette((params || {}).hue);
    const ic = (name, o) => ({ svg: PS.LIST[name].fn(pal, o || {}), w: PS.LIST[name].w, h: PS.LIST[name].h });
    const byH = (name, h) => Ch.icon(ic(name), 0, 0, h * Math.max(PS.LIST[name].w, PS.LIST[name].h) / PS.LIST[name].h);   // 以高度定大小
    const prop = (name, h, x, y, rot, id) => Ch.sheet(byH(name, h), { x, y, u: U, rot, kind: 'prop', id, wide: true });
    let s = `<rect width="1920" height="1080" fill="${pal.main}"/>`;
    s += K.paper(`<circle r="300" fill="${pal.bg}"/>`, { x: 1500, y: 520, scale: U, k: 'spot', id: 'spot' });
    // 「?」大牌(冠軍不揭曉)與皇冠
    s += K.tile('?', { x: 1500, y: 360, size: 300, rot: -4, u: U, fill: K.INK, ink: K.YELLOW, id: 'q' });
    s += prop('crown', 170, 1488, 128, -7, 'crown');
    // 三樣小吃
    s += prop('braisedPorkRice', 260, 1233, 845, -5, 'rice');
    s += prop('chickenCutlet', 260, 1543, 850, 4, 'cutlet');
    s += prop('bobaCup', 290, 1790, 835, -6, 'boba');
    // 左側字牌
    const T = (ch, x, y, rot, q) => K.tile(ch, { x, y, size: 300, rot, u: U, fill: q ? K.INK : K.YELLOW, ink: q ? K.YELLOW : K.INK, id: 't' + x + '_' + y });
    s += T('誰', 250, 230, -3) + T('漲', 560, 220, 2);
    s += T('最', 250, 560, 2) + T('多', 560, 570, -2) + T('?', 850, 590, 8, true);
    // 鴿子與翅尖的 50 元硬幣
    const pose = Object.assign({}, K.expr(K.clip('tilt', 5), 'surprised'), { flip: 1, wing: WING, wlen: 1 });
    s += K.pigeon(pose, { x: PX, y: PY, scale: PU, id: 'p' });
    const a = WING * Math.PI / 180, vx = 76, vy = 30;
    const px = 146 + vx * Math.cos(a) - vy * Math.sin(a), py = 176 + vx * Math.sin(a) + vy * Math.cos(a);
    const tipX = PX + PU * (300 - px - 132), tipY = PY - 280 * PU + PU * py;
    s += prop('coin50', 140, tipX + 44, tipY + 4, 8, 'coin');
    return K.wrap(pal, s);
  }
  const Scene = { name: 's_thumb', dur: 0.1, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
