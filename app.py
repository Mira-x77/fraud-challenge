"""
FraudShield — Full-screen Broadcast HUD with loading sequence and live data FX.
"""

import base64
import html
import mimetypes
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from fraud_detection import detect_fraud, load_transactions

SAMPLE_CSV = Path(__file__).parent / "data" / "sample_transactions.csv"
ASSETS = Path(__file__).parent / "assets"


@st.cache_data
def _globe_asset() -> tuple[str, str]:
    return _img_b64(ASSETS / "globe.png")


@st.cache_data
def _bg_asset(name: str) -> tuple[str, str]:
    return _img_b64(ASSETS / name)


def _img_b64(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    if path.suffix.lower() in (".jfif", ".jpe"):
        mime = "image/jpeg"
    return base64.b64encode(raw).decode(), mime


def _render_html(markup: str) -> None:
    if hasattr(st, "html"):
        st.html(markup)
    else:
        st.markdown(markup, unsafe_allow_html=True)


def _esc(text) -> str:
    return html.escape(str(text))


def _inject_global_css(mode: str = "broadcast") -> None:
    bg_file = "hud-broadcast.jfif" if mode == "idle" else "hud-results.jfif"
    if not (ASSETS / bg_file).exists():
        bg_file = "hud-template.jfif"
    bg_b64, bg_mime = _bg_asset(bg_file)

    accent = "#00ff88" if mode == "results" else "#ff2844"
    accent_rgb = "0, 255, 136" if mode == "results" else "255, 40, 68"

    _render_html(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@500;700;900&display=swap');

            .stApp {{
                background: #030303;
                background-image:
                    linear-gradient(rgba(3,3,3,0.82), rgba(3,3,3,0.9)),
                    url("data:{bg_mime};base64,{bg_b64}");
                background-size: cover;
                background-attachment: fixed;
            }}

            html, body, [class*="css"] {{
                font-family: 'Share Tech Mono', monospace;
                color: #dce8dc;
            }}

            header[data-testid="stHeader"] {{
                background: rgba(0,0,0,0.4) !important;
            }}

            .block-container {{
                padding: 0.5rem 1rem 2rem 1rem !important;
                max-width: 100% !important;
            }}

            section.main > div {{
                max-width: 100%;
            }}

            [data-testid="stSidebar"] {{
                background: rgba(4, 8, 6, 0.97) !important;
                border-right: 1px solid rgba({accent_rgb}, 0.35) !important;
            }}

            div[data-testid="stButton"] > button {{
                width: 100%;
            }}

            div[data-testid="stButton"] button[kind="primary"] {{
                background: linear-gradient(180deg, rgba({accent_rgb},0.25), rgba({accent_rgb},0.08)) !important;
                border: 2px solid {accent} !important;
                color: {accent} !important;
                font-family: 'Orbitron', sans-serif !important;
                font-weight: 700 !important;
                letter-spacing: 0.28em !important;
                text-transform: uppercase;
                padding: 0.85rem 2rem !important;
                box-shadow: 0 0 28px rgba({accent_rgb}, 0.45);
                animation: btn-pulse 2s ease-in-out infinite;
            }}

            @keyframes btn-pulse {{
                0%, 100% {{ box-shadow: 0 0 18px rgba({accent_rgb}, 0.35); }}
                50% {{ box-shadow: 0 0 36px rgba({accent_rgb}, 0.65); }}
            }}

            /* Scanlines + live noise */
            .stApp::before {{
                content: "";
                pointer-events: none;
                position: fixed;
                inset: 0;
                z-index: 9998;
                background: repeating-linear-gradient(
                    0deg,
                    rgba(255,255,255,0.03) 0px,
                    rgba(255,255,255,0.03) 1px,
                    transparent 1px,
                    transparent 3px
                );
                animation: scan-move 8s linear infinite;
            }}
            @keyframes scan-move {{
                0% {{ transform: translateY(0); }}
                100% {{ transform: translateY(4px); }}
            }}

            .cyber-box {{
                position: relative;
                background: rgba(0, 10, 6, 0.78);
                border: 1px solid rgba({accent_rgb}, 0.45);
                padding: 0.9rem 1rem;
                margin: 0.5rem 0;
                clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px));
            }}
            .cyber-box::before {{
                content: "";
                position: absolute;
                top: 0; left: 0;
                width: 16px; height: 16px;
                border-top: 2px solid {accent};
                border-left: 2px solid {accent};
            }}
            .cyber-box::after {{
                content: "";
                position: absolute;
                bottom: 0; right: 0;
                width: 16px; height: 16px;
                border-bottom: 2px solid {accent};
                border-right: 2px solid {accent};
            }}

            .cyber-title {{
                font-family: 'Orbitron', sans-serif;
                font-weight: 900;
                letter-spacing: 0.16em;
                text-transform: uppercase;
                color: {accent};
                text-shadow: 0 0 12px rgba({accent_rgb}, 0.5);
                margin: 0 0 0.4rem 0;
            }}
            .cyber-tag {{
                display: inline-block;
                font-size: 0.6rem;
                letter-spacing: 0.14em;
                padding: 0.15rem 0.45rem;
                border: 1px solid rgba({accent_rgb}, 0.6);
                color: {accent};
                margin-bottom: 0.45rem;
                animation: tag-blink 3s step-end infinite;
            }}
            @keyframes tag-blink {{
                0%, 92%, 100% {{ opacity: 1; }}
                93%, 97% {{ opacity: 0.35; }}
            }}

            .fs-stage {{
                min-height: 78vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                position: relative;
                padding: 1rem;
            }}

            .globe-scan-panel {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: stretch;
                min-height: 440px;
                padding-bottom: 1rem !important;
            }}
            .globe-scan-label {{
                font-size: 0.65rem;
                letter-spacing: 0.14em;
                margin-bottom: 0.5rem;
                width: 100%;
                text-align: center;
                flex-shrink: 0;
            }}
            .globe-scan-stage {{
                flex: 1 1 auto;
                display: flex;
                align-items: center;
                justify-content: center;
                width: 100%;
                min-height: 380px;
                position: relative;
            }}
            .globe-scan-wrap {{
                width: min(320px, 96%) !important;
                height: min(320px, 96%) !important;
                margin: 0 auto !important;
            }}
            .globe-scan-wrap .fs-orbit {{
                inset: -14px;
            }}
            .globe-scan-wrap .fs-orbit-2 {{
                inset: -26px;
            }}
            .globe-scan-wrap .fs-orbit-3 {{
                inset: -40px;
            }}
            .globe-scan-wrap .fs-radar {{
                inset: -50px;
            }}

            .fs-globe-wrap {{
                position: relative;
                width: min(340px, 55vw);
                height: min(340px, 55vw);
                margin: 1rem auto;
            }}
            .fs-orbit {{
                position: absolute;
                inset: -18px;
                border: 1px dashed rgba({accent_rgb}, 0.55);
                border-radius: 50%;
                animation: spin 24s linear infinite;
            }}
            .fs-orbit-2 {{
                inset: -32px;
                border-style: dotted;
                opacity: 0.45;
                animation-direction: reverse;
                animation-duration: 32s;
            }}
            .fs-orbit-3 {{
                inset: -48px;
                border: 1px solid rgba(255,255,255,0.12);
                animation-duration: 40s;
            }}
            .fs-globe {{
                width: 100%;
                height: 100%;
                border-radius: 50%;
                animation: spin 20s linear infinite;
                filter: drop-shadow(0 0 24px rgba({accent_rgb}, 0.7));
                border: 1px solid rgba(255,255,255,0.2);
            }}
            @keyframes spin {{
                from {{ transform: rotate(0deg); }}
                to {{ transform: rotate(360deg); }}
            }}

            .fs-radar {{
                position: absolute;
                inset: -60px;
                border-radius: 50%;
                background: conic-gradient(from 0deg, transparent 0deg, rgba({accent_rgb},0.12) 40deg, transparent 80deg);
                animation: spin 4s linear infinite;
                pointer-events: none;
            }}

            .live-ticker {{
                width: 100%;
                max-width: 900px;
                overflow: hidden;
                white-space: nowrap;
                font-size: 0.65rem;
                color: rgba({accent_rgb}, 0.75);
                border-top: 1px solid rgba({accent_rgb}, 0.25);
                border-bottom: 1px solid rgba({accent_rgb}, 0.25);
                padding: 0.35rem 0;
                margin-top: 1rem;
            }}
            .live-ticker span {{
                display: inline-block;
                animation: ticker 18s linear infinite;
            }}
            @keyframes ticker {{
                0% {{ transform: translateX(0); }}
                100% {{ transform: translateX(-50%); }}
            }}

            /* ── LOADING SCREEN (cyberpunk GIF style) ── */
            .load-screen {{
                min-height: 88vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                position: relative;
            }}
            .load-rings {{
                position: relative;
                width: 220px;
                height: 220px;
            }}
            .load-ring {{
                position: absolute;
                inset: 0;
                border: 2px solid rgba({accent_rgb}, 0.35);
                border-radius: 50%;
                border-top-color: {accent};
                animation: spin 1.2s linear infinite;
            }}
            .load-ring:nth-child(2) {{ inset: 20px; animation-duration: 1.8s; animation-direction: reverse; }}
            .load-ring:nth-child(3) {{ inset: 40px; animation-duration: 2.4s; }}
            .load-glitch {{
                font-family: 'Orbitron', sans-serif;
                font-size: 1.1rem;
                letter-spacing: 0.2em;
                color: {accent};
                margin-top: 2rem;
                animation: glitch 1.5s infinite;
            }}
            @keyframes glitch {{
                0%, 90%, 100% {{ opacity: 1; transform: translate(0); }}
                91% {{ opacity: 0.8; transform: translate(-2px, 1px); }}
                93% {{ opacity: 1; transform: translate(2px, -1px); }}
                95% {{ opacity: 0.7; transform: translate(-1px, 2px); }}
            }}
            .load-binary {{
                margin-top: 1.5rem;
                font-size: 0.62rem;
                line-height: 1.6;
                color: rgba({accent_rgb}, 0.55);
                text-align: center;
                max-width: 520px;
                animation: binary-flicker 0.15s step-end infinite;
            }}
            @keyframes binary-flicker {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.85; }}
            }}
            .load-bar-wrap {{
                width: min(420px, 80vw);
                height: 6px;
                background: rgba(255,255,255,0.08);
                margin-top: 1.5rem;
                border: 1px solid rgba({accent_rgb}, 0.3);
            }}
            .load-bar-fill {{
                height: 100%;
                width: 0%;
                background: linear-gradient(90deg, transparent, {accent});
                animation: load-progress 2.8s ease-out forwards;
                box-shadow: 0 0 12px rgba({accent_rgb}, 0.8);
            }}
            @keyframes load-progress {{
                to {{ width: 100%; }}
            }}

            /* ── RESULTS GRID (green HUD) ── */
            .hud-grid {{
                display: grid;
                grid-template-columns: repeat(12, 1fr);
                gap: 0.65rem;
                width: 100%;
            }}
            .span-3 {{ grid-column: span 3; }}
            .span-4 {{ grid-column: span 4; }}
            .span-5 {{ grid-column: span 5; }}
            .span-6 {{ grid-column: span 6; }}
            .span-8 {{ grid-column: span 8; }}
            .span-12 {{ grid-column: span 12; }}
            @media (max-width: 900px) {{
                .span-3, .span-4, .span-5, .span-6, .span-8 {{ grid-column: span 12; }}
            }}

            .metric-num {{
                font-family: 'Orbitron', sans-serif;
                font-size: 1.8rem;
                color: #00ff88;
                text-shadow: 0 0 10px rgba(0,255,136,0.5);
            }}
            .metric-danger {{ color: #ff4466 !important; text-shadow: 0 0 10px rgba(255,68,102,0.6) !important; }}

            .alert-card {{
                border-left: 3px solid #ff4466;
                padding: 0.65rem 0.75rem;
                margin-bottom: 0.55rem;
                background: rgba(255, 40, 68, 0.06);
                font-size: 0.78rem;
                line-height: 1.55;
            }}
            .alert-card .reason {{
                display: block;
                margin: 0.4rem 0;
                color: #ffb8c4;
                word-break: break-word;
            }}
            .alert-card.medium {{ border-left-color: #ffaa00; background: rgba(255,170,0,0.06); }}

            .hud-bar-row {{
                display: grid;
                grid-template-columns: 40px 1fr 28px;
                gap: 0.4rem;
                align-items: center;
                margin-bottom: 0.4rem;
                font-size: 0.68rem;
            }}
            .hud-bar-track {{
                height: 8px;
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(0,255,136,0.2);
            }}
            .hud-bar-fill {{
                height: 100%;
                background: linear-gradient(90deg, #004422, #00ff88);
                box-shadow: 0 0 6px rgba(0,255,136,0.5);
            }}

            .hud-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.72rem;
            }}
            .hud-table th {{
                text-align: left;
                color: #00ff88;
                border-bottom: 1px solid rgba(0,255,136,0.35);
                padding: 0.35rem 0.4rem;
                letter-spacing: 0.08em;
            }}
            .hud-table td {{
                padding: 0.35rem 0.4rem;
                border-bottom: 1px solid rgba(255,255,255,0.06);
                vertical-align: top;
            }}
            .hud-table tr.flagged td {{
                background: rgba(255, 40, 68, 0.08);
                color: #ffd0d8;
            }}
            .hud-table .reason-cell {{
                max-width: 280px;
                word-break: break-word;
                color: #ffc8d0;
            }}
            .hud-kv {{
                display: grid;
                grid-template-columns: 140px 1fr;
                gap: 0.25rem 0.75rem;
                font-size: 0.72rem;
            }}
            .hud-kv .k {{ color: rgba(0,255,136,0.7); }}
            .hud-kv .v {{ color: #fff; word-break: break-word; }}
            .hud-kv .v.danger {{ color: #ff6688; font-weight: bold; }}

            .pulse-dot {{
                display: inline-block;
                width: 6px; height: 6px;
                border-radius: 50%;
                background: #00ff88;
                margin-right: 6px;
                animation: pulse 1s ease infinite;
            }}
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; box-shadow: 0 0 6px #00ff88; }}
                50% {{ opacity: 0.3; }}
            }}

            .btn-row-center {{
                display: flex;
                justify-content: center;
                max-width: 280px;
                margin: 0 auto 0.5rem auto;
            }}
        </style>
        """
    )


def _globe_html(
    globe_b64: str,
    globe_mime: str,
    size: int = 340,
    wrap_class: str = "fs-globe-wrap",
) -> str:
    px = f"{size}px"
    style = f"width:{px};height:{px};margin:0 auto"
    if "globe-scan-wrap" in wrap_class:
        style = ""
    return f"""
    <div class="{wrap_class}" style="{style}">
        <div class="fs-radar"></div>
        <div class="fs-orbit"></div>
        <div class="fs-orbit fs-orbit-2"></div>
        <div class="fs-orbit fs-orbit-3"></div>
        <img class="fs-globe" src="data:{globe_mime};base64,{globe_b64}" alt="globe" />
    </div>
    """


def _live_ticker() -> str:
    bits = "01001101 11010010 10101001 01101100 01000101 10110101 " * 4
    return f'<div class="live-ticker"><span>{bits}{bits}</span></div>'


def _render_idle_header() -> None:
    _render_html(
        """
        <div style="text-align:center;padding-top:0.5rem">
            <span class="cyber-tag">// FRAUDSHIELD HUD v3.0 — BROADCAST MODE</span>
            <div class="cyber-title" style="font-size:1.5rem">FraudShield Cyber HUD</div>
            <p style="opacity:0.7;font-size:0.78rem;letter-spacing:0.12em;margin:0.5rem 0">
                SCANNING FINANCIAL NETWORKS · AWAITING ANALYSE COMMAND
            </p>
        </div>
        """
    )


def _render_idle_globe(globe_b64: str, globe_mime: str) -> None:
    _render_html(
        f"""
        <div class="fs-stage" style="min-height:auto;padding:0.5rem 0">
            {_globe_html(globe_b64, globe_mime, size=320)}
            {_live_ticker()}
            <p style="text-align:center;font-size:0.65rem;opacity:0.45;margin-top:0.75rem">
                <span class="pulse-dot"></span>LIVE UPLINK ACTIVE · ENCRYPTED CHANNEL SECURE
            </p>
        </div>
        """
    )


def _render_idle_screen(globe_b64: str, globe_mime: str) -> None:
    _render_idle_header()


def _render_loading_screen() -> None:
    binary_rows = "<br>".join(
        [
            "F1-200NS  F6-4852  0x017EE2F3  SCANNING TXN BATCH",
            "10110101 01001101 11001010 01100101 01001100",
            "VELOCITY CHECK · GEO HASH · CNP PROTOCOL · ATO SCAN",
        ]
    )
    _render_html(
        f"""
        <div class="load-screen">
            <span class="cyber-tag">// SPGFX · FRAUD DETECTION PROTOCOL</span>
            <div class="load-rings">
                <div class="load-ring"></div>
                <div class="load-ring"></div>
                <div class="load-ring"></div>
            </div>
            <div class="load-glitch">ANALYSING TRANSACTION STREAM</div>
            <div class="load-binary">{binary_rows}</div>
            <div class="load-bar-wrap"><div class="load-bar-fill"></div></div>
            <p style="margin-top:1rem;font-size:0.68rem;opacity:0.6;letter-spacing:0.15em">
                DECODING · CROSS-REFERENCING · SCORING
            </p>
        </div>
        """
    )


def _action_label(score: float) -> tuple[str, str]:
    if score >= 0.85:
        return "🔒 CARTE BLOQUÉE", "alert-high"
    if score >= 0.5:
        return "⚠️ REVUE MANUELLE + SMS", "alert-medium"
    return "✅ AUCUNE ACTION", ""


def _hud_bar_chart(items: list[tuple[str, float]]) -> str:
    if not items:
        return "<p style='opacity:0.5'>—</p>"
    max_v = max(v for _, v in items) or 1.0
    rows = ""
    for label, val in items:
        pct = max(5, int((val / max_v) * 100))
        rows += (
            f'<div class="hud-bar-row">'
            f"<span>{_esc(label)}</span>"
            f'<div class="hud-bar-track"><div class="hud-bar-fill" style="width:{pct}%"></div></div>'
            f"<span>{val:.0f}</span></div>"
        )
    return rows


def _hud_table_html(df: pd.DataFrame, cols: list[str], highlight_suspicious: bool = True) -> str:
    header = "".join(f"<th>{_esc(c)}</th>" for c in cols)
    body = ""
    for _, row in df.iterrows():
        flagged = highlight_suspicious and row.get("is_suspicious")
        tr_cls = ' class="flagged"' if flagged else ""
        cells = ""
        for c in cols:
            val = row.get(c, "")
            if pd.isna(val):
                val = "—"
            cls = ""
            if c == "reason":
                cls = ' class="reason-cell"'
            if c == "amount" and flagged:
                cls = ' style="color:#ff6688;font-weight:bold"'
            cells += f"<td{cls}>{_esc(val)}</td>"
        body += f"<tr{tr_cls}>{cells}</tr>"
    return f'<table class="hud-table"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>'


def _detail_kv(row: pd.Series) -> str:
    fields = [
        ("transaction_id", False),
        ("timestamp", False),
        ("user_id", False),
        ("amount", True),
        ("currency", False),
        ("merchant", False),
        ("country", False),
        ("card_present", False),
        ("fraud_score", True),
        ("is_suspicious", False),
        ("reason", False),
    ]
    lines = ""
    for key, danger in fields:
        if key not in row.index:
            continue
        val = row[key]
        if pd.isna(val):
            val = "—"
        vcls = "v danger" if danger and (key == "amount" and float(val or 0) < 0 or key == "fraud_score") else "v"
        lines += f'<div class="k">{_esc(key)}</div><div class="{vcls}">{_esc(val)}</div>'
    return f'<div class="hud-kv">{lines}</div>'


def render_results(transactions: list[dict], results: list[dict]) -> None:
    globe_b64, globe_mime = _globe_asset()

    df = pd.DataFrame(transactions)
    res_df = pd.DataFrame(results)
    full = df.merge(res_df, on="transaction_id", how="left")

    total = len(full)
    flagged = full[full["is_suspicious"] == True].copy()
    safe_count = total - len(flagged)
    protected = flagged["amount"].fillna(0).sum()

    display_cols = [
        "transaction_id", "user_id", "amount", "currency",
        "merchant", "country", "fraud_score", "is_suspicious", "reason",
    ]
    display_cols = [c for c in display_cols if c in full.columns]

    alerts_html = ""
    if flagged.empty:
        alerts_html = "<p>◉ AUCUNE MENACE DÉTECTÉE</p>"
    else:
        for _, row in flagged.sort_values("fraud_score", ascending=False).iterrows():
            action, cls = _action_label(float(row["fraud_score"]))
            medium = " medium" if cls == "alert-medium" else ""
            amt = row.get("amount", 0)
            amt_str = f"{amt:,.0f}" if isinstance(amt, (int, float)) else str(amt)
            alerts_html += (
                f'<div class="alert-card{medium}">'
                f"<strong>{_esc(row['transaction_id'])}</strong> · "
                f"CLIENT <strong>{_esc(row.get('user_id'))}</strong> · "
                f"MONTANT <strong>{amt_str}</strong> {_esc(row.get('currency', ''))} · "
                f"SCORE <strong>{row['fraud_score']}</strong><br>"
                f"<span class='reason'>{_esc(row['reason'])}</span>"
                f"<strong style='color:#ff6688'>{_esc(action)}</strong>"
                f"</div>"
            )

    country_items: list[tuple[str, float]] = []
    if not flagged.empty:
        for k, v in flagged.groupby("country", dropna=False).size().items():
            country_items.append((str(k or "??"), float(v)))

    _render_html(
        f"""
        <div class="hud-grid">
            <div class="cyber-box span-12">
                <span class="cyber-tag"><span class="pulse-dot"></span>LIVE BROADCAST · RESULTS TRANSMITTED</span>
                <div class="cyber-title" style="font-size:1.15rem">◈ Analyse terminée — monitoring actif</div>
            </div>

            <div class="cyber-box span-3">
                <div style="font-size:0.65rem;opacity:0.65;letter-spacing:0.1em">TRANSACTIONS</div>
                <div class="metric-num">{total}</div>
            </div>
            <div class="cyber-box span-3">
                <div style="font-size:0.65rem;opacity:0.65;letter-spacing:0.1em">ALERTES</div>
                <div class="metric-num metric-danger">{len(flagged)}</div>
            </div>
            <div class="cyber-box span-3">
                <div style="font-size:0.65rem;opacity:0.65;letter-spacing:0.1em">SÛRES</div>
                <div class="metric-num">{safe_count}</div>
            </div>
            <div class="cyber-box span-3">
                <div style="font-size:0.65rem;opacity:0.65;letter-spacing:0.1em">CAPITAL PROTÉGÉ</div>
                <div class="metric-num">{protected:,.0f} XOF</div>
            </div>

            <div class="cyber-box span-4 globe-scan-panel">
                <div class="globe-scan-label">GLOBAL SCAN</div>
                <div class="globe-scan-stage">
                    {_globe_html(globe_b64, globe_mime, wrap_class="fs-globe-wrap globe-scan-wrap")}
                </div>
            </div>

            <div class="cyber-box span-8">
                <div class="cyber-title" style="font-size:0.8rem">▸ Fil d'alertes complet</div>
                {alerts_html}
            </div>

            <div class="cyber-box span-6">
                <div class="cyber-title" style="font-size:0.8rem">▸ Alertes par pays</div>
                {_hud_bar_chart(country_items)}
            </div>
            <div class="cyber-box span-6">
                <div class="cyber-title" style="font-size:0.8rem">▸ Scores de risque</div>
                {_hud_bar_chart([(f"BIN{i}", float(v)) for i, v in enumerate(
                    pd.cut(full["fraud_score"], bins=8).value_counts(sort=False).values
                )])}
            </div>
        </div>
        {_live_ticker()}
        """
    )

    _render_html('<div class="cyber-title" style="margin-top:1rem;font-size:0.85rem">▸ Enquêteur — toutes les alertes</div>')

    st.markdown("")
    view = st.radio(
        "Afficher",
        ["Uniquement les suspectes", "Toutes les transactions"],
        horizontal=True,
        label_visibility="collapsed",
    )
    table = flagged if view == "Uniquement les suspectes" else full
    _render_html(_cyber_box(_hud_table_html(table, display_cols)))

    if not flagged.empty:
        ids = flagged["transaction_id"].tolist()
        selected = st.selectbox("Inspecter une transaction signalée", ids, label_visibility="visible")

        for tid in ids:
            row = full[full["transaction_id"] == tid].iloc[0]
            expanded = tid == selected
            with st.expander(f"◈ {tid} — score {row['fraud_score']} — {row.get('user_id')}", expanded=expanded):
                action, _ = _action_label(float(row["fraud_score"]))
                _render_html(
                    _cyber_box(
                        f"<span class='cyber-tag'>SIGNAL DÉTECTÉ</span><br>"
                        f"<strong>POURQUOI ?</strong><br>"
                        f"<span style='color:#ffb8c4;line-height:1.6'>{_esc(row['reason'])}</span><br><br>"
                        f"<strong>ACTION :</strong> {_esc(action)}"
                    )
                )
                _render_html(
                    _cyber_box(
                        "<strong>DÉTAILS COMPLETS</strong><br><br>" + _detail_kv(row)
                    )
                )
                uid = row.get("user_id")
                if uid:
                    history = full[full["user_id"] == uid]
                    _render_html(
                        _cyber_box(
                            f"<strong>HISTORIQUE CLIENT {_esc(uid)}</strong> ({len(history)} txns)<br><br>"
                            + _hud_table_html(history, display_cols)
                        )
                    )


def _cyber_box(inner: str) -> str:
    return f'<div class="cyber-box">{inner}</div>'


def main() -> None:
    st.set_page_config(page_title="FraudShield HUD", page_icon="🛡️", layout="wide")

    if "phase" not in st.session_state:
        st.session_state.phase = "idle"
    if "results" not in st.session_state:
        st.session_state.results = None
    if "transactions" not in st.session_state:
        st.session_state.transactions = []

    mode = "results" if st.session_state.phase == "results" else "idle"
    if st.session_state.phase == "loading":
        mode = "idle"
    _inject_global_css(mode)
    globe_b64, globe_mime = _globe_asset()

    with st.sidebar:
        st.markdown("### ◈ DONNÉES")
        use_sample = st.toggle("Fichier d'exemple", value=True)
        transactions: list[dict] = []

        if use_sample:
            transactions = load_transactions(str(SAMPLE_CSV))
            st.success(f"{len(transactions)} transactions")
        else:
            uploaded = st.file_uploader("CSV", type=["csv"])
            if uploaded:
                tmp = Path(".streamlit_upload.csv")
                tmp.write_bytes(uploaded.getvalue())
                transactions = load_transactions(str(tmp))
                tmp.unlink(missing_ok=True)
                st.success(f"{len(transactions)} transactions")

        if st.session_state.phase == "results":
            if st.button("↺ Nouvelle analyse"):
                st.session_state.phase = "idle"
                st.session_state.results = None
                st.rerun()

    if not transactions:
        _render_html(_cyber_box("◉ Chargez des transactions (barre latérale)."))
        return

    st.session_state.transactions = transactions

    if st.session_state.phase == "idle":
        _render_idle_screen(globe_b64, globe_mime)
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            if st.button("Analyser", type="primary", use_container_width=True):
                st.session_state.phase = "loading"
                st.rerun()
        _render_idle_globe(globe_b64, globe_mime)

    elif st.session_state.phase == "loading":
        _render_loading_screen()
        time.sleep(2.8)
        try:
            st.session_state.results = detect_fraud(transactions)
            st.session_state.phase = "results"
        except Exception as exc:
            st.error(str(exc))
            st.session_state.phase = "idle"
        st.rerun()

    elif st.session_state.phase == "results" and st.session_state.results is not None:
        render_results(st.session_state.transactions, st.session_state.results)


if __name__ == "__main__":
    main()
