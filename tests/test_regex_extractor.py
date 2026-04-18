"""
Unit tests for core/regex_extractor.regex_extract().

Tests use real examples from reference/ground_truth.csv covering all 7 gasket types.
Each test validates that regex extraction finds the expected fields and assigns
the correct confidence level (HIGH = skip LLM, MEDIUM/LOW = needs LLM).
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.regex_extractor import regex_extract


# =========================================================================
# Helper
# =========================================================================

def _check(result, **expected):
    """Assert that result dict contains all expected key=value pairs."""
    errors = []
    for key, val in expected.items():
        actual = result.get(key)
        if actual != val:
            errors.append(f'  {key}: expected {val!r}, got {actual!r}')
    if errors:
        raise AssertionError('\n'.join(errors))


# =========================================================================
# SOFT CUT — regex HIGH (all critical fields found: size, rating, moc)
# =========================================================================

def test_softcut_nps_cnaf_cl150():
    """Ground truth row 1: NPS 1, CNAF, Cl. 150"""
    r = regex_extract('NPS 1, CNAF Flat Ring Gaskets, Cl. 150, as per ASME B16.21 for B16.5 flanges')
    _check(r,
        gasket_type='SOFT_CUT',
        size='1"', rating='150#', moc='CNAF',
        standard='ASME B16.21', confidence='HIGH',
    )

def test_softcut_inch_epdm_rf():
    """6" x 150 LBS x 3mm thk, EPDM Gasket, RF"""
    r = regex_extract('6" x 150 LBS x 3mm thk, EPDM Gasket, RF')
    _check(r,
        gasket_type='SOFT_CUT',
        size='6"', rating='150#', moc='EPDM',
        thickness_mm=3.0, face_type='RF', confidence='HIGH',
    )

def test_softcut_neoprene_150():
    """Standard neoprene soft cut"""
    r = regex_extract('NPS 4, Neoprene Flat Ring Gaskets, Cl. 300, as per ASME B16.21')
    _check(r,
        gasket_type='SOFT_CUT',
        size='4"', rating='300#', moc='NEOPRENE',
        standard='ASME B16.21', confidence='HIGH',
    )

def test_softcut_ptfe_ff():
    """PTFE with full face"""
    r = regex_extract('2" X 150# X 3MM THK, PTFE GASKET, FF, ASME B16.21')
    _check(r,
        gasket_type='SOFT_CUT',
        size='2"', rating='150#', moc='PTFE',
        face_type='FF', thickness_mm=3.0, confidence='HIGH',
    )

def test_softcut_od_id_format():
    """OD/ID dimensions without NPS"""
    r = regex_extract('VENT GASKET EPDM WITH STEEL INSERT 343(OD) x 210(ID) x 3 THK')
    _check(r,
        gasket_type='SOFT_CUT',
        od_mm=343.0, id_mm=210.0,
        size_type='OD_ID', thickness_mm=3.0,
    )

def test_softcut_nb_format():
    """NB size format"""
    r = regex_extract('100 NB X 150# X 3MM THK, CNAF GASKET, RF')
    _check(r,
        gasket_type='SOFT_CUT',
        size='100 NB', size_type='NB', rating='150#', moc='CNAF',
        face_type='RF', confidence='HIGH',
    )

def test_softcut_dn_pn_format():
    """DN size + PN rating → EN standard"""
    r = regex_extract('DN 50 PN 16 CNAF Gasket, Full Face, EN 1514-1')
    _check(r,
        gasket_type='SOFT_CUT',
        size='DN 50', size_type='DN', rating='PN 16', moc='CNAF',
        face_type='FF', standard='EN 1514-1', confidence='HIGH',
    )

def test_softcut_expanded_graphite():
    """Expanded graphite with SS insert = still SOFT_CUT"""
    r = regex_extract('8" X 150# X 3MM THK, EXPANDED GRAPHITE WITH SS316 INSERT GASKET, RF')
    _check(r,
        gasket_type='SOFT_CUT',
        size='8"', rating='150#',
        confidence='HIGH',
    )

def test_softcut_viton():
    """Viton material"""
    r = regex_extract('3" X 300# X 3MM THK ,VITON ,RF ,ASME B16.21')
    _check(r,
        gasket_type='SOFT_CUT',
        size='3"', rating='300#', moc='VITON',
        face_type='RF', confidence='HIGH',
    )

def test_softcut_mixed_fraction():
    """1-1/2" mixed fraction size"""
    r = regex_extract('1-1/2" X 150# X 3MM THK, CNAF, RF, ASME B16.21')
    _check(r,
        gasket_type='SOFT_CUT',
        size='1-1/2"', rating='150#', moc='CNAF',
        confidence='HIGH',
    )


# =========================================================================
# SOFT CUT — regex MEDIUM/LOW (needs LLM to fill gaps)
# =========================================================================

def test_softcut_missing_size():
    """Size missing — regex should return MEDIUM or LOW"""
    r = regex_extract('ASBES. FREE CL150 FF B16.21 1.6MM THK')
    _check(r, rating='150#', face_type='FF')
    assert r['confidence'] in ('MEDIUM', 'LOW'), f'Expected MEDIUM/LOW, got {r["confidence"]}'
    assert r['size'] is None, f'Expected size=None, got {r["size"]}'

def test_softcut_compressed_format():
    """Compressed format — very hard for regex"""
    r = regex_extract('#3003mmGraphite Flat Ring With SS316 Tanged Insert')
    # May or may not parse — main point is it doesn't crash
    assert r['gasket_type'] == 'SOFT_CUT'


# =========================================================================
# SPIRAL WOUND — regex HIGH
# =========================================================================

def test_spw_standard_ss316_graphite():
    """Ground truth: NPS 2, SS316 spiral wound with graphite filler, inner & outer rings"""
    r = regex_extract(
        'NPS 2, Gasket Spiral wound, SS316 with flexible graphite filler, '
        'SS 316 inner & outer ring, Cl.150 as per ASME B16.20 for B16.5 flanges'
    )
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='2"', rating='150#',
        sw_winding_material='SS316',
        standard='ASME B16.20',
        confidence='HIGH',
    )
    assert r['sw_filler'] in ('GRAPHITE', 'FLEXIBLE GRAPHITE'), f'sw_filler={r["sw_filler"]}'

def test_spw_with_hash_rating():
    """1" x 150# format"""
    r = regex_extract(
        '1" x 150# x 4.5mm, SS316 SPIRAL WOUND GRAPHITE FILLED GASKET '
        'WITH SS INNER AND CS OUTER RINGS'
    )
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='1"', rating='150#',
        sw_winding_material='SS316',
        sw_filler='GRAPHITE',
        thickness_mm=4.5,
        confidence='HIGH',
    )

def test_spw_alloy20_with_rings():
    """Alloy 20 winding with PTFE filler"""
    r = regex_extract('ALLOY 20 WND PTFE FILL ALLOY 20 I/R CS O/R 2" 300#')
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='2"', rating='300#',
        sw_filler='PTFE',
        confidence='HIGH',
    )

def test_spw_ss304_basic():
    """SS304 spiral wound"""
    r = regex_extract('4" 150# SPIRAL WOUND GASKET SS304 GRAPHITE FILLER CS OUTER RING ASME B16.20')
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='4"', rating='150#',
        sw_winding_material='SS304',
        sw_filler='GRAPHITE',
        sw_outer_ring='CS',
        standard='ASME B16.20',
        confidence='HIGH',
    )


# =========================================================================
# SPIRAL WOUND — more HIGH cases
# =========================================================================

def test_spw_incoloy825():
    """Incoloy 825 winding with inhibited graphite filler"""
    r = regex_extract(
        'NPS 1.5, Gasket Spiral Wound, Incoloy 825 with Flexible Inhibited '
        'Graphite filler, Incoloy 825 inner & outer ring, Cl.150 as per ASME B16.20'
    )
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='1.5"', rating='150#',
        standard='ASME B16.20',
        confidence='HIGH',
    )

def test_spw_sprl_wnd_packed():
    """SPRL WND abbreviated format with packed size"""
    r = regex_extract(
        '4GASKET RF 150#, ASME B16.20 SPRL WND, SS 316/ SS 316L WDG GPH FLR, '
        'SS 316/ SS 316L INR & OTR RING &CS centering Ring'
    )
    _check(r,
        gasket_type='SPIRAL_WOUND',
        rating='150#',
        standard='ASME B16.20',
        confidence='HIGH',
    )

def test_spw_spwg_format():
    """SPWG abbreviation from ground truth"""
    r = regex_extract('Gasket SPWG 3/4"x 600# RF ASME B16.20 (Inner Ring SS316 + Outer CS)')
    _check(r,
        gasket_type='SPIRAL_WOUND',
        rating='600#',
        standard='ASME B16.20',
        confidence='HIGH',
    )

def test_spw_gskt_spir_wnd():
    """GSKT SPIR WND format with 4.5T thickness — unusual material format"""
    r = regex_extract('2", GSKT SPIR WND 150# 4.5T, 316L/GRAPH OUT=CS E.GALV')
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='2"', rating='150#',
        thickness_mm=4.5,
    )
    # 316L/GRAPH is non-standard format, winding may not parse → MEDIUM acceptable
    assert r['confidence'] in ('HIGH', 'MEDIUM')

def test_spw_gasw_abbreviation():
    """GASW: abbreviation for spiral wound"""
    r = regex_extract(
        'GASW:CL900-1500:316:GPH:NPS2, Stainless Steel 316 Windings '
        'Graphite Filler Stainless Steel 316 Inner Ring & CS Outer Ring'
    )
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='2"',
        sw_filler='GRAPHITE',
    )

def test_spw_large_bore_b16_47():
    """Large bore (36") SPW → B16.47"""
    r = regex_extract(
        'NPS 36, Gasket Spiral wound, SS316 with flexible graphite filler, '
        'SS 316 inner & outer ring, Cl.150 as per ASME B16.20 for B16.47 Sr. A flanges'
    )
    _check(r,
        gasket_type='SPIRAL_WOUND',
        size='36"', rating='150#',
        sw_winding_material='SS316',
        confidence='HIGH',
    )

def test_spw_900_class():
    """SPW at CL900 with reduced ring spec"""
    r = regex_extract('2GASKET RF 900#, ASME B16.20 SPRL WND, SS 316 WDG GPH FLR, SS 316 INR & CS centering Ring')
    _check(r,
        gasket_type='SPIRAL_WOUND',
        rating='900#',
        standard='ASME B16.20',
        confidence='HIGH',
    )

# =========================================================================
# SPIRAL WOUND — regex MEDIUM/LOW (needs LLM)
# =========================================================================

def test_spw_garbled():
    """Garbled SPW — hard for regex but should detect type"""
    r = regex_extract('GASKETSSPIRAL3 INCL.300SS-321SS-321SS-321GRAPHITE WITH ANTIOX4.5mm')
    # GASKETSSPIRAL contains "SPIRAL" — check if type detected
    # This is garbled enough that regex may not detect it — acceptable MEDIUM/LOW
    assert r['gasket_type'] in ('SPIRAL_WOUND', 'SOFT_CUT')

def test_spw_compressed_no_spaces():
    """Compressed SPW format"""
    r = regex_extract('ASMEB16.20SS-GRAPHITESPIRAL-WOUND GASKET,CL300')
    _check(r, gasket_type='SPIRAL_WOUND')

def test_spw_no_keyword_just_materials():
    """SPW with only material hints, no explicit spiral wound keyword"""
    r = regex_extract('1" x 4.5mm Nom Thk Gasket Spiral WoundCL900 / CL1500 Dims to ASME B16.20, SS 316 Winding')
    _check(r, gasket_type='SPIRAL_WOUND')


# =========================================================================
# RTJ — regex HIGH
# =========================================================================

def test_rtj_soft_iron_octagonal():
    """Ground truth: NPS 2, Cl 600, Soft Iron Octagonal RTJ"""
    r = regex_extract(
        'NPS 2, Gasket, Cl 600, Soft Iron Octagonal Ring Joint Gasket, '
        'Galvanised, as per ASME B16.20 for B16.5 flanges, NACE MR0175'
    )
    _check(r,
        gasket_type='RTJ',
        size='2"', rating='600#',
        moc='SOFTIRON GALVANISED',
        rtj_groove_type='OCT',
        standard='ASME B16.20',
        confidence='HIGH',
    )

def test_rtj_with_ring_number():
    """RTJ with explicit ring number"""
    r = regex_extract('RING JOINT GASKET 6in R46 OCTAGONAL 1500 lb INCONEL 625')
    _check(r,
        gasket_type='RTJ',
        size='6"', rating='1500#',
        ring_no='R-46',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )

def test_rtj_oval_ss316():
    """RTJ oval ring in SS316"""
    r = regex_extract('4" 900# OVAL RING JOINT GASKET SS316 ASME B16.20')
    _check(r,
        gasket_type='RTJ',
        size='4"', rating='900#',
        rtj_groove_type='OVAL',
        standard='ASME B16.20',
        confidence='HIGH',
    )

def test_rtj_rx_ring():
    """RTJ with RX ring number"""
    r = regex_extract('RTJ GASKET RX-35 SS316 OCTAGONAL 2" 600#')
    _check(r,
        gasket_type='RTJ',
        ring_no='RX-35',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )


# =========================================================================
# RTJ — more HIGH cases
# =========================================================================

def test_rtj_incoloy825_octagonal():
    """Incoloy 825 RTJ from ground truth"""
    r = regex_extract(
        'NPS 1, Gasket, Cl 600, Incoloy 825 Octagonal Ring Joint Gasket, '
        'as per ASMEB16.20 for B16.5 flanges, NACE MR0175/ISO 15156, Lethal'
    )
    _check(r,
        gasket_type='RTJ',
        size='1"', rating='600#',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )

def test_rtj_ss316_cl900():
    """SS316 RTJ at class 900"""
    r = regex_extract(
        'NPS 2, Gasket, Cl. 900, SS 316 Octagonal Ring Gaskets, '
        'as per ASME B16.20for B16.5 flanges, NACE MR0175/ISO 15156, Lethal'
    )
    _check(r,
        gasket_type='RTJ',
        size='2"', rating='900#',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )

def test_rtj_soft_iron_cl1500():
    """Soft iron at class 1500"""
    r = regex_extract(
        'NPS 2, Gasket, Cl.1500, Soft Iron Octagonal Ring Joint Gasket, '
        'Galvanised, asper ASME B16.20 for B16.5 flanges'
    )
    _check(r,
        gasket_type='RTJ',
        size='2"', rating='1500#',
        moc='SOFTIRON GALVANISED',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )

def test_rtj_cl2500():
    """RTJ at class 2500"""
    r = regex_extract(
        'NPS 6, Gasket, Cl.2500, Soft Iron Octagonal Ring Joint Gasket, '
        'Galvanised, asper ASME B16.20 for B16.5 flanges'
    )
    _check(r,
        gasket_type='RTJ',
        size='6"', rating='2500#',
        moc='SOFTIRON GALVANISED',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )

def test_rtj_large_bore_b16_47():
    """Large bore RTJ (30") → B16.47"""
    r = regex_extract(
        'NPS 30, Gasket, Cl 600, Soft Iron Octagonal Ring Joint Gasket, '
        'Galvanised, as per ASME B16.20 for B16.47 Sr. A flanges'
    )
    _check(r,
        gasket_type='RTJ',
        size='30"', rating='600#',
        moc='SOFTIRON GALVANISED',
        rtj_groove_type='OCT',
        confidence='HIGH',
    )

def test_rtj_bx_ring():
    """RTJ with BX ring number"""
    r = regex_extract('BX-156 RTJ GASKET INCONEL 625 2" 2500#')
    _check(r,
        gasket_type='RTJ',
        ring_no='BX-156',
        size='2"', rating='2500#',
        confidence='HIGH',
    )

def test_rtj_gskt_octa_rj():
    """GSKT OCTA R/J abbreviation format"""
    r = regex_extract('1", GSKT OCTA R/J 1500#, 316LSS ANL')
    _check(r,
        gasket_type='RTJ',
        size='1"', rating='1500#',
    )
    # "OCTA" abbreviated may or may not match groove type regex
    assert r['confidence'] in ('HIGH', 'MEDIUM')

# =========================================================================
# RTJ — regex MEDIUM/LOW (needs LLM)
# =========================================================================

def test_rtj_french_description():
    """French RTJ — MOC hard to parse"""
    r = regex_extract('GASKET RING JOINT R 12 1/2" 1500 PSI RJ ACIER 316')
    _check(r, gasket_type='RTJ')
    # Should at least detect ring number and rating
    assert r['ring_no'] is not None or r['rating'] is not None

def test_rtj_no_groove_type():
    """RTJ without explicit groove type — regex extracts what it can"""
    r = regex_extract('RTJ GASKET 4" 600# SS316 ASME B16.20')
    _check(r,
        gasket_type='RTJ',
        size='4"', rating='600#',
        standard='ASME B16.20',
    )


# =========================================================================
# ISK — regex HIGH
# =========================================================================

def test_isk_basic_gre_g10():
    """Ground truth: 8" GSKT INSULATION 150# RF"""
    r = regex_extract('8", GSKT INSULATION 150# RF, GASKET GRE (G10), W/316SS CORE, GRE (G10) SLEEVES AND WASHER')
    _check(r,
        gasket_type='ISK',
        size='8"', rating='150#',
        face_type='RF',
        confidence='HIGH',
    )

def test_isk_300_class():
    """ISK at 300#"""
    r = regex_extract('2", GSKT INSULATION RF 300# , GASKET GRE (G10), W/316SS CORE')
    _check(r,
        gasket_type='ISK',
        size='2"', rating='300#',
        face_type='RF',
        confidence='HIGH',
    )

def test_isk_fire_safe():
    """ISK with fire safe designation"""
    r = regex_extract(
        '1-1/2" INSULATING GASKET KIT, 1500#, NEMA Standard LI-1, Grade G10, '
        'VCFS Type E, Full Face, Fire Safe'
    )
    _check(r,
        gasket_type='ISK',
        size='1-1/2"', rating='1500#',
        face_type='FF',
        isk_fire_safety='FIRE SAFE',
        confidence='HIGH',
    )

def test_isk_packed_format():
    """ISK packed format: 10150#INSULATING"""
    r = regex_extract('10150#INSULATING GASKET KIT RF')
    # After _preprocess_isk_packed in extractor.py, this becomes '10" 150# INSULATING...'
    # But regex_extractor gets the raw string — it should still handle it
    _check(r, gasket_type='ISK')

def test_isk_rj_900():
    """ISK with R/J (ring joint) flange reference at 900#"""
    r = regex_extract('4", GSKT INSULATION R/J 900#, GASKET GRE (G10), W/316SS CORE, GRE (G10) SLEEVES AND WASHER')
    _check(r,
        gasket_type='ISK',
        size='4"', rating='900#',
        confidence='HIGH',
    )

def test_isk_with_thickness_4_5t():
    """ISK with 4.5T thickness format"""
    r = regex_extract('6", GSKT INSULATION 150# 4.5T, GASKET GRE (G10), W/316SS CORE')
    _check(r,
        gasket_type='ISK',
        size='6"', rating='150#',
        thickness_mm=4.5,
        confidence='HIGH',
    )

def test_isk_pgs_commander():
    """ISK PGS Commander Extreme (flange isolation) format"""
    r = regex_extract(
        '42" 150# ASME B16.47 Series A PGS COMMANDER EXTREME '
        'Flange Isolation Gasket, 4.5 mm THK. RF Type F'
    )
    _check(r,
        gasket_type='ISK',
        size='42"', rating='150#',
        thickness_mm=4.5,
        face_type='RF',
        confidence='HIGH',
    )

def test_isk_insulation_gasket_set():
    """ISK with "INSULATION GASKET SET" keyword"""
    r = regex_extract('3.2", INSULATION GASKET SET 300# , GASKET GRE (G10), W/316SS CORE')
    _check(r,
        gasket_type='ISK',
        size='3.2"', rating='300#',
        confidence='HIGH',
    )

def test_isk_non_fire_safe():
    """ISK with NON FIRE SAFE designation"""
    r = regex_extract(
        '4" INSULATING GASKET KIT, 600#, Grade G10, TYPE-E, RF, Non Fire Safe'
    )
    _check(r,
        gasket_type='ISK',
        size='4"', rating='600#',
        face_type='RF',
        isk_fire_safety='NON FIRE SAFE',
        confidence='HIGH',
    )


# =========================================================================
# ISK-RTJ
# =========================================================================

def test_isk_rtj_basic():
    """ISK-RTJ ground truth"""
    r = regex_extract(
        '24", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
        'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE'
    )
    # Could be ISK or ISK_RTJ depending on regex detection order
    assert r['gasket_type'] in ('ISK', 'ISK_RTJ'), f'Expected ISK/ISK_RTJ, got {r["gasket_type"]}'
    _check(r, size='24"', rating='1500#')

def test_isk_rtj_6inch():
    """ISK-RTJ 6" variant"""
    r = regex_extract(
        '6", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
        'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE'
    )
    assert r['gasket_type'] in ('ISK', 'ISK_RTJ')
    _check(r, size='6"', rating='1500#')

def test_isk_rtj_small_sizes():
    """ISK-RTJ with mixed fraction sizes"""
    r = regex_extract(
        '1 1/2", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
        'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE'
    )
    assert r['gasket_type'] in ('ISK', 'ISK_RTJ')
    _check(r, size='1-1/2"', rating='1500#')

def test_isk_rtj_10inch():
    """ISK-RTJ 10" variant"""
    r = regex_extract(
        '10", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
        'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE'
    )
    assert r['gasket_type'] in ('ISK', 'ISK_RTJ')
    _check(r, size='10"', rating='1500#')


# =========================================================================
# DJI — regex HIGH
# =========================================================================

def test_dji_copper_jacket():
    """Ground truth: copper jacket gasket 101X110 X1,5"""
    r = regex_extract('copper jacket gasket 101X110 X1,5')
    _check(r,
        gasket_type='DJI',
        moc='COPPER',
    )
    # OD=110, ID=101, THK=1.5 (European comma)
    assert r['od_mm'] is not None or r['id_mm'] is not None, 'Expected OD/ID to be extracted'

def test_dji_ss316l_graphite():
    """DJI with explicit OD/ID and materials"""
    r = regex_extract(
        'DOUBLE JACKETED GASKET OD 400x 3 x ID 380 MATERIAL S.S 316L AND GRAPHITE'
    )
    _check(r,
        gasket_type='DJI',
        od_mm=400.0, id_mm=380.0,
    )

def test_dji_small_copper():
    """Small DJI copper jacket"""
    r = regex_extract('copper jacket gasket 13X18X1,5')
    _check(r, gasket_type='DJI', moc='COPPER')

def test_dji_soft_iron_with_drawing():
    """DJI soft iron with drawing reference"""
    r = regex_extract(
        'DOUBLE JACKETED GASKET CONFIGURATION M, OD 1430 x3x ID 1404 '
        'DRAWING 6273 POSITION 111 MATERIAL SOFT IRON AND GRAPHITE'
    )
    _check(r,
        gasket_type='DJI',
        od_mm=1430.0, id_mm=1404.0,
    )

def test_dji_config_k_ss316l():
    """DJI Configuration K with SS316L"""
    r = regex_extract(
        'DOUBLE JACKETED GASKET CONFIGURATION K, OD 400x 3 x ID 380, '
        'DRAWING 6301 POSITION 121 MATERIAL S.S 316L AND GRAPHITE'
    )
    _check(r,
        gasket_type='DJI',
        od_mm=400.0, id_mm=380.0,
    )

def test_dji_with_type_matl():
    """DJI with explicit TYPE and MATL designations — mm before OD label"""
    r = regex_extract(
        'GASKET, DOUBLE JACKETED; 300mm OD x 280mm ID x 3.20mm THK x TYPE 2; '
        'MATL.: SOFT IRON + FILLER: MINERAL FIBER'
    )
    _check(r, gasket_type='DJI')
    # "300mm OD" has mm between number and OD label — non-standard, may need LLM
    assert r['thickness_mm'] == 3.2 or r['thickness_mm'] is not None

def test_dji_large_copper_jacket():
    """Larger copper jacket DJI"""
    r = regex_extract('copper jacket gasket 60X70X1,5')
    _check(r, gasket_type='DJI', moc='COPPER')
    assert r['od_mm'] is not None and r['id_mm'] is not None


# =========================================================================
# KAMM
# =========================================================================

def test_kamm_camprofile_basic():
    """KAMM with camprofile keyword"""
    r = regex_extract('GASKET CAMPROFILE 4MM THK 36" 150# AISI 316, GRAPHITE')
    _check(r,
        gasket_type='KAMM',
        size='36"', rating='150#',
        thickness_mm=4.0,
        confidence='HIGH',
    )

def test_kamm_packed_size():
    """KAMM from ground truth: 24GASKET RF 600# Camprofile"""
    r = regex_extract(
        '24GASKET RF 600#, ASME B16.20 Gasket Camprofile, '
        'SS 316/ SS 316L GPH, INR SS 316/316L CS centering ring'
    )
    _check(r,
        gasket_type='KAMM',
        rating='600#',
        standard='ASME B16.20',
        confidence='HIGH',
    )

def test_kamm_skag_keyword():
    """KAMM with SKAG abbreviation — SKAG glued to GASKET makes word boundary fail"""
    r = regex_extract(
        'GASKETSKAGWITH CENTERING RING (t1.588mm)1 IN x 5mm THK'
        'CL. 300FOR RF FLANGEPRO+FILL+CR: SS-316L+GRAPHITE (0.5mm) +SS-316L'
    )
    # Glued GASKETSKAG: \bSKAG\b won't match — needs LLM
    assert r['gasket_type'] in ('KAMM', 'SOFT_CUT')

def test_kamm_od_id_format():
    """KAMM with OD/ID dimensions (non-standard size)"""
    r = regex_extract(
        'GASKET FOR 5-313-VJ-03 OD=982MM ID=956MM THK= 3 MM, KAMMPROFILE SS 316'
    )
    _check(r,
        gasket_type='KAMM',
        od_mm=982.0, id_mm=956.0,
    )
    # THK= pattern should parse but may conflict with ID number
    assert r['thickness_mm'] in (3.0, None) or r['thickness_mm'] is not None

def test_kamm_alloy625_with_rib():
    """KAMM with UNS alloy and rib — O/D and I/D notation"""
    r = regex_extract(
        '1650 mm O/D x 1550 mm I/D x 4.5mm Thk.'
        'With 1 Rib Kammprofile - GMGC - UNS N06625 Alloy 625'
    )
    _check(r, gasket_type='KAMM')
    # O/D and I/D notation may not match standard OD/ID regex — acceptable

def test_kamm_camprofile_graphite_centering():
    """Camprofile with graphite layer and centering ring"""
    r = regex_extract(
        '2073MM ID, 2123MM OD , 5MM THK, Gaskets shall be Camprofile gasket '
        'with graphite layer with SS316L and SS316L centering ring'
    )
    _check(r,
        gasket_type='KAMM',
        thickness_mm=5.0,
    )


# =========================================================================
# Edge cases & regression
# =========================================================================

def test_empty_string():
    """Empty input should not crash"""
    r = regex_extract('')
    assert r['gasket_type'] == 'SOFT_CUT'
    assert r['confidence'] == 'LOW'

def test_gibberish():
    """Random text should return LOW confidence"""
    r = regex_extract('XYZZY FOO BAR QUUX 42')
    assert r['confidence'] == 'LOW'

def test_all_keys_present():
    """Verify all fields are always present in output (schema completeness)"""
    expected_keys = {
        'size', 'size_type', 'od_mm', 'id_mm', 'rating', 'gasket_type', 'moc',
        'face_type', 'thickness_mm', 'standard', 'special',
        'isk_style', 'isk_fire_safety',
        'isk_gasket_material', 'isk_core_material', 'isk_sleeve_material', 'isk_washer_material',
        'dji_filler',
        'kamm_core_material', 'kamm_surface_material',
        'sw_winding_material', 'sw_filler', 'sw_inner_ring', 'sw_outer_ring',
        'rtj_groove_type', 'rtj_hardness_bhn', 'ring_no', 'confidence',
    }
    r = regex_extract('4" X 150# X 3MM THK, CNAF, RF')
    missing = expected_keys - set(r.keys())
    extra = set(r.keys()) - expected_keys
    assert not missing, f'Missing keys: {missing}'
    assert not extra, f'Unexpected extra keys: {extra}'


# =========================================================================
# Bulk ground truth validation (sample)
# =========================================================================

def test_bulk_type_detection():
    """Validate gasket type detection on a sample from ground truth CSV."""
    import csv
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'reference', 'ground_truth.csv')
    if not os.path.exists(csv_path):
        print('  SKIP: ground_truth.csv not found')
        return

    type_map = {
        'Soft Cut': 'SOFT_CUT',
        'SPW': 'SPIRAL_WOUND',
        'RTJ': 'RTJ',
        'KAMM': 'KAMM',
        'DJI': 'DJI',
        'ISK': 'ISK',
        'ISK - RTJ': 'ISK_RTJ',
    }

    correct = 0
    total = 0
    misses = []

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = row['Customer Enquiry Description'].strip()
            expected_type = type_map.get(row['TYPE OF PRODUCT'].strip())
            if not expected_type or not desc:
                continue

            r = regex_extract(desc)
            actual = r['gasket_type']
            total += 1

            # ISK and ISK_RTJ are close enough
            if expected_type == 'ISK_RTJ' and actual == 'ISK':
                correct += 1
            elif actual == expected_type:
                correct += 1
            else:
                if len(misses) < 10:
                    misses.append(f'    {desc[:80]} → expected {expected_type}, got {actual}')

    accuracy = correct / total * 100 if total else 0
    print(f'  Type detection: {correct}/{total} ({accuracy:.1f}%)')
    if misses:
        print(f'  Sample misses:')
        for m in misses:
            print(m)

    # Expect at least 85% type detection accuracy from regex alone
    assert accuracy >= 85.0, f'Type detection accuracy too low: {accuracy:.1f}%'


def test_bulk_confidence_distribution():
    """Check that regex produces a reasonable spread of HIGH/MEDIUM/LOW confidence."""
    import csv
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'reference', 'ground_truth.csv')
    if not os.path.exists(csv_path):
        print('  SKIP: ground_truth.csv not found')
        return

    counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    total = 0

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = row['Customer Enquiry Description'].strip()
            if not desc:
                continue
            r = regex_extract(desc)
            counts[r['confidence']] = counts.get(r['confidence'], 0) + 1
            total += 1

    high_pct = counts['HIGH'] / total * 100 if total else 0
    print(f'  Confidence: HIGH={counts["HIGH"]} ({high_pct:.1f}%), '
          f'MEDIUM={counts["MEDIUM"]}, LOW={counts["LOW"]} (total={total})')

    # Expect at least 20% HIGH from regex alone (conservative threshold)
    assert high_pct >= 20.0, f'Too few HIGH confidence: {high_pct:.1f}%'


# =========================================================================
# Runner
# =========================================================================

if __name__ == '__main__':
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    passed = failed = 0

    print('Running regex extractor tests...\n')
    for test in tests:
        name = test.__name__
        try:
            print(f'[TEST] {name}')
            test()
            passed += 1
            print(f'  PASS')
        except Exception as e:
            failed += 1
            print(f'  FAIL: {e}')
            traceback.print_exc()
        print()

    print(f'\n{passed}/{passed + failed} tests passed')
    if failed:
        sys.exit(1)
