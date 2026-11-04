/* ChannelC片頭 3 秒(獨立鏡頭,給 build.py 當影片鏡頭用;不用鴿子)。render(t, params) 回傳完整 <svg> 內容,純函式。
 * 0.0–0.8 五字每 0.2 秒彈出一個 → 1.0 印章從 1.6 倍砸下、1.2 落地,整畫面震動 4 格(1.2–1.5)→ 停住到 3.0。
 * Logo:墨底方格紙紋、「C」黃色傾斜印章框 + 「範例頻道」紙白,GenSen。寬約 1300px 置中,垂直中心 Y=470(避開 Y≈924 字幕帶)。
 * 頓感:時間先取整格(每秒 10 格)再算,不補間。 */
(function () {
  const Y = '#FFD23F', INK = '#1B1414', PAPER = '#FFF8E7', FONT = 'GenSen';
  const W = 1920, H = 1080, FPS = 10;
  const f = (n) => Math.round(n * 100) / 100;
  const FS = 210, BOX = 210, GAP = 40, CY = 470, ROT = -6;            // 字級、印章邊長、印章與字間距、Logo 垂直中心、印章傾斜
  const TOTAL = BOX + GAP + FS * 5, X0 = (W - TOTAL) / 2;              // 1300、x0=310
  const SX = X0 + BOX / 2, TX0 = X0 + BOX + GAP;                       // 印章中心 x、文字起點 x
  const K_CHAR = 2, K_SLAM = 10, K_LAND = K_SLAM + 2;          // 字逐個彈出的間隔(格)、印章起砸格、落地格
  const SHAKE = [[14, -10], [-12, 9], [8, -6], [-5, 4]];              // 落地起 4 格的整畫面位移(固定表,無亂數)
  const CHARS = ['範', '例', '頻', '道'];
  
  const text = (s, x, y, fs, fill) =>
    `<text x="${f(x)}" y="${f(y)}" font-family="${FONT}" font-size="${f(fs)}" fill="${fill}" text-anchor="middle" dominant-baseline="central">${s}</text>`;
  const grid = () => {                                                 // 方格紙紋:間距 80,延伸出畫面外 80 讓震動不露邊
    let o = '';
    for (let x = -80; x <= W + 80; x += 80) o += `<line x1="${x}" y1="-80" x2="${x}" y2="${H + 80}"/>`;
    for (let y = -80; y <= H + 80; y += 80) o += `<line x1="-80" y1="${y}" x2="${W + 80}" y2="${y}"/>`;
    return `<g stroke="${PAPER}" stroke-width="2" opacity="0.07">${o}</g>`;
  };
  const stampAt = (sc, op) => {                                        // 印章:黃描邊、墨底、黃色「C」,轉 ROT 度後以中心縮放
    const sw = 14, s = BOX - sw;
    return `<g opacity="${op}" transform="translate(${SX} ${CY}) scale(${sc}) rotate(${ROT})">` +
      `<rect x="${f(-s / 2)}" y="${f(-s / 2)}" width="${s}" height="${s}" rx="${f(BOX * 0.04)}" fill="${INK}" stroke="${Y}" stroke-width="${sw}" stroke-linejoin="round"/>` +
      text('C', 0, BOX * 0.01, BOX * 0.72, Y) + '</g>';
  };
  const POP = [0.6, 1.18, 1.0];                                        // 字彈出 3 格的縮放(之後 1.0)

  function render(t) {
    const k = Math.floor(t * FPS + 1e-6);
    let s = '';
    CHARS.forEach((ch, i) => {                                         // 「範例頻道」依序彈出
      const d = k - i * K_CHAR;
      if (d < 0) return;
      const sc = d < POP.length ? POP[d] : 1, cx = TX0 + (i + 0.5) * FS;
      s += `<g transform="translate(${f(cx)} ${CY}) scale(${sc}) translate(${f(-cx)} ${-CY})">${text(ch, cx, CY, FS, PAPER)}</g>`;
    });
    if (k >= K_SLAM) {                                                 // 印章:1.6 倍砸下,落地後留住
      const sc = [1.6, 1.28, 1.0][Math.min(k - K_SLAM, 2)], op = [0.55, 0.85, 1][Math.min(k - K_SLAM, 2)];
      s += stampAt(sc, op);
      const kr = k - K_LAND;                                           // 落地衝擊框:兩格擴散淡出
      if (kr === 0 || kr === 1) {
        const g = kr === 0 ? 1.12 : 1.3, bx = BOX * g;
        s += `<g transform="translate(${SX} ${CY}) rotate(${ROT})"><rect x="${f(-bx / 2)}" y="${f(-bx / 2)}" width="${f(bx)}" height="${f(bx)}" rx="${f(bx * 0.04)}" fill="none" stroke="${Y}" stroke-width="6" opacity="${kr === 0 ? 0.6 : 0.3}"/></g>`;
      }
    }
    
    const kr = k - K_LAND, sh = kr >= 0 && kr < SHAKE.length ? SHAKE[kr] : [0, 0];
    return `<rect width="${W}" height="${H}" fill="${INK}"/><g transform="translate(${sh[0]} ${sh[1]})">${grid()}${s}</g>`;
  }

  const Scene = { name: 'lab_intro', dur: 3, render, meta: () => ({ clear: [] }) };
  if (typeof module !== 'undefined') module.exports = Scene;
  if (typeof window !== 'undefined') window.Scene = Scene;
})();
