# director A→B4 與 LLM 函式層(Phase 3 規格,2026-10-31 主對話定)

本檔是 Phase 3 的設計;實作時的差異補在各節末「實作差異」。C→E 見 `director.md`,計畫見 `PLAN_工作室v2_2026-10-31.md` §6.1、§6.4。

## 1. LLM 函式層 `pipeline\llm.py`(實測 2026-10-31)
`claude -p` 底座實測(Haiku,回一句):預設 44.8k;`--setting-sources project --tools Read` 22.4k;**`--agent <x> --tools Read` 11.0k** → 一律用 `--agent` + 限定 `--tools`。`--bare` 不讀 OAuth,不可用(走 Max 訂閱)。別名 `haiku` 會解析到舊模型,**一律傳完整 ID**。
```python
MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}

@dataclass
class Result:
    ok: bool; text: str; data: dict | None; rc: int; model: str
    usage: dict; secs: float; error: str; limited: bool   # limited = 用量上限

def call(tag, fn, prompt, *, agent=None, model="sonnet", effort=None, tools=("Read","Grep","Glob"),
         schema=None, seg=None, timeout=1800, validate=None, cwd=None) -> Result
def call_escalating(tag, fn, prompt, **kw) -> Result   # 同模型失敗 2 次 → model="opus";Opus 再失敗回 ok=False
```
- 指令:`claude -p --output-format json --no-session-persistence --model <id> [--effort] [--agent] --tools <t,...> --allowedTools <t,...> [--json-schema <schema>]`,prompt 走 stdin,cwd = 素材根;不用 `--max-budget-usd`、不用 `--bare`。
- 不給 Agent 工具(subagent 不巢狀)。`schema` 有給時解析 `structured_output`(或 result 內 JSON)進 `data`,解析失敗 = 失敗。`validate(result)->str|None`:回字串 = 失敗原因,下一次 prompt 附上。
- 每次呼叫(含失敗)寫 `director.log_call`:input = input_tokens + cache_creation,cache = cache_read,另加 `secs`、`ok`、`seg`、`agent`;log_call 擴充參數,舊呼叫相容。
- 用量上限(結果文字含 usage limit / rate limit、或 rc 非 0 且訊息同類)→ `limited=True`,不重試,director 記卡點 `用量上限` 停下,不換模型硬跑。
- 逾時、非 JSON、is_error → 失敗。原始輸出存 `tmp\llm\<tag>\<時間>_<fn>.json`(除錯用,不進 git)。

實作差異(2026-10-31):
- 實測 `--json-schema`:結果物件有 `structured_output`(dict)與 `result`(JSON 字串),usage 欄位 input_tokens/cache_creation_input_tokens/cache_read_input_tokens/output_tokens;先取前者,否則解析後者。stderr 會印 `[claude-code:unrecognized_model]`,模型仍正確(modelUsage 為所傳 ID),不當錯誤。
- **`--agent` 下 `--json-schema` 不生效**(實測 Haiku 兩次,代理 frontmatter 的 tools 白名單濾掉 StructuredOutput,加進 `--tools` 也沒用,回應只有文字)。所以 `call` 把 schema 附進 prompt、從回覆文字取 JSON,`schema_miss` 自己驗 required 與型別;旗標保留(無 `--agent` 時有效)。規格的「`schema` → structured_output」改以文字路徑為主。`--agent` 配 `--model` 會覆寫 frontmatter 的 model(實測 modelUsage 為所傳 ID)。
- 用量上限只在失敗(rc 非 0、非 JSON、is_error、api_error_status 429)時比對文字;成功回覆只看 ≤400 字的短回覆,避免內文提到 rate limit 被誤判。
- `validate` 在 `call` 內評,失敗原因由 `call_escalating` 附進下一次 prompt。`call` 跑一次,不重試。

## 2. 開工資料 `projects\<tag>\brief.json`(主對話唯一要寫的檔)
`{tag, channel, format, topic, angle, spoiler, played, one_line, publish, urls:[...], event, query, allow_short}`。`format` 取 `gates\specs.py` 的片型鍵。`director.py brief <tag> --topic --angle --channel --format [--publish ...]` 寫入。沒有 brief → A 段卡點 `待開工提問`,不動。

## 3. 片型規格單一來源 `pipeline\gates\specs.py`
由 `channel\規則\1_選題.md` §3 搬入:`FORMATS = {("ChannelA","評論片"): {target:(7,10), floor:6}, ("ChannelA","長篇"): (15,30)/12, ("ChannelA","搬運"): 不設, ("ChannelB","考據片"): (6,10)/5, ("ChannelB","長篇"): (12,25)/10(2026-11-03), ("ChannelB","搬運"): 不設, ("ChannelC",None): 不設, ...}`(頻道鍵用現有資料裡的實際名字)。`gate_d` 的片長判斷改用它(ChannelB下限 5,不再寫死 6)。`SPEECH_CPM`:用最近 6 支有 `timeline_tts.json` 的片量實際「旁白字數 ÷ 成片旁白分鐘」取中位數(規則寫 330,ea_me5 估片長要實測校準),數字寫進 specs 並註明量測日。

實作差異(2026-10-31):多一個 `("ChannelA","主場片")`:(10,15)/6、`("ChannelC",None)`。沒有 brief 的舊片片型:ChannelA = 評論片、ChannelB = 考據片;頻道不明比照ChannelA評論片。`spec(channel, fmt=None)` 的 fmt 可省。頻道字串含鍵即對應(ChannelA → ChannelA)。**SPEECH_CPM = 307**(2026-10-31 量,旁白字數 ÷ 首句起點到末句終點:ea_me5 322.2、wow_return 306.0、ally_ai 307.2、fog_still 305.8、bioware_dei 333.1、horror_sound 305.8,中位數 306.6;`python -X utf8 pipeline\gates\specs.py` 重量)。gate_d 目標下緣改看片型(ChannelA 7 分、不再寫死 8)。`pace.CHARS_PER_MIN` 330 未動(script_lint 用)。

## 4. A 段步驟(`run --from A`,每步可跳過:產物已有且比輸入新)
| 步 | 種類 | 做什麼 | 產物 |
|---|---|---|---|
| brief | 檢查 | §2 | — |
| context | cmd | `context_pack.py --tag --channel [--event/--query]` | `context.md` |
| comments | cmd | brief.urls 或 context 給的同題片 → `yt-dlp --write-comments --skip-download`;沒有網址就跳過並記 warn | `comments_ref\` |
| consensus | LLM Sonnet,agent `ab-planner` | 讀 context.md §4、comments_ref、brief → 寫玩家共識 3–5 行、論點清單(每點:來源、絕對值、畫面)、待查清單 | `projects\<tag>\plan.json` `{consensus:[...], claims:[{id,text,source,abs,visual,block}], todo:[...], blocks:[{title,claim_ids,est_sec}]}` |
| research | LLM Haiku,agent `researcher` | plan.todo 一次派完 | `facts_raw*.md` |
| facts | LLM Sonnet high,agent `ab-planner` | raw → `facts.md`(2_文案 §5 閘門 2 欄位;待查 0;共識段放檔頭) | `facts.md` |
| replan | LLM Sonnet high,agent `ab-planner` | 查證後依 facts.md 重排 claims/blocks(只用非查無編號,「主對話裁定」段優先);consensus 原稿留 `plan_draft.json`,前段 skip 比對 draft | `plan.json`(`replanned: true`) |
| assets | LLM Sonnet,agent `asset-collector`,截圖與片段兩呼叫平行 | 依 plan.claims 的 visual 備素材:`pipeline\docs\assets.md`;`--check` 0 錯、hl 原字核對、`clips_lib --check` 達標 | `projects\<tag>\assets_manifest.json` `[{claim,kind,path,hl,ok[,why]}]`。flow v3(B10):effort low + 指令白名單、禁 Read 圖;代理回來後 director 對 ok=true 截圖項再跑 `assets_*_news.py --check`,不過改 ok=false 附 why |

實作差異(2026-10-31):步驟實作在 `pipeline\director_ab.py`,`steps()` 回 director 步驟 dict(`cmd` 或 `fn`);`skip` 可為 callable,因 A/B 後步依賴前步產物,執行前才評。`--ver` 只有 C/D/E 必填,A/B/B4 的 log 寫 `output\<tag>\director_ab.log`。comments 用 yt-dlp `-o comments_ref\%(id)s.%(ext)s`,yt-dlp 失敗只記 warn(`production.json.warns`),`comments_ref\*.json` 已有就略過。consensus/assets 用 schema 回傳、由 director 寫檔(代理不用 Write)。截圖 `assets_screen`、片段 `assets_clip` 兩呼叫 `ThreadPoolExecutor(2)` 平行;`director._append` 加鎖。

## 5. B 段步驟
| 步 | 種類 | 做什麼 |
|---|---|---|
| write | LLM Opus high,agent `script-writer` | 輸入路徑:plan.json、facts.md、assets_manifest、頻道檔、2_文案 §1–§3 §6、`speakable.py --explain` 輸出、taste B 段案例摘要;寫 `<tag>\script.txt` 與 `projects\<tag>\outline.md` |
| speak | cmd + 改句 | `speakable.check_tag` 硬項 → `line_fix` |
| lint | cmd + 改句 | `script_lint` / `script_structure` / `facts_check` / `visual_check --table`;句級命中 → `line_fix`;結構級 → `revise`;≤3 輪 |
| editor | LLM Opus,agent `editor-review` | `editor_review_r<n>.md` + 結構化報告;連貫斷點 >0 → `revise`;一輪 |
| player | LLM Opus,agent `player-review` | `player_review_r<n>.md` + 結構化報告;≤2 輪;第 2 輪仍有 誇大/可疑/相反 → 進 `ask_user`,卡點 `要問使用者`,不開第三輪 |
**B4**:`tts_script.py <tag>` → `sub_scan`(ckip)接縫 0 → LLM Sonnet `pron-review` → LLM Sonnet `pron-apply`(只新增 `pron_rules.json`/`cosy_pron.json` 條目)→ 重跑到未決 0 → `pron_backlog.md` 本片前 3 條 → gate。
- 結構化報告:`llm.call(schema=…)` 取代解析散文;審稿代理定義不改審查內容,只在 prompt 尾附「最後回報用此 JSON」。`player_review_r<n>.json` / `editor_review_r<n>.json`:`{counts:{...}, items:[{line, type, severity, text, reason, fix}]}`。
- **警告處理紀錄** `projects\<tag>\warn_log.json`:`{<檢查>:<sha8>:<代碼>: {action: "fixed"|"kept", reason, at}}`(sha8 = 句文字雜湊,見下方實作差異);`kept` 要有理由,由 `line_fix`/`revise` 回報寫入。gate_b 看本次所有警告都有紀錄(§6.2)。
- `revise`(Opus medium,agent `script-writer`,改內容用):給審稿條目,回 `[{line, new_line, note}]`,director 套用;與 `line_fix` 分開:**line_fix 不得改意思,revise 可以**。
- director 在段過 gate 時 commit:只 add 明確路徑(`<tag>\`、`projects\<tag>\`、本段動到的讀音檔),訊息 `director <tag>: <段> 過 gate`。index.lock 重試 3 次,失敗記 warn 不中止。

實作差異(2026-10-31):
- **句號與行號**:`line_fix`、`script_lint.check_sentences`、`speakable.check_tag` 的 line = script.txt 行號;tts_review idx、E4、審稿報告、revise 的 line = 第幾句旁白。director 在交界換算(`script_rows`)。
- **warn_log 鍵(2026-11-01)**:`<檢查>:<sha8>:<代碼>`,sha8 = 該句旁白文字雜湊(`gate_b.sha8`),加句不失效;structure 警告對不到句時用所在段標題雜湊。`warnings()` 同時帶 `legacy`(舊行號鍵),`unrecorded` 新鍵優先、舊鍵也認,舊片不用重記。line_fix 仍回行號鍵,`_record_fix` 用改前句文字換算;line_fix/revise 改過的句,舊句上的 `kept` 跟到新句(`_carry_kept`),其他手改句子 = 新句,警告要重新處理。
- **審稿有效性(2026-11-01)**:`editor/player_review_r<n>.json` 多 `narration`(審稿當時每句旁白 sha8,不含標籤與行尾 json),`_review_state` 比對目前旁白:沒變 = 報告有效(改 @say、hl、畫面標籤不開新輪);改動 >5 句 = 下一輪(玩家審滿 2 輪照舊 Block);≤5 句 = 編輯審不重跑,玩家審走 `_spot_review`,含滿 2 輪後。舊報告沒有 `narration` 退回 mtime。editor 報告 revise 後更新 `narration`;player r1 revise 完中斷 = 照走 r2。
- **小範圍玩家審**:prompt 列改動句與前後各一句,結果寫 `player_spot_<k>.json`(檔名不入 `latest_review`,不佔 MAX_PLAYER);審完更新最新報告的 `narration`;命中 PLAYER_MUST 不自動 revise,併進 `ask_user.json`,卡點 `要問使用者`。
- **改稿回歸檢查(2026-11-01)**:`regress_why(old, new, prev, nxt, reason, names)` 任一成立退回該句原文:a. 改前的《…》、主體名(`speakable.subject_names`)改後不見,revise 另看行尾 hl 字串;b. 改前的數字不見且 reason 沒提到數字;c. 新句與相鄰句相似度 ≥0.7(整句,或 ≥8 字的子句間);d. 改後字數 < 改前 60%。line_fix(lint/speak)改完逐條查,revise 留快照後逐句比(句數變動時對不到的句子保留 revise 結果);C 段 qc 不查。退回記 `regress:<舊句 sha8>` 鎖與該句警告 `kept` + 原因,鎖住的句不再送 line_fix/revise(不花 LLM);退回的句不算進 `revised`,審稿條目 gate 照算未處理。
- 編輯審「一輪」:r1 有連貫斷點 → revise → 報告寫 `revised:[句號]`,不重審;gate 不計已 revise 的條目。
- 玩家審:r1 必處理 = 錯/誇大/推論/相反/矛盾/關掉/可疑;r2 仍有 錯/關掉/誇大/可疑/相反 → `ask_user.json`,卡點 `要問使用者`(規格只列後三者,錯/關掉 r2 仍在 gate 必不過,一起問)。使用者回覆後由主對話清空 `ask_user.json`。
- 每次 revise 後重跑 speak + lint(`_recheck`),沒命中不花 LLM。
- write 的 skip 只比 plan.json 與 assets_manifest(`_write_skip`):facts.md 比稿新只印一行提醒,不整支重寫,facts_check 在 lint 步照跑。
- speakable 的 `backlog`、`poly_unmarked` 命中在《…》或主體名內不報(`check_line(names=…)`,硬項不受影響),讀音由 B4 pron-review 處理;line_fix 同樣帶主體名,模型看不到這些命中。
- 警告來源:lint 句級、speakable warn、`structure.json`(gate 只讀檔,不跑 script_structure,check-only 不動 build)。`revise` schema 多 `kept:[{key,reason}]`。warn_log 記 `fixed` 但警告還在 = 沒紀錄,要 `kept` + 理由才算齊。
- `pron-apply` 是新代理(`.claude\agents\pron-apply.md`);除 pron_rules/cosy_pron 也可追加 `pipeline\sub_words.txt`(接縫修法,words.txt 會被 tts_script 重產)。「只新增」由 director 比對(`_only_added`),違反就還原並算失敗。
- `pron_review.json`(schema 回傳)取代解析 md,status = 未決/已決/可疑,只有未決擋;`pron_apply.json` 記 added 與 backlog 處理紀錄;`build\<tag>\sub_scan.json` 是 sub_scan `--json` 產物。B4 只有一步 `pron`,內含 txt2json、tts_script、sub_scan 迴圈。
- commit 排除 `comments_ref\`(大檔);只有 A/B/B4 commit,C→E 照舊。

### flow v3(2026-11-03,`PLAN_token重設計_2026-11-03.md` §2(b) B1/B3/B4/B5/B6/B8)
`brief.json` 的 `flow`:缺 = `"v2"`(上表與上列實作差異,程式路徑不動);`"v3"` 走下表。單一來源 `specs.flow(tag)`(`director_ab.flow`、`gate_b` 都讀);一支片內不切。
| 步 | 做什麼 |
|---|---|
| write | 同 v2,另給 `Bash` 與 `--allowedTools` 白名單(`WRITER_ALLOWED`:`python -X utf8 pipeline/{script_lint,speakable,script_txt2json,facts_check,visual_check,script_structure}.py`,兩種分隔符)。寫稿員自己跑到 lint 擋 0、硬項 0、facts_check 0;保留的警告寫 `projects\<tag>\warn_log_writer.json` = `[{check, line(script.txt 行號), code, action:"kept", reason}]`,director 用 `gate_b.warn_mark` 換成句雜湊鍵併進 warn_log(`merge_writer_log`,只併本次寫的檔)|
| speak / lint | 同 v2(自檢過了就不花 LLM;殘留才 line_fix / revise)|
| review | 取代 editor + player:①editor r1(四類、只回 JSON,director 產 `editor_review_r1.md`)與 player r1(現行 prompt)**平行**審同一版稿;②editor 四類全部 + player `PLAYER_MUST` → **一次** revise(B6 機械驗)→ `_recheck`;③玩家審只驗改過的句(`_spot_items`,>20 句分批),必處理 → 再 revise+recheck+spot,迴圈 ≤2;④r2 = `fact-check`(Sonnet)全稿只查錯/查無,「錯」→ revise → 只驗那些句一次;⑤結算 |
- **B4 v3**(B2,`step_pron_v3`):`step_b4_prep`(txt2json → tts_script → sub_scan)→ `pron_pre.candidates(tag)` → **n == 0:不呼叫 LLM**,直接寫 `pron_review.json = {counts, items:[], source:"pron_pre"}`;n > 0:一次 Sonnet `pron-review`(tools 只給 Read;prompt = 候選 JSON + 候選字的 `pron_rules.json` 現有條目 + `_doc` + decision 格式)→ 回 `items:[{line,kind,char,word,current,status,decision,basis}]` → `pron_apply.apply` 逐條程式寫入 → 重跑 prep + 候選;LLM 最多 2 輪,之後只重算,剩的寫成未決並卡點。可疑且無 decision 的條目記 `可疑` 不擋。
  - 候選來源 `build\<tag>\tts_script.json`(tts_script.py 另寫,結構化 lines/open;md 與送引擎文字不變)與 `sub_scan.json`(新增 `seam_list`/`seam_list_judge`,每個接縫的詞與「是否為斷詞器單一 token」)。接縫詞是單一 token → 程式直接寫 `projects\<tag>\seam_words.txt` + `build\<tag>\words.txt` 並重跑 sub_scan(已凍結片不寫;tts_script 重產 words.txt 時併入 seam_words.txt);仍剩的才是候選。多音字 = tts_script 算進「未決」者(unverified 命中、g2p 不一致、記憶 bad),附 `tts_moe.lookup`(字與語境詞)與該字規則條目;詞規則的 `note` 含「讀音審」者視為已審過不再列;本片 `pron_apply.json` 的 `decided` 帳本(`pron_apply.record_seen`)同理。英文 = 未登錄與直送多次。backlog = `gate_b4.backlog_pending`。
  - `pron_apply.apply(decisions, tag)`:kind = rule/word/term/sub_word/backlog;只新增、驗 py token(tokenizer)與 re、詞含該字與 pos;原子寫,寫後 `_only_added` 自驗不符還原;backlog 只記進 `pron_apply.json`。`pron-apply` 代理仍給 v2 用。
  - `gate_b4.status`:v3 看 `pron_review.json`(不要求 `.md`);`run` 四項不變。
- **B9 步驟雜湊**(v3):`production.json` 的 `step_hash: {"<seg>/<step>": sha8}`,步驟成功(沒丟 Block)後記下輸入雜湊(`memoized`);`A/assets` = plan.json 各 claim 的 id+visual(再加原本的 mtime 判斷)、`B/review` = 旁白雜湊 + facts.md(只記錄,略過仍由 `review_skip` 決定)、`B4/pron` = 送配音文字 + `pron_rules`/`cosy_pron`/`cosy_terms`/`sub_words` + seam_words.txt。雜湊相同且該步 gate 仍過(B4 看 `gate_b4.run`、assets 看 manifest 存在)→ 略過並印原因。
- **ask_user 規則**:錯/關掉(spot 或事實專審後仍在、或 revise 沒改到)+ 誇大/可疑/相反(revise 後仍在)→ 整批寫 `ask_user.json`,卡點 `要問使用者:N 條`;推論/矛盾/外行/吵/查無 → 只記 `review_state.soft`,不擋。`ask_user.json` 未清 → review 步直接卡點不花 LLM;主對話清空後重跑 = 該批結案(移到 `resolved`)。
- **`projects\<tag>\review_state.json`**:`{narration(審完時旁白 sha8), rounds:[{kind,file,items,lines?,at}], stage(中斷接續:r1/revised/spot/fact), pre(r1 當時旁白), spot_left, fact_left, open_hard, ask, soft, unresolved(B6 退回), resolved, done}`。重跑:done 且旁白沒變 → 整步 skip;旁白變了(主對話手改)→ 只對改過的句做玩家小範圍審 + 事實專審(平行),命中直接問,不重來。編輯審只跑一輪,旁白改動不重跑。r1 報告的 narration 等於目前旁白就沿用(中斷不重審)。
- **gate_b(v3)**:「編輯審」= `editor_review_r1.json` 已合併改稿(有 `revised`)且每條在 `revised` 或 `kept`(有理由);「玩家審」= `review_state.done` 且 `open_hard` 空。其餘項目同 v2。
- **B6 revise 機械驗**(`revise(check=True)`,只 v3 用):每條 `new_line` 驗數字集合不變(該句條目 reason/fix 含 數字/日期/金額/%/阿拉伯數字 才放行)、行尾 hl 仍在、不含 `|`、`;;`、換行;不過的帶原因重送一次(`revise_retry`,只送不過的),再不過不套用、記 `unresolved`,條目照算未處理。`_guard_revise` 照跑。
- **B5(v2/v3 都適用)**:`_write_skip` = script.txt 已有就不重寫(plan/manifest/facts 較新只印提醒)。要整稿重寫:該次 run 前設環境變數 `CV_REWRITE=1`(暫代 `run --rewrite`,之後併成旗標)。
- **B8(v2/v3 都適用)**:`line_fix` 呼叫用 `agent="line-fix"`(`.claude\agents\line-fix.md`,Sonnet、只 Read)、`effort="low"`,改句規則與硬驗不變。
- `llm.build_cmd/call(allowed=…)`:給了就 `--allowedTools` 逐條傳(可含 `Bash(…:*)` 樣式),`--tools` 仍是工具名;沒給行為不變。
- 新代理:`fact-check.md`(Sonnet;Read/Grep/Glob/WebSearch/WebFetch)、`line-fix.md`;`editor-review.md` 縮成四類(prompt 給報告路徑才寫 md,v2 相容)、`script-writer.md` 加 Bash 與自檢一段。

## 6. gate(每支 `run(tag, ver, ctx)`/`status(tag, ctx)`,同 gate_c)
- **gate_a**:brief;context.md;共識 3–5 行;claims 每點 source/abs/visual 非空;facts 待查 0;manifest 全 ok;估片長(claims 依 blocks 加總)≥ floor,不足 = 不過,note「要問使用者:補素材/併題/照發」,`brief.allow_short` 放行。
- **gate_b**:lint 擋 0;warn_log 齊;facts_check 未連結 0、狀態不符 0;visual_check 錯誤 0;每句標籤對到實檔;speakable 硬項 0;編輯審連貫斷點 0;玩家審 錯/關掉 0;ask_user 空;**估片長 = 旁白字數 ÷ SPEECH_CPM,< floor 不過(allow_short 放行),< target 下限過但 note**。
- **gate_b4**:tts_script.md 比 script.txt 新;接縫 0;pron_review 未決 0;backlog 前 3 條有處理。
- 既有 `director.check_a/b/b4` 收進 gates(`status` 寬鬆推斷不變)。

實作差異(2026-10-31):`gate_a.run`/`gate_b.run`/`gate_b4.run` 的 `ver`、`ctx` 可省;`status` = 原 `check_a/b/b4`。「每句標籤對到實檔」= `gate_b.missing_labels`:`img:x` 在 `images\` 有 `x.*` 或 `*_x.*`,片段標籤在 clips `tags` 裡,`anim`、`cta`、卡片種類不查檔。平行模組未就緒 → 該項不過,不中止。`director --explain <段>` 印 `IDS` 與 `run` 的 docstring。C 段前置仍用寬鬆 `check_b4`(舊片沒有新 gate 的產物)。

## 7. C 段改句迴圈(改 `plan_steps` C 段)
`make_version --tts-review`(不帶 --freeze)→ 讀 `tts_review.json` failed/timing 與 `ear_e4_<ver>.json`(poly/particle/runon,garble 不改)→ 有句 → `line_fix(mode="qc")` → 重跑(只重錄改過的句)→ 全清或第 3 輪 → `--tts-review --freeze`。E4 句改過仍有旗標 → 留給必聽,不擋。品管未過到第 3 輪仍在 → 卡點。**不可放寬別名、不可動品管門檻**(記憶 no-alias-to-pass-qc)。已凍結片 line_fix 拒絕(`freeze.check` 為 None 且有 freeze.json)。

實作差異(2026-10-31):C 段新步 `改句迴圈`(`director_ab.step_qc`)排在 `配音凍結` 前,已凍結同樣略過。第 3 次 `--tts-review` 後不再改句:品管未過或無句號的時長錯誤 = 卡點;只剩 E4 → 進凍結。改過的 E4 行不再送改。`timing_errors` 從字串抓「句 N」換行號。

## 8. 介面(平行實作時彼此依賴這些,不可改名)
```python
# speakable.py
def check_line(text: str, says=None, names=()) -> list[dict]   # {code, severity:"err"|"warn", span, why}
def check_tag(tag: str) -> dict           # {lines:[{line, hits:[...]}], errors:n, warns:n}
def explain() -> str                      # 給寫稿 prompt 的短規則,≤40 行
# line_fix.py
def fix_lines(tag, items, mode, *, call=None, dry_run=False) -> dict
    # items=[{line:int, reasons:[str]}];mode="lint"|"qc"|"speak";call 預設 llm.call_escalating(測試注入)
    # 回 {fixed:[{line,old,new}], unresolved:[{line,why}], warn_log:[...]}
# script_lint.py
def check_sentences(tag, line_nos=None) -> list[dict]  # 句級子集:{line, code, block:bool, why}
# terms_check.py(英文詞單一來源)
def unregistered(texts) -> list[str]
def analyze(texts, terms=None) -> dict    # 原 tts_terms.analyze
# gates\specs.py
FORMATS; SPEECH_CPM; def spec(channel, fmt) -> dict; def est_minutes(tag) -> float
```
