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
        return ', '.join([size_part, moc])

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
    # come between MOC and standard per GGPL convention
    if gtype == 'SPIRAL_WOUND' and special:
        parts.append(special)
    if standard:
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


def _fmt_kamm(item: dict) -> str:
    """SIZE : {size} X {rating} X {thk}MM THK,{core} KAMMPROFILE GASKET WITH {surface},{standard}"""
    # Prefer dedicated KAMM fields; fall back to legacy moc field
    core = (item.get('kamm_core_material') or item.get('moc') or '').strip().upper()
    surface = (item.get('kamm_surface_material') or '').strip().upper()
    size = item.get('size')
    rating = item.get('rating')
    standard = item.get('standard')
    thk = item.get('thickness_mm')

    if item.get('size_type') == 'OD_ID':
        od = item.get('od_mm')
        id_ = item.get('id_mm')
        if not (od and id_):
            return ''
        special = (item.get('special') or '').strip()
        dims = f'SIZE : {_fmt_num(id_)}MM ID X {_fmt_num(od)}MM OD X {_fmt_num(thk)}MM THK'
        moc_str = _kamm_moc_str(core, surface)
        parts = [dims]
        if special:
            parts.append(f',{special}')
        if moc_str:
            parts.append(f',{moc_str}')
        if standard:
            parts.append(f',{standard}')
        return ''.join(parts)

    if not (size and rating):
        return ''
    size_str = _fmt_size(size, 'KAMM')
    rating_str = _fmt_rating(rating)
    moc_str = _kamm_moc_str(core, surface)
    thk_str = f' X {_fmt_num(thk)}MM THK' if thk else ''
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
    od = item.get('od_mm')
    id_ = item.get('id_mm')
    thk = item.get('thickness_mm')
    moc = item.get('moc')
    if not (od and id_ and moc):
        return ''
    thk_str = f' X {_fmt_num(thk)}MM THK' if thk else ''
    filler = (item.get('dji_filler') or 'GRAPHITE').strip().upper()
    special = (item.get('special') or '').upper()
    dims = f'SIZE : {_fmt_num(od)}MM OD X {_fmt_num(id_)}MM ID{thk_str}'

    if 'AS PER DRAWING' in special or 'DRAWING' in special:
        # Industrial / heat-exchanger pattern: DOUBLE JACKETED, {moc} WITH {filler} FILLER (AS PER DRAWING)
        filler_str = f'{filler} FILLER' if filler == 'GRAPHITE' else filler
        return f'{dims}, DOUBLE JACKETED, {moc} WITH {filler_str} (AS PER DRAWING)'
    elif 'CORRUGATED' in filler:
        # Corrugated type pattern: {moc} DOUBLE JACKETED GASKET WITH {filler} FILLER
        filler_str = filler if filler.endswith('FILLER') else f'{filler} FILLER'
        return f'{dims}, {moc} DOUBLE JACKETED GASKET WITH {filler_str}'
    else:
        # Standard piping pattern: DOUBLE JACKET GASKET WITH {moc} + {filler} FILLED
        return f'{dims}, DOUBLE JACKET GASKET WITH {moc} + {filler} FILLED'


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

    # STYLE-CS: "SIZE : {size} X {rating} X 3MM THK ,ISK,STYLE-CS (SET:{content}) {standard} ( NON FIRE SAFE )"
    # This is the GGPL format for TYPE-A insulating gasket kits.
    if isk_style == 'STYLE-CS':
        size_str = _fmt_size(size, gtype)
        rating_str = _fmt_rating(rating)
        set_content = _style_cs_set(item)
        out = f'SIZE : {size_str} X {rating_str} X 3MM THK ,ISK,STYLE-CS (SET:{set_content})'
        if standard:
            out += f' {standard}'
        out += ' ( NON FIRE SAFE )'
        return out

    # STYLE-N and equivalent parenthesized styles (FCS, TYPE-D):
    # "SIZE: S X R, INSULATING GASKET KIT ({style}) spec, face (fire_safety)"
    if isk_style in ('STYLE-N', 'FCS', 'TYPE-D'):
        out = f'{base}, INSULATING GASKET KIT ({isk_style})'
        if special:
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
    Format: G11 GASKET WITH 316 STEEL CORE WITH PTFE SPRING ENERGISED SEAL, G11 WASHER & SLEEVES,ZINC PLATED CS WASHER
    """
    import re as _re
    gasket_grade = _cs_grade(item.get('isk_gasket_material'))
    core_grade   = _cs_core(item.get('isk_core_material'))
    sleeve_grade = _cs_grade(item.get('isk_sleeve_material'))

    out = ''
    if gasket_grade:
        out += f'{gasket_grade} GASKET '
    if core_grade:
        out += f'WITH {core_grade} STEEL CORE '
    out += 'WITH PTFE SPRING ENERGISED SEAL'
    if sleeve_grade:
        out += f', {sleeve_grade} WASHER & SLEEVES'
    out += ',ZINC PLATED CS WASHER'
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


def _fmt_size(size: str, gtype: str) -> str:
    """Format size string for GGPL descriptions.
    - NB sizes ('25 NB') → kept as '25 NB'
    - DN sizes ('DN 25') → kept as 'DN 25'
    - NPS inch sizes (with or without NPS/INCH/IN label) → 'N"'
    - Mixed fractions → decimal: '1 1/4"' → '1.25"'
    """
    import re as _re
    s = size.strip()
    # Already has inch symbol — strip any stray 'NPS' label, then convert fraction to decimal
    if '"' in s:
        s = _re.sub(r'\bNPS\b\s*', '', s, flags=_re.IGNORECASE).strip()
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
