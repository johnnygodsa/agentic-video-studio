# 讀音待辦 pron_backlog(程式自動 upsert;規則見 pipeline/pron_backlog.py 檔頭、docs/tts.md §4.5)

每支片主對話只處理「待規則」命中最多的前 3 條(`tts_script.py --backlog-top 3`);登 `_verified` 要有證據。


| 字 | 語境詞 | 證據 | 命中次數 | 狀態 | 來源片 | 日期 |
|---|---|---|---|---|---|---|
| 可 | 尼可萊 | polyphone strong | 3 | 待規則 | rc_3days×3 | 2026-11-03 |
| 伺 | 的伺服 | polyphone strong | 2 | 待規則 | bioware_dei×1, wow_realm×1 | 2026-11-01 |
| 取 | 讀取畫 | polyphone strong | 2 | 待規則 | door_load×1, fog_still×1 | 2026-11-01 |
| 取 | 讀取的 | polyphone strong | 2 | 待規則 | door_load×1, fog_still×1 | 2026-11-01 |
| 打 | 快打二 | polyphone strong | 2 | 待規則 | sf_dying×2 | 2026-10-29 |
| 语 | 之語 | polyphone strong | 2 | 待規則 | diablo_legacy×2 | 2026-11-04 |
| 路 | 網路上 | polyphone strong | 2 | 待規則 | wow_eternal_pre×2 | 2026-10-29 |
| 迹 | 追跡者 | polyphone strong | 2 | 待規則 | safe_room×2 | 2026-10-29 |
| 一 | 同一串 | polyphone strong | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 上 | 三上真 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 中 | 抽中爆 | pron_rules 未驗證 | 1 | 待規則 | headshot_hp×1 | 2026-11-01 |
| 主 | 有主角 | polyphone strong | 1 | 待規則 | rc_3days×1 | 2026-11-03 |
| 之 | 影之 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 乌 | 沙烏地 | polyphone strong | 1 | 待規則 | bioware_dei×1 | 2026-10-30 |
| 了 | 為了跟 | polyphone strong | 1 | 待規則 | ally_ai×1 | 2026-10-30 |
| 了 | 回得了本 | pron_rules 未驗證 | 1 | 待規則 | gow_budget×1 | 2026-11-01 |
| 传 | 前傳大 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 伺 | 美伺服 | polyphone strong | 1 | 待規則 | dei_ellie×1 | 2026-10-29 |
| 伺 | 連伺服 | polyphone strong | 1 | 待規則 | wow_stress×1 | 2026-10-29 |
| 伺 | 洲伺服 | polyphone strong | 1 | 待規則 | wow_stress×1 | 2026-10-29 |
| 伺 | 版伺服 | polyphone strong | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 伺 | 型伺服 | polyphone strong | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 佣 | 本傭兵 | polyphone strong | 1 | 待規則 | rc_3days×1 | 2026-11-04 |
| 倒 | 倒是 | polyphone strong | 1 | 待規則 | bioware_dei×1 | 2026-10-29 |
| 倒 | 手倒是 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 倒 | 型倒是 | polyphone strong | 1 | 待規則 | wow_return×1 | 2026-10-31 |
| 几 | 幾把 | polyphone strong | 1 | 待規則 | headshot_hp×1 | 2026-11-01 |
| 分 | 的分 | polyphone strong | 1 | 待規則 | pbz_ign×1 | 2026-11-04 |
| 分 | 的分不 | polyphone strong | 1 | 待規則 | pbz_ign×1 | 2026-11-04 |
| 削 | 有削也 | polyphone strong | 1 | 待規則 | wow_eternal_pre×1 | 2026-10-29 |
| 勾 | 不勾也 | polyphone strong | 1 | 待規則 | bioware_dei×1 | 2026-10-29 |
| 压 | 壓測 | polyphone strong | 1 | 待規則 | wow_stress×1 | 2026-10-29 |
| 取 | 讀取已 | polyphone strong | 1 | 待規則 | fog_still×1 | 2026-10-30 |
| 取 | 讀取消 | polyphone strong | 1 | 待規則 | fog_still×1 | 2026-10-30 |
| 取 | 讀取那 | polyphone strong | 1 | 待規則 | fog_still×1 | 2026-10-30 |
| 取 | 讀取不 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 取 | 讀取變 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 取 | 讀取早 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 取 | 讀取藏 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 取 | 讀取時 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 取 | 讀取沒 | polyphone strong | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 只 | 一隻坐 | polyphone strong | 1 | 待規則 | wow_eternal_pre×1 | 2026-10-29 |
| 哪 | 到哪一 | polyphone strong | 1 | 待規則 | ps5_own×1 | 2026-11-03 |
| 哪 | 在哪 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 坊 | 遊坊在 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 太 | 作太依 | polyphone strong | 1 | 待規則 | hide_locker×1 | 2026-11-04 |
| 好 | 偏好 | pron_rules 未驗證 | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 岭 | 天嶺上 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 岭 | 天嶺慘 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 差 | 差了 | pron_rules 未驗證 | 1 | 待規則 | ps5_own×1 | 2026-11-03 |
| 得 | 就得改 | pron_rules 未驗證 | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 打 | 快打四 | polyphone strong | 1 | 待規則 | sf_dying×1 | 2026-10-29 |
| 打 | 快打六 | polyphone strong | 1 | 待規則 | sf_dying×1 | 2026-10-29 |
| 打 | 想打到 | polyphone strong | 1 | 待規則 | wow_return×1 | 2026-10-31 |
| 挑 | 直挑達 | polyphone strong | 1 | 待規則 | bioware_dei×1 | 2026-10-30 |
| 挑 | 用挑伺 | polyphone strong | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 支 | 那支影 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 放 | 要放水 | polyphone strong | 1 | 待規則 | hidden_diff×1 | 2026-10-29 |
| 教 | 偷教了 | pron_rules 未驗證 | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 数 | 倒數想 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 数 | 倒數 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 暴 | 暴露 | pron_rules 未驗證 | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 暴 | 暴雪 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 有 | 沒有接 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 服 | 開服前 | polyphone strong | 1 | 待規則 | wow_return×1 | 2026-10-31 |
| 服 | 開服以 | polyphone strong | 1 | 待規則 | wow_return×1 | 2026-10-31 |
| 服 | 開服是 | polyphone strong | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 柏 | 的柏 | polyphone strong | 1 | 待規則 | bioware_dei×1 | 2026-10-29 |
| 柏 | 還有 | polyphone strong | 1 | 待規則 | pbz_week1×1 | 2026-11-01 |
| 柏 | 多和 | polyphone strong | 1 | 待規則 | pbz_week1×1 | 2026-11-01 |
| 样 | 兩樣東 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 格 | 馬格南 | polyphone strong | 1 | 待規則 | headshot_hp×1 | 2026-11-01 |
| 梯 | 天梯跟 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 演 | 城演 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 為 | 人為事變日付 | pron_rules 未驗證 | 1 | 待規則 | gow_budget×1 | 2026-11-01 |
| 為 | 能為單一陣營 | pron_rules 未驗證 | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 片 | 這片光 | polyphone strong | 1 | 待規則 | sf_dying×1 | 2026-10-29 |
| 片 | 這片霧 | polyphone strong | 1 | 待規則 | fog_still×1 | 2026-10-30 |
| 片 | 那片 | polyphone strong | 1 | 待規則 | fog_still×1 | 2026-10-30 |
| 當 | 當對照 | pron_rules 未驗證 | 1 | 待規則 | gow_budget×1 | 2026-11-01 |
| 看 | 在看門 | pron_rules 未驗證 | 1 | 待規則 | door_load×1 | 2026-11-01 |
| 科 | 百科的 | polyphone strong | 1 | 待規則 | rc_3days×1 | 2026-11-03 |
| 空 | 普空自 | polyphone strong | 1 | 待規則 | sf_dying×1 | 2026-10-29 |
| 空 | 有空 | pron_rules 未驗證 | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 结 | 連結 | polyphone strong | 1 | 待規則 | ally_ai×1 | 2026-10-30 |
| 结 | 正結局 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 脚 | 的第一 | polyphone strong | 1 | 待規則 | wow_realm×1 | 2026-11-01 |
| 莫 | 阿莫的 | polyphone strong | 1 | 待規則 | wow_stress×1 | 2026-10-29 |
| 著 | 條著色 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 著 | 譯著色 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 著 | 著色 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 著 | 槽著色 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 著 | 的著色 | polyphone strong | 1 | 待規則 | pbz_day1×1 | 2026-10-29 |
| 血 | 有血量 | polyphone strong | 1 | 待規則 | ally_ai×1 | 2026-10-30 |
| 血 | 來血就 | pron_rules 未驗證 | 1 | 待規則 | headshot_hp×1 | 2026-11-01 |
| 衝 | 衝著 | pron_rules 未驗證 | 1 | 待規則 | pbz_week1×1 | 2026-11-01 |
| 角 | 女主 | polyphone strong | 1 | 待規則 | pbz_ign×1 | 2026-11-04 |
| 调 | 有調 | polyphone strong | 1 | 待規則 | pbz_review×1 | 2026-10-29 |
| 路 | 網路有 | polyphone strong | 1 | 待規則 | wow_stress×1 | 2026-10-29 |
| 路 | 網路吵 | polyphone strong | 1 | 待規則 | pbz_ign×1 | 2026-11-04 |
| 那 | 年那版 | polyphone strong | 1 | 待規則 | wow_return×1 | 2026-10-31 |
| 那 | 在那棟 | polyphone strong | 1 | 待規則 | rc_3days×1 | 2026-11-03 |
| 那 | 年那支 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 重 | 輪重打 | polyphone strong | 1 | 待規則 | pbz_review×1 | 2026-10-29 |
| 重 | 尊重玩 | polyphone strong | 1 | 待規則 | diablo_legacy×1 | 2026-11-04 |
| 長 | 子長怎 | pron_rules 未驗證 | 1 | 待規則 | ps5_own×1 | 2026-11-03 |
| 障 | 元紗 | polyphone strong | 1 | 待規則 | bioware_dei×1 | 2026-10-30 |
| 雨 | 雨血 | polyphone strong | 1 | 待規則 | pbz_lore×1 | 2026-11-03 |
| 喪 | 喪屍 | pron_rules 詞規則 sāng(審訂音 喪事 sāng),未聽審,列優先聽、pron_rules 未驗證 | 19 | 已規則 | headshot_hp×19 | 2026-11-01 |
| 哩 | 咕哩 | polyphone strong | 7 | 已規則 | dei_ellie×7 | 2026-10-29 |
| 打 | 快打五 | polyphone strong | 5 | 已規則 | sf_dying×5 | 2026-10-29 |
| 取 | 讀取 | polyphone strong | 3 | 已規則 | door_load×1, fog_still×1, safe_room×1 | 2026-11-01 |
| 妮 | 奧妮克 | polyphone strong | 2 | 已規則 | wow_eternal_pre×2 | 2026-10-29 |
| 晃 | 搖搖晃晃 | pron_rules 已有規則(審訂音 率 lǜ、晃 huàng),未聽審列優先聽 | 2 | 已規則 | headshot_hp×2 | 2026-11-01 |
| 率 | 暴擊率 | pron_rules 已有規則(審訂音 率 lǜ、晃 huàng),未聽審列優先聽、pron_rules 未驗證 | 2 | 已規則 | headshot_hp×2 | 2026-11-01 |
| 良 | 林良章 | polyphone strong | 2 | 已規則 | headshot_hp×1, hidden_diff×1 | 2026-11-01 |
| 率 | 機率 | pron_rules 已有規則(審訂音 率 lǜ、晃 huàng),未聽審列優先聽、pron_rules 未驗證 | 1 | 已規則 | headshot_hp×1 | 2026-11-01 |
