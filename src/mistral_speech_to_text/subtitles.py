class SubtitleBuffer:
    def __init__(self, max_lines: int = 3):
        self.max_lines = max_lines
        self._closed: list[str] = []
        self._current = ""
        self._current_speaker: str | None = None

    def append_delta(self, text: str) -> None:
        self._current += text

    def append_segment(self, text: str, speaker_id: str | None = None) -> None:
        if speaker_id is not None and speaker_id != self._current_speaker:
            self.close_line()
            self._current_speaker = speaker_id
            self._current += f"{speaker_id}: "
        self._current += text

    def close_line(self) -> None:
        line = self._current.strip()
        self._current = ""
        self._current_speaker = None
        if line:
            self._closed.append(line)

    def display_lines(self) -> list[str]:
        live = self._current.strip()
        lines = self._closed + ([live] if live else [])
        return lines[-self.max_lines:]

    @property
    def full_text(self) -> str:
        parts = self._closed + ([self._current] if self._current else [])
        return "\n".join(parts)
