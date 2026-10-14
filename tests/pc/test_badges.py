"""pc/badges: the rules, the collection file, and the wire.

Every frame is built here; the clock is injected so a badge about 2 am can
be tested at any hour.
"""
import datetime
import json

from pc import badges, ingest, protocol
from pc.bridge import Bridge
from pc.providers import base

T0 = datetime.datetime(2026, 10, 14, 14, 0).timestamp()   # a Wednesday, 2 pm


def book(tmp_path):
    return badges.BadgeBook(path=str(tmp_path / "badges.json"))


def claude(now, **kw):
    kw.setdefault("observed_at", now)
    return base.NormalizedUsageFrame(provider="claude", src="cli", **kw)


def codex(now, **kw):
    kw.setdefault("observed_at", now)
    return base.NormalizedUsageFrame(provider="codex", src="cli", **kw)


def test_the_ids_never_move():
    """A wire contract: bit N is badge N on the board too."""
    assert [b for b, _ in badges.BADGES] == [
        "first_light", "early_bird", "night_owl", "multitasker",
        "agent_wrangler", "polyglot", "week_streak", "quick_draw",
        "cool_head", "centurion", "iron_streak", "bullseye", "swarm_lord",
        "blacksmith", "dont_panic"]


def test_the_firmware_table_agrees(tmp_path):
    import pathlib
    import re
    src = (pathlib.Path(__file__).resolve().parents[2] / "firmware" / "src"
           / "badges.c").read_text()
    names = re.findall(r'\{\s*"([^"]+)",', src)
    assert names == [n for _, n in badges.BADGES]


def test_first_light(tmp_path):
    b = book(tmp_path)
    assert b.observe(claude(T0), None, T0) == []
    assert b.observe(claude(T0, session_pct=20.0), None, T0) == ["first_light"]
    assert b.observe(claude(T0, session_pct=21.0), None, T0) == []


def test_night_owl_and_early_bird_need_something_running(tmp_path):
    b = book(tmp_path)
    two_am = datetime.datetime(2026, 10, 14, 2, 0).timestamp()
    five_am = datetime.datetime(2026, 10, 14, 5, 0).timestamp()
    assert b.observe(claude(two_am, n_idle=1), None, two_am) == []
    assert b.observe(claude(two_am, n_run=1), None, two_am) == ["night_owl"]
    assert b.observe(claude(five_am, n_run=1), None, five_am) == ["early_bird"]


def test_a_stale_frame_is_not_somebody_working_at_night(tmp_path):
    b = book(tmp_path)
    two_am = datetime.datetime(2026, 10, 14, 2, 0).timestamp()
    old = claude(two_am - 3600, n_run=1)
    assert b.observe(old, None, two_am) == []


def test_crowds(tmp_path):
    b = book(tmp_path)
    got = b.observe(claude(T0, n_run=2, n_agents=3),
                    codex(T0, n_run=1, n_agents=2), T0)
    # Claude and Codex both busy is also Polyglot -- correctly.
    assert got == ["multitasker", "agent_wrangler", "polyglot"]
    assert b.observe(claude(T0, n_run=4, n_agents=10), None, T0) == \
        ["swarm_lord"]


def test_polyglot_is_both_on_one_day(tmp_path):
    b = book(tmp_path)
    assert b.observe(claude(T0, session_pct=1.0), None, T0) == ["first_light"]
    later = T0 + 3600
    assert b.observe(None, codex(later, session_pct=1.0), later) == \
        ["polyglot"]


def test_streaks_survive_a_restart_and_forgive_this_morning(tmp_path):
    p = tmp_path / "badges.json"
    days = [(datetime.date(2026, 10, 14) - datetime.timedelta(days=i))
            .isoformat() for i in range(1, 7)]
    p.write_text(json.dumps({"days": days, "earned": {}}), encoding="utf-8")
    b = badges.BadgeBook(path=str(p))
    # Six days ending yesterday, nothing yet today: no badge, no penalty.
    assert "week_streak" not in b.observe(None, None, T0)
    assert "week_streak" in b.observe(claude(T0, n_run=1), None, T0)
    assert "week_streak" in json.loads(p.read_text())["earned"]


def test_iron_streak(tmp_path):
    p = tmp_path / "badges.json"
    days = [(datetime.date(2026, 10, 14) - datetime.timedelta(days=i))
            .isoformat() for i in range(0, 30)]
    p.write_text(json.dumps({"days": days}), encoding="utf-8")
    got = badges.BadgeBook(path=str(p)).observe(None, None, T0)
    assert "iron_streak" in got and "week_streak" in got


def test_centurion_counts_finishes_not_the_first_reading(tmp_path):
    b = book(tmp_path)
    b.observe(claude(T0, n_idle=40), None, T0)         # a restart: not 40
    b._s["finished"] = 98
    assert b.observe(claude(T0, n_idle=41), None, T0) == []
    assert b.observe(claude(T0, n_idle=42), None, T0) == ["centurion"]


def test_quick_draw_is_ten_fast_answers(tmp_path):
    b = book(tmp_path)
    t = T0
    b.observe(claude(t), None, t)
    for i in range(10):
        b.observe(claude(t, n_wait=1), None, t)
        t += 4
        got = b.observe(claude(t, n_wait=0, n_run=1), None, t)
        t += 60
    assert got == ["quick_draw"]


def test_a_slow_answer_is_not_a_quick_draw(tmp_path):
    b = book(tmp_path)
    b.observe(claude(T0), None, T0)
    b.observe(claude(T0, n_wait=1), None, T0)
    b.observe(claude(T0 + 30, n_wait=0), None, T0 + 30)
    assert b._s["quick"] == 0


def _week(b, pct, at, resets_at):
    return b.observe(claude(at, weekly_pct=pct, weekly_resets_at=resets_at),
                     None, at)


def test_cool_head_and_bullseye_judge_the_last_reading(tmp_path):
    reset = T0 + 3600
    nxt = reset + 7 * 86400
    b = book(tmp_path)
    _week(b, 30.0, T0, reset)
    assert _week(b, 1.0, reset + 60, nxt) == ["cool_head"]

    b = book(tmp_path / "b")
    _week(b, 97.0, T0, reset)
    assert _week(b, 1.0, reset + 60, nxt) == ["bullseye"]

    b = book(tmp_path / "c")
    _week(b, 100.0, T0, reset)                      # over the line
    assert _week(b, 1.0, reset + 60, nxt) == []


def test_a_week_watched_only_at_its_start_earns_nothing(tmp_path):
    b = book(tmp_path)
    reset = T0 + 5 * 86400
    _week(b, 10.0, T0, reset)
    assert _week(b, 1.0, reset + 60, reset + 7 * 86400) == []


def test_dont_panic_is_the_drawn_number(tmp_path):
    b = book(tmp_path)
    b.observe(claude(T0, session_pct=41.4), None, T0)
    assert "dont_panic" not in b.earned()
    assert "dont_panic" in b.observe(claude(T0, session_pct=41.6), None, T0)


def test_a_spend_page_is_not_a_window(tmp_path):
    b = book(tmp_path)
    f = claude(T0, session_pct=42.0, plan=base.PLAN_SPEND)
    assert "dont_panic" not in b.observe(f, None, T0)


def test_the_board_can_only_award_eggs(tmp_path):
    b = book(tmp_path)
    assert b.record_egg("centurion", T0) == []
    assert b.record_egg("blacksmith", T0) == ["blacksmith"]
    assert b.record_egg("blacksmith", T0) == []
    assert b.mask() == 1 << badges.INDEX["blacksmith"]


def test_a_damaged_file_starts_a_fresh_collection(tmp_path):
    p = tmp_path / "badges.json"
    p.write_text("{nope", encoding="utf-8")
    assert badges.BadgeBook(path=str(p)).mask() == 0
    p.write_text(json.dumps({"earned": "all of them", "days": 7}),
                 encoding="utf-8")
    b = badges.BadgeBook(path=str(p))
    assert b.mask() == 0 and b._s["days"] == []


def test_the_default_file_is_resolved_late(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    assert badges.state_path().startswith(str(tmp_path / "elsewhere"))


# ------------------------------------------------------------------ wire

class Fixed:
    def __init__(self, *frames):
        self.frames = list(frames)

    def get_provider_id(self):
        return "claude"

    def poll(self, now):
        return list(self.frames)


def test_the_bus_collects_and_announces_once(tmp_path):
    bus = ingest.IngestionBus(providers=[Fixed(claude(T0, session_pct=5.0))],
                              now=lambda: T0, badge_book=book(tmp_path))
    bus.poll()
    assert bus.badges_msg() == protocol.badges(1)
    assert bus.take_new_badges() == [0]
    bus.poll()
    assert bus.take_new_badges() == []


def test_a_scenario_bus_earns_nothing():
    assert ingest.IngestionBus(providers=[])._badges is None


def test_the_bridge_sends_the_collection_then_the_news(tmp_path):
    sent = []
    bus = ingest.IngestionBus(providers=[Fixed(claude(T0, session_pct=5.0))],
                              now=lambda: T0, badge_book=book(tmp_path))
    br = Bridge(write_msg=sent.append, fetch_usage=bus.fetch(),
                now=lambda: 0.0, wall=lambda: (int(T0), 0),
                record_egg=bus.record_egg)
    br.poll_once()
    kinds = [m["t"] for m in sent]
    assert kinds.index("badges") < kinds.index("badge")
    assert sent[kinds.index("badge")]["id"] == 0
    sent.clear()
    br.poll_once()
    assert "badge" not in [m["t"] for m in sent]
    sent.clear()
    br.on_message({"t": "egg", "v": 2, "id": "blacksmith"})
    assert sent[-1] == protocol.badge_earned(badges.INDEX["blacksmith"])
    assert sent[-2]["got"] & (1 << badges.INDEX["blacksmith"])
