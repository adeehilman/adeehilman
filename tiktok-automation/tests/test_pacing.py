from tiktok_bot.pacing import Pacer


def test_budget_accounting():
    pacer = Pacer(min_seconds=0, max_seconds=0, budget=2)
    assert pacer.remaining == 2
    pacer.consume()
    assert not pacer.exhausted()
    pacer.consume()
    assert pacer.exhausted()
    assert pacer.remaining == 0


def test_wait_stays_inside_the_configured_bounds(monkeypatch):
    slept = []
    monkeypatch.setattr("tiktok_bot.pacing.time.sleep", slept.append)
    pacer = Pacer(min_seconds=10, max_seconds=20, budget=1)
    pacer._sleep = slept.append
    delay = pacer.wait()
    assert 10 <= delay <= 20
    assert slept and 10 <= slept[0] <= 20
