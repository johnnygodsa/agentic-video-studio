# start_session brief 模板(開下一段對話用)

> prompt ≤ 600 字,background ≤ 600 字。必填欄只寫「路徑 + 一句結論」,細節留在 handoff。`context: fresh`、`use_worktree: false`、**model/effort 見 0_流程 §4**:ab = `claude-opus-5-5`/`high`,cde = `claude-opus-5-5`/`medium`。開成功後立刻 `detach_session(<子 id>)` 與 `board.py set <tag> --session <子 id>`,再 wrap_up,本對話結束,不留著等通知。

## prompt(任務本身)
```
繼續製作 <tag>(<頻道>,第 <N> 段:<A 資料+B 文案|C 配音+D 畫面+E 自審上片|改版>)。
第一步只讀 projects\<tag>\handoff.md(第 <N-1> 段交接),不要讀整個 projects\<tag>\,不重查、不改已定稿的文案、不問 handoff「已定」節裡的事。
本段做到:<例:C 配音 --tts-review --freeze 自動凍結 → D 畫面渲染前 0 錯 → E 自審排程、發否決窗訊息 → 結束>。每段完成定義見 0_流程 §1,缺一不進下一段。模型與智慧程度已由本 brief 設定,不寫建議、不問使用者。
```

## background(給沒看過前段的人)
```
檔案:<tag>\script.txt <句數> 句(lint 0、tts_terms 0 錯,commit <hash>);截圖規格 pipeline\assets_<簡稱>_news.py <有/無>;片段 projects\<tag>\clips.json <有/無>;前綴 <xx_>。
進度板:channeloard.md(其他片的階段與 GPU 需求看這裡,不讀各片 handoff);GPU 由 gpu_lock 排隊,背景跑等通知(0_流程 §6)。凍結:<未凍結|已凍結 <日期>>,凍結只鎖配音文本,畫面欄位照改;改旁白走 refreeze(2_文案 §7)。素材清單:截圖 <N/N>、片段 <N/N>(段 A 完成定義)。
規則:專案 CLAUDE.md + channel\規則\README.md(依階段讀對應檔)+ 頻道檔;截圖代理給 pipeline\docs\assets.md 與 assets_TEMPLATE_news.py。
上下文:projects\<tag>\context.md(context_pack 產生 <日期>;Youtube AD <可用|不可用>),寫稿前讀完。
文案結構(摘自 handoff「文案結構」節):論點清單 <路徑或 N 點一句結論>;結構大綱 <路徑或一句>;逐句畫面表 projects\<tag>\visual_table.md <未解警告 N>;自查 <script_lint 警告 N、visual_check 警告 N>。
譯名表(查證階段 researcher 必填,寫進 projects\<tag>\spec.json 的 tw_names(不是 names,那是真人姓名清單);沒有外文專名寫「無」):{"原文": {"tw": "台灣譯名", "avoid": ["常見他譯"]}};spec_check 會擋字幕/@say 出現 avoid 他譯、或出現原文卻同句沒譯名。<列出或「無」>。
使用者未決事項:<無|列出>。
選題依據(規則見 1_選題):事件 ID <intel 事件 ID>、heat <數值>(報導量)與來源數 <N>;官方事前預告 <有/無>;同事件近 7 天已發 <N> 支(含搬運);檔次 <…>;槽位 <…>;引用倍數 <自製|搬運,片長,形式>。
玩家共識(2_文案 閘門 1):<路徑 + 主流看法一句;我們的角度同/異>。
選題會議(1_選題 §10):最強反駁 <一句> → 回應 <一句>;預失敗 <這支最可能敗在哪,一句>。
```
