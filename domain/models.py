"""
Pydantic v2 model for a single gasket line item.
Used for structured output validation and as the canonical schema reference.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class GasketItem(BaseModel):
    line_no: Optional[int] = None
    quantity: Optional[float] = None
    uom: str = 'NOS'
    raw_description: str = ''
    is_gasket: bool = True
    size: Optional[str] = None
    size_type: str = 'UNKNOWN'
    od_mm: Optional[float] = None
    id_mm: Optional[float] = None
    rating: Optional[str] = None
    gasket_type: str = 'SOFT_CUT'
    moc: Optional[str] = None
    face_type: Optional[str] = None
    thickness_mm: Optional[float] = None
    standard: Optional[str] = None
    special: Optional[str] = None
    confidence: str = 'MEDIUM'
    # Spiral wound
    sw_winding_material: Optional[str] = None
    sw_filler: Optional[str] = None
    sw_inner_ring: Optional[str] = None
    sw_outer_ring: Optional[str] = None
    # RTJ
    rtj_groove_type: Optional[str] = None
    rtj_hardness_bhn: Optional[float] = None
    rtj_hardness_spec: Optional[str] = None
    ring_no: Optional[str] = None
    # Kammprofile
    kamm_core_material: Optional[str] = None
    kamm_surface_material: Optional[str] = None
    kamm_covering_layer: Optional[str] = None
    kamm_rib: Optional[str] = None
    kamm_core_thk: Optional[float] = None
    kamm_integral_outer_ring: Optional[str] = None
    # DJI
    dji_filler: Optional[str] = None
    dji_rib: Optional[str] = None
    dji_face_type: Optional[str] = None
    dji_id_first: bool = False
    # ISK
    isk_style: Optional[str] = None
    isk_type: Optional[str] = None
    isk_fire_safety: Optional[str] = None
    isk_gasket_material: Optional[str] = None
    isk_core_material: Optional[str] = None
    isk_sleeve_material: Optional[str] = None
    isk_washer_material: Optional[str] = None
    isk_primary_seal: Optional[str] = None
    isk_secondary_seal: Optional[str] = None
    isk_insulating_washer: Optional[str] = None
    isk_standard_explicit: bool = True
    # Output
    ggpl_description: str = ''
    status: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    size_norm: Optional[str] = None

    model_config = {"extra": "allow"}  # allow unknown fields from LLM
