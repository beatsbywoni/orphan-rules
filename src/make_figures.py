#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_figures.py — 원고의 그림 2장을 생성한다. 모든 수치는 본문 확정값.

  Fig. 1  §7.1 — 7,558 위임 엣지의 목적지 구조 (수평 비례 밴드 + 괄호 주석)
  Fig. 2  §7.2 — D1 트리아지 깔때기 (상자 폭이 건수에 비례)

설계 원칙 (2차 개정 — "왜 그림인가"가 보이게)
  - 그림의 논지는 기하가 전달한다. Fig. 1 은 괄호가 가르는 42:58, Fig. 2 는
    폭이 좁아지는 깔때기 자체. 글자는 이름과 % 만 남기고 캡션·본문으로 뺀다.
  - 본문에 없는 수치를 만들지 않는다. 출처→목적지 흐름(생키)은 그리지 않는다.
  - 흑백 인쇄 안전: 명도 단계만. 라벨은 겹침·튀어나옴 없이 배치.
  - 600dpi PNG (Springer 조합화상 기준).

사용:  python3 make_figures.py [출력디렉터리=현재]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
DPI = 600
INK = "0.15"          # 본문 텍스트 토큰 — 데이터 색을 글자에 입히지 않는다
MUTED = "0.40"
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Times New Roman"],
    "font.size": 8,
    "text.color": INK,
})

# ─────────────────────────────────────────────────────────────────────────────
# Fig. 1 — destination structure of the 7,558 edges
# §5.2/§7.1: 2,089 / 825 / 280 / 4,364
# ─────────────────────────────────────────────────────────────────────────────
def fig1():
    segs = [  # (짧은 라벨, n, pct, 명도)
        ("Presidential decree", 2089, 27.6, "0.82"),
        ("Ministerial decree",   825, 10.9, "0.66"),
        ("Administrative rules", 280,  3.7, "0.50"),
        ("Self-governing legislation", 4364, 57.7, "0.25"),
    ]
    total = sum(n for _, n, _, _ in segs)
    assert total == 7558

    fig, ax = plt.subplots(figsize=(6.3, 1.9))
    Y0, H, GAP = 0.36, 0.34, 0.0028          # 밴드 위치 / 높이 / 흰 간격

    x = 0.0
    narrow = 0                                # 좁은 밴드 순번 → 세로 2단 배치
    for label, n, pct, fill in segs:
        w = n / total
        ax.add_patch(Rectangle((x + GAP/2, Y0), w - GAP, H,
                               facecolor=fill, edgecolor="none"))
        cx = x + w / 2
        if w > 0.20:                          # 넓은 밴드: 안쪽 라벨
            ax.text(cx, Y0 + H/2, f"{label}\n{pct}%",
                    ha="center", va="center", fontsize=8,
                    color="white" if float(fill) < 0.5 else INK,
                    fontweight="bold" if pct > 50 else "normal")
        else:                                 # 좁은 밴드: 아래 한 줄, 리더 좌우로
            ax.plot([cx, cx], [Y0 - 0.03, Y0 - 0.12], lw=0.7, color=MUTED,
                    solid_capstyle="butt")
            ha = "right" if narrow == 0 else "left"        # 리더 양쪽으로 벌린다
            dx = -0.012 if narrow == 0 else 0.012
            ax.text(cx + dx, Y0 - 0.14, f"{label} — {pct}%",
                    ha=ha, va="top", fontsize=7.5, color=INK)
            narrow += 1
        x += w

    # 괄호 주석 — 이 그림의 논지: 절반 이상이 부처를 지나쳐 지방으로 간다
    def bracket(x0, x1, text, bold=False):
        yb, t = Y0 + H + 0.06, 0.045
        ax.plot([x0, x0, x1, x1], [yb, yb + t, yb + t, yb],
                lw=0.9, color=INK, solid_capstyle="butt")
        ax.text((x0 + x1)/2, yb + t + 0.045, text, ha="center", va="bottom",
                fontsize=8, color=INK, fontweight="bold" if bold else "normal")

    split = (2089 + 825 + 280) / total
    bracket(0.004, split - 0.006, "to central-government instruments")
    bracket(split + 0.006, 0.996, "past the ministry — 57.7%", bold=True)

    ax.set_xlim(0, 1); ax.set_ylim(-0.34, 1.06)
    ax.axis("off")
    fig.savefig(OUT / "fig1_edges.png", dpi=DPI, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Fig. 2 — D1 triage funnel, bar widths ∝ n  (§7.2, Table 5)
# 257 → 149 → 138 → 61 ; exits 108 / 7+4 / 77
# ─────────────────────────────────────────────────────────────────────────────
def fig2():
    stages = [  # (n, 라벨, %, 명도)
        (257, "current rules",        None,    "0.90"),
        (149, "flagged as D1",        "58.0%", "0.72"),
        (138, "adjudicated",          None,    "0.55"),
        ( 61, "externally directed",  "23.7%", "0.25"),
    ]
    exits = [  # 단계 i → i+1 사이 우측 라벨
        "108 with recorded delegation",
        "− 7 cross-ministry · − 4 annex-only",
        "− 77 internal housekeeping",
    ]

    fig, ax = plt.subplots(figsize=(5.6, 3.1))
    FULL = 4.4                                # 257건 = 이 폭
    BH, VG = 0.62, 0.55                       # 상자 높이 / 세로 간격
    CX = FULL / 2                             # 중심축
    ys = [ (len(stages)-1-i) * (BH+VG) for i in range(len(stages)) ]

    # 연결 사다리꼴 — 폭이 줄어드는 것 자체가 보이게
    for i in range(len(stages)-1):
        w0 = stages[i][0]   / 257 * FULL
        w1 = stages[i+1][0] / 257 * FULL
        y0, y1 = ys[i], ys[i+1] + BH
        ax.add_patch(Polygon([(CX-w0/2, y0), (CX+w0/2, y0),
                              (CX+w1/2, y1), (CX-w1/2, y1)],
                             closed=True, facecolor="0.955", edgecolor="none"))

    for (n, label, pct, fill), y in zip(stages, ys):
        w = n / 257 * FULL
        ax.add_patch(Rectangle((CX-w/2, y), w, BH, facecolor=fill,
                               edgecolor="none"))
        white = float(fill) < 0.5
        inside = f"{n} {label}" if w > 2.0 else str(n)
        ax.text(CX, y + BH/2, inside, ha="center", va="center",
                fontsize=8.5, color="white" if white else INK,
                fontweight="bold" if n == 61 else "normal")
        out = (f"{label} — {pct}" if w <= 2.0 and pct else
               pct if pct else None)
        if out:                               # 이름·% 는 상자 오른쪽 바깥
            ax.text(CX + w/2 + 0.10, y + BH/2, out, ha="left", va="center",
                    fontsize=8.5, color=INK,
                    fontweight="bold" if n == 61 else "normal")

    # 이탈 라벨 — 사다리꼴 우측 사면에 짧게
    for i, txt in enumerate(exits):
        w0 = stages[i][0] / 257 * FULL
        ymid = (ys[i] + ys[i+1] + BH) / 2
        ax.text(CX + w0/2 + 0.10, ymid, txt, ha="left", va="center",
                fontsize=7.3, color=MUTED)

    ax.set_xlim(-0.1, FULL + 2.3)
    ax.set_ylim(-0.15, ys[0] + BH + 0.15)
    ax.axis("off")
    fig.savefig(OUT / "fig2_triage.png", dpi=DPI, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig1(); fig2()
    for f in ("fig1_edges.png", "fig2_triage.png"):
        p = OUT / f
        print(f"  {f}  {p.stat().st_size/1024:.0f} KB")
