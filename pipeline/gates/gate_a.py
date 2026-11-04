r"""段 A gate(資料)。規格:pipeline\docs\director_ab.md §6。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import director as D  # noqa: E402
import paths as P  # noqa: E402
from gates import specs  # noqa: E402

IDS = ("brief", "context.md", "玩家共識", "論點欄位", "facts待查0", "素材manifest", "估片長")
BRIEF_KEYS = ("topic", "angle", "channel", "format")
CLAIM_KEYS = ("source", "abs", "visual")


def status(tag, ctx):
    """director status 用(原 director.check_a,行為不變)。"""
    pd = P.PROJECTS / tag
    out = [D._item("context.md", (pd / "context.md").exists(), "context.md 沒有", pd / "context.md")]
    facts = find_facts(tag)
    if not facts:
        out.append(D._item("facts", False, "facts.md 沒有"))
    else:
        n = D.count_pending_facts(facts)
        out.append(D._item("facts待查0", n == 0, f"{facts.name} 待查 {n} 條", facts))
    clips = D._first([p for p in (P.clips_file(tag), pd / "clips.json") if p.exists()])
    out.append(D._item("素材(clips)", clips, "clips_<tag>.json / clips.json 沒有", clips))
    return out


def find_facts(tag):
    pd = P.PROJECTS / tag
    facts = pd / "facts.md"
    return facts if facts.exists() else D._first([p for p in D._glob(pd, "facts*.md") if "raw" not in p.name])


def _short_item(iid, mins, sp, brief, unit="估片長"):
    """片長判斷(A/B 共用):< floor 不過(allow_short 放行),< target 下限過但 note。"""
    floor, target = sp["floor"], sp["target"]
    if floor is None:
        return D._item(iid, True, f"{unit} {mins:.1f} 分,此片型不設下限")
    if mins < floor:
        if brief.get("allow_short"):
            return D._item(iid, True, f"{unit} {mins:.1f} 分 < 下限 {floor},brief.allow_short 放行")
        return D._item(iid, False, f"{unit} {mins:.1f} 分 < 下限 {floor},要問使用者:補素材/併題/照發")
    note = f"{unit} {mins:.1f} 分,低於目標 {target[0]} 分" if mins < target[0] else f"{unit} {mins:.1f} 分"
    return D._item(iid, True, note)


def run(tag, ver=None, ctx=None):
    """brief 必填欄齊;context.md;共識 3–5 行;claims 每點 source/abs/visual 非空;facts 待查 0;manifest 全 ok;blocks 估片長 ≥ 下限。"""
    pd = P.PROJECTS / tag
    brief = D._read_json(pd / "brief.json")
    plan = D._read_json(pd / "plan.json")
    miss = [k for k in BRIEF_KEYS if not (brief or {}).get(k)]
    out = [D._item("brief", brief is not None and not miss, f"brief.json {'缺 ' + '、'.join(miss) if brief else '沒有'}",
                   pd / "brief.json")]
    brief = brief or {}
    out.append(D._item("context.md", (pd / "context.md").exists(), "context.md 沒有", pd / "context.md"))
    if plan is None:
        out += [D._item("玩家共識", False, "plan.json 沒有"), D._item("論點欄位", False, "plan.json 沒有")]
    else:
        n = len(plan.get("consensus") or [])
        out.append(D._item("玩家共識", 3 <= n <= 5, f"共識 {n} 行(要 3–5)", pd / "plan.json"))
        claims = plan.get("claims") or []
        bad = [str(c.get("id", "?")) for c in claims if not all(c.get(k) for k in CLAIM_KEYS)]
        out.append(D._item("論點欄位", claims and not bad,
                           f"claims {len(claims)} 點,欄位缺:{'、'.join(bad) or '無'}", pd / "plan.json"))
    facts = find_facts(tag)
    if not facts:
        out.append(D._item("facts待查0", False, "facts.md 沒有"))
    else:
        n = D.count_pending_facts(facts)
        out.append(D._item("facts待查0", n == 0, f"{facts.name} 待查 {n} 條", facts))
    mf = D._read_json(pd / "assets_manifest.json")
    if not mf:
        out.append(D._item("素材manifest", False, "assets_manifest.json 沒有或空"))
    else:
        bad = [str(m.get("claim") or m.get("path")) for m in mf if not m.get("ok")]
        out.append(D._item("素材manifest", not bad, f"{len(mf)} 項,未過:{'、'.join(bad) or '無'}", pd / "assets_manifest.json"))
    if plan is None:
        out.append(D._item("估片長", False, "plan.json 沒有"))
    else:
        mins = sum(float(b.get("est_sec") or 0) for b in plan.get("blocks") or []) / 60
        sp = specs.spec((ctx or {}).get("channel") or brief.get("channel"), brief.get("format"))
        out.append(_short_item("估片長", mins, sp, brief))
    return out
