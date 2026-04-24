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
# Shared CSS (mirrors app.py palette)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f4f6f9; }
[data-testid="stSidebar"] { background: #1a2740 !important; }
[data-testid="stSidebar"] * { color: #e8ecf1 !important; }

.da-header {
    background: linear-gradient(135deg, #1a2740 0%, #2e4470 100%);
    color: #fff;
    padding: 1.2rem 2rem 1rem;
    border-radius: 12px;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    gap: 1.1rem;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.da-header-icon  { font-size: 2.4rem; line-height: 1; }
.da-header-title { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.4px; margin: 0; }
.da-header-sub   { font-size: 0.82rem; opacity: 0.72; margin: 3px 0 0; }

.da-card {
    background: #fff;
    border-radius: 10px;
    padding: 1.3rem 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    margin-bottom: 1.1rem;
    border-left: 4px solid #2e4470;
}
.da-card-title { font-size: 0.95rem; font-weight: 600; color: #1a2740; margin: 0 0 0.8rem; }

/* Chat bubbles */
.da-msg-user {
    background: #2e4470;
    color: #fff;
    padding: 0.65rem 1rem;
    border-radius: 14px 14px 4px 14px;
    max-width: 75%;
    margin-left: auto;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.da-msg-ai {
    background: #fff;
    color: #1a2740;
    padding: 0.65rem 1rem;
    border-radius: 14px 14px 14px 4px;
    max-width: 82%;
    margin-right: auto;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    border: 1px solid #dde3f0;
    white-space: pre-wrap;
    word-wrap: break-word;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.da-msg-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    opacity: 0.55;
    margin-bottom: 2px;
}
.da-chat-wrap {
    max-height: 440px;
    overflow-y: auto;
    padding: 0.8rem 0.2rem;
}
.da-chip {
    display: inline-block;
    background: #eef2fa;
    color: #2e4470;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    margin-right: 4px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers — text extraction
# ---------------------------------------------------------------------------
MAX_CONTEXT_CHARS = 120_000  # ~30k tokens, safe for gpt-4o 128k context


def _extract_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    texts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
    return "\n\n".join(texts)


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_excel(file_bytes: bytes, fname: str) -> str:
    ext = fname.rsplit(".", 1)[-1].lower()
    engine = "openpyxl" if ext in ("xlsx", "xlsm") else "xlrd"
    xl = pd.ExcelFile(io.BytesIO(file_bytes), engine=engine)
    parts = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        parts.append(f"=== Sheet: {sheet} ===\n{df.to_string(index=False)}")
    return "\n\n".join(parts)


def _extract_csv(file_bytes: bytes) -> str:
    df = pd.read_csv(io.BytesIO(file_bytes))
    return df.to_string(index=False)


def extract_text(uploaded_file) -> str:
    """Dispatch extraction by file type; return plain text."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        return _extract_pdf(raw)
    elif name.endswith(".docx"):
        return _extract_docx(raw)
    elif name.endswith(".doc"):
        return "[.doc format not supported — please convert to .docx]"
    elif name.endswith((".xlsx", ".xls", ".xlsm")):
        return _extract_excel(raw, uploaded_file.name)
    elif name.endswith(".csv"):
        return _extract_csv(raw)
    else:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return "[Unable to read file content]"


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = textwrap.dedent("""\
    You are a helpful technical document assistant for Goodrich Gasket Pvt. Ltd (GGPL).
    The user has uploaded one or more technical documents and will ask questions about them.

    Instructions:
    - Answer accurately and concisely based strictly on the provided document content.
    - If the answer is not in the documents, say so clearly — do NOT hallucinate.
    - For tables or specifications, present data in a clean, readable way.
    - Keep responses focused and professional.
""")


def _get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def ask_llm(doc_context: str, history: list[dict], user_question: str) -> str:
    client = _get_openai_client()
    if not client:
        return "No OpenAI API key set. Please enter it in the sidebar."

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Attach document context as the first user turn
    messages.append({
        "role": "user",
        "content": (
            f"Here is the content of the uploaded document(s):\n\n"
            f"<document>\n{doc_context[:MAX_CONTEXT_CHARS]}\n</document>\n\n"
            f"Please confirm you have read the document."
        ),
    })
    messages.append({"role": "assistant", "content": "Understood. I have read the document and am ready to answer your questions."})

    # Append chat history (skip the first "document loaded" placeholder)
    for msg in history:
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Current question
    messages.append({"role": "user", "content": user_question})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error calling OpenAI: {e}"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "da_docs" not in st.session_state:
    st.session_state.da_docs = {}          # fname -> extracted text
if "da_chat" not in st.session_state:
    st.session_state.da_chat = []          # {role, content}
if "da_input" not in st.session_state:
    st.session_state.da_input = ""

# ---------------------------------------------------------------------------
# Sidebar — API key + doc list
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<p style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;opacity:0.55;margin:0.5rem 0 0.3rem">AI Status</p>',
        unsafe_allow_html=True,
    )
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0.8rem;'
            'background:#1a4a2e;border-radius:8px;font-size:0.82rem;font-weight:500">'
            '<div style="width:8px;height:8px;border-radius:50%;background:#4caf50;'
            'box-shadow:0 0 6px #4caf50"></div>GPT-4o active</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0.8rem;'
            'background:#2e3a52;border-radius:8px;font-size:0.82rem;font-weight:500">'
            '<div style="width:8px;height:8px;border-radius:50%;background:#7a8eaa"></div>'
            'No API key</div>',
            unsafe_allow_html=True,
        )
        key_in = st.text_input(
            "OpenAI API Key", type="password", placeholder="sk-...",
            label_visibility="collapsed",
            help="Paste your key to enable Q&A",
        )
        if key_in:
            os.environ["OPENAI_API_KEY"] = key_in
            st.rerun()

    st.markdown('<hr style="margin:0.9rem 0;border-color:#2e4470">', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;opacity:0.55;margin:0 0 0.3rem">Loaded Documents</p>',
        unsafe_allow_html=True,
    )
    if st.session_state.da_docs:
        for fname in list(st.session_state.da_docs.keys()):
            col_a, col_b = st.columns([5, 1])
            col_a.markdown(f'<span style="font-size:0.83rem">📄 {fname}</span>', unsafe_allow_html=True)
            if col_b.button("✕", key=f"rm_{fname}", help=f"Remove {fname}"):
                del st.session_state.da_docs[fname]
                st.session_state.da_chat = []
                st.rerun()
    else:
        st.markdown('<p style="font-size:0.8rem;opacity:0.45;margin:0.3rem 0">No documents loaded.</p>', unsafe_allow_html=True)

    if st.session_state.da_docs:
        st.markdown('<hr style="margin:0.7rem 0;border-color:#2e4470">', unsafe_allow_html=True)
        if st.button("Clear All & Reset", type="secondary", use_container_width=True):
            st.session_state.da_docs = {}
            st.session_state.da_chat = []
            st.rerun()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="da-header">
  <div class="da-header-icon">📄</div>
  <div>
    <p class="da-header-title">Document Q&amp;A Assistant</p>
    <p class="da-header-sub">Upload technical documents and ask anything — powered by GPT-4o</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Layout: left col = upload + doc info | right col = chat
# ---------------------------------------------------------------------------
left, right = st.columns([2, 3], gap="large")

# ── LEFT — Upload ────────────────────────────────────────────────────────────
with left:
    st.markdown('<div class="da-card"><p class="da-card-title">Upload Documents</p>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Drag & drop or browse",
        type=["pdf", "docx", "xlsx", "xls", "xlsm", "csv", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if uploaded:
        new_files = [f for f in uploaded if f.name not in st.session_state.da_docs]
        if new_files:
            with st.spinner(f"Reading {len(new_files)} file(s)…"):
                for f in new_files:
                    text = extract_text(f)
                    st.session_state.da_docs[f.name] = text
            # Reset chat when new docs loaded
            st.session_state.da_chat = []
            st.rerun()

    if st.session_state.da_docs:
        st.markdown('<div class="da-card"><p class="da-card-title">Document Summary</p>', unsafe_allow_html=True)
        for fname, text in st.session_state.da_docs.items():
            word_count = len(text.split())
            char_count = len(text)
            ext = fname.rsplit(".", 1)[-1].upper()
            st.markdown(
                f'<span class="da-chip">{ext}</span>'
                f'<span style="font-size:0.85rem;font-weight:600">{fname}</span><br>'
                f'<span style="font-size:0.75rem;color:#777">~{word_count:,} words &nbsp;·&nbsp; {char_count:,} chars</span>',
                unsafe_allow_html=True,
            )
            if char_count > MAX_CONTEXT_CHARS:
                st.warning(f"Document truncated to {MAX_CONTEXT_CHARS:,} chars for context window.")
            st.markdown('<hr style="margin:0.6rem 0;border-color:#eee">', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Quick-start suggestion chips
        st.markdown('<div class="da-card"><p class="da-card-title">Suggested Questions</p>', unsafe_allow_html=True)
        suggestions = [
            "Summarise this document",
            "What are the key specifications?",
            "List all dimensions or sizes mentioned",
            "What materials are specified?",
            "Are there any pressure ratings?",
            "What standards or codes are referenced?",
        ]
        for i, s in enumerate(suggestions):
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.da_input = s
                # Trigger answer immediately
                combined = "\n\n---\n\n".join(
                    f"[File: {fn}]\n{txt}" for fn, txt in st.session_state.da_docs.items()
                )
                reply = ask_llm(combined, st.session_state.da_chat, s)
                st.session_state.da_chat.append({"role": "user", "content": s})
                st.session_state.da_chat.append({"role": "assistant", "content": reply})
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.markdown("""
        <div class="da-card" style="text-align:center;padding:2rem 1rem;border-left-color:#aab8d0">
          <div style="font-size:2.8rem;margin-bottom:0.6rem">📂</div>
          <p style="color:#5a7aab;font-size:0.88rem;margin:0">
            Upload a PDF, Word, Excel, or CSV file above to get started.
          </p>
        </div>
        """, unsafe_allow_html=True)

# ── RIGHT — Chat ─────────────────────────────────────────────────────────────
with right:
    if not st.session_state.da_docs:
        st.markdown("""
        <div class="da-card" style="text-align:center;padding:3rem 1rem;border-left-color:#aab8d0">
          <div style="font-size:2.4rem;margin-bottom:0.6rem">💬</div>
          <p style="color:#5a7aab;font-size:0.9rem;margin:0">
            Load a document on the left to start the conversation.
          </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="da-card"><p class="da-card-title">Conversation</p>', unsafe_allow_html=True)

        # Chat history display
        if st.session_state.da_chat:
            chat_html = '<div class="da-chat-wrap" id="da-chat-scroll">'
            for msg in st.session_state.da_chat:
                if msg["role"] == "user":
                    chat_html += (
                        '<div class="da-msg-label" style="text-align:right;color:#5a7aab">You</div>'
                        f'<div class="da-msg-user">{msg["content"]}</div>'
                    )
                else:
                    chat_html += (
                        '<div class="da-msg-label" style="color:#5a7aab">GPT-4o</div>'
                        f'<div class="da-msg-ai">{msg["content"]}</div>'
                    )
            chat_html += "</div>"
            st.markdown(chat_html, unsafe_allow_html=True)
            # Auto-scroll JS
            st.markdown("""
            <script>
            const el = document.getElementById('da-chat-scroll');
            if (el) el.scrollTop = el.scrollHeight;
            </script>
            """, unsafe_allow_html=True)
        else:
            st.markdown(
                '<p style="color:#9aaac0;font-size:0.85rem;text-align:center;padding:1.5rem 0">'
                'Ask your first question below…</p>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

        # Input row
        inp_col, btn_col = st.columns([8, 1], gap="small")
        with inp_col:
            user_q = st.text_input(
                "Your question",
                value=st.session_state.da_input,
                placeholder="e.g. What is the bolt circle diameter for 6\" 150# flange?",
                label_visibility="collapsed",
                key="da_question_input",
            )
        with btn_col:
            send = st.button("Send", type="primary", use_container_width=True)

        if send and user_q.strip():
            st.session_state.da_input = ""
            combined = "\n\n---\n\n".join(
                f"[File: {fn}]\n{txt}" for fn, txt in st.session_state.da_docs.items()
            )
            with st.spinner("Thinking…"):
                reply = ask_llm(combined, st.session_state.da_chat, user_q.strip())
            st.session_state.da_chat.append({"role": "user", "content": user_q.strip()})
            st.session_state.da_chat.append({"role": "assistant", "content": reply})
            st.rerun()

        # Clear chat
        if st.session_state.da_chat:
            if st.button("Clear conversation", type="secondary"):
                st.session_state.da_chat = []
                st.rerun()
