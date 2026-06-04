from core.rules import apply_rules


def test_compact_size_rating_from_llm_size_field_is_split_before_validation():
    item = apply_rules(
        {
            "description": "Gasket, Flat GASKET,FLAT RING TYPE,1.5mm THK, RF FE ANSI B16.5, 150LB, COMPRESSED NON ASBESTOS FIBRE, ASME B16.21 2 X 150",
            "raw_description": "Gasket, Flat GASKET,FLAT RING TYPE,1.5mm THK, RF FE ANSI B16.5, 150LB, COMPRESSED NON ASBESTOS FIBRE, ASME B16.21 2 X 150",
            "gasket_type": "SOFT_CUT",
            "size": "2 X 150",
            "rating": None,
            "moc": "COMPRESSED NON ASBESTOS FIBRE",
            "face_type": "RF",
            "standard": "ASME B16.21",
            "thickness_mm": 1.5,
            "quantity": 73,
            "uom": "NOS",
        }
    )

    assert item["size"] == '2"'
    assert item["size_norm"] == '2"'
    assert item["rating"] == "150#"
    assert item["rating_norm"] == "150 #"
    assert item["moc"] == "CNAF"
    assert item["status"] == "ready"


def test_compact_size_rating_is_cleaned_when_rating_already_exists():
    item = apply_rules(
        {
            "gasket_type": "SPIRAL_WOUND",
            "raw_description": 'Gasket - Spiral Wound, Class 300, 1 1/2"',
            "size": '1 1/2" X 300',
            "rating": "300#",
            "quantity": 1,
            "sw_winding_material": "SS316",
            "sw_filler": "GRAPHITE",
            "sw_inner_ring": "SS316",
            "sw_outer_ring": "CS",
        }
    )

    assert item["size"] == '1 1/2"'
    assert item["size_norm"] == '1.5"'
    assert item["rating"] == "300#"


def test_spw_recovers_explicit_standard_and_thickness_before_defaults():
    item = apply_rules(
        {
            "gasket_type": "SPIRAL_WOUND",
            "raw_description": '4in x 4.5mm Nom Thk Gasket Spiral Wound CL1500 Stainless Steel 316 Windings Flexible Graphite Filler Stainless Steel 316 Inner Ring CS Outer Ring Dims to ASME B16.20',
            "size": '4"',
            "rating": "1500#",
            "quantity": 1,
            "sw_winding_material": "SS316",
            "sw_filler": "GRAPHITE",
            "sw_inner_ring": "SS316",
            "sw_outer_ring": "CS",
        }
    )

    assert item["thickness_mm"] == 4.5
    assert item["standard"] == "ASME B16.20"
    assert item["flags"] == []
    assert item["status"] == "ready"


def test_spw_asme_standard_default_does_not_force_review_when_core_fields_are_complete():
    item = apply_rules(
        {
            "gasket_type": "SPIRAL_WOUND",
            "raw_description": '1in x 4.5mm Nom Thk Gasket SPW CL900 Incoloy 825 Winding Flexible Graphite Filler CS IR Alloy 825 OR',
            "size": '1"',
            "rating": "900#",
            "quantity": 1,
            "thickness_mm": 4.5,
            "sw_winding_material": "ALLOY 825",
            "sw_filler": "GRAPHITE",
            "sw_inner_ring": "ALLOY 825",
            "sw_outer_ring": "CS",
        }
    )

    assert item["standard"] == "ASME B16.20"
    assert item["flags"] == []
    assert item["status"] == "ready"


def test_common_soft_cut_material_phrases_do_not_get_spelling_flags():
    modified_ptfe = apply_rules(
        {
            "gasket_type": "SOFT_CUT",
            "raw_description": '2" CL150 MODIFIED PTFE FLAT RING 1.5MM B16.21',
            "size": '2"',
            "rating": "150#",
            "moc": "MODIFIED PTFE",
            "face_type": "RF",
            "standard": "ASME B16.21",
            "thickness_mm": 1.5,
            "quantity": 1,
        }
    )
    graphite_sheet = apply_rules(
        {
            "gasket_type": "SHEET_GASKET",
            "raw_description": '3" CL150 3MM THK GRAFOIL SHEET GASKET',
            "size": '3"',
            "rating": "150#",
            "moc": "GRAFOIL",
            "face_type": "RF",
            "standard": "ASME B16.21",
            "thickness_mm": 3,
            "quantity": 1,
        }
    )
    composite_graphite = apply_rules(
        {
            "gasket_type": "SOFT_CUT",
            "raw_description": '12" CL150 pure graphite 98% impregnated inlet perforated plate 316SS inside cover 316SS flat ring',
            "size": '12"',
            "rating": "150#",
            "moc": "PURE GRAPHITE 98% - IMPREGNATED INLET PERFORATED PLATE 316SS - INSIDE COVER 316SS",
            "face_type": "RF",
            "standard": "ASME B16.21",
            "thickness_mm": 2,
            "quantity": 1,
        }
    )

    assert modified_ptfe["flags"] == []
    assert modified_ptfe["status"] == "ready"
    assert graphite_sheet["moc"] == "GRAPHITE SHEET"
    assert graphite_sheet["flags"] == []
    assert composite_graphite["flags"] == []
    assert composite_graphite["status"] == "ready"


def test_spw_preserves_customer_uns_material_codes():
    item = apply_rules(
        {
            "gasket_type": "SPIRAL_WOUND",
            "raw_description": 'SPIRAL WOUND GASKET 3" 150 RF UNS N06625 WINDING GRAPHITE FILLER UNS N06625 INNER RING SS 316 OUTER RING',
            "size": '3"',
            "rating": "150#",
            "quantity": 1,
            "sw_winding_material": "UNS N06625",
            "sw_filler": "GRAPHITE",
            "sw_inner_ring": "UNS N06625",
            "sw_outer_ring": "SS316",
        }
    )

    assert item["sw_winding_material"] == "UNS N06625"
    assert item["sw_inner_ring"] == "UNS N06625"
    assert "INCONEL" not in item["moc"]


def test_spw_generic_ss_components_use_same_row_specific_grade():
    item = apply_rules(
        {
            "gasket_type": "SPIRAL_WOUND",
            "raw_description": 'SPW gasket 4" 150 RF SS winding graphite filler SS inner and outer ring, outer ring material SS316',
            "size": '4"',
            "rating": "150#",
            "quantity": 1,
            "sw_winding_material": "SS",
            "sw_filler": "GRAPHITE",
            "sw_inner_ring": "SS",
            "sw_outer_ring": "SS316",
        }
    )

    assert item["sw_winding_material"] == "SS316"
    assert item["sw_inner_ring"] == "SS316"
    assert item["sw_outer_ring"] == "SS316"


def test_isk_fire_safety_defaults_to_non_fire_safe():
    item = apply_rules(
        {
            "gasket_type": "ISK",
            "raw_description": 'ISK Type-F 6" 150 RF GRE G10 gasket with SS316 core',
            "size": '6"',
            "rating": "150#",
            "quantity": 1,
            "isk_gasket_material": "GRE G10",
            "isk_core_material": "SS316",
        }
    )

    assert item["isk_fire_safety"] == "NON FIRE SAFE"
