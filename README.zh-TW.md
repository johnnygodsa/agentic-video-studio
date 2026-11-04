# agentic-video-studio

[![CI](https://github.com/johnnygodsa/agentic-video-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/johnnygodsa/agentic-video-studio/actions/workflows/ci.yml)

以代理協作驅動的長片製作管線:查證過的評論影片(繁體中文配音,遊戲/科普題材)。
每支片由一支 director 程序依段推進,每段有硬性 gate;Claude Code 子代理負責查證、寫稿與審稿;本機 Python 工具鏈負責配音、讀音品管、動畫、字幕與渲染。

本庫是從實際運作的私人工作室抽出的**框架**:pipeline 程式、各段 gate、代理提示詞與製作規則。
**不含**模型、音色、素材、各片資料、頻道數據與任何憑證(見〈不含的內容〉)。

## 快速體驗:離線示範(不需 GPU、模型或 Claude)

把 `pipeline/demo/sample_script.txt` 走過正式產線模組,產出約 28 秒的示範片:
文案解析(`script_txt2json`)、文案 lint(`script_lint`)、讀音標注(`tts_cosy_text.apply_pron`)、
字幕切段(無標點、不拆詞;`build.split_phrases`、`text_wrap`)、gate 檢查(`director._item`,同 `pipeline/gates/`)、
Pillow 畫的標題卡/長條圖/文字卡、ffmpeg 合成與 QA 總覽圖(`qa_sheet.grab`)。

```bash
# Python 3.10 以上、ffmpeg 在 PATH;Linux 需 apt install fonts-noto-cjk(Windows 用微軟正黑體)
pip install -r requirements-ci.txt
python -X utf8 pipeline/demo/run_demo.py --tts none --out demo_out
# 選用 CPU 配音:pip install piper-tts 後改 --tts piper(聲音下載到 demo_out/cache;失敗自動退回靜音軌)
```

產出在 `demo_out/`:`demo.mp4`(字幕燒進畫面)、`demo.srt`、`contact_sheet.png`,另有 `pron.txt`(讀音標注結果)與 `script.json`。
每一步印一行 `[stage] ...`;gate 任一項不過就停在渲染前。
CI 每次 push 都會跑同一支示範(成品在該次 run 的 `demo` artifact)與 `.github/ci_tests.txt` 列的離線測試。

![示範畫面](docs/img/demo_frame.png)
![示範總覽圖](docs/img/demo_contact_sheet.png)

## 功能

- **選題 → brief → 查證 → 文案 → 配音 → 渲染 → 交付**,一支片一個 director 程序,可從任一段續跑。
- **段間硬 gate**(`pipeline/gates/gate_*.py`):前一段 gate 不過不進下一段,卡點寫在 `production.json` 的 `blocks`。
- **三道事實閘門**(配音前):玩家共識 → 逐條事實核對表 → 扮演資深玩家的對抗式審稿。
- **配音品管是唯一的聲音閘門**:操作者與 LLM 都聽不到,所以每句都要過語音辨識回讀、多音字規則、教育部讀音、停頓與連讀偵測、時長預檢,全過才凍結。
- **遠端 GPU 調度**:配音與辨識可跑 Colab、Kaggle 或本機 GPU;本機走全機 GPU 鎖,依到期日排序。
- **模板化動態圖表**(HTML/GSAP,經 Playwright 渲染):圖表、時間軸、閱讀卡、品牌片頭。

## 架構

段序 A → B → B4 → C → D → E:

| 段 | 內容 | 主要代理/工具 |
|---|---|---|
| A | 玩家共識、論點清單、查證、素材 | ab-planner、researcher、asset-collector |
| B | 寫稿、lint、編輯審、事實專審、玩家審 | script-writer、editor-review、fact-check、player-review |
| B4 | 配音稿、斷句與讀音 | pron-review、pron-apply |
| C | 配音與品管(後端:Colab / Kaggle / 本機) | tts_dispatch、cosy3_worker、asr_worker、tts_* 品管 |
| D | 動畫、字幕、BGM、渲染、QA 圖 | build、make_version、anim_* |
| E | 標題、封面、說明、排程與否決窗 | deliver、yt_queue(外部後端,選用) |

完整圖與說明見 [README.md](README.md) 與 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 目錄

- `CLAUDE.md`:Claude Code 每回合載入的專案規則(指到各規則檔)
- `channel/規則/`:流程、選題、文案、製作、交付規則;`頻道_模板.md` 是新頻道模板
- `.claude/agents/`:子代理提示詞
- `pipeline/`:全部程式(入口 `pipeline/README.md`)、`gates/`、`tests/`、`docs/`
- `projects/_templates/`、`projects/framework/`:brief、handoff、逐句畫面表模板與格式規格

規則與程式裡的頻道名已換成 `ChannelA` / `ChannelB` / `ChannelC`;本機路徑換成 `<REPO_ROOT>`、`<EXTERNAL_BACKEND>`、`<HOME>`、`<LOCAL_PATH>`。

## 需求

Windows 10/11、Python 3.10+、FFmpeg、Playwright Chromium、NVIDIA GPU(≥8 GB)或 Colab/Kaggle 帳號、Claude Code。
`python -m pip install -r requirements.txt`;配音引擎各自裝在獨立 venv(見 `pipeline/colab/req_*.txt`)。

## 接上自己的配音模型與音色

不附任何模型權重、音色或參考音檔:

1. 從官方取得 CosyVoice 3:<https://github.com/FunAudioLLM/CosyVoice>(權重依其授權)。
2. 為它建 venv,在 `pipeline/paths.py`(或環境變數)指到模型目錄。
3. 錄製或取得你有權使用的參考音色,設為 `pipeline/cosy3_worker.py` 的說話人提示。
4. 辨識回讀用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper);`pipeline/tts_bakeoff/` 的其他引擎為選用。
5. 讀音資料(`pipeline/moe/`)衍生自教育部《重編國語辭典修訂本》(CC BY-ND 3.0 TW),**不隨庫散布**,依 `pipeline/moe/README.md` 的指令自行重建。

字型也不附,請自備中文字型放 `fonts/`。

## 不含的內容

模型與 venv、音色與參考音、原始素材與截圖、動畫成品、BGM、建置與成片、各片資料夾與各片專用腳本、觀眾留言、成效數據、A/B 測試結論與頻道策略檔、外部發片/數據後端(`yt_queue.py`、`stats.py`、`feedback*.py` 透過檔案與 CLI 呼叫它,沒有時會回報後端不存在)、任何秘密、token、cookie、OAuth 檔。

## GPU 鎖

`pipeline/gpu_lock.py` 先找 `<EXTERNAL_BACKEND>/_shared/` 的跨專案共用鎖(環境變數 `YT_SHARED_DIR`);找不到就退回 `pipeline/gpu_lock_local.py` 的單機互斥鎖(`tmp/.gpu_lock/`、pid 存活判斷、可選顯存門檻),不需額外設定。

## 限制與免責

- 這是單一工作室的實用工具,公開供參考;繁體中文、台灣用語、台幣價格等慣例寫死在規則與程式裡。
- 依賴未附後端、模型或資料的測試可能略過或失敗。
- **遊戲畫面、截圖、預告片與其他第三方素材的著作權由使用者自負。** 本管線只自動化擷取與剪輯,請自行確認適用的授權與合理使用規範。
- 自動產生的旁白可能有誤;事實閘門只能降低、不能消除錯誤,發布內容由使用者負責。
- 不附 GSAP:請自 https://gsap.com 下載 `gsap.min.js`(v3)或 `npm i gsap`,放到 `pipeline/static/vendor/gsap.min.js`。

## 授權

[MIT](LICENSE) © 2026 johnnygodsa
