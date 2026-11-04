# senses:感官層(耳朵 E1/E2/E3、眼睛、觀眾)

計畫在 `PLAN_工作室v2_2026-10-31.md` §6;程式在 `pipeline\senses\`。本檔每個感官一節,各自維護。

## E3 音訊模型審聽(Gemini API)

- 程式 `pipeline\senses\ear_e3_gemini.py`,測試 `pipeline\tests\test_ear_e3.py`(全 mock,不連網不需金鑰)。用配音環境 python:`tts_env_chattts\Scripts\python.exe -X utf8 pipeline\senses\ear_e3_gemini.py ...`。
- 定位:「多一隻耳」,不是唯一閘門(相關 0.6–0.7,論文 TTS-PRISM 表 1:Gemini-2.5-Pro 發音準確度 0.613、停頓 0.731)。上線門檻:對 ground truth 召回 ≥80%、對已通過句誤報 ≤10%;達不到只當優先聽排序。
- 金鑰只從環境變數 `GEMINI_API_KEY` 讀,不進 git、不印出;`--mock` 不需金鑰。

### 指令
| 用途 | 指令 |
|---|---|
| 單句 | `--wav <f> --text <t> [--expect '{"12":"zhe5"}']` |
| 整片 | `--tag <tag> --ver <ver> [--lines 1-3,7] [--redo]` → `projects\<tag>\ear_e3_<ver>.json`(逐句結果、usage)+ `.md`(未過句、issues 計數、token) |
| 真值 | `--truth channel\taste\ear\truth.json [--out f.json]` → 壞例召回、好例誤報表 |
| 共用 | `--model gemini-2.5-pro`(預設;新帳號不可用,免費層改 `--model gemini-3.5-flash-lite --fallback-model ""`)`--fallback-model gemini-2.5-flash`(空字串 = 不備援)`--rpm 5` `--mock` `--no-expect` |

- 整片模式每句做完即寫檔;已有結果且音檔 sha1 沒變、同為真/mock 模式就跳過(斷點續跑,重錄的句子自動重審),`--redo` 強制重審。失敗句記 `error`,下次續跑會重試。
- 音檔:`build\<tag>\<tts_dir>\NNN.line.wav`(多子句行)否則 `NNN.trim.wav`,再退 `NNN.wav`;文字取 `timeline_tts.json` / `timeline.json` 的 lines。
- 期望讀音:`--expect` 或 `tts_g2p.expected`(規則表/詞表指定的多音字,不含 default 來源)進 prompt;載入失敗就略過。
- 輸出 JSON:`pronunciation{score,issues[char,pos,heard_as_pinyin,expected_pinyin,kind]}`、`pauses{score,issues[after_char,kind]}`、`rate{score}`、`clarity{score,issues[]}`、`english_terms[]`、`overall_pass`、`rationale`;解析容忍 markdown 圍欄,缺欄補齊,分數夾 1–5。
- 真值檔(容錯格式,另一代理建):`{"items":[{id, wav 或 tag+idx, text, label:"bad"|"good", expect?, defects?:[{char,pos,kind}]}]}`。壞例命中 = 模型 issues 有同 char / pos / kind 之一;好例誤報 = `overall_pass=false`(另列任何 issue 的嚴格誤報率)。
- 呼叫:每句一次 generateContent;失敗重試 3 次(429/5xx/連線,指數退避、遵守 `retryDelay`),用盡改備援模型;`--rpm` 節流。

### 官方文件查證(2026-10-31)
- 音訊輸入:inline(`inlineData{mimeType,data}`)整個請求上限 20 MB;較大或要重用用 Files API(resumable 上傳,單檔 2 GB、專案 20 GB、保留 48 小時)。音訊 32 token/秒,支援 wav/mp3/aiff/aac/ogg/flac/m4a 等。本程式 ≤30 秒 inline,超過走 Files API(用完刪除)。
- 官方範例已改以新的 Interactions API(`POST /v1beta/interactions`,`input=[{type:"audio",data|uri,mime_type}]`、`response_format` 給 schema,範例模型 `gemini-3.8-flash`);`generateContent` 仍在 API 參考,本程式用它(`generationConfig.responseMimeType="application/json"`、`usageMetadata` 記 token)。
- 模型清單:現行有 gemini-3.8-flash、3.6-flash、3.5-flash-lite、3.1-pro-preview 等;**2.5 系列(pro/flash/flash-lite)仍可用、未棄用,但「限制給過去用過的使用者」**(新帳號可能打 404/403 → 走備援或改 `--model gemini-3.8-flash`);2.0 Flash 已 shut down。
- 免費層:價格表 Free Tier 欄為 Free of charge(2.5-pro、2.5-flash、3.8-flash 皆是;免費層資料會被用來改進 Google 產品)。各模型 RPM/TPM/RPD 的實際數字文件不列,要到 AI Studio rate-limit 頁看(依專案、RPD 午夜太平洋時間重置)。付費 2.5 Pro:輸入 $1.25、輸出 $10 每百萬 token(≤200k);3.8 Flash 到 2026-12-31 輸入 $0.75、輸出 $3.75。
- 沒用 `google-genai` SDK:`pip install --dry-run` 顯示會把 `tts_env_chattts` 的 pydantic 2.11.9 → 2.14.2、typing_extensions 4.15 → 4.16(gradio 5.46 等可能受影響;torch 不動),所以改用標準函式庫 urllib 直接打 REST,零新增依賴。
- 網址:
  - https://ai.google.dev/gemini-api/docs/audio
  - https://ai.google.dev/gemini-api/docs/files
  - https://ai.google.dev/gemini-api/docs/rate-limits
  - https://ai.google.dev/gemini-api/docs/models
  - https://ai.google.dev/gemini-api/docs/pricing
  - https://ai.google.dev/api/generate-content

### 真跑結果(2026-10-31,免費層)
- 新帳號免費層:2.5 系列 404(「no longer available to new users」);3.1-pro-preview / 4-argon / omni 免費額度 0(429 limit 0);3.8/3.6/3.5-flash、flash-latest、3.1-flash-lite 整晚 503 high demand;**只有 `gemini-3.5-flash-lite`、`flash-lite-latest` 能跑**。要用 pro 得開付費。
- 原版提示(附參考文字審稿)對真值 130 筆:召回 2%、誤報 0%,不能用。
- 盲聽版 `pipeline\senses\ear_e3_blind.py`(不給文字,逐字轉寫+帶調拼音+停頓,程式用 pypinyin 對齊比對;快取 `tmp\ear_e3_blind_cache.json`,`--rescore` 不打 API 重算):召回 80%、好例誤報 96%、多音字位置級誤報 9% 但讀音命中 7/16、排序 AUC 0.60。lite 轉寫雜訊太大,不上線;程式留著給付費層模型重測(`--model gemini-3.1-pro-preview`)。
- 真值檔實際格式是扁平欄位(`audio`、`kind`、`line`、`issue`、`char`、`pos`),`load_truth` 已相容;`issue` 文字決定算哪類 issue 命中(斷句/停頓→pause,英文→english,多唸/吞音→pron+clarity,讀音→char/pos)。

## E4 本機拼音級 CTC 耳朵(2026-10-31,採用為 C 段額外旗標;0 token、本機 GPU 0.3 秒/句)

- 程式 `pipeline\senses\ear_e4_pinyin_ctc.py`;模型 `tts_models\ear_e4_pinyin_ctc\`(HF `snu-nia-12/wav2vec2-large-xlsr-53_nia12_phone-pinyin_chinese`,wav2vec2-large CTC,詞表 218 = 聲母 + 帶調韻母 + y 開頭整音節,`u:` = ü;原檔是 fairseq checkpoint 3.8 GB,已用 weights_only 安全載入 + 鍵名對映轉成 HF `model.safetensors` 1.2 GB,原檔留 `pytorch_model.bin.fairseq_orig`;不進 git)。
- 為什麼是它:無語言模型的拼音級輸出不會被字面拉回「正確」讀音(字級 ASR 會把 huán 仍寫成「還」),能直接看到同字異音換讀、garble、輕聲變實調;CTC 幀時間給出停頓長度。
- 用法:
  | 用途 | 指令 |
  |---|---|
  | 整片(生產) | `--tag <tag> --ver <ver> [--lines 1-3] [--redo]` → `projects\<tag>\ear_e4_<ver>.json` + `.md`(有旗標的句子);音檔 sha1 沒變就跳過 |
  | 單句 | `--wav f.wav --text "參考文字"`(全句自由比對,研究用) |
  | 真值 | `--truth channel	aste\ear	ruth.json --out tmp\ear_e4.json [--rescore]`(快取 `tmp\ear_e4_cache.json`) |
- 旗標(生產只用這四種,都是真值量過的):`poly` g2p 指定讀音的位置聽到該字的另一個字典讀音;`garble` 同位置聽到不在字典內的音節;`particle` 的/得 聽到 dé/dì/děi(輕聲 95% 穩);`runon` 參考文字逗號處 CTC 幀距 <0.15 秒。
- 真值實測(130 筆):全句自由比對聲調/音節句級誤報 92–96%(模型用韓籍學習者語料訓練)→ 不當全句閘門;窄旗標:好例句級誤報 4/85、讀音壞例命中 6/16(真值可信的 6 筆中 3 筆 + 聲調 2 筆;騎 ×5 兩隻耳都聽到 qí,是真值推斷錯),runon 誤報 1%。**定位:必聽與重錄候選,不自動擋、不自動放行。**
- 後續 E4b:用本片庫 QC 已過的 CosyVoice 句子(同音色)在 Kaggle 微調同一模型,目標聲調誤報壓到可用。候選 E5:小米 TTS-PRISM-7B(Kaggle 2×T4 要改 fp16/雙卡/關 flash-attn)。

## E2 聲調偵測(2026-10-31,PLAN_工作室v2_2026-10-31 §6.3;本機 CPU、0 token)
目的:估一句配音每個字實際唸成哪個調,與多音字期望讀音比,標出「唸成哪個調」。只是線索,不是閘門(門檻見下)。

- 對齊 `senses/ear_e2_align.py`:快取句直接用品管旁註 `NNN.qc.json` 的 `say_t`(品管時 Qwen3-ForcedAligner-0.6B 已對齊,第 i 字 = [say_t[i], say_t[i+1]],0 成本);任意音檔走 `tts_env_asr` 子行程跑同一個對齊器(`tts_models/asr/qwen3-forcedaligner-0.6b`,預設 CPU 約 25 秒/句含載模型;`--device cuda` 排全機 gpu_lock),結果換成 say_t 寫法。對齊器時間格點 0.08 秒(字邊界誤差的主因)。
- 特徵 `senses/ear_e2_tone.py`:librosa pyin F0(60–450 Hz)換成相對整句中位數的半音;每字 10 點(去頭尾 10%)、前後各延半字寬的 10 點、斜率/範圍/極值位置/有聲比、能量 3 點、長度、前後字 5 點輪廓與高低差、停頓;分類器 sklearn HistGradientBoosting,五類 1–4、5=輕聲,`tts_models/ear_e2_tone.pkl`(含 feat_ver,特徵改了要重訓)。
- 訓練資料:`build/<tag>/tts_cosy3|tts` 與 `tmp/c0`、`tmp/tts_speedup` 的 `*.qc.json` 中 `passed` 且有 say_t 的句子(wav_sha1 去重),特徵快取 `tmp/ear_e2/dataset.pkl`(增量)。標籤 = pypinyin TONE3(詞級、tone_sandhi);多音字(pypinyin 異讀、pron_rules、教育部多讀音)不進訓練,例外是 `NEUTRAL` 虛詞(的了著得地們…)詞級讀輕聲時收「5」。wav_sha1 雜湊留出 10% 句子給評估。
- 判定 `senses/ear_e2.py`:期望調 ≠ 估計第一名且期望調機率 < `FLAG_P`(0.2)= 不符。整片模式期望讀音 = `tts_g2p.expected`(規則表收的多音字位置)。

指令(都用 tts_env_chattts 的 python):
```text
python -X utf8 pipeline/senses/ear_e2_tone.py --build-data --train [--jobs 12]   抽特徵(約 4 分鐘/800 句)+ 訓練
python -X utf8 pipeline/senses/ear_e2_eval.py [--truth <json>]                   留出集準確率/混淆矩陣/每調 F1;truth.json 有才算召回/誤報
python -X utf8 pipeline/senses/ear_e2.py --tag <tag> --ver <ver>                 整片 -> projects/<tag>/ear_e2_<ver>.json
python -X utf8 pipeline/senses/ear_e2.py --wav <f> --text <t> [--expect '{"5": "zhi2"}']   單句
python -X utf8 pipeline/tests/test_ear_e2.py
```
ground truth 格式(`channel/taste/ear/truth.json`,見 ear_e2_eval.py 檔頭):每項 tag+unit 或 wav+text、pos、expect、bad/label。

結果(2026-10-31,feat f2):

| 項目 | 數字 |
|---|---|
| 資料 | 833 句(目標 3,000 未達,本機快取只有這些);訓練 734 句 / 9,109 字 |
| 留出集 | 99 句 / 1,303 字,準確率 **64.1%**(只算 1–4 調約 66%;目標 85% 未達) |
| 每調 F1 | 1:0.615  2:0.555  3:0.605  4:0.730  輕聲:0.502 |
| ea_me5 v1(已上片、全數品管通過) | 55 句、多音字位置 231、不符 53(23%,多為誤報,目前只能當優先聽排序) |
| ground truth | truth.json 尚未建立,未評 |

下一步候選(未做):句數加到 3,000+(各片 attempts 的落選音檔不含標籤問題可收)、逐幀模型(CNN/GRU 吃整段 F0 而非 10 點)、對齊格點改 0.02 秒(MMS_FA 或 F0 斷點細修邊界)。

## 眼睛 eye.py 機械項(Phase 2,2026-10-31 設計;D 段成片後,0 token)
`python -X utf8 pipeline\senses\eye.py --tag <tag> --ver <ver> [--json]` → `projects\<tag>\eye_<ver>.json` `{ok, items:[{id, ok, note, at}]}`;任一 item 不 ok 就 `ok=false`、結束碼 1。只用 ffmpeg/ffprobe 與標準函式庫(配音環境 python 可跑,不需 GPU)。
| id | 量什麼 | 門檻 |
|---|---|---|
| black | `blackdetect=d=0.5:pic_th=0.98` 的黑場(片頭 1 秒、片尾 2 秒內不算) | 0 段 |
| freeze | `freezedetect=n=-60dB:d=10` 的靜止畫面 >10 秒(靜態圖本來就會連續,所以門檻放到 10 秒;同圖 ≤9 秒規則由渲染前檢查管) | 0 段 |
| lufs | `ebur128` 整片 integrated LUFS | 在 build.py/音訊常數的目標 ±1.5 LU(找不到常數就用 -14 ±1.5) |
| sync | 成片音軌 VAD(ffmpeg `silencedetect` 反推語音段)對 `timeline_tts.json` 每句 start 的偏移 | ≥95% 的句子 |偏移| ≤0.3 秒 |
| tail | 成片總長 vs timeline 最後一句 end + 片尾 | 差 ≤3 秒 |
| chapters | 說明檔「發片資料」章節時間戳 vs `timeline_tts.json` 對應句 start | 每章 |差| ≤2 秒(說明檔沒有章節就 note 略過,ok) |
封面 OCR 對標題、QA 格語意判讀不在此檔(Phase 4)。

實作差異(2026-10-31):
- lufs:pipeline 內找不到 loudnorm/LUFS 常數,目標改用實測。2026-10-31 量最近 6 支已交付成片的 integrated LUFS:ea_me5 v1 -18.9、wow_return v2 -19.0、ally_ai v1 -19.3、bioware_dei v4 -19.0、fog_still v1 -19.1、horror_sound v1 -19.2,中位數 -19.05,帶 ±1.5(常數在 eye.py 頂端)。
- sync:優先用 `build\<tag>oice.wav`(純人聲軌)做 `silencedetect=n=-35dB:d=0.25`,沒有才退回成片混音並在 note 標「混音,結果僅供參考」(混 BGM 時偵測不到停頓,ea_me5 成片只有 2 個靜音點、voice.wav 有 81 個)。
- tail 的期望值取 `timeline.total`(沒有才用最後一句 end);black 片頭 1 秒、片尾 2 秒是把黑場區間裁切後再看剩餘 ≥0.5 秒;chapters 以最近的句首比對。
