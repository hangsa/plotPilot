import pytest
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
from domain.storyos.contracts import SFLogType


@pytest.fixture
def parser():
    return SFLogRegexParser()


def test_parse_single_mystery_clue(parser):
    text = 'Chapter text... <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" --> ...'
    records = parser.parse(text, chapter_id=3)
    assert len(records) == 1
    rec = records[0]
    assert rec.log_type == SFLogType.MYSTERY_CLUE
    assert rec.params == {"mystery_id": "m1", "content": "blood"}
    assert rec.chapter_id == 3
    assert rec.asset_id == "m1"  # 解析为单资产型
    assert rec.char_position > 0


def test_parse_relationship_log_has_no_asset_id(parser):
    text = '<!-- SF_LOG CHARACTER_RELATION_CHANGE char_a="alice" char_b="bob" type="ally" -->'
    records = parser.parse(text, chapter_id=1)
    assert len(records) == 1
    rec = records[0]
    assert rec.log_type == SFLogType.CHARACTER_RELATION_CHANGE
    assert rec.asset_id is None  # 关系型无 asset_id


def test_parse_multiple_records(parser):
    text = '''
    A <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" --> B
    C <!-- SF_LOG CONFLICT_ESCALATE conflict_id="c1" intensity="HIGH" --> D
    '''
    records = parser.parse(text, chapter_id=2)
    assert len(records) == 2
    assert records[0].log_type == SFLogType.MYSTERY_CLUE
    assert records[1].log_type == SFLogType.CONFLICT_ESCALATE


def test_parse_no_sflog_returns_empty(parser):
    records = parser.parse("Plain text without any SF_LOG tags.", chapter_id=1)
    assert records == []


def test_parse_raw_field_preserves_full_tag(parser):
    text = 'before <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" --> after'
    records = parser.parse(text, chapter_id=1)
    assert records[0].raw == '<!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" -->'


def test_parse_all_11_log_types(parser):
    """11 类 SFLogType 全部能解析。"""
    cases = [
        ('CHARACTER_EMOTION', 'char_id="alice" emotion="angry"'),
        ('CHARACTER_RELATION_CHANGE', 'char_a="a" char_b="b" type="ally"'),
        ('CHARACTER_LOCATION_CHANGE', 'char_id="alice" location="cave"'),
        ('CHARACTER_PHYSICAL_CHANGE', 'char_id="alice" status="injured"'),
        ('KNOWLEDGE_GAIN', 'char_id="alice" fact="x"'),
        ('CONFLICT_ESCALATE', 'conflict_id="c1" intensity="HIGH"'),
        ('MYSTERY_CLUE', 'mystery_id="m1" content="x"'),
        ('TWIST_REVEAL', 'twist_id="t1" trigger="x"'),
        ('EXPECTATION_FULFILL', 'expectation_id="e1"'),
        ('GOAL_MILESTONE', 'goal_id="g1" marker="T5"'),
        ('REGISTRY_CREATE', 'asset_type="mystery" asset_id="m2"'),
    ]
    for log_name, params in cases:
        text = f'<!-- SF_LOG {log_name} {params} -->'
        records = parser.parse(text, chapter_id=1)
        assert len(records) == 1, f"failed to parse {log_name}"
        assert records[0].log_type.value == log_name.lower()


def test_parse_malformed_tag_raises(parser):
    """语法错误 → 抛 FormatError（由 FormatError dataclass 表达）。"""
    from domain.storyos.value_objects.format_error import FormatError
    text = '<!-- SF_LOG MYSTERY_CLUE mystery_id="m1"'  # 缺闭合 -->
    with pytest.raises(FormatError):
        parser.parse(text, chapter_id=1)