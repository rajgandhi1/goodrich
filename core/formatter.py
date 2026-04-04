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
        parts = [f'SIZE : OD {_fmt_num(od)}MM X ID {_fmt_num(id_)}MM']
        if thickness:
            parts.append(f'X {_fmt_num(thickness)}MM THK')
        parts.append(f',{moc}')
        if special:
            parts.append(f',{special}')
        return ' '.join(parts)

    size = item.get('size')
    rating = item.get('rating')
    if not (size and rating and moc):
        return ''

    size_str = size if ('"' in size or 'NB' in size or 'MM' in size) else f'{size}"'
    rating_str = _fmt_rating(rating)

    parts = [f'SIZE : {size_str} X {rating_str} X {_fmt_num(thickness)}MM THK ,{moc}']
    if special:
        parts.append(f',{special}')
    if face:
        parts.append(f',{face}')
    if standard:
        # SPIRAL_WOUND appends standard with no comma; SOFT_CUT uses comma
        parts.append(standard if gtype == 'SPIRAL_WOUND' else f',{standard}')

    return ' '.join(parts)


def _fmt_rtj(item: dict) -> str:
    """SIZE : R-23 ,RTJ , OCT ,SOFTIRON ,90 BHN HARDNESS ,ASME B16.20"""
    ring_no = item.get('ring_no')
    moc = item.get('moc')
    groove = item.get('rtj_groove_type') or 'OCT'
    hardness_spec = item.get('rtj_hardness_spec')
    bhn = item.get('rtj_hardness_bhn')
    standard = item.get('standard') or 'ASME B16.20'
    if not (ring_no and moc):
        return ''
    parts = [f'SIZE : {ring_no} ,RTJ , {groove} ,{moc}']
    if hardness_spec:
        parts.append(f',{hardness_spec}')
    elif bhn:
        parts.append(f',{int(bhn)} BHN HARDNESS')
    parts.append(f',{standard}')
    return ' '.join(parts)


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
        parts = [f'SIZE: {_fmt_num(id_)}MM ID X {_fmt_num(od)}MM OD X {_fmt_num(thk)}MM THK,{moc}']
        if standard:
            parts.append(f',{standard}')
        return ''.join(parts)

    if not (size and rating and moc):
        return ''
    size_str = size if ('"' in size or 'NB' in size or 'MM' in size) else f'{size}"'
    rating_str = _fmt_rating(rating)
    parts = [f'SIZE: {size_str} X {rating_str} X {_fmt_num(thk)}MM THK,{moc}']
    if standard:
        parts.append(f',{standard}')
    return ''.join(parts)


def _fmt_dji(item: dict) -> str:
    """SIZE: {od}MM OD X {id}MM ID X {thk}MM THK, DOUBLE JACKET GASKET WITH {moc} + GRAPHITE FILLED"""
    od = item.get('od_mm')
    id_ = item.get('id_mm')
    thk = item.get('thickness_mm')
    moc = item.get('moc') or ''
    if not (od and id_):
        return ''
    thk_str = f' X {_fmt_num(thk)}MM THK' if thk else ''
    return f'SIZE: {_fmt_num(od)}MM OD X {_fmt_num(id_)}MM ID{thk_str}, DOUBLE JACKET GASKET WITH {moc} + GRAPHITE FILLED'


def _fmt_isk(item: dict) -> str:
    """SIZE: {size} X {rating}#, INSULATING GASKET, ..."""
    size = item.get('size')
    rating = item.get('rating')
    if not (size and rating):
        return ''
    size_str = size if ('"' in size or 'NB' in size or 'MM' in size) else f'{size}"'
    rating_str = _fmt_rating(rating)
    special = item.get('special') or ''
    if item.get('gasket_type') == 'ISK_RTJ':
        spec = f'({special}) ' if special else ''
        return f'SIZE: {size_str} X {rating_str}, ISK STYLE-N (TYPE F - RF) {spec}TO SUIT ASME B16.5 (TYPE-RTJ)'
    else:
        spec = f', {special}' if special else ' KIT'
        return f'SIZE: {size_str} X {rating_str}, INSULATING GASKET{spec}'


def _fmt_rating(rating: str) -> str:
    """Format rating for display: '150#' or 'PN 10'."""
    return rating  # already normalized


def _fmt_num(val) -> str:
    """Format number: no trailing zeros for integers."""
    if val is None:
        return ''
    f = float(val)
    return str(int(f)) if f == int(f) else str(f)
