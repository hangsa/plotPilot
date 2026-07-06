"""世界观实体在 V2 schema 下应「以 JSON 为主、scalar 列回填缺失字段」。

历史脏数据：LLM 偶发在 JSON 块里漏掉某个 schema 字段，但该字段在
Worldbuilding 实体的 scalar 列（如 class_system）上仍有非空值。
原实现（any-non-empty 时整块走 JSON）会让这些字段在读取时消失，
导致向用户展示「世界视为空」并无法通过重新生成恢复。

本测试覆盖 _dimension_from_document_or_scalar_projection 的合并语义。
"""
from domain.worldbuilding.worldbuilding import Worldbuilding


def _entity(
    *,
    politics: str = "",
    economy: str = "",
    class_system: str = "",
    dimensions=None,
) -> Worldbuilding:
    return Worldbuilding(
        id="wb-1",
        novel_id="n-1",
        politics=politics,
        economy=economy,
        class_system=class_system,
        dimensions=dimensions or {},
    )


def test_json_missing_key_falls_back_to_scalar():
    """LLM 漏掉 society.class_system，但 scalar 列仍有值 → 读取时必须能拿到。"""
    entity = _entity(
        class_system="阶层秩序：内廷-外朝-江湖",
        dimensions={"society": {"politics": "王权", "economy": "实物税"}},
    )
    assert entity.society == {
        "politics": "王权",
        "economy": "实物税",
        "class_system": "阶层秩序：内廷-外朝-江湖",
    }


def test_json_empty_value_falls_back_to_scalar():
    """JSON 块里有 key 但 value 为空 → 仍以 scalar 列覆盖（避免空字符串污染 UI）。"""
    entity = _entity(
        class_system="三层结构",
        dimensions={"society": {"politics": "王权", "class_system": "   "}},
    )
    assert entity.society["politics"] == "王权"
    assert entity.society["class_system"] == "三层结构"


def test_json_populated_wins_over_scalar():
    """JSON 块已有非空值 → 以 JSON 为准，scalar 列不覆盖。"""
    entity = _entity(
        class_system="旧值（应被忽略）",
        dimensions={"society": {"class_system": "新值（来自 JSON）"}},
    )
    assert entity.society["class_system"] == "新值（来自 JSON）"


def test_json_only_dimension_keeps_non_schema_keys():
    """非 schema 的扩展 key 在 JSON 块里应原样保留（下游 projection 才过滤）。"""
    entity = _entity(
        dimensions={"society": {"politics": "王权", "extra_legacy": "历史遗留字段"}},
    )
    assert entity.society["extra_legacy"] == "历史遗留字段"
    assert entity.society["politics"] == "王权"


def test_empty_json_and_empty_scalar_returns_empty_strings():
    """JSON 为空且 scalar 列为空 → schema 字段应回退为 ''（不是缺失 key）。"""
    entity = _entity(dimensions={"society": {}})
    out = entity.society
    for field in ("politics", "economy", "class_system"):
        assert field in out
        assert out[field] == ""


def test_no_json_block_falls_back_to_scalar_columns():
    """dimensions 整体为空（旧数据未迁到 V2 文档）→ 整维走 scalar 列。"""
    entity = _entity(
        class_system="纯 scalar 数据",
    )
    assert entity.society["class_system"] == "纯 scalar 数据"


def test_to_dict_uses_merged_projection():
    """to_dict 输出的 5 维字段应当反映合并后的最新值（不只是 JSON）。"""
    entity = _entity(
        class_system="scalar 来源",
        dimensions={"society": {"politics": "json 来源"}},
    )
    snapshot = entity.to_dict()
    assert snapshot["society"]["politics"] == "json 来源"
    assert snapshot["society"]["class_system"] == "scalar 来源"
