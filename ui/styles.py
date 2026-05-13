import streamlit as st


def apply_global_styles():
    # ---------------------------------------------------------------------------
    # Custom CSS
    # ---------------------------------------------------------------------------
    st.markdown("""
    <style>
    /* ── Global resets ─────────────────────────────────────────── */
    [data-testid="stAppViewContainer"] { background: #f5f7fb; }
    .block-container {
        max-width: 1500px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    /* ── Hide sidebar completely ─────────────────────────────────── */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* ── Top navigation bar ──────────────────────────────────────── */
    .gq-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #1a2740;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        margin-bottom: 1rem;
    }
    .gq-topbar-status {
        display: flex;
        align-items: center;
        gap: 1rem;
        font-size: 0.78rem;
        color: #e8ecf1;
    }
    .gq-topbar-dot {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
    }
    .gq-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }
    .gq-dot-green { background: #22c55e; box-shadow: 0 0 5px #22c55e88; }
    .gq-dot-red   { background: #ef4444; }
    .gq-dot-amber { background: #f59e0b; }

    /* ── App header ─────────────────────────────────────────────── */
    .gq-header {
        background: linear-gradient(135deg, #1a2740 0%, #2e4470 100%);
        color: #fff;
        padding: 1.4rem 2rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1.2rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    }
    .gq-header-icon { font-size: 2.6rem; line-height: 1; }
    .gq-header-title { font-size: 1.7rem; font-weight: 700; letter-spacing: 0; margin: 0; }
    .gq-header-sub   { font-size: 0.85rem; opacity: 0.75; margin: 3px 0 0; }

    /* Dashboard shell */
    .gq-dashboard-hero {
        display: flex;
        justify-content: space-between;
        align-items: stretch;
        gap: 1.4rem;
        background: #0f172a;
        color: #f8fafc;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 1.45rem 1.6rem;
        margin-bottom: 1rem;
        box-shadow: 0 18px 50px rgba(15, 23, 42, 0.18);
    }
    .gq-dashboard-hero h1 {
        margin: 0.15rem 0 0.35rem;
        font-size: 2rem;
        line-height: 1.15;
        font-weight: 750;
        letter-spacing: 0;
    }
    .gq-dashboard-hero p {
        margin: 0;
        color: #cbd5e1;
        font-size: 0.95rem;
        max-width: 620px;
    }
    .gq-eyebrow {
        color: #93c5fd;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: uppercase;
    }
    .gq-hero-status {
        width: 320px;
        border-radius: 8px;
        border: 1px solid rgba(226, 232, 240, 0.18);
        background: rgba(15, 23, 42, 0.58);
        padding: 1rem;
        flex-shrink: 0;
    }
    .gq-hero-status-label {
        color: #94a3b8;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0;
    }
    .gq-hero-status-value {
        margin-top: 0.35rem;
        font-size: 1.15rem;
        font-weight: 750;
        color: #ffffff;
    }
    .gq-hero-status-sub {
        margin-top: 0.2rem;
        min-height: 2.2rem;
        font-size: 0.78rem;
        line-height: 1.35;
        color: #cbd5e1;
    }
    .gq-hero-dots {
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        margin-top: 0.65rem;
        color: #e2e8f0;
        font-size: 0.76rem;
    }

    .gq-kpi-grid {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
    }
    .gq-kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.9rem 0.95rem;
        min-height: 126px;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
        position: relative;
        overflow: hidden;
    }
    .gq-kpi-card::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: #64748b;
    }
    .gq-kpi-topline {
        color: #64748b;
        font-size: 0.72rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0;
    }
    .gq-kpi-value {
        margin-top: 0.5rem;
        color: #0f172a;
        font-size: 2rem;
        line-height: 1;
        font-weight: 800;
    }
    .gq-kpi-hint {
        margin-top: 0.55rem;
        color: #64748b;
        font-size: 0.76rem;
        line-height: 1.3;
    }
    .gq-kpi-card.tone-indigo::before { background: #6366f1; }
    .gq-kpi-card.tone-emerald::before { background: #10b981; }
    .gq-kpi-card.tone-amber::before { background: #f59e0b; }
    .gq-kpi-card.tone-blue::before { background: #3b82f6; }
    .gq-kpi-card.tone-green::before { background: #22c55e; }
    .gq-kpi-card.tone-violet::before { background: #8b5cf6; }
    .gq-kpi-card.tone-slate::before { background: #64748b; }

    .gq-section-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
        margin-bottom: 0.9rem;
    }
    .gq-section-title {
        color: #0f172a;
        font-size: 1rem;
        font-weight: 760;
        line-height: 1.25;
    }
    .gq-section-sub {
        color: #64748b;
        font-size: 0.8rem;
        line-height: 1.35;
        margin-top: 0.15rem;
        margin-bottom: 0.75rem;
    }
    .gq-lane-head {
        border-left: 4px solid;
        border-radius: 8px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.55rem;
        min-height: 76px;
    }
    .gq-lane-label {
        min-height: 30px;
        font-size: 0.69rem;
        line-height: 1.2;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0;
    }
    .gq-lane-count {
        margin-top: 0.25rem;
        font-size: 1.5rem;
        line-height: 1;
        font-weight: 800;
    }
    .gq-pipeline-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #64748b;
        border-radius: 8px;
        padding: 0.6rem 0.65rem;
        margin-bottom: 0.48rem;
        box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
    }
    .gq-pipeline-title {
        color: #0f172a;
        font-size: 0.78rem;
        font-weight: 750;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .gq-pipeline-meta {
        color: #64748b;
        font-size: 0.72rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        margin-top: 0.08rem;
    }
    .gq-pipeline-foot {
        color: #94a3b8;
        font-size: 0.68rem;
        margin-top: 0.28rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .gq-history-spacer { height: 0.25rem; }
    .gq-row-title {
        color: #0f172a;
        font-size: 0.92rem;
        line-height: 1.25;
        font-weight: 760;
    }
    .gq-row-sub, .gq-row-date, .gq-row-meta {
        color: #64748b;
        font-size: 0.76rem;
        line-height: 1.35;
    }
    .gq-row-meta {
        padding-top: 0.35rem;
        border-top: 1px solid #e2e8f0;
        margin-top: 0.55rem;
    }
    .gq-stage-pill, .gq-status-pill {
        display: inline-flex;
        align-items: center;
        max-width: 100%;
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        font-size: 0.68rem;
        line-height: 1.25;
        font-weight: 760;
        margin: 0.1rem 0.25rem 0.1rem 0;
    }
    .pill-slate { background: #f1f5f9; color: #334155; }
    .pill-blue { background: #eff6ff; color: #1d4ed8; }
    .pill-amber { background: #fffbeb; color: #92400e; }
    .pill-green { background: #ecfdf5; color: #047857; }
    .pill-red { background: #fef2f2; color: #b91c1c; }
    .gq-item-stats {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin-top: 0.35rem;
        color: #475569;
        font-size: 0.72rem;
    }
    .gq-item-stats .ok { color: #047857; }
    .gq-item-stats .warn { color: #b45309; }
    .gq-item-stats .bad { color: #b91c1c; }

    @media (max-width: 1200px) {
        .gq-kpi-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
        .gq-dashboard-hero { flex-direction: column; }
        .gq-hero-status { width: auto; }
        .gq-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 520px) {
        .gq-kpi-grid { grid-template-columns: 1fr; }
        .gq-dashboard-hero h1 { font-size: 1.6rem; }
    }

    /* ── Step cards ─────────────────────────────────────────────── */
    .gq-step {
        background: #fff;
        border-radius: 10px;
        padding: 1.4rem 1.6rem 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        margin-bottom: 1.2rem;
        border-left: 4px solid #2e4470;
    }
    .gq-step-label {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        margin-bottom: 1rem;
    }
    .gq-step-badge {
        background: #2e4470;
        color: #fff;
        border-radius: 50%;
        width: 28px; height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.85rem;
        flex-shrink: 0;
    }
    .gq-step-title { font-size: 1.05rem; font-weight: 600; color: #1a2740; margin: 0; }

    /* ── Status metric cards ────────────────────────────────────── */
    .gq-metrics { display: flex; gap: 0.8rem; margin: 0.8rem 0 1rem; }
    .gq-metric {
        flex: 1;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .gq-metric .val { font-size: 1.9rem; font-weight: 700; line-height: 1.1; }
    .gq-metric .lbl { font-size: 0.73rem; text-transform: uppercase; letter-spacing: 0; margin-top: 2px; }
    .gq-total   { background: #eef2fa; color: #2e4470; }
    .gq-total .lbl { color: #5a7aab; }
    .gq-ready   { background: #e6f4ec; color: #1a7a3c; }
    .gq-ready .lbl { color: #3a9a5c; }
    .gq-check   { background: #fff8e6; color: #9a6800; }
    .gq-check .lbl { color: #c08000; }
    .gq-missing { background: #fdecea; color: #b91c1c; }
    .gq-missing .lbl { color: #d94040; }
    .gq-regret  { background: #eeeeee; color: #666666; }
    .gq-regret .lbl { color: #888888; }

    /* ── Sidebar status strip ───────────────────────────────────── */
    .gq-status-strip {
        display: flex; align-items: center; gap: 10px;
        padding: 0.35rem 0.5rem;
        font-size: 0.75rem; opacity: 0.8;
    }
    .gq-ai-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
    .gq-ai-dot-on  { background: #4caf50; box-shadow: 0 0 5px #4caf50; }
    .gq-ai-dot-off { background: #7a8eaa; }

    /* ── Sidebar section title ──────────────────────────────────── */
    .gq-sidebar-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0;
        opacity: 0.55;
        margin: 0.5rem 0 0.4rem;
    }

    /* ── History date-group label ───────────────────────────────── */
    .gq-hist-group {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0;
        opacity: 0.45;
        margin: 0.8rem 0 0.2rem;
        padding-left: 2px;
    }

    /* ── History row item ───────────────────────────────────────── */
    .gq-hist-row {
        display: flex; align-items: center; gap: 6px;
        padding: 0.38rem 0.5rem;
        border-radius: 6px;
        cursor: pointer;
        font-size: 0.82rem;
        transition: background 0.12s;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .gq-hist-row:hover  { background: #2e4470; }
    .gq-hist-row.active { background: #3d5a8a; }
    .gq-hist-row-label  { flex:1; overflow:hidden; text-overflow:ellipsis; }
    .gq-hist-row-pending { opacity: 0.55; font-style: italic; font-size: 0.72rem; }

    /* ── History expanded detail ────────────────────────────────── */
    .gq-hist-detail {
        background: #1e2d48;
        border-radius: 6px;
        padding: 0.5rem 0.6rem;
        margin: 0.15rem 0 0.4rem;
        font-size: 0.78rem;
    }
    .gq-hist-meta { font-size: 0.75rem; opacity: 0.65; margin-bottom: 4px; }
    .gq-hist-pills { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
    .gq-pill {
        font-size: 0.68rem; padding: 1px 6px;
        border-radius: 20px; font-weight: 600;
    }
    .gq-pill-ready   { background: #1a7a3c; color: #fff; }
    .gq-pill-check   { background: #9a6800; color: #fff; }
    .gq-pill-missing { background: #b91c1c; color: #fff; }
    .gq-pill-regret  { background: #888888; color: #fff; }

    /* ── Status indicator (legacy, kept for compat) ─────────────── */
    .gq-ai-status {
        display: flex; align-items: center; gap: 0.5rem;
        padding: 0.55rem 0.8rem; border-radius: 8px;
        font-size: 0.82rem; font-weight: 500; margin-bottom: 0.5rem;
    }
    .gq-ai-on  { background: #1a4a2e; }
    .gq-ai-off { background: #2e3a52; }

    /* ── Process button ─────────────────────────────────────────── */
    [data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #2e4470, #1a2740) !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        letter-spacing: 0 !important;
        padding: 0.6rem 2rem !important;
        box-shadow: 0 3px 10px rgba(46,68,112,0.35) !important;
        transition: transform 0.1s, box-shadow 0.1s !important;
    }
    [data-testid="stButton"] > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 5px 14px rgba(46,68,112,0.45) !important;
    }

    /* ── Download button ────────────────────────────────────────── */
    [data-testid="stDownloadButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #1a7a3c, #155c2e) !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 3px 10px rgba(26,122,60,0.35) !important;
    }

    /* ── Data editor container ──────────────────────────────────── */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    /* ── Warning / info callouts ────────────────────────────────── */
    [data-testid="stAlert"] { border-radius: 8px !important; }

    /* ── Expander ────────────────────────────────────────────────── */
    details { border-radius: 8px !important; }

    /* ── Filter radio ───────────────────────────────────────────── */
    [data-testid="stRadio"] > div { gap: 0.5rem !important; }

    /* ── Progress bar ───────────────────────────────────────────── */
    [data-testid="stProgressBar"] > div > div { background: #2e4470 !important; border-radius: 8px !important; }

    /* ── Tabs — force navigation bar to scroll if labels overflow ── */
    [data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        scrollbar-width: none !important;
    }
    [data-baseweb="tab-list"]::-webkit-scrollbar { display: none !important; }
    [data-baseweb="tab"] { flex-shrink: 0 !important; white-space: nowrap !important; }

    /* ── Floating chat widget ───────────────────────────────────── */
    #gq-fab {
        position: fixed !important;
        bottom: 28px !important;
        right: 28px !important;
        width: 58px !important;
        height: 58px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, #2e4470, #1a2740) !important;
        color: #fff !important;
        font-size: 1.5rem !important;
        border: none !important;
        cursor: pointer !important;
        box-shadow: 0 4px 20px rgba(46,68,112,0.55) !important;
        z-index: 10001 !important;
        transition: transform 0.18s, box-shadow 0.18s !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    #gq-fab:hover {
        transform: scale(1.1) !important;
        box-shadow: 0 6px 26px rgba(46,68,112,0.7) !important;
    }

    /* Full panel — input placeholder is built into the bottom of the panel */
    #gq-chat-panel {
        position: fixed !important;
        bottom: 88px !important;
        right: 28px !important;
        width: 460px !important;
        height: 520px !important;
        background: #fff !important;
        border-radius: 16px !important;
        border: 1px solid #dde3f0 !important;
        z-index: 10000 !important;
        display: none !important;
        flex-direction: column !important;
        overflow: hidden !important;
        box-shadow: 0 8px 40px rgba(0,0,0,0.18) !important;
    }
    #gq-chat-panel.gqcp-open { display: flex !important; }

    #gq-chat-hdr {
        background: linear-gradient(135deg, #2e4470, #1a2740);
        color: #fff;
        padding: 0.85rem 1.1rem;
        font-weight: 600;
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        flex-shrink: 0;
    }
    #gq-chat-hdr .gq-online-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #4ade80;
        box-shadow: 0 0 5px #4ade80;
        flex-shrink: 0;
    }
    .gq-chat-hdr-close {
        margin-left: auto;
        background: rgba(255,255,255,0.15) !important;
        border: none !important;
        color: #fff !important;
        cursor: pointer !important;
        width: 28px !important;
        height: 28px !important;
        border-radius: 50% !important;
        font-size: 1rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        line-height: 1 !important;
        transition: background 0.15s !important;
    }
    .gq-chat-hdr-close:hover { background: rgba(255,255,255,0.28) !important; }

    #gq-chat-body {
        flex: 1;
        overflow-y: scroll;
        overscroll-behavior: contain;
        padding: 1rem 1rem 0.5rem;
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
        background: #f4f7fd;
        scroll-behavior: smooth;
        min-height: 0;
    }
    #gq-chat-body::-webkit-scrollbar { width: 5px; }
    #gq-chat-body::-webkit-scrollbar-track { background: transparent; }
    #gq-chat-body::-webkit-scrollbar-thumb { background: #c8d3e8; border-radius: 4px; }

    #gq-chat-nokey {
        padding: 0.55rem 1rem;
        background: #fffbe6;
        border-top: 1px solid #fde68a;
        font-size: 0.83rem;
        color: #92620a;
        flex-shrink: 0;
    }

    /* Typing / loading indicator */
    @keyframes gq-bounce {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
        40%            { transform: translateY(-5px); opacity: 1; }
    }
    .gq-typing { display: flex; gap: 5px; align-items: center; padding: 10px 14px; }
    .gq-typing span {
        width: 8px; height: 8px; border-radius: 50%;
        background: #8fa3c8;
        animation: gq-bounce 1.1s infinite;
    }
    .gq-typing span:nth-child(2) { animation-delay: 0.18s; }
    .gq-typing span:nth-child(3) { animation-delay: 0.36s; }

    /* Input footer — visual placeholder at the bottom of the panel */
    #gq-chat-footer {
        flex-shrink: 0;
        height: 64px;
        background: #fff;
        border-top: 1px solid #e4eaf5;
    }

    /* stBottom — transparent floating layer over the panel footer */
    [data-testid="stBottom"] {
        position: fixed !important;
        bottom: 88px !important;
        right: 28px !important;
        width: 460px !important;
        height: 64px !important;
        left: auto !important;
        padding: 0 !important;
        margin: 0 !important;
        z-index: 10002 !important;
        display: none !important;
        overflow: visible !important;
    }
    /* Kill every white/shadowed box inside stBottom */
    [data-testid="stBottom"],
    [data-testid="stBottom"]::before,
    [data-testid="stBottom"]::after,
    [data-testid="stBottom"] * {
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
    }
    body:has(#gq-chat-panel.gqcp-open) [data-testid="stBottom"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    /* Flatten every wrapper layer so they don't break vertical centering */
    body:has(#gq-chat-panel.gqcp-open) [data-testid="stBottom"] > *,
    body:has(#gq-chat-panel.gqcp-open) [data-testid="stBottom"] > * > * {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        height: auto !important;
        padding: 0 !important;
        margin: 0 !important;
        flex: 1 !important;
    }
    /* The actual input element — 90% width */
    body:has(#gq-chat-panel.gqcp-open) [data-testid="stChatInput"],
    body:has(#gq-chat-panel.gqcp-open) .stChatInput {
        width: 90% !important;
        flex: none !important;
    }
    body:has(#gq-chat-panel.gqcp-open) [data-testid="stChatInputContainer"] {
        background: #f0f4fa !important;
        border-radius: 24px !important;
        border: 1.5px solid #cdd6ea !important;
        padding: 2px 8px !important;
        width: 100% !important;
        flex: 1 !important;
    }
    body:has(#gq-chat-panel.gqcp-open) [data-testid="stChatInput"] textarea {
        color: #111 !important;
        background: transparent !important;
        caret-color: #2e4470 !important;
        font-size: 0.93rem !important;
        line-height: 1.5 !important;
        padding: 8px 4px !important;
    }

    </style>
    """, unsafe_allow_html=True)

