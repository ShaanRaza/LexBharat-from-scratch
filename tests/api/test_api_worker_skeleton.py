"""The ARQ worker skeleton: registered jobs, one at a time, stubs fail loudly."""

import pytest

from workers import main as worker


def test_worker_runs_one_job_at_a_time_and_knows_its_jobs():
    assert worker.WorkerSettings.max_jobs == 1
    names = {f.__name__ for f in worker.WorkerSettings.functions}
    assert names == {"ocr_document", "delete_document", "delete_account"}


def test_worker_reads_redis_from_settings_not_code():
    rs = worker.WorkerSettings.redis_settings
    assert rs.host == "redis"  # the default REDIS_URL host from core.settings


async def test_ocr_stub_says_it_is_not_implemented():
    out = await worker.ocr_document({}, document_id="d1", user_id="u1")
    assert out == {"document_id": "d1", "status": "not_implemented"}


@pytest.mark.parametrize(
    "call",
    [
        lambda: worker.delete_document({}, "u", "d", "p"),
        lambda: worker.delete_account({}, "u", firebase_uid="f"),
    ],
)
async def test_delete_jobs_fail_loudly_until_adapters_exist(call):
    with pytest.raises(NotImplementedError):
        await call()
