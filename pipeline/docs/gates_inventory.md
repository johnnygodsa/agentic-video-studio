# 檢查點盤點(C→E)
盤點日 2026-10-31(log-analyzer 代理唯讀盤點,主對話落檔)。總 67 項:硬擋 41、警告 14、只印 12(D1「檢查」步為彙總,不計入)。路徑皆在 `pipeline\`。
「硬擋」= 結束碼非 0 且 make_version 中止(或明確 sys.exit);「警告」= 有判定但不中止;「只印」= 產清單/報告,無判定。
用途:Phase 2 `gates\` 統一的依據(計畫 §6.2);改完一項就在這裡把狀態改掉,不另開檔。

## C 配音(24)
| # | 段 | 名稱 | 檔:行 | 檢查什麼 | 硬擋/警告/只印 | 重複或相近 |
|---|---|---|---|---|---|---|
| C1 | C | 凍結文本比對 FZ.check | make_version.py:372 → freeze.py:115 | 已凍結片的配音文本 narration_sha 與 freeze.json 一致(--tts-review 不受限) | 硬擋 | C2,C16,C19 |
| C2 | C | 配音稿 --verify | make_version.py:375 → tts_script.py:172-190 | 送引擎文字與 freeze.json 重算比對(CV_REFREEZE_OK=1 可繞) | 硬擋 | C1,C16 |
| C3 | C | script_lint | make_version.py:111,145 → script_lint.py:725 | 句長/字速/判斷句/kit 等超標;另 v2 與連貫警告(--strict 才升格) | 硬擋(超標)+警告 | D13(kit),D8(畫面單調) |
| C4 | C | sub_scan 接縫 | make_version.py:112,150 → sub_scan.py:106 | 字幕拆段切開詞(jieba 拆、ckip 互判) | 硬擋 | D9,tts_script.py:265 |
| C5 | C | sub_scan 片語切開 | sub_scan.py:87,105 | 功能詞後/數量詞/英文名中間切開 | 只印 | C4 |
| C6 | C | spec_check | make_version.py:113 → spec_check.py:128/220/350/399,732 | facts 覆蓋、譯名表、標題 5 個/字數、封面方案文字、判語近 N 天重複、素材疊動畫 | 硬擋(errs)+警告(warns) | C9,E2,D12(素材疊動畫) |
| C7 | C | visual_check | make_version.py:114,155 → visual_check.py:595 | 句畫對應:數字句配片段、hl 找不到(E1)、@def 未定義(E2)、同圖估秒 | 警告(程式回 exit1 但 make_version 不中止) | D6(hl),D8(同圖),C17 |
| C8 | C | script_structure | make_version.py:115,159 → script_structure.py:337 | 開場鉤子/新事實/實體/數字結構 | 警告 | C3 |
| C9 | C | facts_check | make_version.py:118,162 → facts_check.py:250 | 事實核對表對稿覆蓋(有 facts*.md 才跑) | 警告 | C6 |
| C10 | C | 英文詞對照 tts_terms | make_version.py:429 → tts_terms.py:128 | 英文詞未登錄/已登錄唸法未套用 | 硬擋 | C14,C23,C12,tts_script.py:247-255 |
| C11 | C | GPU 全機鎖 | make_version.py:507 → gpu_lock.py | 排隊,顯存已用 ≤3000/4000 MiB 才跑 | 硬擋(等待) | 無 |
| C12 | C | C0 風險句試配 | tts_c0.py:372-414(結束碼 3 唸錯/1 合成不全) | 風險位置試配多 seed,唸錯 0 才過;不在 make_version 內,人工先跑 | 硬擋(只在 dispatch --prefer 閘門) | C10,C14 |
| C13 | C | 後端調度 | tts_dispatch.py:445 | 印 Colab/Kaggle/本機狀態;--prefer 才檢 C0 報告 script_sha | 只印(+C12 閘門) | C12 |
| C14 | C | 單句品管 QC | tts_chattts.py:612-646;tts_cosy3.py:392-411;tts_tail.py:9(qc8) | pitch/speaker/content/pron/句尾/停頓/tail_rise/term_misread/asr_insert/asr2_bad 等,未過換 seed 取最佳 | 警告(重錄後仍未過只記 failed) | C10,C15 |
| C15 | C | 品管未過彙總 | build.py:272-287,466-469 | 寫 tts_qc.json,未過單位印「警告: TTS 品管未通過」 | 警告 | C14,C18,C19 |
| C16 | C | 凍結後禁新合成 | build.py:356-365,449;--no-synth 447 | 快取未命中(含重新檢驗)exit 2 / exit 1,不動音檔 | 硬擋 | C1,C2 |
| C17 | C | 時長預檢 | make_version.py:435,553 → build.py:3787 | 同圖>9 秒/>2 句、鏡頭最短、動畫步秒數、卡片(缺素材不算) | 警告(紅字不中止,記 timing_errors,凍結才擋) | D8,D10,D11,D12 |
| C18 | C | 審核紀錄 tts_review.json | make_version.py:201-214,554 | 寫 units/failed/no_qc/timing_errors/keys sha;缺 tts_qc.json 即失敗 | 硬擋(缺檔)/其餘只記錄 | C15,C19 |
| C19 | C | 凍結門檻+自動凍結 | make_version.py:630-646 → freeze.py:80-107 | script sha、品管未過 0、無紀錄 0、時長錯 0 才凍結,否則結束碼 3 | 硬擋 | C1,C2,C16 |
| C20 | C | 配音報告 | make_version.py:444 → tts_report.py:76 | 句界靜音/語速偏差診斷,寫 projects/<tag>/tts_report.json | 只印 | C14 |
| C21 | C | E4 耳朵 | make_version.py:445,547 → senses/ear_e4_pinyin_ctc.py:254 | 拼音級 CTC 旗標多音字/輕聲/逗號停頓 | 警告(失敗不中斷) | C14,C22 |
| C22 | C | 優先聽清單 | make_version.py:447,564 → listen_page.py:110 | 依品管/E4/聲紋邊緣/未驗證讀音挑句 | 只印(但寫檔失敗 rc=1 會中止) | C14,C21 |
| C23 | C | 唸法清單 | make_version.py:459,570 → decide_list.py:98 | 未驗證英文詞/讀音標注/多音字前 15 筆 | 只印(失敗不中斷) | C10,C12 |
| C24 | C | 聽審頁 | make_version.py:460,582 → listen_page.py:240 | 產 HTML | 只印(失敗 rc=1 中止) | C22 |

## D 畫面(26;D1 為彙總不計)
| # | 段 | 名稱 | 檔:行 | 檢查什麼 | 硬擋/警告/只印 | 重複或相近 |
|---|---|---|---|---|---|---|
| D1 | D | 渲染前檢查(彙總) | make_version.py:438 → build.py:5228-5362 | build --check-only,errors>0 exit 1;含 D2–D18 | 硬擋 | D19 |
| D2 | D | 素材存在 | build.py:5270,5284,5286;1083 | raw/*.mp4、images/*.png 不存在 | 硬擋 | 無 |
| D3 | D | 片段挑不到/來源上限 | build.py:1184,5319 | 標籤挑不到 N 秒片段;單一來源 > max-per-src | 硬擋 | 無 |
| D4 | D | 放大仍洩漏字幕/浮水印 | build.py:5279 | 裁切洩漏 ≥3px | 警告(look_list 收) | D26 |
| D5 | D | layout 欄位 | build.py:1016,1030 | 不支援 fx、句無畫面 | 硬擋 | C7 |
| D6 | D | precheck_images | build.py:3640-3655 | 重點區過大、hl 在圖上找不到 | 硬擋 | C7(hl) |
| D7 | D | 文字裁切/補邊 | build.py:3659,3739 | 截圖邊緣裁到文字、動態露出畫布外 | 硬擋 | 無 |
| D8 | D | 同圖連續 | build.py:3753,5303 | >9 秒或 >2 句 | 硬擋 | C7,C17,C3 |
| D9 | D | 字幕接縫 | build.py:1756,5304 | 拆段切詞 | 硬擋 | C4 |
| D10 | D | 硬切/鏡頭時長 | build.py:3819,3833 | 離頭尾不到 N 秒、鏡頭最短、同片段最長 | 硬擋 | C17(同函式重用) |
| D11 | D | 卡片規劃 | build.py:3880,3890,5313 | 卡片疊在非影片/截圖、顯示秒數不足 | 硬擋 | C17 |
| D12 | D | 動畫參數與秒數 | build.py:4361-4431,5311 | 類型/欄位/step、最後一步停留 | 硬擋 | C17,C7,C6 |
| D13 | D | kit 節制 | build.py:3063,5335 | kit t0、同句上限 | 硬擋 | C3 |
| D14 | D | 動畫容量 | build.py:3202,5337 | 網頁動畫字級/安全區/重疊 | 硬擋 | 無 |
| D15 | D | label_style | build.py:2755,5293 | 標籤樣式名稱 | 硬擋 | 無 |
| D16 | D | 轉場/劇透警告彙整 | build.py:4659,4661,5340 | 轉場超量、glitch、小件放不下 | 警告 | D26 |
| D17 | D | 直式檢查 | build.py:5016-5045 | 直式總長/鉤子字數/字幕安全框/按鈕區 | 硬擋(errs)+警告 | 只直式 |
| D18 | D | 小件擺放檢查 | build.py:5343 | try/except,失敗只記警告 | 警告(失敗不擋) | D13 |
| D19 | D | 渲染內同檢查再跑 | build.py:5363-5366 | 渲染階段重跑 D2–D18;errors 且無 --force exit | 硬擋(--force 可繞) | D1 |
| D20 | D | 成片音軌缺口 | build.py:5551-5554 | audio_gaps;印「錯誤…不可交付」但不 exit | 只印(實為錯誤沒擋) | E7(deliver 不查) |
| D21 | D | 字幕最寬 | build.py:2016 | 橫式警告;直式寫「錯誤」同樣只 log | 警告 | D17(5030) |
| D22 | D | BGM 動態 | build.py:5478 | p90-p10、max-p50 過大建議換曲 | 只印 | 無 |
| D23 | D | 劇透牌寬度 | build.py:1268 | 牌寬超畫面即 sys.exit | 硬擋 | 無 |
| D24 | D | 預覽大小 | make_version.py:516 | 720p < 29,000,000 bytes(僅 --preview) | 硬擋 | 無 |
| D25 | D | QA 總覽圖 | make_version.py:442 → qa_sheet.py | 每 6 秒一格,無判定 | 只印 | 無 |
| D26 | D | 優先看清單 | make_version.py:448,576 → look_list.py:212 | 收 build log 警告、lint visual 警告、assets 側檔警告 | 只印(失敗不中斷) | D4,D16,C7 |
| D27 | D | 文案檢查與英文詞對照重跑 | make_version.py:427-430(完整版同樣跑,除非 --skip-checks) | 同 C3–C10 | 硬擋 | C3–C10 |

## E 自審上片(17)
| # | 段 | 名稱 | 檔:行 | 檢查什麼 | 硬擋/警告/只印 | 重複或相近 |
|---|---|---|---|---|---|---|
| E1 | E | 說明檔與發片資料區塊 | make_version.py:291,543;deliver.py:225,241 | 說明檔存在、能解析【YouTube章節摘要】~【輸出完畢】 | 硬擋(make_version 端印「未交付」exit 0) | E5 |
| E2 | E | 封面人像跨片重複 | make_version.py:533 → spec_check.py:569-607 | 六格/手勢/場景與近 N 筆相同 | 硬擋(未交付但 exit 0) | C6 |
| E3 | E | 封面檔 | deliver.py:100-114 | 存在、PNG、1920x1080 或 1280x720 | 硬擋 | E4 |
| E4 | E | 科普頻道必須有封面 | deliver.py:231 | 無封面 sys.exit | 硬擋 | E3 |
| E5 | E | enqueue 資料齊全 | deliver.py:75,235-239 | 署名、發片資料、「(待填)」,exit 2 | 硬擋 | E1 |
| E6 | E | 署名區塊/長片連結 | deliver.py:242-245 | 缺署名、仍是「長片發布後填」 | 警告 | E5 |
| E7 | E | 成片解析度 | deliver.py:259-262 | 必須 1920x1080(Shorts 1080x1920) | 硬擋 | 無(不查音軌缺口 D20) |
| E8 | E | 目的同名檔 | deliver.py:263-273 | 內容不同須 --force | 硬擋 | 無 |
| E9 | E | 複製大小 | deliver.py:280 | 複製後大小相符 | 硬擋 | 無 |
| E10 | E | 參數相依 | deliver.py:194-205;make_version.py:355-362 | --enqueue 需 --channel、--publish-at 需 --enqueue、--freeze 需 --tts-review | 硬擋 | 無 |
| E11 | E | 入佇列 | yt_queue.py:10(rc 0/1/2) | 後端沒開 rc 2、其他錯 rc 1 | 硬擋 | 無 |
| E12 | E | 排程 | yt_queue.py:147-159 | 失敗只警告,印補排程指令 | 警告 | 無 |
| E13 | E | 進度板更新 | make_version.py:217-236 | 失敗只印警告 | 警告 | E14 |
| E14 | E | 階段名稱 | board.py:160 | stage 必須在 STAGES;無任何前置條件檢查 | 硬擋(僅名稱) | E13 |
| E15 | E | 改稿凍結理由 | freeze.py:200-210 | --refreeze/--force 必須給 --reason | 硬擋 | C1 |
| E16 | E | 說明檔骨架 | make_version.py:523 → re9_notes.py | 已存在不覆寫、無 spec 略過;程式內無任何檢查 | 只印 | E1 |
| E17 | E | 結案回填 | feedback.py:396-474(--due,手動) | 72h 成效回填,無閘門 | 只印 | 無 |

## 重複與缺口
**重複(多處各自實作)**
- 英文詞:tts_terms.py:128(C10)、tts_script.py:247-255、tts_cosy3.py:395/409(term_misread/term_inconsistent)、decide_list.py(7 處引用 cosy_terms)、tts_c0.py(直送英文)、listen_page.py:140(cosy_en)——6 個檔各判一次,規則分散。
- 凍結比對:freeze.check(freeze.py:115)、tts_script --verify(:172-190)、build frozen_abort(:356)、review_problems(freeze.py:80)、colab/pack_for_colab.py:136、shorts_build.py:246、tts_dispatch 的 C0 script_sha——7 處,sha 計算有 narration_sha 與整檔 sha256 兩套。
- 字幕接縫:build.check_sub_seams、sub_scan.py、tts_script.py:265(B4);且 D 段完整版 make_version 又整串重跑 C3–C10(D27)。
- 同圖/動畫秒數:visual_check(C7)、script_lint 畫面單調(C3)、timing_only_check(C17)、build D8/D12 四處;kit 規則 script_lint 與 build D13 各一份。
- BGM 常數:make_version.py:66 BGM_BY_CHANNEL、build.py:3463-3540(BGM_BELOW_VOICE_DB 5.7 等)、sci/make_film.py:280 自行重做同算法、曲側檔 .json、CLAUDE.md「BGM 音量」節;測試 tests/test_make_version_bgm.py。

**只印警告沒人處理**
- C8 script_structure、C9 facts_check、C20 tts_report 的警告只進 json/md,未進 look/listen 清單(look_list 只收 build log、lint、assets 側檔)。
- C7 visual_check 的「錯誤」(@def 未定義、hl 找不到)結束碼 1 卻被 make_version 當不中止;hl 後面由 D6 補擋,@def 未定義沒有第二道。
- C15 品管未過只印警告;非 --tts-review 的完整渲染不擋(只靠 C16/C19 與凍結)。
- D20 成片音軌缺口寫「錯誤…不可交付」但 build 不 exit,deliver(E7)也不查;D21 直式字幕「錯誤」同樣只 log;D22 BGM 動態只印。

**失敗不中斷(或不一致)**
- 不中斷:C17 時長預檢、C21 E4 耳朵、C23 唸法清單、D18、D26 優先看、E12 排程、E13 進度板、C7/C8/C9 執行失敗。
- 反例不一致:C22 優先聽、C24 聽審頁寫檔失敗 rc=1 直接中止整版。
- 緊急繞過:--skip-checks(文案檢查+英文詞)、build --force(D19)、CV_REFREEZE_OK=1(C2)、deliver --force(E8)、tts_dispatch --skip-c0。

**缺口**
- 舊 0_流程 完成定義(C ①–⑤、D ①–③)沒有程式驗證;board.set_stage(E14)只驗名稱,可無條件推階段。
- deliver 不查:凍結狀態、渲染前檢查是否通過、QA/look 是否處理、成片時長是否在頻道片長帶、成片響度(無 LUFS/峰值檢查)。
- 封面:pipeline 內沒有 cover*/mindvideo* 程式(封面在 Youtube AD 後端);封面圖只有 E3 尺寸與 spec_check 文字欄位,168x94 可讀、字逐字對照為人工(4_交付發片 §封面)。
- 結案/72h 回填/24h 留言無閘門(E17),靠 handoff 待辦。
- C12(C0 試配)不在 make_version 步驟表,只在 tts_dispatch --prefer 才檢。
- make_version 檔頭 docstring 仍寫「三項」文案檢查,實際為六項(:31 vs :110-119)。

## 狀態(2026-10-31 深夜;Phase 3 尾項同日補)
- 已做:1(gate_c/d/e + deliver `--enqueue` 先過 gate_d,aae9ca2;board 前置條件已做,見下)、2(C7/D20/C15 升硬擋,aae9ca2)、3(`review_md.py` → `review_<ver>.md`,f8a93f6;三份原清單照舊)、`tts_review.json.new_synth`(a0ef49a)。
- 已做(2026-10-31 後):凍結 sha 收成 `freeze.text_same/narration_sha`(de18e45)、BGM 常數收成 `audio_consts.py`、`board.set_stage/update` 設已凍結要 gate_c、已排程要 gate_e 全 ok(`--force` 繞過;make_version/freeze 自動流程傳 force)。
- 已做(Phase 3,2026-10-31):gate_a/gate_b/gate_b4、片型規格單一來源 `gates\specs.py`(gate_d 片長改用它,ChannelB下限 5)、director A→B4 與 C 段改句迴圈(`docs\director_ab.md`)。
- 已做(Phase 3 尾項,2026-10-31):gate_e 加 `spec_check`(呼叫既有 spec_check.py --tag,錯誤 0;無 spec.json 略過);gate_c 加 `唸法`(讀 decide_<ver>.md 摘要行,英文+讀音未定 0;檔不存在視為沒有待定,舊片相容;疑似誤讀不算);`visual_check` 新警告 O(開場第 1–6 句文字卡〔截圖/引言卡〕連續 >=3)、Q(引言卡 @def 缺 who),最近 10 支實掃 O 1 支、Q 0;`taste_run` T32 由 gap 改 pass(visual_check H + build.precheck_images 壞例/好例實測);`make_version` 不給 --img-prefix 時讀 script.txt 說明行「前綴 xx_」(director C 段改句迴圈 `step_qc` 不帶前綴,每輪 make_version 第一步 txt2json 會重轉 script.json)。
- 未做:5 失敗不中斷一致化、C12 C0 進 make_version 步驟表。4 英文詞檢查由 terms_check 那支處理。
- **規則有、程式沒擋**(2026-10-31 盤點,靠人或代理自守;要擋再開項目):
  - 選題會議完成項(`1_選題.md`:選題會議與反駁、觀眾人設)——gate_a 只查 brief/context/共識欄位,不查會議紀錄。
  - QA 圖與 look 清單「逐項看過」(`3_製作.md`)——gate_d 只查 qa_<ver>*.png、look_<ver>.md 存在,不查處理紀錄。
  - handoff 必填欄位(`0_流程.md`:段末 handoff)——沒有程式驗必填。
  - 自製動畫鏡頭比例約 13%(`3_製作.md`)——visual_check 只印各類比例,不判上限。
  - 標題 5 個中至少 4 個以名字開頭(`4_交付發片.md`)——spec_check 只擋長度與必含主體名/數字,「4 個名字開頭」未驗。
  - 公開後 24h 留言、72h 回填(`4_交付發片.md`)——無閘門,靠下一支開工時順手做。

## Phase 2b 處理順序(主對話 2026-10-31 定)
1. gate_c/d/e(director)補上述缺口:deliver 前必須 gate_d 過(含 D20 音軌缺口、片長帶、LUFS);board 推階段加前置條件(E14)。
2. 升硬擋:C7 visual_check 錯誤、D20 音軌缺口、C15 品管未過在完整渲染也擋(非 --tts-review 且未凍結就中止)。
3. 警告進清單:C8/C9/C20 的警告併入 look/listen → 一份 `review_<ver>.md` 三節(聽/看/決定),取代 listen_/look_/decide_ 三檔(清單仍各自產生,review 只彙整)。
4. 去重:英文詞檢查收成 `terms_check.py` 一處;凍結 sha 收成 `freeze.narration_sha()` 一處;BGM 常數收成 `audio_consts.py`。
5. 一致性:失敗不中斷的步驟統一「記 warn 進 production.json」,寫檔失敗一律不中止整版。
