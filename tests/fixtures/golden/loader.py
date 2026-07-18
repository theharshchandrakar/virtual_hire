"""Loader for the golden seed dataset (TESTING.md §8): golden resumes,
requisitions, and transcripts, each paired with a hand-verified answer
key (except requisitions, which are themselves structured input, not
something to grade). See README.md for what consumes this and why.
"""

import json
from dataclasses import dataclass
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent


@dataclass(frozen=True)
class GoldenResume:
    slug: str
    text: str
    answer_key: dict


@dataclass(frozen=True)
class GoldenRequisition:
    slug: str
    data: dict


@dataclass(frozen=True)
class GoldenTranscript:
    slug: str
    text: str
    answer_key: dict


def _answer_key_path(text_path: Path) -> Path:
    return text_path.parent / f"{text_path.stem}.expected.json"


def load_golden_resumes() -> list[GoldenResume]:
    """Load every golden resume paired with its hand-verified answer key."""
    resumes_dir = GOLDEN_DIR / "resumes"
    resumes = []
    for text_path in sorted(resumes_dir.glob("*.txt")):
        answer_key = json.loads(_answer_key_path(text_path).read_text(encoding="utf-8"))
        resumes.append(
            GoldenResume(
                slug=text_path.stem,
                text=text_path.read_text(encoding="utf-8"),
                answer_key=answer_key,
            )
        )
    return resumes


def load_golden_requisitions() -> list[GoldenRequisition]:
    """Load every golden job requisition."""
    requisitions_dir = GOLDEN_DIR / "requisitions"
    requisitions = []
    for json_path in sorted(requisitions_dir.glob("*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        requisitions.append(GoldenRequisition(slug=json_path.stem, data=data))
    return requisitions


def load_golden_transcripts() -> list[GoldenTranscript]:
    """Load every golden interview transcript paired with its hand-verified answer key."""
    transcripts_dir = GOLDEN_DIR / "transcripts"
    transcripts = []
    for text_path in sorted(transcripts_dir.glob("*.txt")):
        answer_key = json.loads(_answer_key_path(text_path).read_text(encoding="utf-8"))
        transcripts.append(
            GoldenTranscript(
                slug=text_path.stem,
                text=text_path.read_text(encoding="utf-8"),
                answer_key=answer_key,
            )
        )
    return transcripts
