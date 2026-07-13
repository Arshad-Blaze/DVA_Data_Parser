"""Progressive Configuration Builder & Configuration Validator.

Builds configuration in stages (A-E), validates completeness
before processing, and provides section-level UI helpers.
"""

import logging
from typing import Any, Dict, List, Optional

from dav_tool.format_config import (
    FormatConfig, ConfigSection, ValidationConfig, ValidationRule, OutputConfig,
    iter_sections, get_section_fields,
)
from dav_tool.options import OutputMode

logger = logging.getLogger(__name__)


# ── Progressive Builder Stages ──────────────────────────────────────

STAGE_LABELS = {
    ConfigSection.GENERAL: "Stage A: General Information",
    ConfigSection.FILE: "Stage B: File Format",
    ConfigSection.SCHEMA: "Stage C: Schema & Columns",
    ConfigSection.BUSINESS_RULES: "Stage D: Business Rules",
    ConfigSection.VALIDATION: "Stage E: Validation Settings",
    ConfigSection.OUTPUT: "Stage F: Output Settings",
}


def get_current_stage(cfg: FormatConfig) -> ConfigSection:
    """Return the next incomplete config section (stage)."""
    return cfg.next_incomplete_section()


def stage_fields(cfg: FormatConfig, section: ConfigSection) -> List[str]:
    """Return field names for the given config section that are relevant."""
    return list(get_section_fields(section))


def stage_summary(cfg: FormatConfig, section: ConfigSection) -> Dict[str, Any]:
    """Return a human-readable summary of fields in a section."""
    summary = {}
    fields = stage_fields(cfg, section)

    for field in fields:
        val = getattr(cfg, field, None)
        if field == "validation_config":
            vc: ValidationConfig = val
            for rule_name in ["store_validation", "item_validation", "compare_store_list", "file_review"]:
                rule: ValidationRule = getattr(vc, rule_name)
                summary[f"{rule_name}_enabled"] = rule.enabled
                if rule.group_by_columns:
                    summary[f"{rule_name}_group_by"] = ", ".join(rule.group_by_columns)
                if rule.aggregation_columns:
                    summary[f"{rule_name}_agg_cols"] = ", ".join(rule.aggregation_columns)
        elif field == "output_config" and isinstance(val, OutputConfig):
            summary["format"] = val.format
            summary["include_file_review"] = val.include_file_review
            summary["include_validation_details"] = val.include_validation_details
        elif val is not None:
            summary[field] = val
    return summary


# ── Configuration Validation ────────────────────────────────────────


class ConfigValidationError(Exception):
    """Raised when configuration fails validation."""


def validate_config(cfg: FormatConfig, mode: OutputMode = OutputMode.VALIDATE) -> List[str]:
    """Validate configuration completeness and correctness for the given OutputMode.

    The validator only checks fields required by the selected operation:
    - VALIDATE: all standard fields (store, upc, units, price, etc.)
    - AGGREGATE_ONLY: requires group_by and aggregation columns
    - STATISTICS: nothing required (schema columns remain available, not errors)
    - EXPORT: nothing required

    Returns a list of error messages (empty = valid).
    """
    errors: List[str] = []

    # GENERAL (always required)
    if not cfg.file_type:
        errors.append("File type is not set (required: delimited, fixed, or multiline).")
    elif cfg.file_type not in ("delimited", "fixed", "multiline"):
        errors.append(f"Invalid file type '{cfg.file_type}'. Must be: delimited, fixed, or multiline.")

    # FILE (always required for parsing)
    if cfg.file_type == "fixed" and not cfg.layout_file:
        errors.append("Fixed-width files require a layout CSV file path.")
    if cfg.file_type == "multiline":
        if cfg.header_prefix:
            if not cfg.header_layout_file:
                errors.append("HDR files require a header layout CSV.")
            if not cfg.detail_layout_file:
                errors.append("HDR files require a detail layout CSV.")
        elif not cfg.ml_record_types:
            errors.append("Multiline files require record type prefixes (e.g. H,D).")
    if cfg.file_type == "delimited" and not cfg.delimiter:
        errors.append("Delimited files require a delimiter.")

    # SCHEMA
    if not cfg.schema and not cfg.detected_columns:
        errors.append("No schema or detected columns — cannot determine data structure.")

    # BUSINESS RULES — operation-aware
    if mode == OutputMode.VALIDATE:
        if not cfg.store_col:
            errors.append("Store column mapping is required for Validate mode.")
        if not cfg.upc_col:
            errors.append("UPC column mapping is required for Validate mode.")
        if not cfg.units_col:
            errors.append("Units column mapping is required for Validate mode.")
        if not cfg.price_col:
            errors.append("Price column mapping is required for Validate mode.")

        if cfg.price_type and cfg.price_type not in ("Total Price", "Unit Price"):
            errors.append(f"Invalid price type '{cfg.price_type}'. Must be: Total Price or Unit Price.")

    elif mode == OutputMode.AGGREGATE_ONLY:
        if not cfg.store_col:
            errors.append("Store column (group_by) is required for Aggregate Only mode.")

    elif mode == OutputMode.STATISTICS:
        pass  # No column mapping required

    elif mode == OutputMode.EXPORT:
        pass  # No column mapping required

    # Check mapped columns exist in schema (only for VALIDATE and AGGREGATE_ONLY)
    if mode in (OutputMode.VALIDATE, OutputMode.AGGREGATE_ONLY):
        all_cols = (cfg.schema or []) + (cfg.detected_columns or [])
        if all_cols:
            required = {cfg.store_col}
            if mode == OutputMode.VALIDATE:
                required.update({cfg.upc_col, cfg.desc_col, cfg.units_col, cfg.price_col})
            required.discard(None)
            missing = required - set(all_cols)
            if missing:
                errors.append(f"Mapped columns not found in schema: {', '.join(sorted(missing))}")

    return errors


def assert_config_valid(cfg: FormatConfig, mode: OutputMode = OutputMode.VALIDATE):
    """Raise ConfigValidationError if config is invalid for the given mode."""
    errors = validate_config(cfg, mode=mode)
    if errors:
        raise ConfigValidationError(
            "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        )


def validate_section(cfg: FormatConfig, section: ConfigSection) -> List[str]:
    """Validate a single config section.

    Returns a list of section-specific errors.
    """
    errors: List[str] = []

    if section == ConfigSection.GENERAL:
        if not cfg.file_type:
            errors.append("File type is required.")
        elif cfg.file_type not in ("delimited", "fixed", "multiline"):
            errors.append(f"Invalid file type '{cfg.file_type}'.")

    elif section == ConfigSection.FILE:
        if not cfg.file_type:
            errors.append("File type is required.")
        if cfg.file_type == "fixed" and not cfg.layout_file:
            errors.append("Fixed-width files need a layout CSV path (set in Stage B).")
        if cfg.file_type == "multiline":
            if not cfg.header_prefix and not cfg.ml_record_types:
                errors.append("Multiline files need record types or HDR prefix.")
        if cfg.file_type == "delimited" and not cfg.delimiter:
            errors.append("Delimited files require a delimiter.")

    elif section == ConfigSection.SCHEMA:
        if not cfg.schema and not cfg.detected_columns:
            errors.append("No columns detected. Ensure a sample was loaded.")

    elif section == ConfigSection.BUSINESS_RULES:
        if not cfg.store_col:
            errors.append("Store column is required.")
        if not cfg.upc_col:
            errors.append("UPC column is required.")
        if not cfg.units_col:
            errors.append("Units column is required.")
        if not cfg.price_col:
            errors.append("Price column is required.")
        if cfg.price_type and cfg.price_type not in ("Total Price", "Unit Price"):
            errors.append(f"Invalid price type '{cfg.price_type}'.")

    return errors
