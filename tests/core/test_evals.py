"""The eval scaffold itself must work, because every threshold is tuned with it."""

from __future__ import annotations

from evals.runner import (
    HERE,
    Question,
    load_corpus,
    load_questions,
    main,
    run_eval,
)


async def test_sample_set_runs_and_every_question_behaves_as_expected():
    questions = load_questions(HERE / "sample_questions.jsonl")
    report = await run_eval(questions, load_corpus(HERE / "sample_corpus.json"))
    assert len(report.results) == len(questions) >= 8
    assert report.question_pass_rate == 1.0
    assert report.forbidden_citations_shown == 0


async def test_honest_model_scores_a_perfect_verified_citation_rate():
    store = load_corpus(HERE / "sample_corpus.json")
    qs = [
        q
        for q in load_questions(HERE / "sample_questions.jsonl")
        if q.fake_model == "honest"
    ]
    report = await run_eval(qs, store)
    assert report.total_citations > 0
    assert report.verified_citation_rate == 1.0
    assert report.meets_launch_gates()


async def test_misbehaving_fake_models_lower_the_rate_and_fail_the_gate():
    store = load_corpus(HERE / "sample_corpus.json")
    qs = [
        q
        for q in load_questions(HERE / "sample_questions.jsonl")
        if q.fake_model != "honest"
    ]
    report = await run_eval(qs, store)
    reasons = {reason for r in report.results for reason in r.removed_reasons}
    assert reasons == {"not_retrieved", "quote_not_found"}
    assert report.verified_citation_rate < 1.0
    assert not report.meets_launch_gates()


async def test_a_wrong_expectation_is_reported_as_a_failed_question():
    store = load_corpus(HERE / "sample_corpus.json")
    q = Question(
        "x1", "Give me a recipe for biryani with saffron and rice."
    )  # expects answered
    report = await run_eval([q], store)
    assert report.results[0].outcome == "not_found" and not report.results[0].ok


def test_cli_runs_and_gate_flag_sets_the_exit_code(capsys):
    assert main([]) == 0
    assert "verified-citation rate" in capsys.readouterr().out
    assert main(["--gate"]) == 1  # the sample set contains deliberate failures
