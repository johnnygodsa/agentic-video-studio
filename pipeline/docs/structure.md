# 文案結構檢查 `script_structure.py` 與語速常數 `pace.py`

## 用途
寫稿後、渲染前檢查 `<tag>/script.txt` 的骨架與節奏是否照 `channel/規則/2_文案.md` §2。**全部是警告**,只有 `--strict` 才讓警告變成結束碼 1。
門檻是 2026-10-26 依規則訂的初值,留存證據 n=6(弱證據),未校準。make_version 的 precheck 會在 script_lint 之後跑它,警告數進摘要、不中止。

## 指令
```
python -X utf8 pipeline/script_structure.py <tag> [--json] [--timeline <path>] [--strict]
```
- 輸出 `build/<tag>/structure.json`(路徑由 `paths.build_dir`)與 stdout 摘要(≤25 行);`--json` 時 stdout 改印完整 JSON。
- 秒數來源:`--timeline`,否則 `keep/<tag>/timeline.json`、`build/<tag>/timeline.json`(依序,且 `lines` 數須等於資料行數,不符就忽略並在 `notes` 說明);都沒有就用 `pace` 估(字數 ÷ 5.5)。同一行含多句時,句子秒數依字數在該行起訖內內插。
- 沒有 timeline 時字/分恆為 330(自己除自己),所以不檢查字/分,摘要印「字/分 需 timeline」。
- 解析失敗(`script_txt2json.parse` 報錯)回結束碼 2;環境變數 `CLAUDE_VIDEO_ROOT` 可指定素材根(Linux 測試用)。
- `cta` 標籤句不計入開場、結尾、判斷句、新料,也不算塊內時間;不用 jieba(沒裝也跑,結果一致)。

## 檢查項(code:規則出處與門檻)
| code | 規則 | 門檻 |
|---|---|---|
| `HOOK_TYPE` | 2_文案 §2 開場站觀眾;前 3 句分類(**單一來源 `script_structure.classify_hook(sentences) -> (primary, matches)`,retention_align 也呼叫它**),優先序:反差(前 3 句含數字——阿拉伯或中文數字+單位如 十月、一個多月、七十美金——且含 可是/結果/卻/偏偏/反而/竟)→ 觀眾利害(前 2 句含 你/你的/你們、`(台灣)?玩家(們)?(等|花|買|付|被|要)`,或 美金/元/塊/月費/預購)→ 事件宣告(第 1 句以 日期、公告、宣布、更新說明、官方、Beta、測試期、年月日 開頭,且前 3 句沒有轉折也沒有你)→ 背景交代 | 事件宣告、背景交代警告並附證據句。0_診斷:事件宣告開場 0–1% 跌 6.6–7.8 點,反差 2.3(n=6) |
| `NEUTRAL` | 不寫「我不選邊,你自己判斷」 | 命中 不選邊/自己判斷/不替你下結論/不評論/中立;再跌約 6.3 點(n=6) |
| `JUDGE_LATE` `JUDGE_NONE` | 前 15 秒內一句站玩家的判斷 | 第一個 `script_lint.JUDGE` 命中句起點 ≤ 15 秒;全片無則 `JUDGE_NONE` |
| `BLOCK_COUNT` `BLOCK_SEC` | 約 4–5 塊、每塊 90–150 秒(2_文案 §2 一塊 90–150 秒;警告文字附此出處) | 以 `# ` 段落為塊;**段名含 開場/結尾/片尾 的段排除**(例:「六、微軟沒講的事與結尾」也會被排除);塊秒數 = 首句起點到最後一句旁白終點 |
| `FACT_GAP` | 塊內每 30–55 秒要有新事實 | 新料 = 含阿拉伯數字、`quote:` 標籤、`img:` 且行尾有 hl 的句;塊內相鄰兩個新料起點差 > 55 秒;整塊無新料且 > 55 秒也警告 |
| `NO_LANDING` | 每塊最後一階落到觀眾 | 塊內需有一句同時含 (你/你的/玩家) 與 (錢/美金/小時/分鐘/天/等/買) |
| `STRONGEST_POS` | 最強證據首次完整出現在片長 55–75% | **代理指標**:取全片「最大數字」所在句的位置 %(萬/億/千/百換算,排除 1990–2035 年份)。`quote:` 句、anim 型態含 num/compare 或 `cmp:` 的句列在 `strongest_candidates` 供參考,不計警告 |
| `CTA_POS` | 訂閱邀請放在第一個完整塊之後 | `cta` 句起點須 ≥ 第一塊結束且位置 < 50%;沒有 cta 只在 `notes` 提示 |
| `END_QUESTIONS` | 結尾 2–3 個問題 | 最後 10 句的問句數(句末 ?/?)在 2–3 |
| `END_JUDGMENT` | 結尾一句判斷 | 最後 10 句有 JUDGE 命中 |
| `END_CALLBACK` | 回扣開場的物件或數字 | 結尾與「結尾之前的前 6 句」共有實體:帶單位的數字、英數專名、「」《》內名稱、不含虛字的 4 字中文片段(代理指標,有少量誤中) |
| `END_NEWFACT` | 結尾先講沒講過的新事實 | 結尾有前面沒出現過的數字(無單位的 1–2 位數不算) |
| `CPM` | 含停頓每分鐘 315–350 字 | 僅有 timeline 時檢查;總字數 ÷ 總分鐘 |
| `FPM` | 具體事實每分鐘 4–9 | 新料句數 ÷ 分鐘 |

## structure.json 欄位
`timeline_used`(bool)、`hook_type`、`hook_matches`(命中的所有型態)、`judge_sec`、`blocks[{name,start_s,end_s,new_facts,lands_on_viewer}]`、
`strongest_pos_pct`、`strongest_candidates[{line,pct,kind}]`、`cta_pos_pct`、`ending{questions,judgment,callback,new_fact,callback_hits,new_numbers}`、
`chars_per_min`、`facts_per_min`、`metrics{chars,total_s,minutes,sentences,new_fact_sentences,chars_per_min,facts_per_min}`、`notes[]`、`warnings[{code,line,text}]`(line = script.txt 行號,0 = 全片層級)。

## pace.py
`CHARS_PER_MIN = 330`、`CHARS_PER_SEC = 5.5`(2_文案 §2 字數換算:含停頓每分鐘約 330 字)、`count_chars`(去標點空白)、`est_seconds(text, pause=0.0)`、`minutes(chars)`。
`script_lint.py` 的 `chars_per_sec` 已改引用此處;spec_check / style_metrics / visual_check 的常數下一輪再統一。

## 測試
`PYTHONPATH=<repo> python3 -X utf8 -m pytest pipeline/tests/test_script_structure.py -q`;fixture 在 `pipeline/tests/fixtures/structure/`(good.txt、bad.txt、good_timeline.json)。
測試也會對 repo 內每支 `*/script.txt` 跑一次(暫存素材根,不寫入 repo 的 build/),只驗不拋例外。
