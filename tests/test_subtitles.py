from mistral_speech_to_text.subtitles import SubtitleBuffer


def test_deltas_append_with_their_own_spacing():
    buf = SubtitleBuffer()
    buf.append_delta("Hello")
    buf.append_delta(" world.")
    assert buf.display_lines() == ["Hello world."]


def test_close_line_starts_new_line():
    buf = SubtitleBuffer()
    buf.append_delta("first line")
    buf.close_line()
    buf.append_delta("second")
    assert buf.display_lines() == ["first line", "second"]


def test_display_lines_keeps_last_n():
    buf = SubtitleBuffer(max_lines=2)
    for i in range(4):
        buf.append_delta(f"line{i} ")
        buf.close_line()
    assert buf.display_lines() == ["line2", "line3"]


def test_empty_close_line_is_dropped():
    buf = SubtitleBuffer()
    buf.close_line()
    buf.append_delta("x")
    assert buf.display_lines() == ["x"]


def test_segments_switch_speaker():
    buf = SubtitleBuffer()
    buf.append_segment("hi there", "speaker_0")
    buf.append_segment("hello", "speaker_1")
    buf.append_segment(" again", "speaker_1")
    assert buf.display_lines() == ["speaker_0: hi there", "speaker_1: hello again"]


def test_full_text():
    buf = SubtitleBuffer()
    buf.append_delta("one")
    buf.close_line()
    buf.append_delta("two")
    assert buf.full_text == "one\ntwo"
