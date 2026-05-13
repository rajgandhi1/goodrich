import datetime as _dt
import os as _os

import pandas as pd
import streamlit as st

from ui.history import _append_history, _make_history_entry

_LOGO_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'logo.png')

_CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'KWD', 'SAR', 'SGD', 'AUD', 'CAD', 'JPY', 'CNY']
_DEFAULT_FX_RATES = {
    'INR': 1.0,
    'USD': 83.0,
    'EUR': 90.0,
    'GBP': 105.0,
    'AED': 22.5,
    'KWD': 270.0,
    'SAR': 22.1,
    'SGD': 62.0,
    'AUD': 55.0,
    'CAD': 61.0,
    'JPY': 0.56,
    'CNY': 11.5,
}


def _fx_rate_for(qd: dict, currency: str) -> float:
    """Return the editable INR-per-currency-unit conversion rate."""
    if currency == 'INR':
        return 1.0
    rates = qd.setdefault('currency_rates', {})
    if currency not in rates:
        rates[currency] = _DEFAULT_FX_RATES.get(currency, 1.0)
    try:
        return max(float(rates[currency]), 0.0001)
    except (TypeError, ValueError):
        return _DEFAULT_FX_RATES.get(currency, 1.0)


# ---------------------------------------------------------------------------
# Quote page — rendered instead of main app when _show_quote_page is True
# ---------------------------------------------------------------------------
def render_quote_page():
    """Full-page quote details form."""
    from core.quote_pdf import build_quotation_pdf

    items   = st.session_state.working_items
    qd      = st.session_state._quote_data          # persisted form values
    today   = _dt.date.today().strftime('%d/%m/%Y')

    # ── Back button ─────────────────────────────────────────────────────────
    back_col, title_col = st.columns([1, 9])
    with back_col:
        if st.button('← Back', key='qp_back_btn'):
            st.session_state._show_quote_page = False
            st.session_state._quote_excel = None
            st.rerun()
    with title_col:
        st.markdown("""
        <div class="gq-header" style="margin-bottom:0.8rem">
          <div class="gq-header-icon">📄</div>
          <div>
            <p class="gq-header-title">Generate Sales Quotation</p>
            <p class="gq-header-sub">Fill in the details below to produce a professional GGPL quotation</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Section 1 — Quote Reference ─────────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">1</span>
        <p class="gq-step-title">Quote Reference</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    qd['quote_no']   = r1c1.text_input('Quote Number',
                           value=qd.get('quote_no', f"GGPL/SD/QT/{_dt.date.today().strftime('%y%m')}"),
                           key='qp_quote_no')
    qd['quote_date'] = r1c2.text_input('Quote Date', value=qd.get('quote_date', today),
                           key='qp_quote_date')
    qd['rev_no']     = r1c3.text_input('Rev No', value=qd.get('rev_no', '0'),
                           key='qp_rev_no')
    qd['rev_date']   = r1c4.text_input('Rev Date', value=qd.get('rev_date', today),
                           key='qp_rev_date')

    # ── Section 2 — Buyer Info ───────────────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">2</span>
        <p class="gq-step-title">Buyer Details</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    b_left, b_right = st.columns(2)
    with b_left:
        qd['buyer_name_address'] = st.text_area(
            'Name & Address of the Buyer',
            value=qd.get('buyer_name_address', ''),
            height=120,
            placeholder='Company Name\nStreet Address\nCity, State PIN\nCountry',
            key='qp_buyer_addr',
        )
        qd['customer_enq_no'] = st.text_input(
            'Customer Enquiry Number',
            value=qd.get('customer_enq_no', ''),
            key='qp_enq_no',
        )
    with b_right:
        qd['attention']    = st.text_input('Kind Attention (Contact Person)',
                                value=qd.get('attention', ''), key='qp_attention')
        qd['designation']  = st.text_input('Designation',
                                value=qd.get('designation', ''), key='qp_designation')
        qd['contact_no']   = st.text_input('Contact Number',
                                value=qd.get('contact_no', ''), key='qp_contact')
        qd['email']        = st.text_input('Email ID',
                                value=qd.get('email', ''), key='qp_email')

    # ── Section 3 — GGPL Sales Rep ───────────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">3</span>
        <p class="gq-step-title">Followed By (GGPL Sales Representative)</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    rep_c1, rep_c2, rep_c3, rep_c4 = st.columns(4)
    qd['rep_name']        = rep_c1.text_input('Name',
                                value=qd.get('rep_name', ''), key='qp_rep_name')
    qd['rep_designation'] = rep_c2.text_input('Designation',
                                value=qd.get('rep_designation', 'SALES OFFICER'), key='qp_rep_desig')
    qd['rep_contact']     = rep_c3.text_input('Contact Number',
                                value=qd.get('rep_contact', ''), key='qp_rep_contact')
    qd['rep_email']       = rep_c4.text_input('Email ID',
                                value=qd.get('rep_email', 'mktg1@flosil.com'), key='qp_rep_email')

    # ── Section 4 — Item Pricing ─────────────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">4</span>
        <p class="gq-step-title">Item Pricing</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption('Enter base unit prices in INR. The selected quote currency is calculated from the editable conversion rate.')

    cur_c1, cur_c2, cur_c3, _ = st.columns([2, 2, 3, 3])
    currency_options = list(_CURRENCIES)
    _cur_val = qd.get('currency', 'INR')
    _previous_currency = _cur_val
    if _cur_val not in currency_options:
        currency_options = [_cur_val] + currency_options
    qd['currency'] = cur_c1.selectbox(
        'Quote Currency',
        currency_options,
        index=currency_options.index(_cur_val),
        key='qp_currency',
    )
    _cur = qd.get('currency', 'INR')
    if _cur == 'INR':
        qd['currency_rate'] = 1.0
        cur_c2.number_input(
            'Conversion Rate',
            value=1.0,
            min_value=1.0,
            format='%.4f',
            disabled=True,
            help='INR quote; no conversion applied.',
            key='qp_currency_rate_inr',
        )
    else:
        rate_default = _fx_rate_for(qd, _cur)
        qd['currency_rate'] = cur_c2.number_input(
            f'INR per 1 {_cur}',
            value=float(rate_default),
            min_value=0.0001,
            step=0.5,
            format='%.4f',
            help='Default internal conversion rate. Edit this value for the quotation; no market-rate lookup is used.',
            key=f'qp_currency_rate_{_cur}',
        )
        qd.setdefault('currency_rates', {})[_cur] = qd['currency_rate']
    cur_c3.caption('Conversion is fixed per quote and can be adjusted before generating the PDF.')

    # Build pricing dataframe from base INR prices, then convert to quote currency.
    prev_base_prices = qd.get('unit_prices_inr')
    if prev_base_prices is None:
        existing_prices = qd.get('unit_prices', [0.0] * len(items))
        existing_currency = _previous_currency
        existing_rate = float(qd.get('currency_rate') or 1.0)
        if existing_currency and existing_currency != 'INR':
            prev_base_prices = [float(p or 0) * existing_rate for p in existing_prices]
        else:
            prev_base_prices = list(existing_prices)
    if len(prev_base_prices) != len(items):
        prev_base_prices = list(prev_base_prices) + [0.0] * (len(items) - len(prev_base_prices))

    _base_col = 'Unit Price (INR)'
    _quote_col = f'Unit Price ({_cur})'
    _tot_col = f'Total ({_cur})'
    _rate = float(qd.get('currency_rate') or 1.0)

    pricing_rows = []
    for i, item in enumerate(items):
        status_icon = {'ready': '✅', 'check': '🟡', 'missing': '🔴', 'regret': '⛔'}.get(
            item.get('status', ''), '')
        pricing_rows.append({
            '#':                    item.get('line_no', i + 1),
            'Status':               status_icon,
            'GGPL Description':     item.get('ggpl_description', ''),
            'Customer Description': (item.get('raw_description') or '')[:120],
            'Qty':                  float(item.get('quantity') or 0),
            'UOM':                  item.get('uom') or 'NOS',
            _base_col:              float(prev_base_prices[i]) if prev_base_prices[i] else 0.0,
            _quote_col:             0.0,
            _tot_col:               0.0,
        })

    pricing_df = pd.DataFrame(pricing_rows)
    pricing_df[_quote_col] = (
        pricing_df[_base_col].astype(float) if _cur == 'INR'
        else pricing_df[_base_col].astype(float) / _rate
    )
    pricing_df[_tot_col] = pricing_df['Qty'].astype(float) * pricing_df[_quote_col].astype(float)

    edited_pricing = st.data_editor(
        pricing_df,
        use_container_width=True,
        hide_index=True,
        height=min(80 + 35 * len(items), 520),
        column_config={
            '#':                    st.column_config.NumberColumn('#', width='small', disabled=True),
            'Status':               st.column_config.TextColumn('S', width='small', disabled=True),
            'GGPL Description':     st.column_config.TextColumn('GGPL Description', width='large', disabled=True),
            'Customer Description': st.column_config.TextColumn('Customer Description', width='large', disabled=True),
            'Qty':                  st.column_config.NumberColumn('Qty', width='small', min_value=0,
                                        help='Edit to override extracted quantity'),
            'UOM':                  st.column_config.TextColumn('UOM', width='small', disabled=True),
            _base_col:              st.column_config.NumberColumn(_base_col, width='medium',
                                        min_value=0, format='%.2f',
                                        help='Enter the base unit price in INR'),
            _quote_col:             st.column_config.NumberColumn(_quote_col, width='medium',
                                        disabled=True, format='%.2f',
                                        help=f'Calculated as INR price divided by the {_cur} conversion rate'),
            _tot_col:               st.column_config.NumberColumn(_tot_col, width='medium',
                                        disabled=True, format='%.2f'),
        },
        key=f'qp_pricing_editor_{_cur}',
    )

    # Propagate edited quantities back to items (so PDF uses the updated qty)
    for i, item in enumerate(items):
        if i < len(edited_pricing):
            new_qty = edited_pricing.iloc[i]['Qty']
            try:
                item['quantity'] = float(new_qty) if new_qty not in (None, '') else item.get('quantity')
            except (TypeError, ValueError):
                pass

    # Recompute totals from edited INR prices and selected conversion rate.
    edited_pricing[_quote_col] = (
        edited_pricing[_base_col].astype(float) if _cur == 'INR'
        else edited_pricing[_base_col].astype(float) / _rate
    )
    edited_pricing[_tot_col] = edited_pricing['Qty'].astype(float) * edited_pricing[_quote_col].astype(float)
    qd['unit_prices_inr'] = edited_pricing[_base_col].tolist()
    qd['unit_prices'] = edited_pricing[_quote_col].tolist()
    subtotal = edited_pricing[_tot_col].sum()

    # GST preview
    gst_type_live = qd.get('gst_type', 'IGST')
    gst_pct_live  = float(qd.get('gst_pct') or 18)
    disc_pct_live = float(qd.get('discount_pct') or 0)
    disc_amt_live = subtotal * disc_pct_live / 100
    net_live      = subtotal - disc_amt_live
    gst_amt_live  = net_live * gst_pct_live / 100 if _cur == 'INR' else 0.0

    amt_col1, amt_col2, amt_col3, amt_col4 = st.columns(4)
    _cur_live = _cur
    amt_col1.metric(f'Subtotal ({_cur_live})', f'{subtotal:,.2f}')
    if disc_pct_live > 0:
        amt_col2.metric(f'Discount ({disc_pct_live}%)', f'-{disc_amt_live:,.2f}')
        amt_col3.metric(
            f'GST ({gst_type_live} {gst_pct_live}%)' if _cur == 'INR' else 'GST (not applicable)',
            f'{gst_amt_live:,.2f}',
        )
    else:
        amt_col2.metric(
            f'GST ({gst_type_live} {gst_pct_live}%)' if _cur == 'INR' else 'GST (not applicable)',
            f'{gst_amt_live:,.2f}',
        )
    amt_col4.metric(f'Grand Total ({_cur_live})', f'{net_live + gst_amt_live:,.2f}')

    # ── Section 5 — GST & Discount ───────────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">5</span>
        <p class="gq-step-title">GST & Discount</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    gst_c1, gst_c2, gst_c3, _ = st.columns([2, 2, 2, 4])
    qd['gst_type'] = gst_c2.selectbox(
        'GST Type', ['IGST', 'CGST+SGST', 'UGST'],
        index=['IGST', 'CGST+SGST', 'UGST'].index(qd.get('gst_type', 'IGST')),
        key='qp_gst_type',
        help='GST applies to INR quotes only',
        disabled=_cur != 'INR',
    )
    qd['gst_pct'] = gst_c3.number_input(
        'GST %', value=float(qd.get('gst_pct') or 18.0),
        min_value=0.0, max_value=100.0, step=0.5, format='%.1f',
        key='qp_gst_pct',
        disabled=_cur != 'INR',
    )
    qd['discount_pct'] = gst_c1.number_input(
        'Discount %', value=float(qd.get('discount_pct') or 0.0),
        min_value=0.0, max_value=100.0, step=0.5, format='%.2f',
        help='Enter 0 for no discount',
        key='qp_discount',
    )
    if _cur != 'INR':
        st.caption(f'GST is not applied to {_cur} quotes. The quotation uses the editable conversion rate from Section 4.')

    # ── Section 6 — Terms & Conditions ───────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">6</span>
        <p class="gq-step-title">Terms &amp; Conditions</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    tc1, tc2 = st.columns(2)
    with tc1:
        qd['price_basis']    = st.text_input('Price Basis',
                                   value=qd.get('price_basis', 'FOR BASIS'), key='qp_price_basis')
        qd['validity_days']  = st.text_input('Validity (days)',
                                   value=qd.get('validity_days', '7'), key='qp_validity')
        qd['packing']        = st.text_input('Packing & Forwarding',
                                   value=qd.get('packing', 'INCLUSIVE'), key='qp_packing')
        qd['freight']        = st.text_input('Freight',
                                   value=qd.get('freight', 'INCLUSIVE'), key='qp_freight')
        qd['payment_terms']  = st.text_area('Payment Terms',
                                   value=qd.get('payment_terms',
                                       '30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL'),
                                   height=80, key='qp_payment')
        qd['bank_charges']   = st.text_input('Bank Charges',
                                   value=qd.get('bank_charges', 'TO YOUR ACCOUNT'),
                                   key='qp_bank')
        qd['delivery']       = st.text_input('Delivery',
                                   value=qd.get('delivery', ''),
                                   placeholder='e.g. 4-6 WEEKS',
                                   key='qp_delivery')
    with tc2:
        qd['inspection']     = st.text_input('Inspection',
                                   value=qd.get('inspection', 'Not Applicable'),
                                   key='qp_inspection')
        qd['insurance']      = st.text_input('Insurance',
                                   value=qd.get('insurance', 'TO YOUR ACCOUNT'),
                                   key='qp_insurance')
        qd['hsn_code']       = st.text_input('HSN Code',
                                   value=qd.get('hsn_code', '84841010'),
                                   key='qp_hsn')
        qd['ld_clause']      = st.text_input('LD Clause',
                                   value=qd.get('ld_clause', 'Not Applicable'),
                                   key='qp_ld')
        qd['cancellation']   = st.text_area('Cancellation',
                                   value=qd.get('cancellation',
                                       'Products are manufactured on order and hence Goodrich will not be '
                                       'able to accept cancellation of order or reduction in quantity. '
                                       'The product shall be invoiced as per the PO.'),
                                   height=80, key='qp_cancel')
        qd['min_order_value'] = st.text_area('Minimum Order Value',
                                    value=qd.get('min_order_value',
                                        'INR 10,000. No order can be processed below the same. '
                                        'If processed, INR 3,500 shall be paid extra on document charges.'),
                                    height=80, key='qp_min_order')

    # ── Section 7 — Technical Notes ──────────────────────────────────────────
    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">7</span>
        <p class="gq-step-title">Technical Notes</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    qd['technical_notes'] = st.text_area(
        'Technical Notes (entered per quote)',
        value=qd.get('technical_notes', ''),
        height=120,
        placeholder=(
            'e.g.\n'
            '1. Certifications: MTC to EN10204-3.1 for metallic parts and EN10204-2.1 for non-metallic.\n'
            '2. Testing charges for gasket will be extra at actuals for tests other than compression & '
            'sealability test and Chemical test certificate.'
        ),
        key='qp_tech_notes',
    )

    # ── Generate button ──────────────────────────────────────────────────────
    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
    gen_c1, gen_c2, _ = st.columns([2, 2, 6])

    with gen_c1:
        if st.button('📄  Generate Quotation', type='primary', key='qp_generate_btn'):
            st.session_state._quote_data = qd
            with st.spinner('Building quotation PDF…'):
                pdf_bytes = build_quotation_pdf(
                    items=items,
                    quote_data=qd,
                    logo_path=_LOGO_PATH if _os.path.exists(_LOGO_PATH) else None,
                )
            st.session_state._quote_excel = pdf_bytes
            _append_history(_make_history_entry(items, qd, quote_pdf=pdf_bytes))
            st.rerun()

    with gen_c2:
        if st.button('Cancel', key='qp_cancel_btn', type='secondary'):
            st.session_state._show_quote_page = False
            st.session_state._quote_excel = None
            st.rerun()

    # ── Download section ─────────────────────────────────────────────────────
    if st.session_state._quote_excel:
        st.markdown("""
        <div class="gq-step" style="border-left-color:#1a7a3c">
          <div class="gq-step-label">
            <span class="gq-step-badge" style="background:#1a7a3c">✓</span>
            <p class="gq-step-title">Quotation Ready — Download Below</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

        qt_no = qd.get('quote_no', 'quotation').replace('/', '-')
        fname = f"{qt_no}.pdf"
        dl_c1, dl_c2, _ = st.columns([2.5, 2.5, 5])
        with dl_c1:
            st.download_button(
                label='⬇  Download Quotation PDF',
                data=st.session_state._quote_excel,
                file_name=fname,
                mime='application/pdf',
                type='primary',
                key='qp_download_btn',
            )
        with dl_c2:
            if st.button('＋  Start New Enquiry', type='secondary', key='qp_new_btn'):
                st.session_state.working_items = []
                st.session_state._selected_rows = set()
                st.session_state.pop('_bulk_df', None)
                st.session_state._show_quote_page = False
                st.session_state._quote_excel = None
                st.session_state._quote_data = {}
                st.session_state._input_reset_seq += 1
                st.rerun()


