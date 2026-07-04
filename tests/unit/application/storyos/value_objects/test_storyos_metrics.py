from application.storyos.value_objects.storyos_metrics import StoryOSMetrics


def test_storyos_metrics_default_construction():
    m = StoryOSMetrics()
    assert m.sflog_count == 0
    assert m.applied_count == 0
    assert m.skipped_count == 0
    assert m.cascade_executed == 0
    assert m.cascade_blocked == 0
    assert m.bridge_duration_ms == 0


def test_storyos_metrics_full_construction():
    m = StoryOSMetrics(
        sflog_count=100, applied_count=95, skipped_count=5,
        cascade_executed=50, cascade_blocked=2, bridge_duration_ms=180,
    )
    assert m.sflog_count == 100
    assert m.bridge_duration_ms == 180