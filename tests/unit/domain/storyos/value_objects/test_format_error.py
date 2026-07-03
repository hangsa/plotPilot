from domain.storyos.value_objects.format_error import FormatError


def test_format_error_constructs():
    e = FormatError(
        code="MALFORMED_TAG",
        message="missing closing -->",
        raw_text="<!-- SF_LOG MYSTERY",
        char_position=42,
    )
    assert e.code == "MALFORMED_TAG"
    assert e.message == "missing closing -->"
    assert e.raw_text == "<!-- SF_LOG MYSTERY"
    assert e.char_position == 42