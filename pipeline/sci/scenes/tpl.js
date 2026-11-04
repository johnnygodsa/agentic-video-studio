/* 通用模板場景(F4-0):render(t, params) 依 params.tpl 轉呼叫 Tpl[tpl].render;params: {hue, dur, portrait, lines, tpl, data}。
 * check(params) 回傳字串陣列(「警告」開頭 = 只提示,其餘 = 錯誤),render_clip.py 在算圖前呼叫。模板檔在 pipeline\sci\tpl_<名>.js。 */
(function () {
  const Wn = typeof window !== 'undefined' ? window : {};
  const get = (n) => { try { return (Wn.Tpl && Wn.Tpl[n]) || require('../tpl_' + n + '.js'); } catch (e) { return null; } };

  function render(t, params) { return get(params.tpl).render(t, params); }
  function check(params) {
    if (!params || !params.tpl) return ['缺 tpl'];
    const T = get(params.tpl);
    if (!T || !T.check || params.tpl === 'common') return [`沒有模板「${params.tpl}」`];
    return T.check(params);
  }

  const Scene = { name: 'tpl', dur: 3, render, check, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
