"""新片截圖檔:複製本檔改名 assets_<簡稱>_news.py,只填 SPECS 與 HL,不改 news_lib / news_specs。
跑法(repo 根;輸出 images/<prefix><name>.png + .boxes.json + .layout.json):
  python -X utf8 pipeline/assets_<簡稱>_news.py                  全部截圖
  python -X utf8 pipeline/assets_<簡稱>_news.py name1 name2      只截指定的
  python -X utf8 pipeline/assets_<簡稱>_news.py --dump name      列出頁面各文字區塊原文(寫 rules 的英文前綴用)
  python -X utf8 pipeline/assets_<簡稱>_news.py --check          檢查 HL 底線詞、版面、墨跡離邊(交付前必跑,錯誤須為 0)
  python -X utf8 pipeline/assets_<簡稱>_news.py --relabel a,b    只換標籤重截(被擋的圖)
  python -X utf8 pipeline/assets_<簡稱>_news.py --out tmp/x      試截輸出到別的資料夾,避免覆寫定稿圖
說明:docs/assets.md「新片截圖」節。網頁一律暗色、英文換成繁體中文(rules 的第二欄);
原頁沒有的句子不可自己加字。其他網站的工廠(kotaku_head / gs_para / disc ...)見 news_specs.py 的 def 清單
(python -X utf8 pipeline/tools/funcmap.py --grep kotaku)。"""
from news_lib import main
from news_specs import art   # 其他工廠按需 import:para, kotaku_head, kotaku_para, gs_para, gd_para ...

# SPECS:{圖名: spec dict}。圖名 = 輸出檔名去掉前綴;script.txt 的 img 欄位寫 <prefix><圖名>。
# art(url, ptag, targets, rules, site, w, fs, vw, title_sel, title_fs, extra) 欄位:
#   url       原始報導網址
#   ptag      內文段落的 CSS 選擇器(只留這些段落的樣式放大)
#   targets   要保留的區塊:選擇器字串,或 (選擇器, 必含文字) 的 tuple
#   rules     [(原文前綴, 繁中譯文), ...],依頁面出現順序;原文前綴比對該文字區塊開頭,
#             用 --dump 取得;譯文可含 <br> 控制換行;句子很長可用「……」截掉不相干處
#   site      標籤文字,例 "Kotaku 2026/10/09"(畫面上的「中文翻譯 · 原文:網站名」)
#   w / fs / vw   內文欄寬 px / 字級 px / 瀏覽器視窗寬;字要夠大、欄不能太寬(太寬會被縮小)
#   title_sel / title_fs   標題選擇器與字級(沒有標題就省略)
#   extra     額外 CSS 字串(隱藏雜物、改寬度)
# 另可在 dict 上補欄位:spec["js"] 頁內 JS、spec["top_px"] 上緣留白、spec["css"] += "..."。
SPECS = {
    "example_art": art(
        "https://example.com/news/some-article",
        "article p",
        ["article h1", ("article p", "first words of the key paragraph")],
        [("Headline in English", "標題的繁體中文翻譯"),
         ("First words of the key paragraph", "重點段落的繁體中文翻譯,旁白講到的那句要在這裡")],
        "範例網站 2026/10/16", w=1000, fs=40, vw=1100, title_sel="article h1", title_fs=58),
}

# HL:{圖名: [旁白講到、畫面上要畫紅底線的詞]};詞必須是上面「譯文」裡的原字,--check 會驗證找得到。
# 沒有要畫線的圖可省略或給 []。
HL = {"example_art": ["旁白講到的那句"]}

if __name__ == "__main__":
    # main(SPECS, "<tag>", HL, prefix="<前綴>_"):tag = 片名(projects/<tag>、output/<tag>);
    # prefix 預設 "<tag>_",要短前綴(例 sf_)就明寫。
    main(SPECS, "example_tag", HL, prefix="ex_")
