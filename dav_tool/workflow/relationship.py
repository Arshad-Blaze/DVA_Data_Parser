"""Relationship Engine — discovers and manages join relationships between datasets.

Responsibility:
- Propose join key pairs from discovery results
- Validate join compatibility
- Enrich a canonical dataset with attributes from another dataset

This is the formal bridge between Detection (Phase 3 key discovery)
and the Canonical layer (enrichment).
"""
import logging
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

import polars as pl

from dav_tool.detection import detect_relationship_keys

from dav_tool.workflow.discovery import DiscoveryResult
from dav_tool.workflow.canonical import CanonicalDataset

logger = logging.getLogger(__name__)


class RelationshipEngine:
    """Discovers and manages relationships between datasets.

    Consumes ``DiscoveryResult.candidate_keys`` from Phase 3 detection
    and proposes join configurations.  Once confirmed, produces enriched
    canonical output via ``enrich_dataset``.
    """

    @staticmethod
    def discover_relationships(
        source_result: DiscoveryResult,
        target_result: DiscoveryResult,
    ) -> List[Dict]:
        """Propose join relationships between two detection results.

        Compares ``candidate_keys`` from both files and recommends
        pairs where key types and columns match.

        Returns list of dicts: ``source_column``, ``target_column``,
        ``key_type``, ``confidence``, ``match_reason``.
        """
        source_keys = getattr(source_result, "candidate_keys", [])
        target_keys = getattr(target_result, "candidate_keys", [])
        if not source_keys or not target_keys:
            return []

        return detect_relationship_keys(source_keys, target_keys)

    @staticmethod
    def confirm_relationship(
        source_column: str,
        target_column: str,
        join_type: str = "inner",
    ) -> Dict:
        """Validate and return a confirmed relationship config.

        Returns a dict with ``source_column``, ``target_column``,
        ``join_type``, and ``status`` (``"valid"`` or ``"invalid"``).
        """
        if not source_column or not target_column:
            return {
                "source_column": source_column,
                "target_column": target_column,
                "join_type": join_type,
                "status": "invalid",
                "reason": "Both source and target columns must be specified",
            }

        return {
            "source_column": source_column,
            "target_column": target_column,
            "join_type": join_type,
            "status": "valid",
        }

    @staticmethod
    def enrich_dataset(
        source_dataset: CanonicalDataset,
        target_dataset: CanonicalDataset,
        join_mapping: Dict[str, str],
        attributes: Optional[List[str]] = None,
    ) -> Optional[CanonicalDataset]:
        """Enrich a source dataset with attributes from a target (product master) dataset.

        Args:
            source_dataset: Primary dataset (e.g., sales) to enrich.
            target_dataset: Secondary dataset (e.g., product master) providing attributes.
            join_mapping: Maps source column name → target column name for the join key.
            attributes: Target columns to include in enriched output. If None, includes
                       all target columns except the join key.

        Returns:
            A new CanonicalDataset whose schema includes both source and
            selected target columns, or None if enrichment fails.
        """
        try:
            source_key = next(iter(join_mapping.keys()))
            target_key = join_mapping[source_key]

            def _enriched_stream() -> Iterator[pl.DataFrame]:
                for source_chunk in source_dataset.iter_chunks():
                    # Find matching target chunk
                    for target_chunk in target_dataset.iter_chunks():
                        enriched = _join_chunks(
                            source_chunk, target_chunk,
                            source_key, target_key,
                            attributes,
                        )
                        if enriched is not None and not enriched.is_empty():
                            yield enriched
                            break

            enriched_schema = _build_enriched_schema(
                source_dataset.schema,
                target_dataset.schema,
                target_key,
                attributes,
            )

            metadata = dict(source_dataset.metadata)
            metadata["enriched"] = True
            metadata["join_key"] = source_key
            metadata["target_file"] = target_dataset.file_paths

            return CanonicalDataset(
                schema=enriched_schema,
                level=source_dataset.level,
                stream_factory=_enriched_stream,
                file_paths=source_dataset.file_paths,
                metadata=metadata,
                capabilities=source_dataset.capabilities,
            )

        except Exception as e:
            logger.error("Enrichment failed: %s", e, exc_info=True)
            return None


def _join_chunks(
    source: pl.DataFrame,
    target: pl.DataFrame,
    source_key: str,
    target_key: str,
    attributes: Optional[List[str]] = None,
) -> Optional[pl.DataFrame]:
    """Join two chunks on the specified key columns."""
    try:
        if source_key not in source.columns:
            logger.warning("Source key '%s' not found in source chunk", source_key)
            return None
        if target_key not in target.columns:
            logger.warning("Target key '%s' not found in target chunk", target_key)
            return None

        target_cols = [target_key]
        if attributes:
            for attr in attributes:
                if attr in target.columns and attr != target_key:
                    target_cols.append(attr)
        else:
            target_cols = [target_key] + [c for c in target.columns if c != target_key]

        target_subset = target.select(target_cols)

        result = source.join(
            target_subset,
            left_on=source_key,
            right_on=target_key,
            how="left",
        )
        return result

    except Exception as e:
        logger.error("Chunk join failed (source_key=%s, target_key=%s): %s", source_key, target_key, e, exc_info=True)
        return None


def _build_enriched_schema(
    source_schema: List[str],
    target_schema: List[str],
    target_key: str,
    attributes: Optional[List[str]] = None,
) -> List[str]:
    """Build the merged schema for an enriched dataset."""
    enriched = list(source_schema)
    for col in target_schema:
        if col == target_key:
            continue
        if attributes and col not in attributes:
            continue
        if col not in enriched:
            enriched.append(col)
    return enriched
