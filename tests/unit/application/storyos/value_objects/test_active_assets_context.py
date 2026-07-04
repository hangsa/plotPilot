from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


def test_active_assets_context_default():
    ctx = ActiveAssetsContext(
        novel_id="n1", chapter_id=1,
    )
    assert ctx.conflicts == []
    assert ctx.mysteries == []
    assert ctx.total_active == 0


def test_active_assets_context_total_active_counts_all_lists():
    ctx = ActiveAssetsContext(
        novel_id="n1", chapter_id=1,
        conflicts=[{"id": "c1"}, {"id": "c2"}],
        mysteries=[{"id": "m1"}],
        expectations=[{"id": "e1"}],
    )
    assert ctx.total_active == 4
