"""Stage framework — the base contract every pipeline stage implements.

Each stage:
- owns exactly one responsibility,
- receives one contract (via :class:`PipelineContext`),
- returns one contract (stored back on the context),
- defines recoverable vs fatal errors with retry/fallback strategies,
- never imports Streamlit.

Stages are composed into pipelines by the Pipeline Registry.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StageError(Exception):
    """Base class for errors raised by pipeline stages.

    Attributes:
        recoverable: True if the stage may be retried safely.
        retry: True if the engine should retry the stage automatically.
        user_message: Message safe to show in the UI (no internals).
    """

    def __init__(
        self,
        message: str,
        *,
        recoverable: bool = False,
        retry: bool = False,
        user_message: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.recoverable = recoverable
        self.retry = retry
        self.user_message = user_message or message


class RecoverableStageError(StageError):
    """A stage failure that can be recovered from (e.g., transient I/O)."""

    def __init__(self, message: str, *, user_message: Optional[str] = None) -> None:
        super().__init__(message, recoverable=True, retry=True, user_message=user_message)


class FatalStageError(StageError):
    """A stage failure that cannot be recovered from within the pipeline."""

    def __init__(self, message: str, *, user_message: Optional[str] = None) -> None:
        super().__init__(message, recoverable=False, retry=False, user_message=user_message)


@dataclass
class StageResult:
    """Result of running a stage.

    Attributes:
        stage: Stage name.
        success: Whether the stage completed successfully.
        elapsed: Wall-clock seconds.
        warnings: Stage warnings.
        errors: Stage errors (empty when success is True).
    """
    stage: str
    success: bool = True
    elapsed: float = 0.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseStage(ABC):
    """Abstract base for all pipeline stages.

    Subclasses implement :meth:`execute`, which receives the
    :class:`~dav_tool.pipeline.context.PipelineContext` and returns a
    :class:`StageResult`.  Stages store their output on the context section
    they own.
    """

    #: Unique stage name (used by the engine and progress tracking).
    name: str = "base"
    #: Human-readable label for the UI progress display.
    label: str = "Stage"
    #: Maximum automatic retries for recoverable errors.
    max_retries: int = 2
    #: Retry delay (seconds) between attempts.
    retry_delay: float = 1.0

    def run(self, ctx) -> StageResult:
        """Public entry point — wraps :meth:`execute` with timing and retries."""
        t0 = time.perf_counter()
        attempts = 0
        while True:
            attempts += 1
            try:
                result = self.execute(ctx)
                result.elapsed = time.perf_counter() - t0
                return result
            except RecoverableStageError as exc:
                if attempts <= self.max_retries:
                    logger.warning(
                        "Stage %s recoverable error (attempt %d/%d): %s",
                        self.name, attempts, self.max_retries + 1, exc,
                    )
                    time.sleep(self.retry_delay)
                    continue
                return StageResult(
                    stage=self.name,
                    success=False,
                    elapsed=time.perf_counter() - t0,
                    errors=[exc.user_message],
                )
            except StageError as exc:
                return StageResult(
                    stage=self.name,
                    success=False,
                    elapsed=time.perf_counter() - t0,
                    errors=[exc.user_message],
                )
            except Exception as exc:  # noqa: BLE001 — stage boundary converts to StageResult
                logger.exception("Stage %s fatal error: %s", self.name, exc)
                return StageResult(
                    stage=self.name,
                    success=False,
                    elapsed=time.perf_counter() - t0,
                    errors=[f"Internal error in stage '{self.name}': {exc}"],
                )

    @abstractmethod
    def execute(self, ctx) -> StageResult:
        """Execute the stage. Must return a :class:`StageResult`."""
        raise NotImplementedError
