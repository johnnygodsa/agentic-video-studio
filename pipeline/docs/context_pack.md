# context_pack.py:寫稿上下文組裝器

契約:`channel\_archive\plans\PLAN_文案資料驅動_2026-10-26.md` §3.5(讀 YTAD writer_brief §3.1、留言 json §3.3)。

## 用途
定題後、寫稿前每支片跑一次,把散在兩個 repo 的資料組成一份 `projects\<tag>\context.md`(給人/主對話讀)與 `context.json`(給 feedback.py 等程式讀)。全部唯讀,任何來源缺都降級,不中止。

## 指令
```
python -X utf8 pipeline\context_pack.py --tag <tag> --channel <ChannelA|ChannelB|ChannelC> [--event <id>] [--query "<kw>"] [--no-ytad] [--ytad-timeout 120]
```
- 頻道 → slot:ChannelA/ChannelA = main、ChannelB/ChannelB = c、ChannelC = d。
- 沒給 `--query` 時用 spec 的 `package.subject` 第一個當關鍵字;`--event` 與關鍵字都沒有就不跑 YTAD。
- 重跑覆蓋兩個輸出檔;stdout 只印一行摘要(YTAD 狀態、留言數、可信度抱怨數、舊片數、缺口數)。

## 來源與降級
| 來源 | 位置 | 失敗時 |
|---|---|---|
| A YTAD brief | `<ytad_root>\tools\intel_query.py brief <event\|-> --slot <slot> [--query] --json`(子行程,cwd = ytad_root) | 找不到腳本 / 逾時 / 非 0 / JSON 解析失敗 → 「Youtube AD 不可用:<原因>」,§1 2 3 6 8 寫「無資料」 |
| B 留言 | `projects\<tag>\comments_ref\*.info.json`(yt-dlp)+ `paths.ytad_comments_dir()\*.json`(只取 comments_ref 或 brief 出現的影片 id) | 都沒有 → §4 無資料 |
| C 舊片 | `channel\outcomes.jsonl`(一行一支;同 subject、同 topic_class 或標題/subject 含關鍵字) | 不存在 → §5 註明;符合 n<3 只寫「資料不足」 |
| D subject | `projects\<tag>\spec.json`(沒有則 `spec_pkg.json`)的 `package.subject`、`topic_class` | 缺 → §7 列缺口 |

- `ytad_root()`:環境變數 `YTAD_ROOT` 優先,否則同 `yt_ad_root()`(與 trend_db 同根)。
- 留言處理:先以 id、再以正規化文字(小寫、去標點空白)合併,讚數取大、影片取聯集,純表情剔除。每支影片先取讚數前 10 則再合併(免得單一熱門英文片淹掉中文玩家)。語言依字元比例判定:漢字佔字母類字元 ≥30% = zh(含簡體),拉丁字母 ≥50% = en,其餘 other(不列)。zh、en 各自單鏈結分群(jieba 可用時比詞重疊;否則中文用字 bigram、英數用整詞)Jaccard ≥ 0.3,依合計讚數列前 8 群(代表原句 ≤120 字、合計讚、則數、來源影片、旗標)。中文全部不足 20 則時不分群,全部列出。
- 旗標:`pipeline\comment_lexicon.json`(資訊錯誤/沒玩過/AI/標題誇大/邏輯/立場附和;子字串、不分大小寫、啟發式精度未知);`credibility` 列出算「可信度抱怨」的五類,立場附和不算。旗標計數用去重後全部留言,依語言分開;範例只列中文,英文只給計數。與 YTAD comment_flags 詞表同義,改動要互通。

## context.md 章節(固定)
`0 摘要與警示 / 1 事件事實與一手來源 / 2 需求與競品覆蓋 / 3 飽和度 / 4 玩家共識候選 / 5 本頻道可比片與教訓 / 6 受眾輪廓 / 7 待查疑點與資料缺口 / 8 brief 必填欄`
- 每段首行 `來源:…|as_of:…|n:…`;缺資料的段只有一行 `無資料:<原因>`。
- §0 警示:brief flags、留言可信度抱怨數、同事件第 ≥3 支(弱證據)。
- §4 依序:來源影片表(每片一行:id、標題 ≤30 字、頻道、觀看、留言數、上傳日、zh/en/other)→ 總數 → `### 4a 中文玩家` → `### 4b 英文玩家`。內容是候選,人工判讀後才寫進 facts.md「玩家共識(閘門 1)」,以中文玩家為主。
- §8 四欄可直接貼進 brief:事件 ID;heat 與來源數(註:heat=報導量);官方預告有無(event.links 有無 tier=official);同事件近 7 天已發 N 支 = `own_same_event_7d + own_reposts_same_event_7d`(另列姊妹頻道)。

## context.json 主要鍵
`schema(context_pack/1), tag, channel, slot, generated_at, event_id, competitor_videos_7d, same_event_seq(= own_same_event_7d + 1), subject, topic_class, query, ytad{used, ok, error}, brief_fields, comment_sources[](影片表), comments_zh_n, comments_en_n(去重後全部則數), comments{n_raw, n_total, n_other, sources, zh{n, n_sampled, listed_all, items[], groups[], by_flag, credibility_total, flagged_examples}, en{同 zh 但沒有 flagged_examples}, by_flag, credibility_total}, outcomes{path, exists, n, matches[]}, gaps[], brief(原始 doc)`

## 測試
`python -X utf8 -m pytest pipeline\tests\test_context_pack.py -q`;fixture 在 `pipeline\tests\fixtures\context_pack\`(brief.json、project\spec.json + comments_ref 三個 info.json(中文兩支;英文一支 12 則,用來測每片配額)、ytad_comments 兩檔(一檔無關需被略過)、outcomes.jsonl)。`_run_cli` 以 monkeypatch 回 fixture 或模擬逾時/非 0/亂碼;`_jieba` 強制為 None 測 fallback;輸出寫 repo `tmp\test_context_pack_*`,結束即刪。
