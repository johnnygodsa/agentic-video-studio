#!/usr/bin/env python3
r"""ChannelC片頭片尾:scenes\lab_intro.js / lab_outro.js 算成 1920x1080 mp4,供 build.py 當影片鏡頭用。
用法:python -X utf8 pipeline\sci\make_lab.py [intro|outro]   (省略 = 兩個都做)
輸出:anim\lab\lab_<名>.mp4(無聲)、lab_<名>_sfx.mp4(混入 channel\sfx\<名>.wav,檔案不存在就略過);
檢查格 tmp\lab_frames\(intro 0.5/1.0/1.1/2.9 秒、outro 1.3/4.4 秒)。"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

SCENES = {"intro": (3.0, [0.5, 1.0, 1.1, 2.9]), "outro": (4.5, [1.3, 4.4])}


def make(kind):
    dur, checks = SCENES[kind]
    name = f"lab_{kind}"
    r = subprocess.run([sys.executable, "-X", "utf8", str(paths.ROOT / "pipeline" / "sci" / "render_clip.py"), name,
                        "--dur", str(dur), "--out", name, "--frames-only"], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-600:], r.stderr.strip()[-300:])
    if r.returncode:
        sys.exit(f"{name} 算圖失敗")
    frames = paths.TMP / name
    out = paths.ANIM / "lab"
    out.mkdir(parents=True, exist_ok=True)
    mp4 = out / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "10", "-i", str(frames / "f_%03d.png"), "-vf", "fps=30,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", "-an", str(mp4)], check=True)
    wav = paths.ROOT / "channel" / "sfx" / f"{kind}.wav"
    if wav.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-af", f"apad,atrim=0:{dur}", "-t", str(dur), "-map", "0:v", "-map", "1:a", str(out / f"{name}_sfx.mp4")], check=True)
    cf = paths.TMP / "lab_frames"
    cf.mkdir(parents=True, exist_ok=True)
    for t in checks:
        shutil.copy(frames / f"f_{round(t * 10):03d}.png", cf / f"{kind}_{t:.1f}s.png")
    print(f"  → {paths.rel(mp4)}" + (f"、{name}_sfx.mp4" if wav.exists() else "(無音效檔)"))


if __name__ == "__main__":
    for kind in (sys.argv[1:] or SCENES):
        make(kind)
