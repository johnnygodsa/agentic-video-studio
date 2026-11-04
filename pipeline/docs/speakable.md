# speakable:可唸性預檢(2026-10-31,Phase 3;規格 `director_ab.md` §5/§7/§8)

不合成、不用 GPU。看「這句送配音的文字」(@say 之後)有哪些地方 CosyVoice3 容易唸壞;寫稿時 `--explain` 當限制,寫完 `check_tag` 當硬項,改句用 `line_fix`。

```
python -X utf8 pipeline\speakable.py <tag> [--json] [--explain]     # err > 0 結束碼 1
python -X utf8 pipeline\speakable.py --calibrate                    # 重算下表(掃 build\*\tts_qc.json)
```
API:`check_line(text, says=None) -> [{code, severity, span, why}]`、`check_tag(tag) -> {lines:[{line,hits}], errors, warns, n_lines}`、`explain() -> str`、`features(say)`。行號 = script.txt 行號。

## 項目
| code | 嚴重度 | 內容 |
|---|---|---|
| `en_unregistered` | err | 英文詞不在 cosy_terms / `_direct`(`terms_check.unregistered`,沒有就用 `tts_cosy_text.analyze`)。配音前本來就擋,不靠統計 |
| `memory_bad` | err | `pron_memory` 該語境 state=bad 且 fix=rewrite(`PM.blocking`)。bad+mark 會自動套標注、undetermined 是「測過看不出、留優先聽」,都不提示 |
| `backlog` | warn | 句中有 `pron_backlog.md` 狀態「待規則」的語境詞 |
| `poly_unmarked` | warn | 「已知易錯字」(pron_rules ∪ pron_memory ∪ pron_backlog 的字,扣掉 `COMMON_POLY` 高頻字)沒有詞表/規則(含 keep)/記憶覆蓋,且一句 >= 3 個 |
| `num_dense` | warn | 句內送引擎前仍是阿拉伯數字 >= 3 位(@say 沒換) |
| `en_dense` | warn | 英文單字數 ÷ 發音單位 >= 15% |
| `en_tail` | warn | 句尾是英文詞(2_文案 §3「句尾英文能避就避」) |
| `line_short` | warn | 整句 < 16 發音單位 |
| `clause_long` / `line_long` | warn | 最長子句 >= 20 / 整句 >= 45 發音單位 |

發音單位 = 中文一字、英文一詞、數字一位(同 `script_lint._UNIT_RE`)。

## 實測(2026-10-31,`speakable.py --calibrate`)
資料:`build\*\tts_qc.json` 11 支片(ally_ai bioware_dei ea_me5 fog_still hidden_diff horror_sound pbz_day1 pbz_review safe_room wow_eternal_pre wow_return)的最終紀錄 **n = 763 句**。
這些片的 `failed` 都是 0(最終都過品管,`tts_review.json` 的 failed/no_qc/timing_errors 也全 0),所以未過率改用「中途未過」代理,四個目標(以句為單位):
- `retry`:任一次合成未過品管(retries > 0);`retry3`:重錄 >= 3 次;
- `text`:某次合成因 content / pron / term_misread / pause_misplaced 未過(內容或讀音類;tail_*、comma_short、stray_pause 是聲學類不算);
- `sim`:最終語音辨識相似度 < 0.95。

基準:retry 398/763 = 52%、retry3 164 = 21%、text 19 = 2.5%、sim 99 = 13%。

| 特徵 | 區間 | n | retry3 | text | sim |
|---|---|---|---|---|---|
| 整句發音單位 | < 16 | 38 | 37% | 8% | 18% |
| | 16–19 | 56 | 23% | 7% | 21% |
| | 20–39 | 578 | 21% | 2% | 13% |
| | 40–44 | 62 | 13% | 0% | 10% |
| | >= 45 | 29 | 17% | 3% | 7% |
| 最長子句 | < 10 | 64 | 31% | 5% | 17% |
| | 15–17 | 168 | 22% | 1% | 13% |
| | 18–19 | 50 | 6% | 0% | 6% |
| | >= 20 | 36 | 28% | 0% | 11% |
| 英文單字數 | 0 | 637 | 22% | 2% | 12% |
| | 1 | 71 | 15% | 4% | 21% |
| | 2 | 29 | 24% | 0% | 21% |
| | >= 3 | 26 | 23% | 4% | 8% |
| 英文佔比 | >= 15% | 11 | 27% | 9% | 0% |
| 句尾英文 | 是 | 3 | 33% | 0% | 0% |
| 阿拉伯數字位數 | 0 | 677 | 20% | 2% | 12% |
| | 1–2 | 59 | 34% | 5% | 19% |
| | 3–4 | 23 | 26% | 0% | 22% |
| 未覆蓋已知易錯字 | 0 | 264 | 24% | 3% | 10% |
| | 1–2 | 422 | 20% | 2% | 14% |
| | >= 3 | 77 | 19% | 1% | 19% |

(完整輸出含各字別率:跑 `--calibrate`。`的 了 還 要 會 只 那 沒 分 好 打 地 幾 種 覺 給 難 更` 各出現在 >= 5% 句子、四項率都在基準附近,每句都有、提示無資訊,列入 `COMMON_POLY` 略過。)

## 門檻怎麼訂
- **err 的標準**:該特徵的 text 未過率 >= 25% 且 n >= 10(約基準 10 倍)。**沒有任何特徵達到**,所以統計項全是 warn;err 只有「定義上就擋」的兩項(未登錄英文、記憶 bad+rewrite)。
- **warn 的標準**:挑「有任一目標率高於基準約 1.3 倍以上」的區間,且全片命中句數 <= 約 10%(gate_b 要求每個 warn 都有 fixed/kept 紀錄,太吵會變成形式)。
  - `line_short` < 16:retry3 37%(基準 21%)、text 8%(基準 2.5%),n=38 = 5%。
  - `num_dense` >= 3 位:retry3 26%、sim 19~22%,n=27 = 3.5%。(1–2 位也偏高,但命中 11% 的句子太吵,不收。)
  - `poly_unmarked` >= 3 個:sim 19%(基準 13%),n=77 = 10%。其餘個數沒有差異。
  - `en_dense` >= 15%、`clause_long` >= 20、`line_long` >= 45、`en_tail`:**實測沒有顯示更高的未過率**(英文佔比 n=11、句尾英文 n=3 太少),只是依 2_文案 §3 與 script_lint 既有規則取覆蓋率約 5% 以內的上界。n 增加後用 `--calibrate` 重算再調。
- 樣本偏誤:這些片都是定稿片,語助詞、英文詞、讀音都已被前面的步驟處理過(未登錄英文在這批裡必為 0,所以 `en_unregistered` 無法用統計訂)。

## 與其他檔
- `script_lint.check_sentences(tag, line_nos=None)`:句級 lint 子集 `[{line, code, block, why}]`,block=True 只有判決腔 VERDICT、BAD_PARTICLE(T 門檻為 0 的項),其餘是計次/警告項。不含全片比例、連貫、畫面類。
- `line_fix.fix_lines`:改句後用 `check_sentences`(block 0)與 `check_line`(err 0)驗收;見 `line_fix.py` 檔頭。
