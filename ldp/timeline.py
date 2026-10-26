"""Draw one run as an HTML timeline: speech, jobs, ledger states, cancels, unwanted actions."""
from __future__ import annotations

import html
import os

from .channels import ARMS
from .engine import Engine
from .policies import POLICIES, TRAPS
from .sessions import build

PX = 18  # pixels per second


def render(e: Engine, title: str = "") -> str:
    end = max(e.t, 1000) / 1000 + 2
    W = int(end * PX) + 160
    rows = []
    y = 28

    def x(ms):
        return 150 + ms / 1000 * PX

    def lane(label):
        nonlocal y
        rows.append(f'<text x="6" y="{y + 12}" class="lab">{html.escape(label)}</text>')
        yy = y
        y += 22
        return yy

    for sec in range(0, int(end) + 1, 5):
        rows.append(f'<line x1="{x(sec * 1000)}" x2="{x(sec * 1000)}" y1="20" y2="__H__" class="grid"/>'
                    f'<text x="{x(sec * 1000) + 2}" y="14" class="lab">{sec}s</text>')
    # hold windows
    for a, b in e.spec.truth.get("hold_windows", []):
        rows.append(f'<rect x="{x(a)}" y="20" width="{x(b) - x(a)}" height="__H__" class="hold"/>')
    ly = lane("user")
    for t, ev, kw in e.log:
        if ev in ("user_speech", "user_typing"):
            cls = "us" if ev == "user_speech" else "ut"
            rows.append(f'<rect x="{x(t)}" y="{ly}" width="{max(2, x(kw["end"]) - x(t))}" height="14" class="{cls}"><title>{html.escape(kw["text"])}</title></rect>')
        if ev == "onset":
            rows.append(f'<path d="M{x(t)-4} {ly+18} L{x(t)+4} {ly+18} L{x(t)} {ly+12}Z" class="onset"/>')
    ly = lane("agent says")
    if e.arm.voice_out:
        texts = [(t, kw["text"]) for t, ev, kw in e.log if ev == "say_start"]
        for (a, b), (_, tx) in zip(e.speech_log, texts):
            rows.append(f'<rect x="{x(a)}" y="{ly}" width="{max(2, x(b) - x(a))}" height="14" class="as"><title>{html.escape(tx)}</title></rect>')
    else:
        for t, ev, kw in e.log:
            if ev == "say_start":
                rows.append(f'<circle cx="{x(t)}" cy="{ly + 7}" r="4" class="am"><title>{html.escape(kw["text"])}</title></circle>')
    seen = {}
    for job in e.ledger.jobs:
        if job.t_start is None and job.t_end is None:
            continue
        ly = lane(job.name)
        a = job.t_start if job.t_start is not None else job.t_end
        b = job.t_end if job.t_end is not None else e.t
        cls = "jro" if job.kind == "ro" else ("jirr" if not job.reversible else "jchg")
        if job.state.value in ("cancelled",):
            cls += " canc"
        rows.append(f'<rect x="{x(a)}" y="{ly}" width="{max(2, x(b) - x(a))}" height="14" class="{cls}"><title>{job.name}: {job.state.value}</title></rect>')
        if job.t_commit is not None:
            rows.append(f'<line x1="{x(job.t_commit)}" x2="{x(job.t_commit)}" y1="{ly-2}" y2="{ly+16}" class="commit"/>')
    for u in e.unwanted:
        rows.append(f'<text x="{x(u["t"]) - 4}" y="{y + 4}" class="bad">&#10007; {html.escape(u["job"])} ({",".join(u["why"])})</text>')
    H = y + 24
    body = "".join(rows).replace("__H__", str(H - 20))
    css = """
    body{font:13px system-ui,sans-serif;margin:16px;background:#fff;color:#222}
    @media(prefers-color-scheme:dark){body{background:#16181c;color:#ddd}}
    .lab{font-size:11px;fill:currentColor}.us{fill:#2f7de1}.ut{fill:#7b61c9}.as{fill:#2a9d8f}.am{fill:#2a9d8f}
    .jro{fill:#8fb8e8}.jchg{fill:#f4a261}.jirr{fill:#d64545}.canc{opacity:.35;stroke:#000;stroke-dasharray:3}
    .grid{stroke:#8884;stroke-width:1}.commit{stroke:#000;stroke-width:2}.hold{fill:#ffd54f;opacity:.25}.onset{fill:#e76f51}.bad{fill:#d64545;font-size:11px}
    """
    legend = ("blue = user speech, violet = user typing, teal = agent speech or message, light blue = read-only job, "
              "orange = changing job, red = irreversible job, dashed = cancelled, black tick = commit point, "
              "yellow band = the user's hold, &#10007; = unwanted action.")
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title><style>{css}</style>"
            f"<h3>{html.escape(title)}</h3><p>{legend}</p><div style='overflow-x:auto'>"
            f"<svg width='{W}' height='{H}' xmlns='http://www.w3.org/2000/svg'>"
            f"{body}</svg></div>")


def write_examples(outdir: str):
    os.makedirs(outdir, exist_ok=True)
    for sid, v in (("S1", 0), ("S2", 0), ("S4", 1)):
        for arm in ("interactive_voice", "text_interrupt", "basic_voice"):
            e = Engine(build(sid, v), ARMS[arm], POLICIES["ledger_rules"]).run()
            with open(os.path.join(outdir, f"{sid}_v{v}_{arm}.html"), "w") as f:
                f.write(render(e, f"{sid} variant {v}, {arm}, ledger rules"))
