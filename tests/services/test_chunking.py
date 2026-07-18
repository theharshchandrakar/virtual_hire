"""Tests for app.services.chunking (VHIRE-2x / E7): the chunking strategy
shared by resumes and transcripts/audio-derived transcripts alike.
"""

import pytest

from app.services.chunking import chunk_text


def test_chunk_text_returns_empty_list_for_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_returns_a_single_chunk_when_shorter_than_chunk_size():
    text = " ".join(f"word{i}" for i in range(10))

    chunks = chunk_text(text, chunk_size=500, overlap=50)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_splits_into_overlapping_windows():
    words = [f"word{i}" for i in range(120)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=50, overlap=10)

    assert len(chunks) == 3
    assert chunks[0].split() == words[0:50]
    assert chunks[1].split() == words[40:90]
    assert chunks[2].split() == words[80:120]


def test_chunk_text_rejects_overlap_greater_than_or_equal_to_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("some text here", chunk_size=10, overlap=10)
