"""locale_cfg:studio.json 不存在 = 預設全開;locale 關掉後 T08 與 line_fix 用語規則跟著關。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import locale_cfg  # noqa: E402


def _use(tmp_path, monkeypatch, locale):
    f = tmp_path / "studio.json"
    f.write_text(json.dumps({"locale": locale}), encoding="utf-8")
    monkeypatch.setattr(locale_cfg, "CFG", f)
    locale_cfg._load.cache_clear()


def test_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(locale_cfg, "CFG", tmp_path / "missing.json")
    locale_cfg._load.cache_clear()
    assert locale_cfg.enabled("price_local_currency") and locale_cfg.enabled("regional_terms")
    locale_cfg._load.cache_clear()


def test_switch_off(tmp_path, monkeypatch):
    import line_fix
    import script_lint as L
    _use(tmp_path, monkeypatch, {"price_local_currency": False, "regional_terms": False, "unknown_key": 1})
    try:
        assert not locale_cfg.enabled("price_local_currency") and locale_cfg.get("unknown_key") is None
        monkeypatch.setattr(L, "visual_lines", lambda tag, lines: [])
        assert not any("PRICE_TWD" in w[0] for w in L.taste_warnings([(1, "標準版 59.99 美金。")], "x"))
        assert "台灣用語" not in line_fix.build_prompt([], "lint", [])
    finally:
        locale_cfg._load.cache_clear()
