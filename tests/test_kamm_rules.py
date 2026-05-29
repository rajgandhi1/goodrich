from core.formatter import format_description
from core.rules import apply_rules


def _processed_kamm(description: str) -> dict:
    item = apply_rules(
        {
            "description": description,
            "raw_description": description,
            "quantity": 1,
            "uom": "NOS",
        }
    )
    item["ggpl_description"] = format_description(item)
    return item


def test_camprofile_od_id_rules_recover_dimensions_materials_and_type_from_description():
    cases = [
        (
            "SHELL COVER GASKET (CAMPROFILE), FOR TAG 61-A-0201A/B/C-E-01/02/04 "
            "CAMPROFILE GASKET, TYPE-1, CORE MAT'L: SS316L, 3.0MM THICKNESS WITH "
            "0.5MM GRAPHITE ON BOTH SIDES. SIZE: GASKET (CAMPROFILE) OD=560 ID=536 "
            "Th=4 (3+2x0,5) MATERIAL: GRAPHITE / SS316L",
            560,
            536,
            4,
            3,
            None,
            "TYPE-1",
            "SIZE : OD 560MM X ID 536MM X 4MM THK (3MM CORE THK) KAMMPROFILE SS316L GRAPHITE LAYER ON BOTH SIDES, TYPE-1",
        ),
        (
            "CHANNEL COVER / CHANNEL HEAD GASKET (CAMPROFILE) FOR TAG 61-A-0201A/B/C-E-01/02/04 "
            "CAMPROFILE GASKET, TYPE-6, CORE MAT'L: SS316L, 3.0MM THICKNESS WITH "
            "0.5MM GRAPHITE ON BOTH SIDES. SIZE: OD=462MM X ID=438MM X B=10MM X 4.0MM "
            "MATERIAL: GRAPHITE / SS316L",
            462,
            438,
            4,
            3,
            "10MM",
            "TYPE-6, B=10MM",
            "SIZE : OD 462MM X ID 438MM X 4MM THK (3MM CORE THK) KAMMPROFILE SS316L GRAPHITE LAYER ON BOTH SIDES, TYPE-6, B=10MM",
        ),
        (
            "TUBE SHEET TO SHEEL GASKET (CAMPROFILE) FOR TAG 61-A-0201A/B/C-E-01/02/04 "
            "CAMPROFILE GASKET, TYPE-1, CORE MAT'L: SS316L, 3.0MM THICKNESS WITH "
            "0.5MM GRAPHITE ON BOTH SIDES. SIZE: OD=462MM X ID=438MM X 4.0MM "
            "MATERIAL: GRAPHITE / SS316L",
            462,
            438,
            4,
            3,
            None,
            "TYPE-1",
            "SIZE : OD 462MM X ID 438MM X 4MM THK (3MM CORE THK) KAMMPROFILE SS316L GRAPHITE LAYER ON BOTH SIDES, TYPE-1",
        ),
    ]

    for description, od, id_, thk, core_thk, rib, special, ggpl_description in cases:
        item = _processed_kamm(description)

        assert item["status"] == "ready"
        assert item["gasket_type"] == "KAMM"
        assert item["size_type"] == "OD_ID"
        assert item["od_mm"] == od
        assert item["id_mm"] == id_
        assert item["thickness_mm"] == thk
        assert item["kamm_core_thk"] == core_thk
        assert item["kamm_core_material"] == "SS316L"
        assert item["kamm_surface_material"] == "GRAPHITE"
        assert item.get("kamm_rib") == rib
        assert item.get("special") == special
        assert item["ggpl_description"] == ggpl_description
