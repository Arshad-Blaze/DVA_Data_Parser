import json
import os
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from dav_tool._parsers import load_layout, preview_flattened_multiline, preview_flattened_multiline_fixed
from dav_tool.processing_context import ProcessingContext


class QuantityType(str, Enum):
    UNITS = "units"
    WEIGHT = "weight"
    MIXED = "mixed"


class ConfigSection(Enum):
    """Logical sections of a FormatConfig, in progressive order."""
    GENERAL = "GENERAL"
    FILE = "FILE"
    PHYSICAL_SCHEMA = "PHYSICAL_SCHEMA"
    CANONICAL_SCHEMA = "CANONICAL_SCHEMA"
    BUSINESS_MAPPING = "BUSINESS_MAPPING"
    QUANTITY = "QUANTITY"
    VALIDATION = "VALIDATION"
    OUTPUT = "OUTPUT"


@dataclass
class ValidationRule:
    """Configuration for a single validation check.

    If *aggregation_columns* is omitted (empty), the current default
    aggregation implementation is used for that validation.
    """
    enabled: bool = True
    required_columns: List[str] = field(default_factory=list)
    group_by_columns: List[str] = field(default_factory=list)
    aggregation_columns: List[str] = field(default_factory=list)


@dataclass
class ValidationConfig:
    """Per-validation settings that can be overridden per file/profile."""
    store_validation: ValidationRule = field(default_factory=lambda: ValidationRule(
        required_columns=["STORE_NUMBER", "Units", "Totalprice"],
        group_by_columns=["STORE_NUMBER"],
        aggregation_columns=["Units", "Totalprice"],
    ))
    item_validation: ValidationRule = field(default_factory=lambda: ValidationRule(
        required_columns=["UPC_CODE", "PRODUCT_DESCRIPTION", "UNITS_SOLD", "TOTAL_DOLLARS"],
        group_by_columns=["UPC_CODE", "PRODUCT_DESCRIPTION"],
        aggregation_columns=["UNITS_SOLD", "TOTAL_DOLLARS"],
    ))
    compare_store_list: ValidationRule = field(default_factory=lambda: ValidationRule(
        required_columns=["STORE_NUMBER"],
        group_by_columns=["STORE_NUMBER"],
    ))
    file_review: ValidationRule = field(default_factory=lambda: ValidationRule(
        required_columns=["STORE_NUMBER", "UPC_CODE", "UNITS_SOLD", "TOTAL_DOLLARS"],
    ))


@dataclass
class OutputConfig:
    """Output configuration for reports and exports."""
    format: str = "csv"
    include_file_review: bool = True
    include_validation_details: bool = True
    download_results: bool = True


# Mapping of section -> tuple of field names
SECTION_FIELDS: Dict[ConfigSection, Tuple[str, ...]] = {
    ConfigSection.GENERAL: ("version", "name",),
    ConfigSection.FILE: (
        "file_type", "encoding", "has_header", "delimiter",
        "start_line", "record_type", "layout_file",
        "header_prefix", "header_layout_file", "detail_layout_file",
        "trailer_prefix", "trailer_layout_file",
        "ml_record_types", "ml_delimiter",
    ),
    ConfigSection.PHYSICAL_SCHEMA: (
        "physical_schema", "detected_data_types",
    ),
    ConfigSection.CANONICAL_SCHEMA: (
        "canonical_schema",
    ),
    ConfigSection.BUSINESS_MAPPING: (
        "store_col", "upc_col", "desc_col", "quantity_col", "price_col",
        "price_type", "implied_dollars", "implied_units",
    ),
    ConfigSection.QUANTITY: (
        "quantity_type", "weight_col", "weight_uom", "resolution_rule",
    ),
    ConfigSection.VALIDATION: ("validation_config",),
    ConfigSection.OUTPUT: ("output_config",),
}

SECTION_LABELS: Dict[ConfigSection, str] = {
    ConfigSection.GENERAL: "General Information",
    ConfigSection.FILE: "File Format",
    ConfigSection.PHYSICAL_SCHEMA: "Physical Schema (from Discovery)",
    ConfigSection.CANONICAL_SCHEMA: "Canonical Schema (editable)",
    ConfigSection.BUSINESS_MAPPING: "Business Mapping",
    ConfigSection.QUANTITY: "Quantity Configuration",
    ConfigSection.VALIDATION: "Validation Settings",
    ConfigSection.OUTPUT: "Output Settings",
}


def get_section_fields(section: ConfigSection) -> Tuple[str, ...]:
    return SECTION_FIELDS.get(section, ())


def iter_sections() -> List[ConfigSection]:
    """Return sections in progressive order."""
    return [
        ConfigSection.GENERAL,
        ConfigSection.FILE,
        ConfigSection.PHYSICAL_SCHEMA,
        ConfigSection.CANONICAL_SCHEMA,
        ConfigSection.BUSINESS_MAPPING,
        ConfigSection.QUANTITY,
        ConfigSection.VALIDATION,
        ConfigSection.OUTPUT,
    ]


@dataclass
class FormatConfig:
    """Serializable description of a data file format.

    Three-layer schema model:
    - physical_schema:  what Discovery found, never changes
    - canonical_schema: editable business-friendly names
    - business mapping: maps business concepts to canonical schema columns

    Can be saved to / loaded from JSON to bypass manual UI setup.
    Fields are organized into logical sections for progressive building.
    """
    version: int = 2
    name: str = ""
    file_type: Optional[str] = None
    encoding: str = "cp1252"
    has_header: bool = True
    delimiter: Optional[str] = None
    start_line: int = 0
    record_type: Optional[str] = None
    layout_file: Optional[str] = None
    header_prefix: Optional[str] = None
    header_layout_file: Optional[str] = None
    detail_layout_file: Optional[str] = None
    trailer_prefix: Optional[str] = None
    trailer_layout_file: Optional[str] = None
    ml_record_types: Optional[List[str]] = None
    ml_delimiter: str = "|"

    # === Schema (three-layer model) ===
    physical_schema: Optional[List[str]] = None
    detected_data_types: Optional[Dict[str, str]] = None
    canonical_schema: Optional[List[str]] = None

    # === Business Mapping (maps concepts to canonical schema) ===
    store_col: Optional[str] = None
    upc_col: Optional[str] = None
    desc_col: Optional[str] = None
    quantity_col: Optional[str] = None
    price_col: Optional[str] = None
    price_type: str = "Total Price"
    implied_dollars: bool = False
    implied_units: bool = False

    # === Quantity Abstraction ===
    quantity_type: str = "units"  # "units", "weight", "mixed"
    weight_col: Optional[str] = None
    weight_uom: str = "lb"
    resolution_rule: str = "units_preferred"  # "units_preferred", "weight_preferred", "average"

    # === Backward-compat aliases ===
    @property
    def schema(self) -> Optional[List[str]]:
        return self.canonical_schema

    @schema.setter
    def schema(self, value: Optional[List[str]]):
        self.canonical_schema = value

    @property
    def detected_columns(self) -> Optional[List[str]]:
        return self.physical_schema

    @detected_columns.setter
    def detected_columns(self, value: Optional[List[str]]):
        self.physical_schema = value

    @property
    def units_col(self) -> Optional[str]:
        return self.quantity_col

    @units_col.setter
    def units_col(self, value: Optional[str]):
        self.quantity_col = value

    suggested_mapping: Optional[Dict[str, str]] = None

    validation_config: ValidationConfig = field(default_factory=ValidationConfig)
    output_config: OutputConfig = field(default_factory=OutputConfig)
    locked: bool = False
    _completed_sections: set = field(default_factory=set)

    def section_complete(self, section: ConfigSection) -> bool:
        return section in self._completed_sections

    def mark_section_complete(self, section: ConfigSection):
        self._completed_sections.add(section)

    def section_fields(self, section: ConfigSection) -> Tuple[str, ...]:
        return get_section_fields(section)

    def section_label(self, section: ConfigSection) -> str:
        return SECTION_LABELS.get(section, section.value)

    def next_incomplete_section(self) -> Optional[ConfigSection]:
        for s in iter_sections():
            if s not in self._completed_sections:
                return s
        return None

    def is_config_complete(self) -> bool:
        return all(s in self._completed_sections for s in iter_sections())

    def reset_sections(self):
        self._completed_sections.clear()


def load_format_config(path: str) -> FormatConfig:
    """Load a FormatConfig from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    version = data.pop("version", 1)
    name = data.pop("name", "")
    cs = data.pop("_completed_sections", set())
    # Handle nested ValidationConfig
    vc_data = data.pop("validation_config", None)
    oc_data = data.pop("output_config", None)
    cfg = FormatConfig(version=version, name=name, _completed_sections=set(cs), **data)
    if vc_data:
        for key in ("store_validation", "item_validation", "compare_store_list", "file_review"):
            rule_data = vc_data.get(key)
            if rule_data:
                setattr(cfg.validation_config, key, ValidationRule(**rule_data))
    if oc_data:
        cfg.output_config = OutputConfig(**oc_data)
    return cfg


def save_format_config(config: FormatConfig, path: str):
    """Save a FormatConfig to a JSON file."""
    d = asdict(config)
    with open(path, "w") as f:
        json.dump(d, f, indent=2, default=str)


def apply_format_config(
    config: FormatConfig,
    ctx: ProcessingContext,
    config_dir: str,
    file_paths: Optional[List[str]] = None,
):
    """Apply parsing settings from a FormatConfig to a ProcessingContext.

    Sets all fields, loads referenced layout CSVs (resolved relative to
    *config_dir*), flattens multiline data, and auto-applies schema.
    """
    config_dir = config_dir or "."

    def _resolve(p: Optional[str]) -> Optional[str]:
        if not p:
            return None
        if os.path.isabs(p):
            return p
        return os.path.normpath(os.path.join(config_dir, p))

    ctx.file_type = config.file_type
    ctx.delimiter = config.delimiter
    ctx.start_line = config.start_line
    ctx.record_type = config.record_type
    ctx.header_prefix = config.header_prefix
    ctx.trailer_prefix = config.trailer_prefix
    ctx.ml_record_types = config.ml_record_types
    ctx.ml_delimiter = config.ml_delimiter
    ctx.store_col = config.store_col
    ctx.upc_col = config.upc_col
    ctx.desc_col = config.desc_col
    ctx.units_col = config.quantity_col or config.units_col
    ctx.price_col = config.price_col
    ctx.price_type = config.price_type
    ctx.implied_dollars = config.implied_dollars
    ctx.implied_units = config.implied_units

    ctx.quantity_type = config.quantity_type
    ctx.weight_col = config.weight_col
    ctx.weight_uom = config.weight_uom
    ctx.resolution_rule = config.resolution_rule

    if config.canonical_schema:
        ctx.schema = config.canonical_schema
    if config.physical_schema:
        ctx.columns = config.physical_schema
    elif config.canonical_schema:
        ctx.columns = config.canonical_schema

    resolved_layout_file = _resolve(config.layout_file)
    if resolved_layout_file and os.path.exists(resolved_layout_file):
        ctx.layout = load_layout(resolved_layout_file)

    resolved_header = _resolve(config.header_layout_file)
    if resolved_header and os.path.exists(resolved_header):
        ctx.header_layout = load_layout(resolved_header)

    resolved_detail = _resolve(config.detail_layout_file)
    if resolved_detail and os.path.exists(resolved_detail):
        ctx.detail_layout = load_layout(resolved_detail)

    resolved_trailer = _resolve(config.trailer_layout_file)
    if resolved_trailer and os.path.exists(resolved_trailer):
        ctx.trailer_layout = load_layout(resolved_trailer)

    if ctx.file_type != "multiline":
        ctx.ml_flattened = False
        return None
    ctx.ml_flattened = True

    file_paths = file_paths or ctx.file_paths
    if not file_paths:
        return None

    if ctx.header_prefix and ctx.header_layout and ctx.detail_layout:
        flat = preview_flattened_multiline_fixed(
            file_paths,
            ctx.header_prefix,
            ctx.header_layout,
            ctx.detail_layout,
            n_rows=10,
            trailer_prefix=ctx.trailer_prefix,
            trailer_layout=ctx.trailer_layout,
        )
    elif ctx.ml_record_types:
        flat = preview_flattened_multiline(
            file_paths, ctx.ml_record_types, ctx.ml_delimiter, n_rows=10,
        )
    else:
        return None

    if flat is not None and not flat.is_empty():
        if not config.schema:
            ctx.schema = list(flat.columns)
        if not config.detected_columns:
            ctx.columns = list(flat.columns)
        return flat

    return None


def config_from_ctx(ctx: ProcessingContext) -> FormatConfig:
    """Build a FormatConfig from a configured ProcessingContext.

    Used for saving the current configuration.
    """
    mapping = {}
    if ctx.store_col:
        mapping["store"] = ctx.store_col
    if ctx.upc_col:
        mapping["upc"] = ctx.upc_col
    if ctx.desc_col:
        mapping["description"] = ctx.desc_col
    if ctx.units_col:
        mapping["units"] = ctx.units_col
    if ctx.price_col:
        mapping["price"] = ctx.price_col

    cfg = FormatConfig(
        name="",
        file_type=ctx.file_type,
        delimiter=ctx.delimiter,
        start_line=ctx.start_line,
        record_type=ctx.record_type,
        header_prefix=ctx.header_prefix,
        trailer_prefix=ctx.trailer_prefix,
        ml_record_types=ctx.ml_record_types,
        ml_delimiter=ctx.ml_delimiter,
        physical_schema=ctx.columns,
        canonical_schema=ctx.schema,
        store_col=ctx.store_col,
        upc_col=ctx.upc_col,
        desc_col=ctx.desc_col,
        quantity_col=ctx.units_col,
        price_col=ctx.price_col,
        price_type=ctx.price_type,
        implied_dollars=ctx.implied_dollars,
        implied_units=ctx.implied_units,
        quantity_type=getattr(ctx, 'quantity_type', 'units'),
        weight_col=getattr(ctx, 'weight_col', None),
        weight_uom=getattr(ctx, 'weight_uom', 'lb'),
        resolution_rule=getattr(ctx, 'resolution_rule', 'units_preferred'),
    )
    cfg.suggested_mapping = mapping or None
    return cfg
