import os as _os

import streamlit as st


def render_chat_widget():
    # ---------------------------------------------------------------------------
    # Floating chat widget — bottom-right popup
    # ---------------------------------------------------------------------------
    def _build_chat_html():
        msgs = st.session_state.chat_messages[-20:]
        loading = st.session_state.get('chat_loading', False)
        if not msgs and not loading:
            return (
                '<div style="color:#9aabca;font-size:0.88rem;text-align:center;'
                'padding:3rem 1.5rem;line-height:1.6">'
                '<div style="font-size:1.8rem;margin-bottom:0.6rem">⚙️</div>'
                'Ask me anything about gaskets — materials, ratings, standards, dimensions.'
                '</div>'
            )
        out = []
        for m in msgs:
            txt = (m['content']
                   .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                   .replace('\n', '<br>'))
            if m['role'] == 'user':
                out.append(
                    '<div style="background:#2e4470;color:#fff;'
                    'border-radius:16px 16px 4px 16px;'
                    'padding:0.65rem 0.95rem;font-size:0.91rem;line-height:1.5;'
                    'max-width:82%;margin-left:auto;word-break:break-word;'
                    f'box-shadow:0 2px 8px rgba(46,68,112,0.25)">{txt}</div>'
                )
            else:
                if m.get('error'):
                    style = ('background:#fdecea;color:#b91c1c;'
                             'border:1px solid #fca5a5;')
                else:
                    style = ('background:#fff;color:#1a2740;'
                             'border:1px solid #e4eaf5;')
                out.append(
                    f'<div style="{style}border-radius:16px 16px 16px 4px;'
                    f'padding:0.65rem 0.95rem;font-size:0.91rem;line-height:1.5;'
                    f'max-width:88%;word-break:break-word;'
                    f'box-shadow:0 1px 4px rgba(0,0,0,0.06)">{txt}</div>'
                )
        if loading:
            out.append(
                '<div style="background:#fff;border:1px solid #e4eaf5;'
                'border-radius:16px 16px 16px 4px;max-width:88%;'
                'box-shadow:0 1px 4px rgba(0,0,0,0.06)">'
                '<div class="gq-typing">'
                '<span></span><span></span><span></span>'
                '</div></div>'
            )
        return ''.join(out)


    _api_ok = bool(_os.environ.get('OPENAI_API_KEY'))

    st.markdown(f"""
    <button id="gq-fab" title="Gasket Assistant">&#128172;</button>

    <div id="gq-chat-panel">
      <div id="gq-chat-hdr">
        <span class="gq-online-dot"></span>
        <span>Gasket Assistant</span>
        <button id="gq-chat-close" class="gq-chat-hdr-close">&#10005;</button>
      </div>
      <div id="gq-chat-body">{_build_chat_html()}</div>
      <div id="gq-chat-footer">
        {'<div id="gq-chat-nokey">&#128274; Enter your OpenAI API key in the sidebar.</div>' if not _api_ok else ''}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Attach click handlers for both panels
    st.html("""
    <script>
    (function attach() {
      // -- Chat panel --
      var fab = document.getElementById('gq-fab');
      var panel = document.getElementById('gq-chat-panel');
      var closeBtn = document.getElementById('gq-chat-close');
      var body = document.getElementById('gq-chat-body');

      if (!fab || !panel) { setTimeout(attach, 100); return; }

      // -- Restore open state --
      if (sessionStorage.getItem('gq_chat_open') === '1') {
        panel.classList.add('gqcp-open');
        fab.innerHTML = '&#10005;';
        if (body) body.scrollTop = body.scrollHeight;
      }
      // -- Chat FAB toggle --
      fab.onclick = function() {
        var open = panel.classList.toggle('gqcp-open');
        fab.innerHTML = open ? '&#10005;' : '&#128172;';
        sessionStorage.setItem('gq_chat_open', open ? '1' : '0');
        if (open && body) body.scrollTop = body.scrollHeight;
      };
      if (closeBtn) {
        closeBtn.onclick = function() {
          panel.classList.remove('gqcp-open');
          fab.innerHTML = '&#128172;';
          sessionStorage.setItem('gq_chat_open', '0');
        };
      }
      if (body) body.scrollTop = body.scrollHeight;
    })();
    </script>
    """, unsafe_allow_javascript=True)

    if _api_ok:
        _q = st.chat_input('Ask about gaskets…', key='float_chat')
        if _q:
            st.session_state.chat_messages.append({'role': 'user', 'content': _q})
            st.session_state.chat_loading = True
            st.rerun()

    if st.session_state.get('chat_loading'):
        try:
            from openai import OpenAI as _OAI
            _cl = _OAI(api_key=_os.environ['OPENAI_API_KEY'])
            _sys = (
                'You are a concise technical expert on industrial gaskets for Goodrich Gasket Pvt. Ltd. '
                'Specialise in: soft cut (CNAF, PTFE, Neoprene, Graphite, Klingersil), spiral wound, RTJ, '
                'Kammprofile, DJI, ISK. Topics: material selection, pressure ratings (ASME 150#-2500#, PN6-PN400), '
                'standards (ASME B16.21/B16.20/B16.47, EN 1514-1), dimensions, application suitability. '
                'Keep replies short and technical. Politely decline non-gasket topics.'
            )
            _hx = [{'role': 'system', 'content': _sys}]
            _hx += [{'role': m['role'], 'content': m['content']} for m in st.session_state.chat_messages]
            _r = _cl.chat.completions.create(
                model='gpt-4.1-mini', messages=_hx, temperature=0.2, max_tokens=350,
            )
            st.session_state.chat_messages.append(
                {'role': 'assistant', 'content': _r.choices[0].message.content.strip()}
            )
        except Exception as _e:
            st.session_state.chat_messages.append(
                {'role': 'assistant', 'content': f'Error: {_e}', 'error': True}
            )
        finally:
            st.session_state.chat_loading = False
        st.rerun()
