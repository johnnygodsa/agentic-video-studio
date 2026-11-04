/* 閱讀卡字級自適應(PLAN_閱讀卡 §5.3)。字級依摘錄行數:<=2 行 64px、3–4 行 56px、5–6 行 48px;
   卡高固定、內容垂直置中,主欄上下留白合計不得超過卡高 25%,超過就再放大一級(最多 6 行、放得下才放大;64 再往上有 72、80 兩級,只給留白規則用,80 只限 para 版型且行數不增加)。
   48px 仍超過 6 行或主欄內容高過主欄時,有 hero 圖的版型先把圖拿掉(主欄變寬)再量一次。
   標題 > 2 行就縮字(56 -> 50 -> 46)。主欄放不下(卡底留 180px 給字幕)再收行距、縮到 40px。結果寫在 window.__cardInfo,載入完成後 documentElement.dataset.fit = 1。 */
(async () => {
  try { await document.fonts.ready; await Promise.all([document.fonts.load('700 56px NTCB'), document.fonts.load('400 48px NTCR')]); } catch (e) {}
  const card = document.querySelector('.card'), main = document.querySelector('.main'), ex = document.querySelector('.ex'), title = document.querySelector('.title');
  const LV = [[80, 0], [72, 0], [64, 2], [56, 4], [48, 6]];   // [字級, 自然選級時容許的行數];80、72 不參與自然選級,只給留白規則放大用
  const countLines = el => {
    if (!el) return 0;
    const rg = document.createRange(), tops = [];
    for (const p of el.querySelectorAll('p')) {
      rg.selectNodeContents(p);
      for (const r of rg.getClientRects()) if (r.width > 1 && !tops.some(t => Math.abs(t - r.top) < r.height * 0.5)) tops.push(r.top);
    }
    return tops.length;
  };
  const info = {title_lines: 0};
  const used = () => {   // 主欄內容(第一個子元素上緣到最後一個下緣)
    const k = [...main.children]; if (!k.length) return 0;
    return k[k.length - 1].getBoundingClientRect().bottom - k[0].getBoundingClientRect().top;
  };
  // 殘行:段落最後一行(不計標點)<= 2 字時,逐步縮窄該段(每步 16px,最多 10 步),讓上一行最後一個詞掉下來;切點仍只在 <wbr> 處
  const PUNCT = /[\s，。、：；！？」』）》〉…—,.:;!?)"'’”]/;
  const lastLineChars = p => {
    const rg = document.createRange(), cs = [], w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) for (let i = 0; i < n.data.length; i++) { rg.setStart(n, i); rg.setEnd(n, i + 1); const r = rg.getClientRects()[0]; if (r && r.width > 0) cs.push([r.top, n.data[i]]); }
    if (!cs.length) return 99;
    const top = Math.max(...cs.map(c => c[0]));
    return cs.filter(c => Math.abs(c[0] - top) < 5 && !PUNCT.test(c[1])).length;
  };
  const fixOrphans = () => {
    for (const p of ex.querySelectorAll('p')) {
      p.style.maxWidth = '';
      const w0 = p.getBoundingClientRect().width;
      for (let k = 1; k <= 10 && p.getClientRects().length && lastLineChars(p) <= 2; k++) { p.style.maxWidth = (w0 - 16 * k) + 'px'; info.orphan_fixed = (info.orphan_fixed || 0) + 1; }
    }
  };
  const setFs = fs => { ex.style.fontSize = fs + 'px'; fixOrphans(); };
  if (title) {
    for (const fs of [56, 50, 46]) { title.style.fontSize = fs + 'px'; info.title_fs = fs; info.title_lines = Math.round(title.getBoundingClientRect().height / (fs * 1.3)); if (info.title_lines <= 2) break; }
  }
  const pick = () => {
    let idx = LV.length - 1;
    for (let i = 2; i < LV.length; i++) { setFs(LV[i][0]); if (countLines(ex) <= LV[i][1]) { idx = i; break; } }
    setFs(LV[idx][0]);
    return idx;
  };
  let idx = pick();
  const hero = document.querySelector('.hero');
  const avail0 = main.getBoundingClientRect().height;
  if (hero && (countLines(ex) > 6 || used() > avail0)) { hero.style.display = 'none'; info.hero_dropped = true; idx = pick(); }
  const cap = card.getBoundingClientRect().height * 0.25, avail = main.getBoundingClientRect().height;
  while (idx > 0 && avail - used() > cap) {
    const before = countLines(ex);
    setFs(LV[idx - 1][0]);
    // 80px 這級只給 para 版型,且放大後行數不能比原本多(2026-10-22)
    if (countLines(ex) > 6 || used() > avail || (LV[idx - 1][0] === 80 && (card.dataset.layout !== 'para' || countLines(ex) > Math.max(before, 2)))) { setFs(LV[idx][0]); break; }
    idx--;
  }
  // 底部內距 180px(字幕帶讓位,card.css)後可用高度變小:主欄內容仍高過主欄時,先收行距、再逐級縮摘錄字級(48 -> 44 -> 42 -> 40),放得下就停(2026-10-22)
  if (used() > avail) {
    const cur = LV[idx][0];
    for (const [fs, lh] of [[cur, 1.5], [48, 1.5], [44, 1.5], [42, 1.45], [40, 1.45]]) {
      if (fs > cur) continue;
      ex.style.lineHeight = lh; setFs(fs); info.tight = fs;
      if (used() <= avail) break;
    }
  }
  info.fs = parseInt(ex.style.fontSize); info.lines = countLines(ex); info.blank = Math.round(avail - used()); info.cap = Math.round(cap);
  info.sw = main.scrollWidth <= main.clientWidth + 1;
  window.__cardInfo = info;
  document.documentElement.dataset.fit = '1';
})();
