# 教育部讀音資料(tts_moe.py 用)

- 來源:g0v moedict-data `dict-revised.json.xz`(《重編國語辭典修訂本》,教育部;萌典整理)
  https://raw.githubusercontent.com/g0v/moedict-data/main/dict-revised.json.xz (14.7 MB,repo commit a6dc997,2026-07-11)
- 授權:CC BY-ND 3.0 TW(教育部《重編國語辭典修訂本》);本目錄為格式轉換後的精簡檔,未改動讀音內容。
- 下載日期:2026-10-29。《國語一字多音審訂表》未找到結構化開放資料,未納入(多音字清單取自辭典的多讀音單字條目)。
- 檔案(總量約 5.6 MB,進 git):
  - `moe_pron.json`:字 -> [{bopomofo, pinyin, words(例詞 ≤10), note?(「(一)之讀音」等)}]
  - `moe_word_pron.json`:含多音字的 2–4 字詞條 -> 注音
  - `words_moe.txt`:2–4 字純中文詞條,一行一詞
- 重建(下載檔放獨立目錄,用 python -I 解析):
  ```text
  curl -L -o tmp/moe_dl/dict-revised.json.xz https://raw.githubusercontent.com/g0v/moedict-data/main/dict-revised.json.xz
  python -I -X utf8 pipeline/tts_moe.py --build tmp/moe_dl/dict-revised.json.xz
  ```
