import pandas as pd
import streamlit as st

from core.formatter import format_description
from core.rules import apply_rules, STATUS_CHECK, STATUS_MISSING, STATUS_READY, STATUS_REGRET
from ui.constants import FACE_OPTIONS, GROOVE_OPTIONS, TYPE_OPTIONS, UOM_OPTIONS


# ---------------------------------------------------------------------------
def _build_extraction_summary(items: list[dict]) -> list[str]:
    """Return deduplicated summary lines grouped by unique gasket spec."""
    rtj_groups: dict = {}    # (groove, moc, bhn, api_flag) → count
    spw_groups: dict = {}    # (winding, filler, inner, outer) → set[rating]
    soft_groups: dict = {}   # (moc, face) → set[rating]
    kamm_groups: dict = {}   # (core, surface) → count
    dji_groups: dict = {}    # (filler,) → count
    isk_groups: dict = {}    # (isk_type, isk_gasket_material) → count

    for item in items:
        if item.get('status') == STATUS_REGRET:
            continue
        gtype = (item.get('gasket_type') or 'SOFT_CUT').upper()
        rating = (item.get('rating') or '').strip()

        if gtype == 'RTJ':
            groove = (item.get('rtj_groove_type') or 'OCT').upper()
            moc = (item.get('moc') or '').upper()
            bhn = item.get('rtj_hardness_bhn')
            std = (item.get('standard') or '').upper()
            api_flag = 'API-6A TYPE' if 'API 6A' in std else ''
            key = (groove, moc, bhn, api_flag)
            rtj_groups[key] = rtj_groups.get(key, 0) + 1

        elif gtype == 'SPIRAL_WOUND':
            winding = (item.get('sw_winding_material') or '').upper()
            filler  = (item.get('sw_filler') or '').upper()
            inner   = (item.get('sw_inner_ring') or '').upper()
            outer   = (item.get('sw_outer_ring') or '').upper()
            key = (winding, filler, inner, outer)
            if key not in spw_groups:
                spw_groups[key] = set()
            if rating:
                spw_groups[key].add(rating)

        elif gtype == 'SOFT_CUT':
            moc  = (item.get('moc') or '').upper()
            face = (item.get('face_type') or '').upper()
            key = (moc, face)
            if key not in soft_groups:
                soft_groups[key] = set()
            if rating:
                soft_groups[key].add(rating)

        elif gtype == 'KAMM':
            core = (item.get('kamm_core_material') or '').upper()
            surf = (item.get('kamm_surface_material') or '').upper()
            key = (core, surf)
            kamm_groups[key] = kamm_groups.get(key, 0) + 1

        elif gtype == 'DJI':
            filler = (item.get('dji_filler') or '').upper()
            key = (filler,)
            dji_groups[key] = dji_groups.get(key, 0) + 1

        elif gtype == 'ISK':
            isk_type = (item.get('isk_type') or '').upper()
            isk_mat  = (item.get('isk_gasket_material') or '').upper()
            key = (isk_type, isk_mat)
            isk_groups[key] = isk_groups.get(key, 0) + 1

    lines: list[str] = []

    for (groove, moc, bhn, api_flag) in rtj_groups:
        parts = ['RTJ', groove]
        if moc:
            parts.append(moc)
        if bhn is not None:
            parts.append(f'{int(float(bhn))} BHN HARDNESS MAX')
        if api_flag:
            parts.append(api_flag)
        lines.append(' ,'.join(parts))

    for (winding, filler, inner, outer), ratings in spw_groups.items():
        mat = f'{winding}/{filler}' if winding and filler else (winding or filler)
        suffix = ''
        if inner:
            suffix += f'+{inner}IR'
        if outer:
            suffix += f'&{outer}OR'
        desc = mat + suffix
        if ratings:
            _rating_order = {'150#': 0, '300#': 1, '600#': 2, '900#': 3, '1500#': 4, '2500#': 5}
            sorted_ratings = sorted(ratings, key=lambda r: _rating_order.get(r, 99))
            desc += ',' + ','.join(sorted_ratings)
        lines.append(desc)

    for (moc, face), ratings in soft_groups.items():
        parts = ['SOFT CUT']
        if moc:
            parts.append(moc)
        if face:
            parts.append(face)
        desc = ' ,'.join(parts)
        if ratings:
            _rating_order = {'150#': 0, '300#': 1, '600#': 2, '900#': 3, '1500#': 4, '2500#': 5}
            sorted_ratings = sorted(ratings, key=lambda r: _rating_order.get(r, 99))
            desc += ' ,' + ' ,'.join(sorted_ratings)
        lines.append(desc)

    for (core, surf) in kamm_groups:
        parts = ['KAMMPROFILE']
        if core:
            parts.append(f'CORE: {core}')
        if surf:
            parts.append(f'SURFACE: {surf}')
        lines.append(' ,'.join(parts))

    for (filler,) in dji_groups:
        desc = 'DOUBLE JACKET'
        if filler:
            desc += f' ,{filler}'
        lines.append(desc)

    for (isk_type, isk_mat) in isk_groups:
        parts = ['ISK']
        if isk_type:
            parts.append(isk_type)
        if isk_mat:
            parts.append(isk_mat)
        lines.append(' ,'.join(parts))

    return lines


# ---------------------------------------------------------------------------
# Helper — build display rows
# ---------------------------------------------------------------------------
def _build_preview_df(items):
    """Same columns as the working list so users can review during extraction."""
    return pd.DataFrame(_build_rows(items))


def _build_rows(items):
    rows = []
    for item in items:
        status_icon = {'ready': '✅', 'check': '🟡', 'missing': '🔴', 'regret': '⛔'}.get(item['status'], '')
        flags    = item.get('flags', [])
        defaults = item.get('applied_defaults', [])
        parts    = list(flags) + [f'[default] {d}' for d in defaults]
        rows.append({
            '#':                    item.get('line_no', ''),
            'Status':               status_icon,
            'GGPL Description':     item.get('ggpl_description', ''),
            'Notes / Flags':        '; '.join(parts),
            'Qty':                  item.get('quantity') if item.get('quantity') is not None else None,
            'UoM':                  item.get('uom') or 'NOS',
            'Regret':               item.get('regret', False),
            'Customer Description': item.get('raw_description', ''),
            'Type':                 item.get('gasket_type', 'SOFT_CUT'),
            'Size':                 '' if item.get('size_type') == 'OD_ID' else (item.get('size') or ''),
            'Size (in)':            '' if item.get('size_type') == 'OD_ID' else (item.get('size_norm') or ''),
            'OD (mm)':              item.get('od_mm') if item.get('od_mm') is not None else None,
            'ID (mm)':              item.get('id_mm') if item.get('id_mm') is not None else None,
            'Rating':               item.get('rating') or '',
            'MOC':                  item.get('moc') or '',
            'Face':                 item.get('face_type') or '',
            'Thk (mm)':             item.get('thickness_mm') if item.get('thickness_mm') is not None else None,
            'Standard':             item.get('standard') or '',
            'Series':               item.get('series') or '',
            'Special':              item.get('special') or '',
            'Ring No':              item.get('ring_no') or '',
            'Groove':               item.get('rtj_groove_type') or '',
            'BHN':                  item.get('rtj_hardness_bhn') or None,
            'SW Winding':           item.get('sw_winding_material') or '',
            'SW Filler':            item.get('sw_filler') or '',
            'SW Outer Ring':        item.get('sw_outer_ring') or '',
            'SW Inner Ring':        item.get('sw_inner_ring') or '',
            'ISK Gasket Mat':       item.get('isk_gasket_material') or '',
            'ISK Core':             item.get('isk_core_material') or '',
            'ISK Sleeves':          item.get('isk_sleeve_material') or '',
            'ISK Washers':          item.get('isk_washer_material') or '',
            'ISK Primary Seal':     item.get('isk_primary_seal') or '',
            'ISK Secondary Seal':   item.get('isk_secondary_seal') or '',
            'ISK Ins Washer':       item.get('isk_insulating_washer') or '',
            'KAMM Core':            item.get('kamm_core_material') or '',
            'KAMM Surface':         item.get('kamm_surface_material') or '',
            'KAMM Covering':        item.get('kamm_covering_layer') or '',
            'KAMM Rib':             item.get('kamm_rib') or '',
            'KAMM Core Thk':        item.get('kamm_core_thk') or '',
            'DJI Filler':           item.get('dji_filler') or '',
            'DJI Rib':              item.get('dji_rib') or '',
            'DJI Face':             item.get('dji_face_type') or '',
            'AI':                   item.get('confidence', ''),
        })
    return rows


def _delete_selected_items(items, display_indices):
    to_delete = {
        display_indices[i]
        for i in st.session_state._selected_rows
        if i < len(display_indices)
    }
    final = [it for idx, it in enumerate(items) if idx not in to_delete]
    for j, it in enumerate(final, 1):
        it['line_no'] = j
    st.session_state.working_items = final
    st.session_state._selected_rows = set()
    st.session_state.pop('_bulk_df', None)


# ---------------------------------------------------------------------------
# Fragment — data editor + Update/Delete
# ---------------------------------------------------------------------------
def _reset_enquiry_inputs():
    st.session_state._input_reset_seq += 1


def _coerce_optional_number(value, fallback=None):
    if value is None or value == '':
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except TypeError:
        pass
    return value


def _reprocess_customer_descriptions(items, display_indices, edited_df, visible_rows):
    """Run selected/changed customer descriptions through extraction again via Smart Parse."""
    if not visible_rows:
        return 0

    import os as _os2
    from core.document_reader import read_document_smart, SmartParseError

    api_key = _os2.environ.get('OPENAI_API_KEY')
    if not api_key:
        st.warning('Re-processing requires an OpenAI API key.')
        return 0

    target_meta = []
    desc_lines = []
    for visible_idx in visible_rows:
        if visible_idx >= len(edited_df) or visible_idx >= len(display_indices):
            continue
        row = edited_df.iloc[visible_idx]
        new_desc = str(row.get('Customer Description') or '').strip()
        if not new_desc:
            continue
        orig_idx = display_indices[visible_idx]
        current = items[orig_idx]
        qty = _coerce_optional_number(row.get('Qty'), current.get('quantity')) or 1
        uom = row.get('UoM') or current.get('uom') or 'NOS'
        desc_lines.append(f"{new_desc}, Qty: {qty}, UoM: {uom}")
        target_meta.append((orig_idx, bool(row.get('Regret'))))

    if not desc_lines:
        return 0

    try:
        from openai import OpenAI as _OAI_RP
        _rp_client = _OAI_RP(api_key=api_key, timeout=120.0)
        reprocessed, _ = read_document_smart(
            '\n'.join(desc_lines), 'email', _rp_client
        )
    except SmartParseError as e:
        st.warning(f'Re-process failed: {e}')
        return 0
    updated_full = list(items)

    for extracted, (orig_idx, regret) in zip(reprocessed, target_meta):
        item = apply_rules(extracted)
        item['ggpl_description'] = format_description(item)
        item['line_no'] = items[orig_idx].get('line_no', orig_idx + 1)
        item['regret'] = regret
        if regret:
            item['status'] = STATUS_REGRET
        updated_full[orig_idx] = item

    for j, it in enumerate(updated_full, 1):
        it['line_no'] = j
    st.session_state.working_items = updated_full
    st.session_state._selected_rows = set()
    st.session_state.pop('_bulk_df', None)
    return len(reprocessed)


@st.fragment
def _editor_fragment(items, display_indices):
    display_items = [items[i] for i in display_indices]

    if '_bulk_df' in st.session_state:
        df = st.session_state['_bulk_df'].copy()
    else:
        df = pd.DataFrame(_build_rows(display_items))

    df = df.drop(columns=[c for c in ('Select',) if c in df.columns])
    df.insert(0, 'Select', [i in st.session_state._selected_rows for i in range(len(df))])

    edited_df = st.data_editor(
        df,
        width="stretch",
        height=min(80 + 35 * len(display_items), 620),
        hide_index=True,
        column_config={
            'Select':               st.column_config.CheckboxColumn('☑', width='small',
                                        help='Select rows for bulk actions below'),
            'Regret':               st.column_config.CheckboxColumn('⛔ Regret', width='small',
                                        help='Tick = GGPL cannot produce this item'),
            '#':                    st.column_config.NumberColumn('#', width='small', disabled=True),
            'Customer Description': st.column_config.TextColumn(
                'Customer Description',
                width='large',
                help='Edit this text, select the row, then click Reprocess Text.',
            ),
            'Type':                 st.column_config.SelectboxColumn('Type', options=TYPE_OPTIONS, width='small'),
            'Size':                 st.column_config.TextColumn('Size', width='small',
                                        help='Size as written by customer.'),
            'Size (in)':            st.column_config.TextColumn('Size (in)', width='small',
                                        help='Converted to NPS inches (e.g. DN 25 → 1\", 100 NB → 4\").'),
            'OD (mm)':              st.column_config.NumberColumn('OD (mm)', width='small', min_value=0),
            'ID (mm)':              st.column_config.NumberColumn('ID (mm)', width='small', min_value=0),
            'Rating':               st.column_config.TextColumn('Rating', width='small'),
            'Standard':             st.column_config.TextColumn('Standard', width='medium',
                                        help='e.g. ASME B16.20, ASME B16.21, ASME B16.47 (SERIES-A), API 6A'),
            'MOC':                  st.column_config.TextColumn('MOC', width='large'),
            'Face':                 st.column_config.SelectboxColumn('Face', options=FACE_OPTIONS, width='small'),
            'Series':               st.column_config.SelectboxColumn('Series', options=['', 'A', 'B'], width='small',
                                        help='B16.47 only — Series A (ex-API 605) or Series B (ex-MSS SP-44)'),
            'Thk (mm)':             st.column_config.NumberColumn('Thk (mm)', width='small', min_value=0),
            'Ring No':              st.column_config.TextColumn('Ring No', width='small', help='RTJ ring e.g. R-23'),
            'Groove':               st.column_config.SelectboxColumn('Groove', options=GROOVE_OPTIONS, width='small'),
            'BHN':                  st.column_config.NumberColumn('BHN', width='small', min_value=1, step=10, help='Enter number only — BHN HARDNESS appended automatically'),
            'SW Winding':           st.column_config.TextColumn('SW Winding', width='small'),
            'SW Filler':            st.column_config.TextColumn('SW Filler', width='small'),
            'SW Outer Ring':        st.column_config.TextColumn('SW Outer Ring', width='small'),
            'SW Inner Ring':        st.column_config.TextColumn('SW Inner Ring', width='small'),
            'ISK Gasket Mat':       st.column_config.TextColumn('ISK Gasket Mat', width='small',
                                        help='ISK laminated ring material e.g. GRE G10, Mica, G7, PTFE, PEEK'),
            'ISK Core':             st.column_config.TextColumn('ISK Core', width='small',
                                        help='ISK metal core e.g. SS316, CS, UNS S32760, INC 625, DSS 31803'),
            'ISK Sleeves':          st.column_config.TextColumn('ISK Sleeves', width='small',
                                        help='ISK sleeve material e.g. GRE G10, PTFE, Mylar'),
            'ISK Washers':          st.column_config.TextColumn('ISK Washers', width='small',
                                        help='Metallic washer e.g. Zinc Plated CS, SS316, MS'),
            'ISK Primary Seal':     st.column_config.TextColumn('ISK Primary Seal', width='small',
                                        help='Primary seal e.g. PTFE Spring Energised, Viton O-ring, EPDM O-ring'),
            'ISK Secondary Seal':   st.column_config.TextColumn('ISK Secondary Seal', width='small',
                                        help='Secondary seal e.g. Mica'),
            'ISK Ins Washer':       st.column_config.TextColumn('ISK Ins Washer', width='small',
                                        help='Insulating (non-metallic) washer grade e.g. G10, G11, Mica, Mylar'),
            'KAMM Core':            st.column_config.TextColumn('KAMM Core', width='small',
                                        help='Kammprofile metal core e.g. SS316, ALLOY 625'),
            'KAMM Surface':         st.column_config.TextColumn('KAMM Surface', width='small',
                                        help='Kammprofile surface material e.g. GRAPHITE, PTFE'),
            'KAMM Covering':        st.column_config.TextColumn('KAMM Covering', width='small',
                                        help='Kammprofile covering layer: GRAPHITE, PTFE, MICA, NON ASBESTOS'),
            'KAMM Rib':             st.column_config.TextColumn('KAMM Rib', width='small',
                                        help='Rib feature: WITH RIB / WITHOUT RIB'),
            'KAMM Core Thk':        st.column_config.TextColumn('KAMM Core Thk', width='small',
                                        help='Core thickness in mm (for OD/ID format annotation)'),
            'DJI Filler':           st.column_config.TextColumn('DJI Filler', width='small',
                                        help='DJI inner filler e.g. GRAPHITE, ASBESTOS FREE, MINERAL FIBER, PTFE'),
            'DJI Rib':              st.column_config.TextColumn('DJI Rib', width='small',
                                        help='Rib feature: WITH RIB / WITHOUT RIB'),
            'DJI Face':             st.column_config.SelectboxColumn('DJI Face', options=['', 'RF', 'FF'], width='small',
                                        help='Face type for special DJI types (round-lip, TEFLON jacket etc.)'),
            'Qty':                  st.column_config.NumberColumn('Qty', width='small', min_value=0),
            'UoM':                  st.column_config.SelectboxColumn('UoM', options=UOM_OPTIONS, width='small'),
            'Special':              st.column_config.TextColumn('Special', width='medium'),
            'GGPL Description':     st.column_config.TextColumn('GGPL Description', width='large', disabled=True),
            'Status':               st.column_config.TextColumn('Status', width='small', disabled=True),
            'AI':                   st.column_config.TextColumn('AI', width='small', disabled=True,
                                        help='Confidence: HIGH / MEDIUM / LOW'),
            'Notes / Flags':        st.column_config.TextColumn('Notes / Flags', width='large', disabled=True),
        },
    )

    st.session_state._selected_rows = {i for i, row in edited_df.iterrows() if row['Select']}
    n_sel = len(st.session_state._selected_rows)
    sel_label = f'{n_sel} selected' if n_sel else 'none selected'
    changed_description_rows = {
        i for i, row in edited_df.iterrows()
        if (
            str(row.get('Customer Description') or '').strip()
            != str(items[display_indices[i]].get('raw_description') or '').strip()
        )
    }

    act_c1, act_c2, act_c3, act_c4, act_c5 = st.columns([2, 2.2, 2, 2, 2])

    reprocess_targets = st.session_state._selected_rows or changed_description_rows
    if act_c1.button(
        'Reprocess Text',
        type='secondary',
        key='reprocess_text_btn',
        disabled=(len(reprocess_targets) == 0),
        help='Edit Customer Description, then re-run extraction for selected rows. If none are selected, changed descriptions are reprocessed.',
    ):
        done = _reprocess_customer_descriptions(items, display_indices, edited_df, sorted(reprocess_targets))
        if done:
            st.rerun(scope='app')
        else:
            st.warning('No non-empty customer descriptions to reprocess.')

    # ── Update Descriptions ──────────────────────────────────────────────────
    if act_c2.button('↻  Update Descriptions', type='secondary', key='update_btn'):
        updated_full = list(items)

        for i, row in edited_df.iterrows():
            orig_idx = display_indices[i]
            base = items[orig_idx].copy()
            edited_raw_description = str(row.get('Customer Description') or '').strip()
            base['raw_description'] = edited_raw_description
            base['description'] = edited_raw_description
            base['gasket_type']        = row['Type'] or base.get('gasket_type', 'SOFT_CUT')
            od_val = _coerce_optional_number(row.get('OD (mm)'))
            id_val = _coerce_optional_number(row.get('ID (mm)'))
            base['od_mm']              = float(od_val) if od_val is not None else None
            base['id_mm']              = float(id_val) if id_val is not None else None
            if base['od_mm'] is not None or base['id_mm'] is not None:
                base['size'] = None
                base['size_type'] = 'OD_ID'
            else:
                base['size'] = row['Size'] or base.get('size')
                if base.get('size_type') == 'OD_ID':
                    base['size_type'] = 'UNKNOWN'
            base['rating']             = row['Rating'] or base.get('rating')
            base['standard']           = row['Standard'] or None
            base['moc']                = row['MOC'] or None
            base['face_type']          = row['Face'] or None
            base['series']             = row['Series'] or None
            base['thickness_mm']       = row['Thk (mm)'] or None
            base['ring_no']            = row['Ring No'] or None
            base['rtj_groove_type']    = row['Groove'] or None
            bhn_val = row['BHN'] or None
            if bhn_val:
                bhn_int = int(float(bhn_val))
                base['rtj_hardness_bhn']  = bhn_int
                base['rtj_hardness_spec'] = f'{bhn_int} BHN HARDNESS'
            else:
                base['rtj_hardness_bhn']  = None
                base['rtj_hardness_spec'] = None
            base['sw_winding_material']  = row['SW Winding'] or None
            base['sw_filler']            = row['SW Filler'] or None
            base['sw_outer_ring']        = row['SW Outer Ring'] or None
            base['sw_inner_ring']        = row['SW Inner Ring'] or None
            base['isk_gasket_material']  = row['ISK Gasket Mat'] or None
            base['isk_core_material']    = row['ISK Core'] or None
            base['isk_sleeve_material']  = row['ISK Sleeves'] or None
            base['isk_washer_material']  = row['ISK Washers'] or None
            base['isk_primary_seal']     = row['ISK Primary Seal'] or None
            base['isk_secondary_seal']   = row['ISK Secondary Seal'] or None
            base['isk_insulating_washer']= row['ISK Ins Washer'] or None
            base['kamm_core_material']   = row['KAMM Core'] or None
            base['kamm_surface_material']= row['KAMM Surface'] or None
            base['kamm_covering_layer']  = row['KAMM Covering'] or None
            base['kamm_rib']             = row['KAMM Rib'] or None
            core_thk_val = row.get('KAMM Core Thk')
            base['dji_filler']           = row['DJI Filler'] or None
            base['dji_rib']              = row['DJI Rib'] or None
            base['dji_face_type']        = row['DJI Face'] or None
            base['kamm_core_thk'] = float(core_thk_val) if core_thk_val else None
            # For SPW/KAMM, always clear MOC so apply_rules rebuilds it from
            # the current component fields (winding, filler, inner/outer ring).
            if base.get('gasket_type') in ('SPIRAL_WOUND', 'KAMM'):
                base['moc'] = None
            base['quantity']           = row['Qty'] or base.get('quantity')
            base['uom']                = row['UoM'] or 'NOS'
            base['special']            = row['Special'] or None
            # Preserve regret from checkbox
            base['regret'] = bool(row.get('Regret'))
            for f in ('size_norm', 'rating_norm', 'status', 'flags', 'applied_defaults', 'dimensions'):
                base.pop(f, None)
            updated = apply_rules(base)
            updated['ggpl_description'] = format_description(updated)
            # Regret overrides calculated status
            if base['regret']:
                updated['status'] = STATUS_REGRET
                updated['regret'] = True
            updated_full[orig_idx] = updated

        for j, it in enumerate(updated_full, 1):
            it['line_no'] = j
        st.session_state.working_items = updated_full
        st.session_state.pop('_bulk_df', None)
        st.session_state._selected_rows = set()
        st.rerun(scope='app')

    # ── Delete Selected ──────────────────────────────────────────────────────
    if act_c3.button(f'🗑  Delete ({sel_label})', type='secondary', key='delete_sel_btn',
                     disabled=(n_sel == 0)):
        _delete_selected_items(items, display_indices)
        st.rerun(scope='app')

    # ── Mark as Regret ───────────────────────────────────────────────────────
    if act_c4.button(f'⛔  Regret ({sel_label})', type='secondary', key='regret_sel_btn',
                     disabled=(n_sel == 0),
                     help='Mark selected items as REGRET — GGPL cannot produce'):
        updated_full = list(items)
        for i in st.session_state._selected_rows:
            orig_idx = display_indices[i]
            it = dict(updated_full[orig_idx])
            # Toggle: if already regret, clear it; otherwise set it
            if it.get('regret'):
                it['regret'] = False
                it.pop('status', None)
                it = apply_rules(it)
                it['ggpl_description'] = format_description(it)
            else:
                it['regret'] = True
                it['status'] = STATUS_REGRET
            updated_full[orig_idx] = it
        st.session_state.working_items = updated_full
        st.session_state._selected_rows = set()
        st.session_state.pop('_bulk_df', None)
        st.rerun(scope='app')


