"""程式地圖產生器:用 ast 掃 pipeline/*.py 與 pipeline/sci/*.py 的頂層 def/class(含類別方法)。
  python -X utf8 pipeline/tools/funcmap.py            重產 pipeline/docs/funcmap.md
  python -X utf8 pipeline/tools/funcmap.py --grep 關鍵字   只印函式名或 docstring 含關鍵字的項(路徑:行號 + docstring)
行號只存在 funcmap.md 與 --grep 輸出,不寫進 README / docs 章節。"""
import ast
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
OUT = PIPE / "docs" / "funcmap.md"


def files():
    return sorted(PIPE.glob("*.py")) + sorted((PIPE / "sci").glob("*.py"))


def scan(path):
    """回傳 [(kind, name, args, lineno, doc第一行)]"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    rows = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = (ast.get_docstring(n) or "").strip().splitlines()
            doc = doc[0].strip() if doc else ""
            if isinstance(n, ast.ClassDef):
                args = ""
                kind = "class"
            else:
                args = ast.unparse(n.args)
                kind = "def"
            rows.append((kind, n.name, args, n.lineno, doc))
            if isinstance(n, ast.ClassDef):  # 類別的方法也列(Class.method)
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        d = (ast.get_docstring(m) or "").strip().splitlines()
                        rows.append(("def", f"{n.name}.{m.name}", ast.unparse(m.args), m.lineno,
                                     d[0].strip() if d else ""))
    return rows


def line(r, limit=60):
    kind, name, args, no, doc = r
    sig = f"{name}({args})" if kind == "def" else f"class {name}"
    if len(args) > 80:
        sig = f"{name}({args[:77]}...)"
    return f"{sig}  L{no}  {doc[:limit]}"


def main():
    argv = sys.argv[1:]
    if "--grep" in argv:
        kw = argv[argv.index("--grep") + 1].lower()
        for f in files():
            for r in scan(f):
                if kw in r[1].lower() or kw in r[4].lower():
                    rel = f.relative_to(PIPE.parent).as_posix()
                    print(f"{rel}:{r[3]}  {r[1]}({r[2][:60]})  {r[4][:60]}")
        return
    out = ["# 函式地圖(funcmap.py 自動產生,勿手改)", "",
           "重產:`python -X utf8 pipeline/tools/funcmap.py`;只找某個:`--grep <關鍵字>`。", ""]
    total = 0
    for f in files():
        rows = scan(f)
        if not rows:
            continue
        out.append(f"## {f.relative_to(PIPE.parent).as_posix()}")
        out.extend(line(r) for r in rows)
        out.append("")
        total += len(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"funcmap.md: {total} 項,{len(out)} 行")


if __name__ == "__main__":
    main()
