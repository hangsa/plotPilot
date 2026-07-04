import time
import pytest
from application.storyos.services.evolution_bridge_service import EvolutionBridgeService
from application.storyos.services.cascade_service import CascadeService
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


@pytest.mark.slow
def test_bridge_full_chapter_perf(monkeypatch):
    """100 SF_LOG + 50 cascade < 200ms（spec §5.3 锁定）。"""
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: True,
    )
    bridge = EvolutionBridgeService(
        action_mapper=SFLogActionMapper(),
        cascade_service=CascadeService(),
    )
    records = [
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"mystery_id": f"m{i}", "content": "x"},
            raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id=f"m{i}",
        )
        for i in range(100)
    ]
    start = time.perf_counter()
    result = bridge.apply_sflog_batch(novel_id="n1", chapter_id=1, records=records)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert result.success is True
    assert elapsed_ms < 200, f"bridge took {elapsed_ms:.1f}ms, expected < 200ms"