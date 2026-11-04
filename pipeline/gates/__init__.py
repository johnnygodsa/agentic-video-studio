r"""段 A/B/B4/C/D/E 的 gate(規格:pipeline\docs\director.md「run:C→E 串接」、director_ab.md §6)。
每支 gate_x.py 有兩個入口:status(tag, ctx) = director status 的推斷(寬鬆,看最新版產物);
run(tag, ver, ctx) = director run 的硬擋 gate,回傳 [item{id, ok, note, path}]。"""
SEGS = ("A", "B", "B4", "C", "D", "E")


def get(seg):
    """段代號 -> gate 模組(延遲匯入,避免與 director 互相匯入)。"""
    from gates import gate_a, gate_b, gate_b4, gate_c, gate_d, gate_e
    return {"A": gate_a, "B": gate_b, "B4": gate_b4, "C": gate_c, "D": gate_d, "E": gate_e}[seg]
