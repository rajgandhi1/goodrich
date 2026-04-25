"""
Document Q&A Assistant — Goodrich Gasket
Upload PDF, Word, Excel, or CSV files and ask questions about them.
"""
import io
import os
import textwrap

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Doc Assistant — GGPL",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ── Globals ── */
[data-testid="stAppViewContainer"] { background: #f0f4f9; }
[data-testid="stSidebar"]          { background: #1a2740 !important; }
[data-testid="stSidebar"] *        { color: #e8ecf1 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: #2e4470 !important;
    color: #e8ecf1 !important;
    border: 1px solid #3d5a8a !important;
    border-radius: 6px !important;
    width: 100%;
}
[data-testid="stSidebar"] .stButton > button:hover { background: #3d5a8a !important; }

/* ── Hero banner ── */
.da-hero {
    background: linear-gradient(135deg, #1a2740 0%, #2e4470 60%, #3d5a8a 100%);
    border-radius: 16px;
    padding: 1.6rem 2rem 1.4rem;
    margin-bottom: 1.6rem;
    display: flex;
    align-items: center;
    gap: 1.4rem;
    box-shadow: 0 6px 24px rgba(26,39,64,0.22);
    position: relative;
    overflow: hidden;
}
.da-hero::after {
    content: "📄";
    position: absolute;
    right: 2rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 5rem;
    opacity: 0.07;
    pointer-events: none;
}
.da-hero-icon  { font-size: 2.8rem; line-height: 1; flex-shrink: 0; }
.da-hero-title { font-size: 1.65rem; font-weight: 800; color: #fff; margin: 0; letter-spacing: -0.5px; }
.da-hero-sub   { font-size: 0.84rem; color: rgba(255,255,255,0.68); margin: 4px 0 0; }
.da-hero-badge {
    margin-left: auto;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    color: #fff !important;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 20px;
    flex-shrink: 0;
    letter-spacing: 0.3px;
}

/* ── Empty state ── */
.da-empty {
    text-align: center;
    padding: 5rem 2rem;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.da-empty-icon { font-size: 4rem; margin-bottom: 1rem; }
.da-empty-title { font-size: 1.15rem; font-weight: 700; color: #1a2740; margin: 0 0 0.5rem; }
.da-empty-sub   { font-size: 0.88rem; color: #6b7ea8; margin: 0; line-height: 1.6; }

/* ── Doc pill in sidebar ── */
.da-doc-pill {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 0.45rem 0.7rem;
    margin-bottom: 0.35rem;
    font-size: 0.8rem;
}
.da-doc-ext {
    background: #2e4470;
    color: #fff !important;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    letter-spacing: 0.3px;
    flex-shrink: 0;
}
.da-doc-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.da-doc-meta { font-size: 0.68rem; opacity: 0.5; }

/* ── Suggestion pills ── */
.da-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.6rem 0 1rem;
}

/* ── Chat messages — override Streamlit avatar colour ── */
[data-testid="stChatMessage"] {
    background: #fff !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 5px rgba(0,0,0,0.07) !important;
    margin-bottom: 0.6rem !important;
    padding: 0.85rem 1.1rem !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #eef2fa !important;
}

/* ── Chat input bar ── */
[data-testid="stChatInput"] textarea {
    border-radius: 12px !important;
    border: 1.5px solid #c8d3e8 !important;
    font-size: 0.92rem !important;
    background: #fff !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #2e4470 !important;
    box-shadow: 0 0 0 3px rgba(46,68,112,0.12) !important;
}

/* ── Sidebar section header ── */
.sb-section {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.5;
    margin: 0.9rem 0 0.4rem;
}

/* ── Status dot ── */
.da-status-row {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    font-size: 0.82rem; font-weight: 500;
    margin-bottom: 0.3rem;
}
.da-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.da-on  { background: #1a4a2e; }
.da-off { background: #2e3a52; }
.da-dot-on  { background: #4caf50; box-shadow: 0 0 6px #4caf50; }
.da-dot-off { background: #7a8eaa; }

/* ── Progress / truncation warning ── */
[data-testid="stAlert"] { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_CONTEXT_CHARS = 120_000

SUGGESTIONS = [
    "Summarise this document",
    "What are the key specifications?",
    "List all dimensions or sizes mentioned",
    "What materials are specified?",
    "Are there any pressure or temperature ratings?",
    "What standards or codes are referenced?",
    "List all line items or part numbers",
    "What are the quantity and unit details?",
]

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a precise technical document assistant for Goodrich Gasket Pvt. Ltd (GGPL).
    The user has uploaded one or more technical documents.

    Rules:
    - Answer based ONLY on information present in the documents.
    - If something is not in the documents, say so — never hallucinate.
    - For tables or spec sheets, present data in a clean, structured way.
    - Use markdown formatting (bold headings, bullet lists, tables) to make answers readable.
    - Keep answers focused and professional.
""")

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_pdf(raw: bytes) -> str:
    import pdfplumber
    pages = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return "\n\n".join(pages)


def _extract_docx(raw: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_excel(raw: bytes, fname: str) -> str:
    ext = fname.rsplit(".", 1)[-1].lower()
    engine = "openpyxl" if ext in ("xlsx", "xlsm") else "xlrd"
    xl = pd.ExcelFile(io.BytesIO(raw), engine=engine)
    parts = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        parts.append(f"=== Sheet: {sheet} ===\n{df.to_string(index=False)}")
    return "\n\n".join(parts)


def _extract_csv(raw: bytes) -> str:
    return pd.read_csv(io.BytesIO(raw)).to_string(index=False)


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    raw  = uploaded_file.read()
    if   name.endswith(".pdf"):                     return _extract_pdf(raw)
    elif name.endswith(".docx"):                    return _extract_docx(raw)
    elif name.endswith(".doc"):                     return "[.doc not supported — convert to .docx]"
    elif name.endswith((".xlsx", ".xls", ".xlsm")): return _extract_excel(raw, uploaded_file.name)
    elif name.endswith(".csv"):                     return _extract_csv(raw)
    else:
        try:    return raw.decode("utf-8", errors="replace")
        except: return "[Unable to read file]"


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def _openai_client():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)


def ask_llm(doc_context: str, history: list[dict], question: str) -> str:
    client = _openai_client()
    if not client:
        return (
            "**No API key found.**  \n"
            "Enter your OpenAI API key in the sidebar to enable Q&A."
        )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({
        "role": "user",
        "content": (
            f"Document content:\n\n<document>\n"
            f"{doc_context[:MAX_CONTEXT_CHARS]}\n</document>\n\n"
            "Confirm you have read the document."
        ),
    })
    messages.append({
        "role": "assistant",
        "content": "Understood — I have read the document and am ready to answer.",
    })
    for m in history:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question})

    try:
        resp = _openai_client().chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"**Error:** {e}"


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "da_docs"    not in st.session_state: st.session_state.da_docs    = {}
if "da_chat"    not in st.session_state: st.session_state.da_chat    = []
if "da_pending" not in st.session_state: st.session_state.da_pending = None  # question waiting to fire

# ---------------------------------------------------------------------------
# ── SIDEBAR ─────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------
with st.sidebar:
    # ── API status ───────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">AI Status</div>', unsafe_allow_html=True)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        st.markdown(
            '<div class="da-status-row da-on">'
            '<div class="da-dot da-dot-on"></div>GPT-4o ready'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="da-status-row da-off">'
            '<div class="da-dot da-dot-off"></div>No API key'
            '</div>',
            unsafe_allow_html=True,
        )
        key_in = st.text_input(
            "API Key", type="password", placeholder="sk-…",
            label_visibility="collapsed",
            help="Paste your OpenAI key",
        )
        if key_in:
            os.environ["OPENAI_API_KEY"] = key_in
            st.rerun()

    st.markdown('<hr style="margin:0.75rem 0;border-color:#2e4470">', unsafe_allow_html=True)

    # ── Upload ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section">Upload Documents</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "drop files here",
        type=["pdf", "docx", "xlsx", "xls", "xlsm", "csv", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded:
        new_files = [f for f in uploaded if f.name not in st.session_state.da_docs]
        if new_files:
            with st.spinner(f"Reading {len(new_files)} file(s)…"):
                for f in new_files:
                    st.session_state.da_docs[f.name] = extract_text(f)
            st.session_state.da_chat = []
            st.rerun()

    # ── Loaded docs ──────────────────────────────────────────────────────────
    if st.session_state.da_docs:
        st.markdown('<hr style="margin:0.75rem 0;border-color:#2e4470">', unsafe_allow_html=True)
        st.markdown('<div class="sb-section">Loaded Documents</div>', unsafe_allow_html=True)
        for fname, text in list(st.session_state.da_docs.items()):
            ext   = fname.rsplit(".", 1)[-1].upper()
            words = len(text.split())
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f'<div class="da-doc-pill">'
                    f'<span class="da-doc-ext">{ext}</span>'
                    f'<span class="da-doc-name" title="{fname}">{fname}</span>'
                    f'</div>'
                    f'<div class="da-doc-meta" style="margin:-0.2rem 0 0.4rem 0.5rem">'
                    f'~{words:,} words</div>',
                    unsafe_allow_html=True,
                )
                if len(text) > MAX_CONTEXT_CHARS:
                    st.warning("Large file — will be truncated.", icon="⚠️")
            with col2:
                if st.button("✕", key=f"rm_{fname}", help=f"Remove {fname}"):
                    del st.session_state.da_docs[fname]
                    st.session_state.da_chat = []
                    st.rerun()

        st.markdown('<hr style="margin:0.75rem 0;border-color:#2e4470">', unsafe_allow_html=True)

        # ── Suggestions ──────────────────────────────────────────────────────
        st.markdown('<div class="sb-section">Quick Questions</div>', unsafe_allow_html=True)
        for i, s in enumerate(SUGGESTIONS):
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.da_pending = s
                st.rerun()

        st.markdown('<hr style="margin:0.75rem 0;border-color:#2e4470">', unsafe_allow_html=True)
        if st.button("🗑  Clear All & Reset", use_container_width=True):
            st.session_state.da_docs  = {}
            st.session_state.da_chat  = []
            st.session_state.da_pending = None
            st.rerun()

# ---------------------------------------------------------------------------
# ── MAIN AREA ────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

# Hero banner
st.markdown("""
<div class="da-hero">
  <div class="da-hero-icon">🤖</div>
  <div>
    <p class="da-hero-title">Document Q&amp;A Assistant</p>
    <p class="da-hero-sub">Upload any technical document and ask questions in plain English</p>
  </div>
  <span class="da-hero-badge">GPT-4o</span>
</div>
""", unsafe_allow_html=True)

# ── No docs loaded — empty state ────────────────────────────────────────────
if not st.session_state.da_docs:
    st.markdown("""
    <div class="da-empty">
      <div class="da-empty-icon">📂</div>
      <p class="da-empty-title">No documents loaded</p>
      <p class="da-empty-sub">
        Upload a <strong>PDF</strong>, <strong>Word</strong>, <strong>Excel</strong>, or <strong>CSV</strong>
        file using the sidebar on the left.<br>
        Then ask questions — the AI will answer based strictly on your document.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Chat history ─────────────────────────────────────────────────────────────
if not st.session_state.da_chat:
    doc_names = ", ".join(st.session_state.da_docs.keys())
    st.info(
        f"**{len(st.session_state.da_docs)} document(s) loaded:** {doc_names}  \n"
        "Ask anything below, or pick a quick question from the sidebar.",
        icon="📄",
    )

for msg in st.session_state.da_chat:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

# ── Handle a pending suggestion click ────────────────────────────────────────
if st.session_state.da_pending:
    question = st.session_state.da_pending
    st.session_state.da_pending = None

    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)

    combined = "\n\n---\n\n".join(
        f"[File: {fn}]\n{txt}" for fn, txt in st.session_state.da_docs.items()
    )
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking…"):
            reply = ask_llm(combined, st.session_state.da_chat, question)
        st.markdown(reply)

    st.session_state.da_chat.append({"role": "user",      "content": question})
    st.session_state.da_chat.append({"role": "assistant", "content": reply})

    # Clear chat button
    col1, _ = st.columns([1, 5])
    with col1:
        if st.button("Clear conversation", type="secondary"):
            st.session_state.da_chat = []
            st.rerun()

    st.stop()

# ── Chat input (pinned to bottom) ─────────────────────────────────────────────
user_q = st.chat_input(
    "Ask anything about your document… (e.g. What is the bolt circle for 6\" 150#?)"
)

if user_q and user_q.strip():
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_q)

    combined = "\n\n---\n\n".join(
        f"[File: {fn}]\n{txt}" for fn, txt in st.session_state.da_docs.items()
    )
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking…"):
            reply = ask_llm(combined, st.session_state.da_chat, user_q.strip())
        st.markdown(reply)

    st.session_state.da_chat.append({"role": "user",      "content": user_q.strip()})
    st.session_state.da_chat.append({"role": "assistant", "content": reply})
    st.rerun()

# Clear button (shown only once conversation has started)
if st.session_state.da_chat:
    col1, _ = st.columns([1, 5])
    with col1:
        if st.button("Clear conversation", type="secondary", key="clr_bottom"):
            st.session_state.da_chat = []
            st.rerun()
