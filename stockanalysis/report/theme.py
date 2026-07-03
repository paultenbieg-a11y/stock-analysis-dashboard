"""Shared visual theme: colour palette, Plotly defaults, and the report CSS."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

# --- palette ---------------------------------------------------------------

BG        = "#0b0e14"
SURFACE   = "#12161f"
SURFACE_2 = "#151a25"
LINE      = "#232a38"
LINE_SOFT = "#1c2230"
INK       = "#e8ebf0"
MUTED     = "#98a1b3"
FAINT     = "#7c8598"

ACCENT = "#6ea8fe"
GREEN  = "#3fb984"
RED    = "#e0616d"
GOLD   = "#d9a441"
PURPLE = "#a78bfa"
TEAL   = "#4cc3d9"
SLATE  = "#8fa3bf"

COLORWAY = [ACCENT, GREEN, GOLD, PURPLE, RED, TEAL, SLATE]

FONT_STACK = "Inter, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.0.1.min.js"
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def plotly_layout(**overrides: Any) -> dict[str, Any]:
    """Base layout shared by every chart in the report."""
    layout: dict[str, Any] = {
        "template": "plotly_dark",
        "colorway": COLORWAY,
        "font": {"family": FONT_STACK, "size": 12, "color": MUTED},
        "title": None,
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 48, "r": 24, "t": 42, "b": 36},
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": 1.02,
            "xanchor": "right", "x": 1,
            "font": {"size": 11, "color": MUTED}, "bgcolor": "rgba(0,0,0,0)",
        },
        "hoverlabel": {
            "bgcolor": SURFACE_2, "bordercolor": LINE,
            "font": {"family": FONT_STACK, "size": 12, "color": INK},
        },
    }
    layout.update(overrides)
    return layout


def style_axes(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(
        gridcolor="rgba(138,148,166,.10)", zerolinecolor="rgba(138,148,166,.22)",
        linecolor=LINE, tickfont={"size": 11},
    )
    fig.update_yaxes(
        gridcolor="rgba(138,148,166,.10)", zerolinecolor="rgba(138,148,166,.22)",
        linecolor=LINE, tickfont={"size": 11},
    )
    return fig


def fig_html(fig: go.Figure) -> str:
    """Serialize a figure; plotly.js itself is loaded once in the page head."""
    return fig.to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG)


# --- stylesheet -------------------------------------------------------------

CSS = """
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:#0b0e14;color:#e8ebf0;
     font-family:Inter,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
     font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:#8fb8fe}
main{width:min(1280px,100% - 48px);margin:0 auto;padding:0 0 96px}

/* top bar ------------------------------------------------------------- */
.topbar{position:sticky;top:0;z-index:50;background:rgba(11,14,20,.88);
        backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
        border-bottom:1px solid #1c2230}
.topbar-inner{width:min(1280px,100% - 48px);margin:0 auto;display:flex;
              align-items:center;gap:18px;padding:11px 0}
.topbar .brand{font-weight:700;font-size:14px;color:#fff;white-space:nowrap}
.topbar .brand .tk{color:#6ea8fe}
.topbar .brand .px{color:#98a1b3;font-weight:500}
.topbar nav{display:flex;gap:2px;margin-left:auto;overflow-x:auto;scrollbar-width:none}
.topbar nav::-webkit-scrollbar{display:none}
.topbar nav a{color:#98a1b3;text-decoration:none;font-size:11px;font-weight:600;
              text-transform:uppercase;letter-spacing:.08em;padding:6px 10px;
              border-radius:6px;white-space:nowrap}
.topbar nav a:hover{color:#e8ebf0;background:#171c27}

/* hero ------------------------------------------------------------------ */
.hero{padding:52px 0 34px;border-bottom:1px solid #1c2230}
.kicker{color:#6ea8fe;font-size:12px;font-weight:600;text-transform:uppercase;
        letter-spacing:.14em;margin:0 0 14px}
.hero h1{margin:0 0 8px;font-size:clamp(30px,4.5vw,46px);font-weight:650;
         letter-spacing:-.015em;line-height:1.08}
.hero h1 a{color:inherit;text-decoration:none;border-bottom:1px solid rgba(110,168,254,.4)}
.hero h1 a:hover{color:#bcd3ff}
.hero .subline{color:#98a1b3;font-size:15px;margin:0 0 20px}
.hero .subline b{color:#cdd4e0;font-weight:600}
.meta-row{display:flex;flex-wrap:wrap;gap:8px}
.meta-chip{border:1px solid #232a38;background:#12161f;color:#aab3c5;font-size:12px;
           padding:5px 10px;border-radius:6px}
.meta-chip b{color:#e8ebf0;font-weight:600}

/* metric cards ----------------------------------------------------------- */
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:28px 0 0}
.metric{background:#12161f;border:1px solid #232a38;border-radius:10px;padding:16px 18px}
.metric small{display:block;color:#98a1b3;font-size:11px;font-weight:600;
              text-transform:uppercase;letter-spacing:.09em;margin-bottom:8px}
.metric strong{display:block;font-size:23px;font-weight:650;letter-spacing:-.01em;
               font-variant-numeric:tabular-nums;color:#f2f4f8}
.metric span{display:inline-block;margin-top:7px;font-size:12px;color:#98a1b3}
.metric span.up{color:#3fb984}
.metric span.down{color:#e0616d}

/* sections ---------------------------------------------------------------- */
section{margin-top:64px}
.section-head{display:flex;align-items:baseline;gap:14px;
              border-bottom:1px solid #1c2230;padding-bottom:12px}
.section-index{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
               color:#6ea8fe;font-size:13px;font-weight:600}
.section-head h2{margin:0;font-size:22px;font-weight:650;letter-spacing:-.01em}
.section-lead{color:#98a1b3;max-width:880px;margin:12px 0 4px;font-size:14px}
h3{font-size:15px;font-weight:650;margin:28px 0 12px;color:#dfe4ec}
.muted{color:#98a1b3}

/* panels ------------------------------------------------------------------ */
.panel{background:#12161f;border:1px solid #232a38;border-radius:12px;
       overflow:hidden;margin-top:18px}
.panel-pad{padding:8px 8px 2px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px}

/* narrative ---------------------------------------------------------------- */
.narrative{color:#cdd4e0;line-height:1.7;max-width:960px;margin-top:16px}
.narrative p{margin:0 0 12px}

/* callouts ------------------------------------------------------------------ */
.callout{border:1px solid rgba(110,168,254,.32);border-left:3px solid #6ea8fe;
         background:rgba(110,168,254,.06);border-radius:10px;
         padding:18px 20px;margin-top:20px}
.callout h3{margin:0 0 8px}
.callout p{margin:0;color:#cdd4e0;max-width:960px}
.callout b{color:#f2f4f8}
.data-notes{border:1px solid rgba(217,164,65,.38);border-left:3px solid #d9a441;
            background:rgba(217,164,65,.06);border-radius:10px;
            padding:16px 20px;margin-top:28px}
.data-notes h2{font-size:13px;margin:0 0 10px;color:#e7c983;text-transform:uppercase;
               letter-spacing:.09em}
.data-notes ul{margin:0;padding-left:18px;color:#cdb27a;font-size:13.5px;line-height:1.7}

/* generic tables ------------------------------------------------------------ */
.table-scroll{overflow-x:auto;margin-top:18px;border:1px solid #232a38;border-radius:10px}
table.data-table{width:100%;border-collapse:collapse;font-size:13.5px}
.data-table th{text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;
               letter-spacing:.08em;color:#98a1b3;padding:11px 14px;
               border-bottom:1px solid #2a3242;background:#151a25}
.data-table td{padding:11px 14px;border-bottom:1px solid #1c2230;color:#cdd4e0;
               vertical-align:top;line-height:1.45}
.data-table tr:last-child td{border-bottom:none}
.data-table tbody tr:hover td{background:rgba(110,168,254,.04)}
.data-table .num,td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;
                                white-space:nowrap}
.up-text{color:#3fb984}.down-text{color:#e0616d}
.peer-subject td{background:rgba(110,168,254,.09)!important;color:#fff;font-weight:600}

/* financial statement tables -------------------------------------------------- */
.financial-statement-table{width:100%;min-width:820px;border-collapse:collapse;
                           font-size:13.5px;font-variant-numeric:tabular-nums}
.financial-statement-table th,.financial-statement-table td{
  padding:10px 14px;border-bottom:1px solid #1c2230;line-height:1.35}
.financial-statement-table thead th{position:sticky;top:0;z-index:1;color:#98a1b3;
  background:#151a25;font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.08em;border-bottom:1px solid #2a3242}
.financial-statement-table .line-item{width:42%;min-width:300px;text-align:left;color:#cdd4e0}
.financial-statement-table .number-cell{text-align:right;white-space:nowrap;color:#cdd4e0}
.financial-statement-table .fs-section-row td{
  padding:11px 14px 8px;border-top:1px solid #2a3242;border-bottom:1px solid #2a3242;
  color:#8fb8fe;background:#141926;font-size:11px;font-weight:700;
  letter-spacing:.09em;text-transform:uppercase}
.financial-statement-table .fs-indent-1 .line-item{padding-left:32px;color:#9aa5b8}
.financial-statement-table .fs-major .line-item,
.financial-statement-table .fs-major .number-cell{font-weight:650;color:#e8ebf0}
.financial-statement-table .fs-subtotal td{
  border-top:1px solid rgba(138,148,166,.35);font-weight:650;color:#e8ebf0}
.financial-statement-table .fs-total td{
  border-top:2px solid rgba(138,148,166,.45);font-weight:700;color:#f2f4f8}
.financial-statement-table .fs-grand-total td{
  border-top:2px solid rgba(110,168,254,.55);border-bottom:3px double rgba(138,148,166,.45);
  font-weight:750;color:#f6f8fb;background:rgba(110,168,254,.05)}
.financial-statement-table .negative{color:#e0868f}
.statement-unit-note{margin:16px 0 0;font-size:13px;color:#98a1b3}
.statement-unit-note strong{color:#cdd4e0}
.statement-stack{display:grid;gap:26px;margin-top:8px}
.statement-panel{margin-top:16px}
.statement-heading{display:flex;justify-content:space-between;gap:22px;
                   align-items:baseline;margin:26px 0 4px}
.statement-heading h3{margin:0}
.statement-heading .muted{max-width:560px;margin:0;text-align:right;font-size:13px}

/* company overview -------------------------------------------------------------- */
.company-overview-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(300px,.55fr);
                       gap:24px;align-items:start;margin-top:18px}
.company-intro p{font-size:15px;color:#cdd4e0;margin:0 0 12px;line-height:1.7}
.specialty-tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.specialty-tag{display:inline-flex;align-items:center;padding:5px 10px;
               border:1px solid #232a38;border-radius:6px;color:#aab3c5;
               background:#12161f;font-size:12px}
.profile-card{padding:20px;border:1px solid #232a38;border-radius:12px;background:#12161f}
.profile-card h3{margin:0 0 14px}
.profile-facts{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.profile-fact{padding:10px 12px;border:1px solid #1c2230;border-radius:8px;background:#0e1119}
.profile-fact small{display:block;color:#7c8598;font-size:10.5px;font-weight:600;
                    text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px}
.profile-fact strong{display:block;color:#dfe4ec;font-size:13px;font-weight:550;line-height:1.3}
.profile-link-row{display:grid;grid-template-columns:96px minmax(0,1fr);gap:10px;
                  margin:14px 0 0;color:#cdd4e0;overflow-wrap:anywhere;font-size:13px}
.profile-link-row span{color:#7c8598}

/* footer ------------------------------------------------------------------------ */
footer{margin-top:80px;padding-top:22px;border-top:1px solid #1c2230;
       color:#7c8598;font-size:12.5px;line-height:1.75;max-width:960px}

/* responsive ---------------------------------------------------------------------- */
@media(max-width:980px){
  .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  .grid-2{grid-template-columns:1fr}
  .company-overview-grid{grid-template-columns:1fr}
  .statement-heading{display:block}
  .statement-heading .muted{text-align:left;margin-top:6px;max-width:none}
  .topbar .brand .nm{display:none}
}
@media(max-width:560px){
  main{width:min(100% - 28px,1280px)}
  .hero{padding:32px 0 24px}
  .metrics{grid-template-columns:1fr}
  .metric strong{font-size:20px}
}
@media print{
  .topbar{position:static}
  body{background:#fff;color:#111}
}
"""
