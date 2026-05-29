from core.formatter import format_description
from core.rules import apply_rules


def _processed_isk(description: str) -> dict:
    item = apply_rules(
        {
            "description": description,
            "quantity": 1,
            "uom": "NOS",
        }
    )
    item["ggpl_description"] = format_description(item)
    return item


def test_isk_fcs_rules_recover_style_size_rating_set_components_and_flange_standard():
    descriptions = [
        'ISK STYLE-FCS (TYPE F - RF) 2" X 600# (SET: G10/G11 GASKET WITH SS316 6.2 MM THK, PTFE PRIMARY SEAL, MICA SECONDARY SEAL, GRE G10/G11 WASHER & SLEEVES, HARDENED DIELECTRIC COATED 316 METALLIC WASHER 3 MM THK) ASME B16.5',
        'ISK STYLE-FCS (TYPE F - RF) 4" X 600# (SET: G10/G11 GASKET WITH SS316 6.2 MM THK, PTFE PRIMARY SEAL, MICA SECONDARY SEAL, GRE G10/G11 WASHER & SLEEVES, HARDENED DIELECTRIC COATED 316 METALLIC WASHER 3 MM THK) ASME B16.5',
    ]

    expected_sizes = ['2"', '4"']
    for description, expected_size in zip(descriptions, expected_sizes):
        item = _processed_isk(description)

        assert item["status"] == "ready"
        assert item["gasket_type"] == "ISK"
        assert item["size"] == expected_size
        assert item["rating"] == "600#"
        assert item["isk_style"] == "FCS"
        assert item["isk_type"] == "TYPE-F"
        assert item["face_type"] == "RF"
        assert item["standard"] == "ASME B16.5"
        assert item["isk_gasket_material"] == "GRE G10/G11"
        assert item["isk_core_material"] == "SS316"
        assert item["isk_primary_seal"] == "PTFE PRIMARY SEAL"
        assert item["isk_secondary_seal"] == "MICA SECONDARY SEAL"
        assert item["isk_sleeve_material"] == "GRE G10/G11"
        assert item["isk_insulating_washer"] == "GRE G10/G11"
        assert item["isk_washer_material"] == "HARDENED DIELECTRIC COATED SS316"
        assert item["ggpl_description"] == (
            f"SIZE: {expected_size} X 600#, INSULATING GASKET KIT, STYLE-FCS (TYPE F - RF), "
            "(SET: G10/G11 GASKET WITH SS316 6.2 MM THK, PTFE PRIMARY SEAL, MICA SECONDARY SEAL, "
            "GRE G10/G11 WASHER & SLEEVES, HARDENED DIELECTRIC COATED 316 METALLIC WASHER 3 MM THK), "
            "RF, ASME B16.5"
        )
