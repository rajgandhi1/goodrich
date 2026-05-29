from core.formatter import format_description
from core.rules import apply_rules


def _processed_rtj(description: str) -> dict:
    item = apply_rules(
        {
            "description": description,
            "quantity": 1,
            "uom": "NOS",
        }
    )
    item["ggpl_description"] = format_description(item)
    return item


def test_rtj_rules_recover_ring_uns_material_profile_and_api_standard_from_description():
    cases = [
        (
            "R-94, RING JOINT GASKET, G10100 (LCS), OVAL, API 6A",
            "R-94",
            "LOW CARBON STEEL",
            "OVAL",
            "120 BHN HARDNESS",
            "SIZE : R-94 ,RTJ ,OVAL ,LOW CARBON STEEL ,120 BHN HARDNESS ,API 6A",
        ),
        (
            "R-53, RING JOINT GASKET, S30400 (SS304), OVAL, API 6A",
            "R-53",
            "SS304",
            "OVAL",
            "160 BHN HARDNESS",
            "SIZE : R-53 ,RTJ ,OVAL ,SS304 ,160 BHN HARDNESS ,API 6A",
        ),
        (
            "R-57, RING JOINT GASKET, S30400 (SS304), OVAL, API 6A",
            "R-57",
            "SS304",
            "OVAL",
            "160 BHN HARDNESS",
            "SIZE : R-57 ,RTJ ,OVAL ,SS304 ,160 BHN HARDNESS ,API 6A",
        ),
        (
            "RX-57, RING JOINT GASKET, S31600 (SS316), API 6A",
            "RX-57",
            "SS316",
            None,
            "160 BHN HARDNESS",
            "SIZE : RX-57 ,SS316 ,160 BHN HARDNESS ,API 6A",
        ),
        (
            "RX-31, RING JOINT GASKET, S31600 (SS316), API 6A",
            "RX-31",
            "SS316",
            None,
            "160 BHN HARDNESS",
            "SIZE : RX-31 ,SS316 ,160 BHN HARDNESS ,API 6A",
        ),
    ]

    for description, ring_no, moc, groove, hardness, ggpl_description in cases:
        item = _processed_rtj(description)

        assert item["status"] != "missing"
        assert item["ring_no"] == ring_no
        assert item["moc"] == moc
        assert item.get("rtj_groove_type") == groove
        assert item["rtj_hardness_spec"] == hardness
        assert item["standard"] == "API 6A"
        assert item["ggpl_description"] == ggpl_description
