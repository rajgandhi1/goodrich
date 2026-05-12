import streamlit as st


def render_converter_tab(tab_conv):
    # ---------------------------------------------------------------------------
    # Unit Converter tab
    # ---------------------------------------------------------------------------
    from core.unit_converter import (  # noqa: E402
        DN_NPS_TABLE, DN_OPTIONS, NPS_OPTIONS, CLASS_PN, PN_CLASS,
        inches_to_mm, mm_to_inches,
        psi_to_bar, bar_to_psi, psi_to_mpa, mpa_to_psi, bar_to_mpa, mpa_to_bar,
        kpa_to_psi, psi_to_kpa,
        c_to_f, f_to_c, c_to_k, k_to_c,
        nm_to_ftlb, ftlb_to_nm, nm_to_inlb, inlb_to_nm,
        kn_to_kgf, kgf_to_kn, n_to_lbf, lbf_to_n,
        dn_to_nps, nps_val_to_dn, fmt,
    )

    with tab_conv:
        st.caption('Convert gasket-related units instantly — no API required.')

        _cat = st.selectbox(
            'Category',
            ['Length (in ↔ mm)', 'Pipe Size (DN ↔ NPS)', 'Pressure', 'Rating (ASME Class ↔ PN)',
             'Temperature', 'Torque', 'Force'],
            label_visibility='collapsed',
            key='uc_cat',
        )

        st.markdown('---')

        # ── Length ──────────────────────────────────────────────────────────────
        if _cat == 'Length (in ↔ mm)':
            _lc1, _lc2 = st.columns(2)
            with _lc1:
                st.markdown('##### Inches → mm')
                _in_val = st.number_input('Value (inches)', min_value=0.0, value=1.0, step=0.5, format='%.4f', key='uc_in')
                st.metric('Result', f'{fmt(inches_to_mm(_in_val))} mm')
            with _lc2:
                st.markdown('##### mm → Inches')
                _mm_val = st.number_input('Value (mm)', min_value=0.0, value=25.4, step=1.0, format='%.4f', key='uc_mm')
                st.metric('Result', f'{fmt(mm_to_inches(_mm_val))}"')

        # ── Pipe Size ────────────────────────────────────────────────────────────
        elif _cat == 'Pipe Size (DN ↔ NPS)':
            _pc1, _pc2 = st.columns(2)
            with _pc1:
                st.markdown('##### DN → NPS')
                _dn_sel = st.selectbox('DN (mm)', DN_OPTIONS, key='uc_dn')
                _dn_int = int(_dn_sel)
                _nps_result = dn_to_nps(_dn_int)
                st.metric('NPS', _nps_result or '—')
            with _pc2:
                st.markdown('##### NPS → DN')
                _nps_sel = st.selectbox('NPS', NPS_OPTIONS, key='uc_nps')
                # find the NPS decimal for this string
                _nps_dec = next((val for _, nps_str, val in DN_NPS_TABLE if nps_str == _nps_sel), None)
                _dn_result = nps_val_to_dn(_nps_dec) if _nps_dec else None
                st.metric('DN (mm)', f'DN {_dn_result}' if _dn_result else '—')

            st.markdown('##### Full DN / NPS Reference Table')
            import pandas as _pd
            _tbl = _pd.DataFrame(
                [(dn, nps) for dn, nps, _ in DN_NPS_TABLE],
                columns=['DN (mm)', 'NPS (inch)'],
            )
            st.dataframe(_tbl, use_container_width=False, hide_index=True, height=300)

        # ── Pressure ─────────────────────────────────────────────────────────────
        elif _cat == 'Pressure':
            _pr_units = ['psi', 'bar', 'MPa', 'kPa']
            _pr_c1, _pr_c2, _pr_c3 = st.columns(3)
            _pr_val  = _pr_c1.number_input('Value', min_value=0.0, value=100.0, step=1.0, format='%.4f', key='uc_pr_val')
            _pr_from = _pr_c2.selectbox('From', _pr_units, key='uc_pr_from')
            _pr_to   = _pr_c3.selectbox('To',   _pr_units, key='uc_pr_to')

            _PCONV = {
                ('psi', 'bar'): psi_to_bar,  ('bar', 'psi'): bar_to_psi,
                ('psi', 'MPa'): psi_to_mpa,  ('MPa', 'psi'): mpa_to_psi,
                ('bar', 'MPa'): bar_to_mpa,  ('MPa', 'bar'): mpa_to_bar,
                ('kPa', 'psi'): kpa_to_psi,  ('psi', 'kPa'): psi_to_kpa,
                ('kPa', 'bar'): lambda v: psi_to_bar(kpa_to_psi(v)),
                ('bar', 'kPa'): lambda v: psi_to_kpa(bar_to_psi(v)),
                ('kPa', 'MPa'): lambda v: v / 1000, ('MPa', 'kPa'): lambda v: v * 1000,
            }
            if _pr_from == _pr_to:
                st.metric('Result', f'{fmt(_pr_val)} {_pr_to}')
            else:
                _fn = _PCONV.get((_pr_from, _pr_to))
                if _fn:
                    st.metric('Result', f'{fmt(_fn(_pr_val))} {_pr_to}')
                else:
                    st.info('Conversion not supported directly — use an intermediate unit.')

        # ── Rating ───────────────────────────────────────────────────────────────
        elif _cat == 'Rating (ASME Class ↔ PN)':
            _rc1, _rc2 = st.columns(2)
            with _rc1:
                st.markdown('##### ASME Class → PN')
                _cls_sel = st.selectbox('ASME Class', list(CLASS_PN.keys()), key='uc_cls')
                st.metric('Approx. PN', f'PN {CLASS_PN[_cls_sel]}')
                st.caption('Approximate — exact value depends on material group & temperature.')
            with _rc2:
                st.markdown('##### PN → ASME Class')
                _pn_sel = st.selectbox('PN', list(PN_CLASS.keys()), key='uc_pn')
                st.metric('Approx. ASME Class', f'Class {PN_CLASS[_pn_sel]}')
                st.caption('Approximate — exact value depends on material group & temperature.')

        # ── Temperature ──────────────────────────────────────────────────────────
        elif _cat == 'Temperature':
            _tc1, _tc2, _tc3 = st.columns(3)
            with _tc1:
                st.markdown('##### °C → °F / K')
                _tc_val = st.number_input('°C', value=200.0, step=5.0, format='%.2f', key='uc_tc')
                st.metric('°F', f'{fmt(c_to_f(_tc_val))} °F')
                st.metric('K',  f'{fmt(c_to_k(_tc_val))} K')
            with _tc2:
                st.markdown('##### °F → °C')
                _tf_val = st.number_input('°F', value=392.0, step=5.0, format='%.2f', key='uc_tf')
                st.metric('°C', f'{fmt(f_to_c(_tf_val))} °C')
            with _tc3:
                st.markdown('##### K → °C')
                _tk_val = st.number_input('K', value=473.15, step=5.0, format='%.2f', key='uc_tk')
                st.metric('°C', f'{fmt(k_to_c(_tk_val))} °C')

        # ── Torque ───────────────────────────────────────────────────────────────
        elif _cat == 'Torque':
            _tqc1, _tqc2 = st.columns(2)
            with _tqc1:
                st.markdown('##### N·m → ft·lb / in·lb')
                _tq_nm = st.number_input('N·m', min_value=0.0, value=100.0, step=1.0, format='%.4f', key='uc_nm')
                st.metric('ft·lb', f'{fmt(nm_to_ftlb(_tq_nm))}')
                st.metric('in·lb', f'{fmt(nm_to_inlb(_tq_nm))}')
            with _tqc2:
                st.markdown('##### ft·lb → N·m')
                _tq_ftlb = st.number_input('ft·lb', min_value=0.0, value=73.76, step=1.0, format='%.4f', key='uc_ftlb')
                st.metric('N·m', f'{fmt(ftlb_to_nm(_tq_ftlb))}')
                st.markdown('##### in·lb → N·m')
                _tq_inlb = st.number_input('in·lb', min_value=0.0, value=100.0, step=1.0, format='%.4f', key='uc_inlb')
                st.metric('N·m', f'{fmt(inlb_to_nm(_tq_inlb))}')

        # ── Force ────────────────────────────────────────────────────────────────
        elif _cat == 'Force':
            _fc1, _fc2 = st.columns(2)
            with _fc1:
                st.markdown('##### kN → kgf')
                _f_kn = st.number_input('kN', min_value=0.0, value=10.0, step=0.5, format='%.4f', key='uc_kn')
                st.metric('kgf', f'{fmt(kn_to_kgf(_f_kn))}')
                st.markdown('##### N → lbf')
                _f_n = st.number_input('N', min_value=0.0, value=100.0, step=1.0, format='%.4f', key='uc_n')
                st.metric('lbf', f'{fmt(n_to_lbf(_f_n))}')
            with _fc2:
                st.markdown('##### kgf → kN')
                _f_kgf = st.number_input('kgf', min_value=0.0, value=1000.0, step=10.0, format='%.4f', key='uc_kgf')
                st.metric('kN', f'{fmt(kgf_to_kn(_f_kgf))}')
                st.markdown('##### lbf → N')
                _f_lbf = st.number_input('lbf', min_value=0.0, value=100.0, step=1.0, format='%.4f', key='uc_lbf')
                st.metric('N', f'{fmt(lbf_to_n(_f_lbf))}')


