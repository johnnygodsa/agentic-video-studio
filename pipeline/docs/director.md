# director:每支片的生產紀錄 production.json(計畫 `PLAN_工作室v2_2026-10-31.md` §6.1、§10 Phase 0)

`pipeline\director.py`:`init`、`status`(從既有產物推斷每段狀態)、`log`、`intervene`、`feedback`、`cost`、`usage`、`brief`、`run`、`--explain <段>`。A→B4 與 C 段改句見 `director_ab.md`(程式 `director_ab.py`、`llm.py`、`gates\gate_a/b/b4.py`、`gates\specs.py`);下方 run 一節是 C→E,「不呼叫 LLM、不改句」已由 C 段改句迴圈取代。

```
python -X utf8 pipeline\director.py init <tag> [--channel ChannelA]          不存在才建
python -X utf8 pipeline\director.py status <tag> [--json] [--write]      印表;--write 把推斷寫回
python -X utf8 pipeline\director.py log <tag> --fn <name> --model <m> --in N --out N [--cache N] [--cost X]
python -X utf8 pipeline\director.py cost <tag> [--json]                  llm_calls 依段/fn 分組成本表(cost_eq 大到小、段小計、合計)
python -X utf8 pipeline\director.py usage <tag>                          對話用量(`video_cost.py` 逐則訊息歸屬,含子代理與 worktree 對話、依模型加權)寫進 production.json 的 session 欄位(status --write 與 run 的 E 段完成後也會 best-effort 寫);`--since/--sessions` 已不使用
python -X utf8 pipeline\director.py intervene <tag> --what "<一句>"
python -X utf8 pipeline\director.py feedback <tag> --text "<一句>" [--case T12]
```
`log`/`intervene`/`feedback` 在 production.json 不存在時自動 init。檔案:`projects\<tag>\production.json`(原子寫入)。

## production.json 欄位
| 欄位 | 型別 | 說明 |
|---|---|---|
| tag | str | 片名 |
| channel | str | 頻道;依序取 `--channel`、既有檔、board、`projects\<tag>\spec.json`,都沒有 = "" |
| created | ISO 秒 | init 時間 |
| stage | str | `0選題`/`A資料`/`B文案`/`B4配音稿`/`C配音`/`已凍結`/`D畫面`/`E自審`/`已排程`/`結案`;`status --write` 寫入推斷值 |
| gates | {段:{passed, at, items, attempts, state}} | 段鍵 `0 A B B4 C D E`;passed = 該段完成定義全成立;items = [{id, ok, note}];attempts 由人或後續程式累加,`--write` 保留不動;state = 完成/進行中/未開始;at = passed 值最後一次變動的時間 |
| llm_calls | [{at, fn, model, input_tokens, output_tokens, cache_read, cost_eq, cost_w}] | `log` 追加。cost_eq = 等效輸入 token = input + 5×output + 0.1×cache_read(與模型無關,可 `--cost` 覆寫)。cost_w = cost_eq × `MODEL_W`(opus 5、sonnet 1、haiku 1/3;model id 含該字串即套用,都不含 = 1);舊紀錄沒有 cost_w,`cost` 讀取時現算不回寫 |
| session | {at, sessions:[id 前 8 碼], turns, input, cache_creation, cache_read, output, main_eq, sub_eq, cost_eq, main_w, sub_w, cost_w, total_w, interventions} | `usage` 寫入(`pipelineideo_cost.py` 的 `usage_for_tag`:逐則訊息依 tag 切換歸屬,tag 只認 `projects\<tag>` 實存目錄;子代理先看首則 prompt 有無 tag,沒有繼承父對話當時的 tag;未歸屬的不計入任何片)。cost_eq = input+cache_creation + 5×output + 0.1×cache_read(主對話+子代理,未加權);main_eq/sub_eq 同公式;main_w/sub_w = 逐則 eq × `MODEL_W`(opus 5、fable 暫定 5、sonnet 1、haiku 1/3);cost_w = main_w+sub_w;total_w = llm_calls cost_w 合計 + cost_w;找不到對話 = {at, sessions:[], note, total_w(只有 llm_calls)}。`cost <tag>` 最後一行印「對話 w / 全片總 w」。跨片總表:`video_cost.py --all`(寫 `channel\token_ledger.md/.json`,主欄「週 %」= 總 w ÷ 每 1% 的 w,顯示「中文短名(tag)」);百分比校準:`video_cost.py --snap --h5 N --h5-reset ISO --week N --week-reset ISO [--fable N]` 把官方用量寫進 `channel\usage_snapshots.jsonl`,程式以「視窗起點用量 0%」算帳號全部 w(~/.claude/projects 全專案 + production.json llm_calls)得每 1% 的 w,週/五小時各取最近 5 筆(≥3%)中位數;`--now` 一行印最新快照與估計現況;中文名 `channel\tag_names.json`(director brief 自動補 topic 前 12 字);快取 `tmp\video_cost_cache.json`(依檔案 mtime+size,非本專案對話只存用量) |
| interventions | [{at, who:"user", what, resolved}] | 使用者介入;`intervene` 追加,resolved 預設 false |
| feedback | [{at, text, taste_case}] | 使用者回饋與對應口味測試集案例(沒有 = null) |
| artifacts | {script, facts, visual_table, tts_script, freeze, timeline, mp4, cover, video_id} | 相對素材根的路徑;找不到 = null;video_id 取 production.json 已有值,否則 `handoff.md` 的 `video_id` 字樣 |
| versions | [{ver, mp4, look, notes}] | `output\<tag>\<tag>_v*.mp4`(排除 `_720p`)依版號;`--write` 重算 |

## status 推斷規則(門檻以 `gates\` 為準)
| 段 | 項目(全成立 = 完成;有任一 = 進行中) |
|---|---|
| 0 選題 | `tmp\scout_*`(含頻道名)、`tmp\critic_*`。頻道級檔,不分題;只作入口證據,不影響後段 |
| A 資料 | `projects\<tag>\context.md`;`facts.md`(或 `facts*.md`)有且表格內「待查」列 0;片段/素材檔 `clips_<tag>.json` 或 `clips.json` |
| B 文案 | `<tag>\script.txt`;`projects\<tag>\visual_table.md`;`player_review*.md` |
| B4 配音稿 | `build\<tag>\tts_script.md`;`projects\<tag>\pron_review.md`(只查存在,未決條數不解析) |
| C 配音 | `c0_report.md`(且 c0_report.json 唸錯 0);`build\<tag>\tts_review.json` 品管未過 0、時長預檢 0;`freeze.json`;`output\<tag>\listen_v*.txt` |
| D 畫面 | `output\<tag>\<tag>_v*.mp4`;`look_v*.md` |
| E 自審上片 | `*_說明.md`;video_id;board 階段為 已排程/結案 |

推斷階段 = 有證據的最後一段:A→`A資料`、B→`B文案`、B4→`B4配音稿`、C→`C配音`(C 完成 → `已凍結`)、D→`D畫面`、E→`E自審`(E 完成 → `已排程`);board 為 `結案` 則 `結案`;全無證據 = `0選題`。推斷只看檔案存在與簡單內容,不代表「看過」類的閘門(QA 圖、look 清單)已由主對話確認;board 階段另列對照。

## run:C→E 串接(Phase 2,2026-10-31 設計;計畫 §6.1、§10)
```
python -X utf8 pipeline\director.py run <tag> --from C|D|E --to C|D|E --ver vN
      [--backend local|kaggle|colab] [--title <片名> --channel <頻道>] [--publish-at ISO|HH:MM|auto] [--cover <png>]
      [--check-only] [--dry-run] [--max-attempts 3]
```
- 原則:director 只是「照順序跑既有指令 + 每段後評 gate + 全部記進 production.json」;不呼叫 LLM、不改句(Phase 3)。gate 不過就記卡點、停,不問使用者。整個 run 由呼叫者背景跑;GPU 由被呼叫的 make_version/tts_* 自己走 gpu_lock。
- `--check-only`:不跑指令,只對既有產物評各段 gate(影子模式驗收:人工流程做完的片,gate 要全過)。`--dry-run`:列印將跑的指令與 gate。
- 每段:前置 gate(上一段 passed)→ 指令序列 → 本段 gate;任一指令結束碼非 0 或 gate 不過 → `production.json.blocks` 追加 `{at, seg, step, reason, rc, log}`,`gates[seg].attempts += 1`,board 不動,回傳結束碼 3。
- 指令序列(`PY` = `tts_env_chattts\Scripts\python.exe -X utf8`,`SYS` = `python -X utf8`):
  | 段 | 步 | 指令 | 跳過條件 |
  |---|---|---|---|
  | C | c0 | `PY pipeline\tts_c0.py <tag>` | `projects\<tag>\c0_report.json` 比 `<tag>\script.txt` 新 |
  | C | 後端 | `--backend` 未給 → `SYS pipeline\tts_dispatch.py <tag>`(只印狀態,結束碼 4)→ 卡點 `待選後端`(訊息原文進 blocks.reason);`local` → 直接下一步;`kaggle` → `SYS pipeline\tts_dispatch.py <tag> --prefer kaggle --foreground`;`colab` → 卡點 `Colab 要使用者上傳`(不自動) | — |
  | C | 配音凍結 | `SYS pipeline\make_version.py --tag <tag> --ver <ver> --tts-review --freeze`(結束碼 3 = 品管未過,卡點列原因) | `freeze.json` 存在且 `tts_review.json` 未過 0 |
  | D | 出片 | `SYS pipeline\make_version.py --tag <tag> --ver <ver> [--title --channel]`(不帶 `--enqueue`) | `output\<tag>\<tag>_<ver>.mp4` 比 `timeline_tts.json` 新 |
  | D | 眼睛 | `PY pipeline\senses\eye.py --tag <tag> --ver <ver>`(機械項,見 senses.md) | — |
  | E | 交付排程 | `SYS pipeline\deliver.py --tag <tag> --ver <ver> --title --channel --enqueue --publish-at <auto> [--cover]` | sidecar 已存在且 board 已排程 |
- gate(全硬擋;`gates\gate_c.py / gate_d.py / gate_e.py`,每支 `run(tag, ver) -> [item{id, ok, note, path}]`;既有 `director.check_c/d/e` 改為呼叫 gates):
  - **C**:c0 唸錯 0;`tts_review.json` 品管未過 0、時長預檢 0、新合成 0(遠端匯回後);`freeze.json` 有且 narration_sha 等於現在 script.txt 的配音文本 sha(用 `freeze.check(tag)` 為 None);`output\<tag>\listen_<ver>.txt` 有;`projects\<tag>\ear_e4_<ver>.json` 有(E4 旗標只進優先聽,不擋)。
  - **D**:`<tag>_<ver>.mp4` 有且 ffprobe 時長 ≥ 8 分(ChannelA/ChannelB,ChannelC不限);`make_<ver>.log` 裡渲染前檢查 錯誤 0;`qa_<ver>` 圖有;`look_<ver>.md` 有;`eye_<ver>.json` 全 ok。
  - **E**:說明檔有「發片資料」區塊且不含「(待填)」;sidecar `.claude.json` 存在;board 階段 已排程(或 production.json 有 video_id 與 publish_at)。
- production.json 新欄位:`title`(交付片名;`--title` 優先,否則 gate E 從 yt_inbox 掃到 tag 相符的 sidecar 時寫回,已有不覆寫)、`runs: [{at, seg, step, cmd, rc, secs, log}]`(log = `output\<tag>\director_<ver>.log` 內的段落標記)、`blocks: [{at, seg, step, reason, rc}]`、`publish_at`。
- 實作差異(2026-10-31 實作時補):
  - 每支 gate 另有 `status(tag, ctx)` = 原 `check_c/d/e` 的寬鬆推斷(看最新版),`director status` 照舊用它;`run(tag, ver, ctx)` 才是上列硬擋。
  - 片長(1_選題 §3:目標不是硬下限;頻道_ChannelA:<6 分先講):<6 分不過(note 需使用者決定補素材/併題/照發),6–8 分過但註明低於目標 8 分,ChannelC不限。
  - sidecar 不依賴 `--title`:給了先找 `<title>_<ver>.claude.json`,否則掃 `yt_inbox()` 的 `*_<ver>.claude.json`,JSON `tag` 相符即命中。
    找不到但有 video_id(production.json/handoff)或 board 已排程/結案 → 也過(已交付的 sidecar 會被 Youtube AD 後端收走),note 註明以 video_id 為證。
  - 「新合成 0」讀 `tts_review.json` 的 `new_synth`(make_version 目前不寫此欄,沒有 = 0)。找不到 ffprobe → 片長 item 不過(環境問題)。
  - C 的「後端」步在「配音凍結」跳過條件成立時一併跳過(已凍結的片重跑 C 不卡 待選後端)。
  - 前置 gate 只查第一段:C 看 B4(`check_b4`),D/E 跑上一段 `gate.run`;之後各段已在本次 run 過。
  - `--check-only` 不查前置、不停在第一個不過的段:C→E 全評,各段寫 `gates[seg]`,不過的各記一筆 `blocks`(step = `gate`)。
  - `--max-attempts`:段未過且 `attempts` ≥ 上限 → 記卡點(不加 attempts)不跑。
  - `publish_at` 只在 deliver 成功且 `--publish-at` 不是 auto 時寫入(auto 的實際時間由後端決定)。
  - `tts_script.py <tag> --verify` 在 c0 之前,本表沒列,run 也不跑(屬 B4 完成定義)。
- 驗收(Phase 2):對已人工做完的 ea_me5、wow_return 跑 `run --from C --to E --check-only` 全過;`--dry-run` 指令序列與當時 0_流程 §6(`_archive\規則_2026-10-31`)一致;單元測試用假目錄跑 gate 與 run 的跳過/卡點邏輯(不真跑配音)。
