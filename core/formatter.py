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
    if standard:
        parts.append(standard)

    return ', '.join(parts)


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

    moc_base, coating = _split_rtj_moc(moc)
    hardness_str = hardness_spec if hardness_spec else (f'{int(bhn)}BHN HARDNESS' if bhn else None)

    # Large bore RTJ: no ring number — use SIZE: X" X RATING# format
    if not ring_no:
        size = item.get('size')
        rating = item.get('rating')
        if not (size and rating):
            return ''
        size_str = size if ('"' in size or 'NB' in size) else f'{size}"'
        parts = [f'SIZE : {size_str} X {_fmt_rating(rating)}', 'RTJ', groove, moc_base]
        if coating:
            parts.append(coating)
        if hardness_str:
            parts.append(hardness_str)
        parts.append(standard)
        return ', '.join(parts)

    parts = [f'SIZE : {ring_no}', 'RTJ', groove, moc_base]
    if coating:
        parts.append(coating)
    if hardness_str:
        parts.append(hardness_str)
    parts.append(standard)
    return ', '.join(parts)


def _fmt_kamm(item: dict) -> str:
    """SIZE: {size} X {rating} X {thk}MM THK,{moc},{standard}"""
    moc = item.get('moc')
    size = item.get('size')
    rating = item.get('rating')
    standard = item.get('standard')
    thk = item.get('thickness_mm')

    if item.get('size_type') == 'OD_ID':
        od = item.get('od_mm')
        id_ = item.get('id_mm')
        if not (od and id_ and moc):
            return ''
        special = (item.get('special') or '').strip()
        special_str = f' ({special})' if special else ''
        # OD/ID KAMM: space-separated (no comma) between dims/special and MOC
        return f'SIZE : OD {_fmt_num(od)}MM X ID {_fmt_num(id_)}MM X {_fmt_num(thk)}MM THK{special_str} {moc}'

    if not (size and rating and moc):
        return ''
    size_str = _fmt_size(size, 'KAMM')
    rating_str = _fmt_rating(rating)
    parts = [f'SIZE : {size_str} X {rating_str} X {_fmt_num(thk)}MM THK,{moc}']
    if standard:
        parts.append(f',{standard}')
    return ''.join(parts)


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
    isk_style = (item.get('isk_style') or '').strip()
    face_type = item.get('face_type') or ''
    standard = item.get('standard') or ''

    if gtype == 'ISK_RTJ':
        style = isk_style or 'STYLE-N'
        spec = f'({special})' if special else ''
        sep = ' ' if spec else ''
        std_str = f'TO SUIT {standard} (TYPE-RTJ)' if standard else 'TO SUIT ASME B16.5 (TYPE-RTJ)'
        return f'SIZE: {size_str} X {rating_str}, ISK {style} (TYPE F - RF) {spec}{sep}{std_str}'.strip()

    # Standard ISK
    out = f'SIZE: {size_str} X {rating_str}, INSULATING GASKET KIT'
    if isk_style:
        out += f', {isk_style}'
    if special:
        # Comma before (SET:...) when style is present; space-only otherwise
        out += f', ({special})' if isk_style else f' ({special})'
    tail = ', '.join(filter(None, [face_type, standard]))
    if tail:
        out += f', {tail}'
    return out


def _fmt_size(size: str, gtype: str) -> str:
    """Format size string. NB/DN sizes → 'DN N' for all types (EN convention)."""
    import re as _re
    if '"' in size or 'MM' in size:
        return size
    # NB size: "100 NB" / "20 NB" → "DN 100" / "DN 20"
    m = _re.match(r'^(\d+(?:\.\d+)?)\s*NB$', size.strip(), _re.IGNORECASE)
    if m:
        return f'DN {int(float(m.group(1)))}'
    return f'{size}"'


def _fmt_rating(rating: str) -> str:
    """Format rating for display: '150#' or 'PN 10'."""
    return rating  # already normalized


def _fmt_num(val) -> str:
    """Format number: no trailing zeros for integers."""
    if val is None:
        return ''
    f = float(val)
    return str(int(f)) if f == int(f) else str(f)
