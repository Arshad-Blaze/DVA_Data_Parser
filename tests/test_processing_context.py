"""Tests for ProcessingContext and ProcessingMetrics."""
from dav_tool.processing_context import ProcessingContext, ExistingContext
from dav_tool._observability import ProcessingMetrics, ProcessingTimer, setup_logging


def test_fresh_context_defaults():
    ctx = ProcessingContext()
    assert ctx.phase == 0
    assert ctx.file_paths is None
    assert ctx.metrics.aggregation_time == 0.0
    assert ctx.metrics.rows_processed == 0


def test_phase_transition():
    ctx = ProcessingContext()
    assert ctx.phase == 0
    ctx.phase = 2
    assert ctx.phase == 2


def test_context_stores_config():
    ctx = ProcessingContext()
    ctx.store_col = "Store"
    ctx.units_col = "Units"
    ctx.price_col = "Price"
    assert ctx.store_col == "Store"
    assert ctx.units_col == "Units"
    assert ctx.price_col == "Price"


def test_existing_context_defaults():
    ctx = ExistingContext()
    assert ctx.phase == 0
    assert ctx.prod.phase == 0
    assert ctx.test.phase == 0
    assert ctx.prod.metrics.aggregation_time == 0.0
    assert ctx.test.metrics.aggregation_time == 0.0
    assert ctx.metrics.aggregation_time == 0.0


def test_metrics_update():
    m = ProcessingMetrics()
    m.aggregation_time = 1.5
    m.rows_processed = 1000
    m.peak_memory = 256.0
    assert m.aggregation_time == 1.5
    assert m.rows_processed == 1000
    assert m.peak_memory == 256.0


def test_metrics_warnings_errors():
    m = ProcessingMetrics()
    m.warnings.append("Low memory")
    m.errors.append("Parse failed on file X")
    assert len(m.warnings) == 1
    assert len(m.errors) == 1


def test_timer_updates_metrics():
    setup_logging()
    m = ProcessingMetrics()
    with ProcessingTimer(m, "aggregation", "test_phase"):
        import time
        time.sleep(0.01)
        sum(range(100_000))
    assert m.aggregation_time > 0
    assert m.total_execution_time > 0
    assert m.peak_memory >= 0


def test_timer_no_cpu():
    setup_logging()
    m = ProcessingMetrics()
    with ProcessingTimer(m, "validation", "quick"):
        pass
    assert m.validation_time >= 0
    assert m.peak_memory >= 0
