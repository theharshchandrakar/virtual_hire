"""Golden-data integrity check (TESTING.md §8, §13's #3 gap). Pure Python,
no network, no DB - runs in every default `pytest` invocation. Confirms
the golden dataset itself is well-formed and cross-referenced, and runs
the *real* deterministic Scoring Engine (never the LLM agents) against
each answer key to catch a golden file that's internally inconsistent
with the actual scoring code.

This does not validate real extraction/embedding/Judge quality - that's
tests/fixtures/golden/README.md's job description for the (not yet
built) live-LLM tier in TESTING.md §7.9.
"""

import pytest

from app.services.scoring.resume_fit import score_resume_fit
from app.services.scoring.transcript_review import score_transcript
from tests.fixtures.golden.loader import (
    load_golden_requisitions,
    load_golden_resumes,
    load_golden_transcripts,
)

MIN_GOLDEN_RESUMES = 5
MIN_GOLDEN_REQUISITIONS = 2
MIN_GOLDEN_TRANSCRIPTS = 3


def test_at_least_the_minimum_golden_resumes_exist():
    assert len(load_golden_resumes()) >= MIN_GOLDEN_RESUMES


def test_at_least_the_minimum_golden_requisitions_exist():
    assert len(load_golden_requisitions()) >= MIN_GOLDEN_REQUISITIONS


def test_at_least_the_minimum_golden_transcripts_exist():
    assert len(load_golden_transcripts()) >= MIN_GOLDEN_TRANSCRIPTS


def test_every_golden_resume_has_nonempty_text_and_answer_key():
    for resume in load_golden_resumes():
        assert resume.text.strip(), f"{resume.slug} has empty resume text"
        assert "expected_parsed_data" in resume.answer_key, f"{resume.slug} missing expected_parsed_data"
        assert resume.answer_key["expected_parsed_data"]["skills"], f"{resume.slug} expects zero skills"


def test_every_golden_requisition_has_required_skills():
    for requisition in load_golden_requisitions():
        required_skills = requisition.data.get("scorecard_template", {}).get("required_skills")
        assert required_skills, f"{requisition.slug} has no required_skills"


def test_every_golden_transcript_has_a_well_formed_answer_key():
    for transcript in load_golden_transcripts():
        assert transcript.text.strip(), f"{transcript.slug} has empty transcript text"
        scoring = transcript.answer_key.get("expected_scoring")
        assert scoring is not None, f"{transcript.slug} missing expected_scoring"
        assert "meets_minimum_length" in scoring
        assert "expected_flags" in scoring


def test_resume_requisition_matches_reference_real_requisitions():
    known_requisition_slugs = {req.slug for req in load_golden_requisitions()}
    for resume in load_golden_resumes():
        for requisition_slug in resume.answer_key.get("requisition_matches", {}):
            assert requisition_slug in known_requisition_slugs, (
                f"{resume.slug} references unknown requisition {requisition_slug!r}"
            )


@pytest.mark.parametrize(
    "resume",
    load_golden_resumes(),
    ids=lambda r: r.slug,
)
def test_real_scoring_engine_matches_answer_key_expectations(resume):
    """Feed each resume's *expected* parsed_data (bypassing the LLM
    Extraction Agent entirely) into the real, deterministic
    `score_resume_fit`, and assert the result is consistent with the
    hand-verified answer key - catches a golden file whose expectations
    don't actually match how the real Scoring Engine behaves.
    """
    parsed_data = {
        "skills": resume.answer_key["expected_parsed_data"]["skills"],
        "work_history": [{}] * resume.answer_key["expected_parsed_data"]["work_history_min_count"],
    }
    requisitions_by_slug = {req.slug: req.data for req in load_golden_requisitions()}

    for requisition_slug, expectation in resume.answer_key.get("requisition_matches", {}).items():
        requisition_data = requisitions_by_slug[requisition_slug]
        requirements = {
            "required_skills": requisition_data.get("scorecard_template", {}).get("required_skills", [])
        }

        result = score_resume_fit(parsed_data, requirements)

        assert len(result["matched_skills"]) >= expectation["expected_min_matched_skills"], (
            f"{resume.slug} vs {requisition_slug}: expected >= "
            f"{expectation['expected_min_matched_skills']} matched skills, got {result['matched_skills']}"
        )


@pytest.mark.parametrize(
    "transcript",
    load_golden_transcripts(),
    ids=lambda t: t.slug,
)
def test_real_transcript_scoring_matches_answer_key(transcript):
    """Run the real, deterministic `score_transcript` directly against
    each golden transcript's actual text and assert it matches the
    hand-verified expected_scoring.
    """
    expected = transcript.answer_key["expected_scoring"]

    result = score_transcript(transcript.text, rubric={"min_word_count": expected["min_word_count"]})

    assert result["meets_minimum_length"] == expected["meets_minimum_length"], transcript.slug
    assert result["flags"] == expected["expected_flags"], transcript.slug
