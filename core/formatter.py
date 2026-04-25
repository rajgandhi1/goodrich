from __future__ import annotations
"""
Generates the GGPL internal quote description string from a processed item.

Formats by type:
  SOFT_CUT    : SIZE : {size} X {rating} X {thk}MM THK ,{MOC} ,{face} ,{standard}
  SPIRAL_WOUND: SIZE : {size} X {rating} X {thk}MM THK ,{MOC} {standard}
  RTJ         : SIZE : {ring_no} ,RTJ ,{groove} ,{moc} ,{bhn} BHN HARDNESS ,{standard}
  KAMM        : SIZE: {size} X {rating} X {thk}MM THK,{moc},{standard}
  DJI         : SIZE: {od}MM OD X {id}MM ID X {thk}MM THK, DOUBLE JACKET GASKET WITH {moc} + GRAPHITE FILLED
  ISK/ISK_RTJ : SIZE: {size} X {rating}#, INSULATING GASKET, ...
"""


def format_description(item: dict) -> str:
    """Build GGPL description. Returns empty string if critical fields missing."""
    gtype = item.get('gasket_type', 'SOFT_CUT')
    special = item.get('special')

    if gtype == 'RTJ':
        return _fmt_rtj(item)

    if gtype == 'KAMM':
        return _fmt_kamm(item)

    if gtype == 'DJI':
        return _fmt_dji(item)

    if gtype in ('ISK', 'ISK_RTJ'):
        return _fmt_isk(item)

    # --- SOFT_CUT and SPIRAL_WOUND ---
    moc = item.get('moc')
    thickness = item.get('thickness_mm')
    face = item.get('face_type')
    standard = item.get('standard')

    if item.get('size_type') == 'OD_ID':
        od = item.get('od_mm')
        id_ = item.get('id_mm')
        if not (od and id_ and moc):
            return ''
        size_part = f'SIZE : OD {_fmt_num(od)}MM X ID {_fmt_num(id_)}MM'
        if thickness:
            size_part += f' X {_fmt_num(thickness)}MM THK'
        od_id_parts = [size_part, moc]
        if special:
            od_id_parts.append(special)
        if standard:
            od_id_parts.append(standard)
        return ', '.join(od_id_parts)

    size = item.get('size')
    rating = item.get('rating')
    if not (size and rating and moc):
        return ''

    size_str = _fmt_size(size, gtype)
    rating_str = _fmt_rating(rating)

    parts = [f'SIZE : {size_str} X {rating_str} X {_fmt_num(thickness)}MM THK', moc]
    if face:
        parts.append(face)
    # Spiral wound: special notes (e.g. E.GALV, FLEXIBLE INHIBITED GRAPHITE FILLER)
    # come between MOC and standard per GGPL convention. LOW STRESS is a gasket
    # construction note and is shown with the gasket standard.
    if gtype == 'SPIRAL_WOUND' and special and str(special).upper() != 'LOW STRESS':
        parts.append(special)
    if standard:
        if gtype == 'SPIRAL_WOUND' and special and str(special).upper() == 'LOW STRESS':
            standard = f'{standard} (LOW STRESS)'
        parts.append(standard)

    # SOFT_CUT uses GGPL's space-comma separator: "...THK ,MOC ,RF ,ASME B16.21"
    # SPIRAL_WOUND keeps the standard comma-space separator
    sep = ' ,' if gtype == 'SOFT_CUT' else ', '
    return sep.join(parts)


_RTJ_COATINGS = ('GALVANISED', 'ZINC PLATED', 'PHOSPHATE COATED', 'NICKEL PLATED', 'CADMIUM PLATED')


def _split_rtj_moc(moc: str) -> tuple[str, str | None]:
    """Split 'SOFTIRON GALVANISED' → ('SOFTIRON', 'GALVANISED'). Returns (moc, coating)."""
    upper = moc.upper()
    for coating in _RTJ_COATINGS:
        if upper.endswith(coating):
            base = moc[:len(moc) - len(coating)].strip()
            return base, coating
    return moc, None


def _fmt_rtj(item: dict) -> str:
    ring_no = item.get('ring_no')
    moc = item.get('moc')
    groove = item.get('rtj_groove_type') or 'OCT'
    hardness_spec = item.get('rtj_hardness_spec')
    bhn = item.get('rtj_hardness_bhn')
    standard = item.get('standard') or 'ASME B16.20'

    if not moc:
        return ''

    hardness_str = hardness_spec if hardness_spec else (f'{int(bhn)} BHN HARDNESS' if bhn else None)

    # Large bore RTJ: no ring number — use SIZE: X" X RATING# format
    if not ring_no:
        size = item.get('size')
        rating = item.get('rating')
        if not (size and rating):
            return ''
        size_str = size if ('"' in size or 'NB' in size.upper() or size.upper().startswith('DN')) else f'{size}"'
        parts = [f'SIZE : {size_str} X {_fmt_rating(rating)}', 'RTJ', groove, moc]
        if hardness_str:
            parts.append(hardness_str)
        parts.append(standard)
        return ' ,'.join(parts)

    # BX rings (API pressure-containing closures): no groove designation in GGPL description
    if ring_no.upper().startswith('BX-'):
        parts = [f'SIZE : {ring_no}', moc]
        if hardness_str:
            parts.append(hardness_str)
        parts.append(standard)
        return ' ,'.join(parts)

    parts = [f'SIZE : {ring_no}', 'RTJ', groove, moc]
    if hardness_str:
        parts.append(hardness_str)
    parts.append(standard)
    return ' ,'.join(parts)


def _kamm_covering_name(surface: str) -> str:
    """Normalize KAMM covering layer to a simple name for output.
    FLEXIBLE GRAPHITE → GRAPHITE; all others pass through (PTFE, MICA, etc.).
    """
    if not surface:
        return 'GRAPHITE'
    s = surface.strip().upper()
    if 'GRAPHITE' in s:
        return 'GRAPHITE'
    return s  # PTFE, MICA, NON ASBESTOS, etc.


def _fmt_kamm(item: dict) -> str:
    """Build GGPL description for Kammprofile gaskets.

    Supports three format variants (selected automatically):
      1. New OD/ID format  — when kamm_core_thk or kamm_integral_outer_ring is set:
            SIZE : OD {od}MM X ID {id}MM X {thk}MM THK ({core_thk}MM CORE THK)
                   KAMMPROFILE {core} {covering} LAYER ON BOTH SIDES [+ ring_desc]
      2. Legacy OD/ID format — when pre-formatted moc string is supplied:
            SIZE : {id}MM ID X {od}MM OD X {thk}MM THK,{moc_str}
      3. NPS with GROOOVED METAL — when integral_outer_ring or named outer_ring detected:
            SIZE : {size} X {rating} X {thk}MM THK, KAMMPROFILE {core} GROOOVED METAL GASKET
                   WITH {covering} COVERING LAYER ON BOTH SIDES, {ring_desc}, {standard}
      4. NPS legacy — pre-formatted moc string:
            SIZE : {size} X {rating} X {thk}MM THK,{moc_str},{standard}
    """
    # Prefer dedicated KAMM fields; fall back to legacy moc field
    kamm_core = (item.get('kamm_core_material') or '').strip().upper()
    core = kamm_core or (item.get('moc') or '').strip().upper()
    surface = (item.get('kamm_surface_material') or item.get('kamm_covering_layer') or '').strip().upper()
    size = item.get('size')
    rating = item.get('rating')
    standard = item.get('standard')
    thk = item.get('thickness_mm')
    core_thk = item.get('kamm_core_thk')
    integral = item.get('kamm_integral_outer_ring')
    is_integral = integral is True or (isinstance(integral, str) and integral.strip().upper() == 'INTEGRAL')
    outer_ring = (item.get('sw_outer_ring') or '').strip().upper() or None
    inner_ring = (item.get('sw_inner_ring') or '').strip().upper() or None

    covering = _kamm_covering_name(surface)

    if item.get('size_type') == 'OD_ID':
        od = item.get('od_mm')
        id_ = item.get('id_mm')
        if not (od and id_):
            return ''
        special = (item.get('special') or '').strip()

        # New OD/ID format: kamm_core_thk is set, OR integral ring is requested,
        # AND core is a plain material code (not a pre-formatted moc string).
        use_new_format = (core_thk is not None or is_integral) and 'KAMMPROFILE' not in core
        if use_new_format:
            core_thk_str = f' ({_fmt_num(core_thk)}MM CORE THK)' if core_thk is not None else ''
            dims = f'SIZE : OD {_fmt_num(od)}MM X ID {_fmt_num(id_)}MM X {_fmt_num(thk)}MM THK{core_thk_str}'
            body = f' KAMMPROFILE {core} {covering} LAYER ON BOTH SIDES' if core else f' KAMMPROFILE {covering} LAYER ON BOTH SIDES'
            if is_integral:
                ring_suffix = ' + INTEGRAL OUTER RING'
            elif outer_ring:
                ring_suffix = f' + {outer_ring} OUTER RING'
            else:
                ring_suffix = ''
            return f'{dims}{body}{ring_suffix}'

        # Legacy OD/ID format: pre-formatted moc string or no new fields
        moc_str = _kamm_moc_str(core, surface)
        dims = f'SIZE : {_fmt_num(id_)}MM ID X {_fmt_num(od)}MM OD X {_fmt_num(thk)}MM THK'
        parts = [dims]
        if special:
            parts.append(f',{special}')
        if moc_str:
            parts.append(f',{moc_str}')
        if standard:
            parts.append(f',{standard}')
        return ''.join(parts)

    # --- NPS format ---
    if not (size and rating):
        return ''
    size_str = _fmt_size(size, 'KAMM')
    rating_str = _fmt_rating(rating)
    thk_str = f' X {_fmt_num(thk)}MM THK' if thk else ''

    # GROOOVED METAL GASKET format: integral outer ring OR named outer ring (non-pre-formatted)
    use_grooved = (is_integral or outer_ring) and kamm_core and 'KAMMPROFILE' not in kamm_core
    if use_grooved:
        moc_part = f'KAMMPROFILE {kamm_core} GROOOVED METAL GASKET WITH {covering} COVERING LAYER ON BOTH SIDES'
        if inner_ring and outer_ring:
            ring_part = f'{inner_ring} INNER RING & {outer_ring} OUTER RING'
        elif is_integral and outer_ring:
            ring_part = f'INTEGRAL {outer_ring} OUTER RING'
        elif is_integral:
            ring_part = 'INTEGRAL OUTER RING'
        else:
            ring_part = f'{outer_ring} OUTER RING'
        parts = [f'SIZE : {size_str} X {rating_str}{thk_str}', moc_part, ring_part]
        if standard:
            parts.append(standard)
        return ', '.join(parts)

    # Legacy NPS format: pre-formatted moc string
    moc_str = _kamm_moc_str(core, surface)
    parts = [f'SIZE : {size_str} X {rating_str}{thk_str}']
    if moc_str:
        parts.append(f',{moc_str}')
    if standard:
        parts.append(f',{standard}')
    return ''.join(parts)


def _kamm_moc_str(core: str, surface: str) -> str:
    """Build the material string for KAMM: 'SS316 KAMMPROFILE GASKET WITH GRAPHITE FILLER'.
    If core already contains the fully-formatted string (filled by LLM), return it as-is."""
    if core and 'KAMMPROFILE' in core:
        return core  # LLM already produced the full formatted string
    if core and surface:
        return f'{core} KAMMPROFILE GASKET WITH {surface} FILLER'
    if core:
        return f'{core} KAMMPROFILE GASKET'
    if surface:
        return f'KAMMPROFILE GASKET WITH {surface} FILLER'
    return 'KAMMPROFILE GASKET'


def _fmt_dji(item: dict) -> str:
    """Build GGPL description for Double Jacket Interface (DJI) gaskets.

    Supports four format variants (selected automatically):
      1. Face-type format (ID-first): when dji_face_type is set
            SIZE : {id}MM ID X {od}MM OD X {thk}MM THK, {filler} DOUBLE JACKETED GASKET WITH {moc} FILLER ,{face}
            Note: filler (inner sealing material) is listed first; moc (jacket) is labeled 'FILLER'.
      2. Drawing pattern (OD-first): when special contains DRAWING
            a. With moc:   SIZE : {od}MM OD X {id}MM ID X {thk}MM THK, DOUBLE JACKETED, {moc} WITH {filler} FILLER (AS PER DRAWING)
            b. No moc:     SIZE : {od}MM OD X {id}MM ID X {thk}MM THK, DOUBLE JACKETED WITH {filler} (AS PER DRAWING)
      3. Corrugated type (OD-first): when filler contains CORRUGATED
            SIZE : {od}MM OD X {id}MM ID X {thk}MM THK, {moc} DOUBLE JACKETED GASKET WITH {filler} FILLER
      4. ID-first format: when dji_id_first is True (ID before OD in input, or TYPE 3 config)
            SIZE : {id}MM ID X {od}MM OD X {thk}MM THK, DOUBLE JACKETED,{moc} + {filler} FILLER
      5. Standard piping (OD-first, default):
            SIZE : {od}MM OD X {id}MM ID X {thk}MM THK, DOUBLE JACKET GASKET WITH {moc} + {filler} FILLED
    """
    od = item.get('od_mm')
    id_ = item.get('id_mm')
    if not (od and id_):
        return ''
    thk = item.get('thickness_mm')
    moc = item.get('moc')
    thk_str = f' X {_fmt_num(thk)}MM THK' if thk else ''
    filler = (item.get('dji_filler') or 'GRAPHITE').strip().upper()
    special = (item.get('special') or '').upper()
    dji_face = (item.get('dji_face_type') or '').strip().upper() or None
    dji_id_first = item.get('dji_id_first', False)

    # 1. Face-type format (ID-first): filler = inner sealing element (body in output),
    #    moc = jacket material (labeled 'FILLER' in GGPL output per convention)
    if dji_face:
        dims = f'SIZE : {_fmt_num(id_)}MM ID X {_fmt_num(od)}MM OD{thk_str}'
        primary = filler   # inner sealing material → body MOC in output
        jacket  = moc or ''  # jacket material → 'FILLER' label in output
        if primary and jacket:
            return f'{dims}, {primary} DOUBLE JACKETED GASKET WITH {jacket} FILLER ,{dji_face}'
        elif primary:
            return f'{dims}, {primary} DOUBLE JACKETED GASKET ,{dji_face}'
        return f'{dims}, DOUBLE JACKETED GASKET ,{dji_face}'

    dims_od = f'SIZE : {_fmt_num(od)}MM OD X {_fmt_num(id_)}MM ID{thk_str}'
    dims_id = f'SIZE : {_fmt_num(id_)}MM ID X {_fmt_num(od)}MM OD{thk_str}'

    # 2. Drawing pattern (OD-first)
    if 'AS PER DRAWING' in special or 'DRAWING' in special:
        if moc:
            filler_str = f'{filler} FILLER' if filler == 'GRAPHITE' else filler
            return f'{dims_od}, DOUBLE JACKETED, {moc} WITH {filler_str} (AS PER DRAWING)'
        else:
            return f'{dims_od}, DOUBLE JACKETED WITH {filler} (AS PER DRAWING)'

    # 3. Corrugated type (OD-first)
    if 'CORRUGATED' in filler:
        if not moc:
            return ''
        filler_str = filler if filler.endswith('FILLER') else f'{filler} FILLER'
        return f'{dims_od}, {moc} DOUBLE JACKETED GASKET WITH {filler_str}'

    # 4. ID-first format (TYPE 3 / ID-first input)
    if dji_id_first:
        if not moc:
            return ''
        return f'{dims_id}, DOUBLE JACKETED,{moc} + {filler} FILLER'

    # 5. Standard piping pattern (OD-first)
    if not moc:
        return ''
    return f'{dims_od}, DOUBLE JACKET GASKET WITH {moc} + {filler} FILLED'


def _fmt_isk(item: dict) -> str:
    size = item.get('size')
    rating = item.get('rating')
    if not (size and rating):
        return ''
    gtype = item.get('gasket_type', 'ISK')
    size_str = _fmt_size(size, gtype)
    rating_str = _fmt_rating(rating)
    special = (item.get('special') or '').strip()
    isk_style = (item.get('isk_style') or '').strip().upper()
    face_type = item.get('face_type') or ''
    standard = item.get('standard') or ''
    fire_safety = (item.get('isk_fire_safety') or '').strip().upper()
    # Normalize to always use hyphen: "NON FIRE SAFE" → "NON-FIRE SAFE"
    fire_safety = fire_safety.replace('NON FIRE SAFE', 'NON-FIRE SAFE')
    # Only include standard in output when explicitly stated by customer (not rules-defaulted),
    # except for STYLE-CS where the standard is always shown (important for large-bore ID)
    std_explicit = item.get('isk_standard_explicit', True)

    if gtype == 'ISK_RTJ':
        style = isk_style or 'STYLE-N'
        spec = f'({special})' if special else ''
        sep = ' ' if spec else ''
        std_str = f'TO SUIT {standard} (TYPE-RTJ)' if standard else 'TO SUIT ASME B16.5 (TYPE-RTJ)'
        return f'SIZE: {size_str} X {rating_str}, ISK {style} (TYPE F - RF) {spec}{sep}{std_str}'.strip()

    base = f'SIZE: {size_str} X {rating_str}'

    # VCS is the customer term for GGPL's STYLE-CS
    if isk_style in ('VCS', 'STYLE-VCS'):
        isk_style = 'STYLE-CS'

    # STYLE-CS: "SIZE: {size} X {rating}, INSULATING GASKET KIT, STYLE-CS, (SET: {content}), {face}, {standard}"
    # This is the GGPL format for TYPE-A insulating gasket kits.
    if isk_style == 'STYLE-CS':
        size_str = _fmt_size(size, gtype)
        rating_str = _fmt_rating(rating)
        # Build SET content from component fields when available, else fall back to special
        has_components = bool(
            item.get('isk_gasket_material') or item.get('isk_core_material')
            or item.get('isk_sleeve_material') or item.get('isk_insulating_washer')
        )
        set_content = _style_cs_set(item) if has_components else (special or '')
        # If ISK type is TYPE-F, add the "(TYPE F - RF)" qualifier on the style label
        isk_type = (item.get('isk_type') or '').upper()
        style_label = 'STYLE-CS (TYPE F - RF)' if 'TYPE-F' in isk_type else 'STYLE-CS'
        out = f'SIZE: {size_str} X {rating_str}, INSULATING GASKET KIT, {style_label}, (SET: {set_content})'
        tail_parts = []
        if face_type:
            tail_parts.append(face_type)
        if std_explicit and standard:
            tail_parts.append(standard)
        if fire_safety:
            tail_parts.append(f'({fire_safety})')
        if tail_parts:
            out += ', ' + ', '.join(tail_parts)
        return out

    # STYLE-N and equivalent parenthesized styles (FCS, TYPE-D):
    # "SIZE: S X R, INSULATING GASKET KIT ({style}) spec, face (fire_safety)"
    if isk_style in ('STYLE-N', 'FCS', 'TYPE-D'):
        out = f'{base}, INSULATING GASKET KIT ({isk_style})'
        # Build detailed component string when dedicated fields are available
        components = _isk_style_n_components(item)
        if components:
            out += f' {components}'
        elif special:
            out += f' {special}'
        tail_parts = []
        if face_type:
            face_str = face_type
            if fire_safety:
                face_str += f' ({fire_safety})'
            tail_parts.append(face_str)
        elif fire_safety:
            tail_parts.append(f'({fire_safety})')
        if std_explicit and standard:
            tail_parts.append(standard)
        if tail_parts:
            out += ', ' + ', '.join(tail_parts)
        return out

    # TYPE-E / TYPE-F
    if isk_style in ('TYPE-E', 'TYPE-F', 'TYPE E', 'TYPE F'):
        import re as _re
        gasket_mat = (item.get('isk_gasket_material') or '').strip().upper()
        core = (item.get('isk_core_material') or '').strip().upper()

        # "WITH WASHER & SLEEVE" format: used when component fields are populated
        # Ground truth: INSULATING GASKET KIT WITH WASHER & SLEEVE (G-10/11) WITH SS316 CORE, {special}
        if gasket_mat or core:
            out = f'{base}, INSULATING GASKET KIT WITH WASHER & SLEEVE'
            if gasket_mat:
                # Strip "GRE " prefix for parenthesized grade display: "GRE G-10/G-11" → "G-10/G-11"
                display_grade = _re.sub(r'^GRE\s+', '', gasket_mat)
                out += f' ({display_grade})'
            if core:
                out += f' WITH {core} CORE'
            if special:
                out += f', {special}'
        else:
            # No component fields — classic TYPE E/F label format
            display_style = isk_style.replace('-', ' ')
            out = f'{base}, INSULATING GASKET KIT'
            if special:
                out += f', {special}'
            out += f', {display_style}'

        if face_type and fire_safety:
            tail_parts = [f'{face_type} ({fire_safety})']
        elif face_type:
            tail_parts = [face_type]
            if fire_safety:
                tail_parts.append(f'({fire_safety})')
        else:
            tail_parts = [f'({fire_safety})'] if fire_safety else []
        if std_explicit and standard:
            tail_parts.append(standard)
        if tail_parts:
            out += ', ' + ', '.join(tail_parts)
        return out

    # No style / other style: "SIZE: S X R, INSULATING GASKET KIT, {components}, face (fire_safety)"
    out = f'{base}, INSULATING GASKET KIT'
    if isk_style:
        out += f', {isk_style}'
    # Build component string from dedicated fields, fall back to special
    components = _isk_components(item)
    if components:
        sep = ' ' if components.upper().startswith(('WITH ', 'FOR ')) else ', '
        out += f'{sep}{components}'
    elif special:
        sep = ' ' if special.upper().startswith(('WITH ', 'FOR ')) else ', '
        out += f'{sep}{special}'
    std_to_show = standard if std_explicit else ''
    if face_type and fire_safety:
        face_str = f'{face_type} ({fire_safety})'
        tail_parts = list(filter(None, [face_str, std_to_show]))
    else:
        tail_parts = list(filter(None, [face_type, std_to_show]))
        if fire_safety:
            tail_parts.append(f'({fire_safety})')
    if tail_parts:
        out += ', ' + ', '.join(tail_parts)
    return out


def _style_cs_set(item: dict) -> str:
    """Build the SET content for STYLE-CS (TYPE-A) ISK kits.
    Format: {gasket} GASKET WITH {core} CORE 3MM THK WITH {primary_seal},
            {sleeve} SLEEVES, {insulating_washer} INSULATING WASHER 3MM THK,
            METALLIC WASHER {metallic_washer} 3MM THK
    Falls back to legacy compact format when component fields are not populated.
    """
    gasket_grade     = _cs_grade(item.get('isk_gasket_material'))
    core_grade       = _cs_core(item.get('isk_core_material'))
    sleeve_grade     = _cs_grade(item.get('isk_sleeve_material'))
    primary_seal     = (item.get('isk_primary_seal') or '').strip().upper() or 'PTFE SPRING ENERGISED SEAL'
    ins_washer       = _cs_grade(item.get('isk_insulating_washer'))
    metallic_washer  = (item.get('isk_washer_material') or '').strip().upper() or 'ZINC PLATED CS WASHER'

    # If we have both insulating washer AND sleeve as separate components, use detailed format
    if ins_washer and sleeve_grade:
        out = ''
        if gasket_grade:
            out += f'{gasket_grade} GASKET '
        if core_grade:
            out += f'WITH {core_grade} CORE 3MM THK '
        out += f'WITH {primary_seal}'
        out += f', {sleeve_grade} SLEEVES'
        out += f', {ins_washer} INSULATING WASHER 3MM THK'
        out += f', METALLIC WASHER {metallic_washer} 3MM THK'
        return out

    # Legacy compact format (sleeve doubles as insulating washer)
    out = ''
    if gasket_grade:
        out += f'{gasket_grade} GASKET '
    if core_grade:
        out += f'WITH {core_grade} STEEL CORE '
    out += f'WITH {primary_seal}'
    if sleeve_grade:
        out += f', {sleeve_grade} WASHER & SLEEVES'
    out += f',{metallic_washer}'
    return out


def _cs_grade(mat: str | None) -> str:
    """Normalise GRE grade for STYLE-CS SET: 'GRE G-11' → 'G11', 'GRE G10' → 'G10'."""
    import re as _re
    if not mat:
        return ''
    s = mat.strip().upper()
    # Strip "GRE " prefix
    s = _re.sub(r'^GRE\s+', '', s)
    # Remove hyphens from grade: "G-11" → "G11"
    s = _re.sub(r'G[\s\-](\d+)', r'G\1', s)
    return s


def _cs_core(mat: str | None) -> str:
    """Normalise core material for STYLE-CS SET: 'SS316' → '316', 'SS316L' → '316L'."""
    import re as _re
    if not mat:
        return ''
    s = mat.strip().upper()
    # Strip SS prefix: "SS316" → "316", "SS316L" → "316L"
    s = _re.sub(r'^SS\s*', '', s)
    return s


def _isk_style_n_components(item: dict) -> str:
    """Build the detailed component string for STYLE-N ISK kits when fields are available.
    Format: GRE G10 CORE 4MM THK, PRIMARY SEAL PTFE, SLEEVE GRE G10,
            INSULATING WASHER G10, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK
    Returns empty string when no component fields are populated.
    """
    gasket_mat   = (item.get('isk_gasket_material') or '').strip().upper()
    primary_seal = (item.get('isk_primary_seal') or '').strip().upper()
    sleeve       = (item.get('isk_sleeve_material') or '').strip().upper()
    ins_washer   = (item.get('isk_insulating_washer') or '').strip().upper()
    metallic_w   = (item.get('isk_washer_material') or '').strip().upper()

    # Only build component string when we have meaningful data
    if not any([gasket_mat, primary_seal, sleeve, ins_washer, metallic_w]):
        return ''

    parts = []
    if gasket_mat:
        parts.append(f'{gasket_mat} CORE 4MM THK')
    if primary_seal:
        parts.append(f'PRIMARY SEAL {primary_seal}')
    if sleeve:
        parts.append(f'SLEEVE {sleeve}')
    if ins_washer:
        parts.append(f'INSULATING WASHER {ins_washer}')
    if metallic_w:
        parts.append(f'METALLIC WASHER {metallic_w} 3MM THK')
    return ', '.join(parts)


def _isk_components(item: dict) -> str:
    """
    Build ISK component string from dedicated fields.
    Returns e.g. 'GRE G11 GASKET + SS316 CORE + CS WASHERS + GRE G11 SLEEVES'
    Falls back to empty string if no component fields are populated.
    """
    parts = []
    gasket_mat = (item.get('isk_gasket_material') or '').strip().upper()
    core = (item.get('isk_core_material') or '').strip().upper()
    washers = (item.get('isk_washer_material') or '').strip().upper()
    sleeves = (item.get('isk_sleeve_material') or '').strip().upper()

    if gasket_mat:
        # Don't add "GASKET" suffix if material already ends with SEAL/GASKET
        if gasket_mat.endswith(('SEAL', 'GASKET')):
            parts.append(gasket_mat)
        else:
            parts.append(f'{gasket_mat} GASKET')
    if core:
        parts.append(f'{core} CORE')
    if washers:
        parts.append(f'{washers} WASHERS')
    if sleeves:
        parts.append(f'{sleeves} SLEEVES')

    return ' + '.join(parts)


# Sub-1" NPS decimal → standard fractional name (0.875 → 7/8 etc.)
_NPS_DECIMAL_TO_FRAC = {
    0.125: '1/8', 0.25: '1/4', 0.375: '3/8',
    0.5: '1/2', 0.75: '3/4', 0.875: '7/8',
}


def _fmt_size(size: str, gtype: str) -> str:
    """Format size string for GGPL descriptions.
    - NB sizes ('25 NB') → kept as '25 NB'
    - DN sizes ('DN 25') → kept as 'DN 25'
    - NPS inch sizes (with or without NPS/INCH/IN label) → 'N"'
    - Sub-1" decimals → standard fractions: '0.875"' → '7/8"'
    - Mixed fractions → decimal: '1 1/4"' → '1.25"'
    """
    import re as _re
    s = size.strip()
    # Already has inch symbol — strip any stray 'NPS' label, then normalise
    if '"' in s:
        s = _re.sub(r'\bNPS\b\s*', '', s, flags=_re.IGNORECASE).strip()
        # ISK uses hyphenated fraction notation (e.g. 1-1/16", 2-1/16" for wellhead sizes):
        #   "1 1/2"" → "1-1/2"" (normalise space to hyphen, then preserve)
        #   "1-1/2"" → keep as-is
        # All other types convert fractions to decimals (e.g. SPW, SOFT_CUT).
        if gtype in ('ISK', 'ISK_RTJ'):
            mf = _re.match(r'^(\d+)[\s\-]+(\d+)/(\d+)"$', s)
            if mf:
                return f'{mf.group(1)}-{mf.group(2)}/{mf.group(3)}"'
        else:
            # Mixed fraction with space or hyphen: "1 1/4"" or "1-1/4"" → "1.25""
            mf = _re.match(r'^(\d+)[\s\-]+(\d+)/(\d+)"$', s)
            if mf:
                val = int(mf.group(1)) + int(mf.group(2)) / int(mf.group(3))
                return f'{_fmt_num(val)}"'
        # Simple fraction: "3/4"" → "0.75""
        sf = _re.match(r'^(\d+)/(\d+)"$', s)
        if sf:
            val = int(sf.group(1)) / int(sf.group(2))
            return f'{_fmt_num(val)}"'
        # Sub-1" decimal → standard fractional name: "0.875"" → "7/8""
        dec = _re.match(r'^(0\.\d+)"$', s)
        if dec:
            val = float(dec.group(1))
            frac = _NPS_DECIMAL_TO_FRAC.get(round(val, 3))
            if frac:
                return f'{frac}"'
        return s
    # Metric OD/ID strings — pass through unchanged
    if 'MM' in s.upper():
        return s
    # DN prefix: "DN 100" / "DN25" → "DN 100" / "DN 25"
    m = _re.match(r'^DN\s*(\d+(?:\.\d+)?)$', s, _re.IGNORECASE)
    if m:
        return f'DN {int(float(m.group(1)))}'
    # NB suffix: "100 NB" / "25NB" → "100 NB" / "25 NB"
    m = _re.match(r'^(\d+(?:\.\d+)?)\s*NB$', s, _re.IGNORECASE)
    if m:
        return f'{int(float(m.group(1)))} NB'
    # Strip NPS / INCH / IN label and append inch symbol
    bare = _re.sub(r'\bNPS\b|\bINCH(ES)?\b|\bIN\b', '', s, flags=_re.IGNORECASE).strip()
    return f'{bare}"'


def _fmt_rating(rating: str) -> str:
    """Format rating for display: '150#' or 'PN 10'."""
    return rating  # already normalized


def _fmt_num(val) -> str:
    """Format number: no trailing zeros for integers."""
    if val is None:
        return ''
    f = float(val)
    return str(int(f)) if f == int(f) else str(f)
