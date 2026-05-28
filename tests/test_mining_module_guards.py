"""V1.17.0h3b: гранулярные гарды внутри process_mining_reward.

Модуль «Майнинг» включён, но под-модули «Комбо» / «Спринты» / «Штрафы»
можно гасить по отдельности через module_toggles. Проверяем, что
соответствующий блок расчёта НЕ вызывается, когда его модуль OFF.

Тяжёлые db-зависимости и сами расчётные функции замоканы — тест
проверяет только проводку гардов.
"""
from unittest.mock import MagicMock

import handlers.messages.mining_logic as ml


class _FakeDB:
    _DEFAULT_WS_ID = 1

    def __init__(self, toggles):
        self._toggles = toggles
        self.cursor = MagicMock()
        self.conn = MagicMock()

    def is_econ_section_enabled(self, category):
        return self._toggles.get(category, True)

    def get_bank_balance(self):
        return 100000.0

    def update_user_balance(self, *a, **k):
        pass

    def update_bank_balance(self, *a, **k):
        pass

    def add_transaction(self, *a, **k):
        pass


def _make_message():
    msg = MagicMock()
    msg.text = "достаточно длинный текст для возможного комбо «Писатель»"
    msg.caption = None
    msg.photo = None
    msg.video = None
    msg.video_note = None
    msg.voice = None
    msg.audio = None
    msg.animation = None
    msg.reply_to_message = None
    msg.chat.id = -1000
    return msg


def _run(monkeypatch, toggles):
    """Прогоняет process_mining_reward с замоканными расчётами.
    Возвращает счётчик вызовов блоков combo/sprint/penalty."""
    calls = {"combo": 0, "sprint": 0, "penalty": 0}

    monkeypatch.setattr(ml, "get_dynamic_economy_config", lambda db, workspace_id=None: (
        0.002, {}, {}, {}, {},
        {"buff_multiplier": 1, "buff_duration_min": 1,
         "silence_min": 1, "silence_max": 1},
    ))
    monkeypatch.setattr(ml, "calculate_base_coefficients",
                        lambda **k: (1.0, ["текст"]))
    monkeypatch.setattr(ml, "_check_and_grant_defibrillator",
                        lambda *a, **k: False)
    monkeypatch.setattr(ml, "_get_claimed_combos", lambda *a, **k: {})
    monkeypatch.setattr(ml, "_get_claimed_sprints", lambda *a, **k: [])
    monkeypatch.setattr(ml, "_query_user_sprint_metrics",
                        lambda *a, **k: ({}, {}, {}))
    monkeypatch.setattr(ml, "_get_user_buff", lambda *a, **k: 1.0)

    def _combo(**k):
        calls["combo"] += 1
        return (0.0, [])

    def _sprint(**k):
        calls["sprint"] += 1
        return (0.0, [])

    def _penalty(**k):
        calls["penalty"] += 1
        return (0.0, [])

    monkeypatch.setattr(ml, "calculate_instant_combos", _combo)
    monkeypatch.setattr(ml, "check_completed_sprints", _sprint)
    monkeypatch.setattr(ml, "calculate_penalties", _penalty)

    db = _FakeDB(toggles)
    reward, _ = ml.process_mining_reward(
        user_id=42, today="2026-05-21", user_data={"x": 1},
        is_excluded=False, exclusion_reason=None,
        db=db, message=_make_message(), thread_id=None,
    )
    return calls, reward


def test_all_economy_modules_on_runs_every_block(monkeypatch):
    calls, _ = _run(monkeypatch, {
        "mining": True, "combos": True, "sprints": True, "penalty": True,
    })
    assert calls == {"combo": 1, "sprint": 1, "penalty": 1}


def test_combos_off_skips_combo_block(monkeypatch):
    calls, _ = _run(monkeypatch, {
        "mining": True, "combos": False, "sprints": True, "penalty": True,
    })
    assert calls["combo"] == 0
    assert calls["sprint"] == 1 and calls["penalty"] == 1


def test_sprints_off_skips_sprint_block(monkeypatch):
    calls, _ = _run(monkeypatch, {
        "mining": True, "combos": True, "sprints": False, "penalty": True,
    })
    assert calls["sprint"] == 0
    assert calls["combo"] == 1 and calls["penalty"] == 1


def test_penalty_off_skips_penalty_block(monkeypatch):
    calls, _ = _run(monkeypatch, {
        "mining": True, "combos": True, "sprints": True, "penalty": False,
    })
    assert calls["penalty"] == 0
    assert calls["combo"] == 1 and calls["sprint"] == 1


def test_mining_off_skips_everything(monkeypatch):
    """Мастер-свич «Майнинг» OFF → ни один блок не считается, награда 0."""
    calls, reward = _run(monkeypatch, {
        "mining": False, "combos": True, "sprints": True, "penalty": True,
    })
    assert calls == {"combo": 0, "sprint": 0, "penalty": 0}
    assert reward == 0.0
