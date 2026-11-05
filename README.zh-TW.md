# agentic-video-studio

[![CI](https://github.com/johnnygodsa/agentic-video-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/johnnygodsa/agentic-video-studio/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

給它一個題目和切入角度,一組 LLM 代理會去查資料、寫稿、審稿;接著由 Python 工具錄旁白、逐句檢查,最後渲染出有字幕和動態圖表的影片。

English: [README.md](README.md)

![動態圖表模板](docs/img/motion_graphics_zh.gif)

我做這套流程,是為了經營一個實際在更新的旁白影片頻道。最難的地方是不讓錯誤留到成片裡:數字寫錯、字唸錯、字幕把詞切成兩半。所以每一段都把產出寫成檔案,再由該段的關卡程式檢查,通過了下一段才能開始。關卡沒過,流程就停在那一段,原因寫進 `production.json`;問題修好後,用 `--from` 從那一段接著跑。

## 一分鐘試跑

示範不需要 GPU、模型或 API 金鑰。它會把一份短文案送進正式流程用的同一套解析、文案檢查、字幕切段和關卡檢查,產出一支 40 秒內的 MP4。

用 Docker:

```bash
git clone https://github.com/johnnygodsa/agentic-video-studio && cd agentic-video-studio
docker build -t avs .
docker run --rm -v "$PWD/out:/out" avs --theme neon --script pipeline/demo/sample_script.txt   # 產出 out/demo.mp4
```

用安裝腳本(需要 Python 3.10 以上和 ffmpeg):

```bash
./scripts/install.sh       # Linux、macOS、WSL;加 --full 安裝完整流程
.\scripts\install.ps1      # Windows PowerShell;加 -Full 安裝完整流程
```

手動安裝:

```bash
pip install -r requirements-ci.txt
python -X utf8 pipeline/demo/run_demo.py --tts none --script pipeline/demo/sample_script.txt --out demo_out
```

其他參數:`--theme paper|neon|bold|自訂.json` 換風格;不加 `--script` 會跑英文範例;`--tts piper` 用免費的 CPU 配音。輸出有 `demo.mp4`、`demo.srt`,還有一張 `contact_sheet.png`,用 8 格畫面快速看整支片。CI 每次推送都會渲染一次,最新一次執行的產出檔裡隨時有一份。

### 同一份文案,四種風格

下面四排來自同一份文案、同一條時間軸,只換了 `--theme`。主題就是 `pipeline/demo/themes.py` 裡的資料。想做自己的風格,寫一個 JSON 檔,用 `"base": "paper"` 這類內建主題當底,再覆寫想改的顏色。完整流程裡的動態圖表,樣式來自 `pipeline/templates/anim/tokens.css`。

![四種主題](docs/img/themes_zh.png)

## 做一支正式影片

```bash
python pipeline/director.py brief my_video --topic "..." --angle "..." --channel ChannelA --format commentary
python pipeline/director.py run my_video --from A --to E
```

`brief` 記下題目,`run` 依序跑完每一段。每個關卡實際檢查哪些項目,用 `python pipeline/director.py --explain <段>` 可以看到。

| 段 | 做什麼 | 關卡通過條件 |
|---|---|---|
| A | 代理蒐集來源、受眾的普遍看法、截圖或片段 | 每個論點都有來源和預定畫面,沒有待查的事實,素材都在,估計片長達到該片型下限 |
| B | 代理寫稿,再由文案檢查、編輯代理、領域專家代理審稿 | 文案檢查、事實核對、畫面檢查都沒有錯誤,每句的畫面都對得到實際檔案,兩位審稿代理都沒有未處理的意見 |
| B4 | 準備配音稿,決定讀音 | 字幕接縫沒問題,讀音審查沒有未決項目 |
| C | 逐句配音,再用語音辨識轉回文字比對 | 沒有唸錯、沒有未過的句子、時長預檢通過,音檔與凍結的文字一致 |
| D | 圖表、字幕、配樂和最後渲染 | 成片長度達下限、渲染前檢查無錯、QA 總覽圖已產生 |
| E | 標題、封面、說明欄和上片排程 | 發片資料填齊、已排程、資料檢查通過。公開前你仍然可以否決 |

查資料、寫稿、審稿這幾段預設用 Claude Code。設 `STUDIO_LLM=codex` 會改用 OpenAI Codex CLI 跑同一套角色提示詞(見 [AGENTS.md](AGENTS.md))。Codex 這條路有單元測試,但還沒實際做完過一整支片。

配音和語音辨識可以跑在自己的 NVIDIA GPU、Colab 或 Kaggle 上。用本機 GPU 時,會用一個鎖檔避免兩個工作同時搶 GPU。

## 適合做什麼

只要是旁白講解、畫面用圖表、截圖、片段或文字來配的影片都適合:科學或歷史的知識解說、新聞整理、產品或遊戲評測、課程單元、內部教育訓練、數據故事,或是希望每一集畫面和聲音都一致的長期系列。做出來的片子多半是 5 到 20 分鐘,短影音也走同一條時間軸。

## 正式使用前的準備

有些東西要自己準備:

- 配音模型,以及你有使用權的聲音。預設引擎是 CosyVoice 3:在 `pipeline/paths.py` 指定模型位置,再到 `pipeline/cosy3_worker.py` 登記參考音。只有 CPU 的話可以用 Piper。
- 讀回比對用的 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)。
- `fonts/` 裡的字型,以及 `pipeline/static/vendor/` 裡的 `gsap.min.js`;用 `--full` 安裝會自動下載 GSAP。
- 讀音資料:照 `pipeline/moe/README.md` 從教育部辭典重建,或接上自己的詞庫。

內建兩項地區慣例,預設都關閉:使用在地用語(內附設定是台灣用語),以及在美金旁另標本地幣。要開啟就改 `studio.json`,可用的鍵列在 `pipeline/locale_cfg.py`。

讀音和字幕工具是針對中文調的,規則檔和代理提示詞目前是繁體中文,英文版正在補。流程調度、關卡、渲染和品管不挑文案語言,示範片本身就是英文。

發片與數據相關的程式(`yt_queue.py`、`stats.py`、`feedback*.py`)需要一個外部後端,不在這個庫裡。沒有後端時它們會提示缺少後端,其餘流程照常可以跑。

完整流程需要 Python 3.10 以上、FFmpeg、畫圖表用的 Playwright Chromium,以及 8 GB 以上的 NVIDIA GPU(或 Colab、Kaggle 帳號)來跑配音和語音辨識。開發環境是 Windows 10/11,CI 跑在 Ubuntu。

## 檔案在哪裡

| 路徑 | 內容 |
|---|---|
| `CLAUDE.md`、`AGENTS.md` | 主代理每回合都會讀的規則(Claude Code 與 Codex 各一份) |
| `channel/規則/` | 製作規則:流程、選題、文案與查證、製作與配音品管、交付 |
| `.claude/agents/` | 每個代理角色一份提示詞 |
| `pipeline/director.py`、`director_ab.py` | 導演程式:`brief`、`run`、`--explain`,狀態存在 `production.json` |
| `pipeline/gates/` | 每段一個關卡 |
| `pipeline/tts_*.py`、`cosy3_worker.py`、`asr_worker.py` | 配音、讀回比對、讀音檢查 |
| `pipeline/build.py`、`anim_*.py`、`templates/` | 時間軸、渲染、圖表模板 |
| `pipeline/script_lint.py`、`facts_*.py` | 文案檢查與事實核對 |
| `pipeline/llm.py` | 所有代理呼叫的唯一出口,在 Claude Code 與 Codex 之間切換 |
| `pipeline/demo/` | 離線示範與主題 |
| `pipeline/tests/` | 測試;`.github/ci_tests.txt` 列出 CI 離線跑的 73 個 |

## 參與貢獻

歡迎回報問題或送 PR。適合入手的地方有圖表模板、主題、其他語言的規則檔,以及其他配音引擎或 LLM CLI 的轉接。怎麼跑檢查寫在 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 發布前

流程擷取的影片、截圖、預告片等素材,版權由你自己負責。事實關卡能降低寫錯的機率,但沒辦法保證完全不錯,影片發出去之前請自己讀一遍文案。

## 授權

[MIT](LICENSE) © 2026 johnnygodsa
