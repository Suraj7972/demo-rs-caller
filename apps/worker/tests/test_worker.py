from worker.main import WorkerSettings, ping


async def test_ping() -> None:
    assert await ping({}) == "pong"


def test_worker_settings_registers_functions() -> None:
    assert WorkerSettings.functions
