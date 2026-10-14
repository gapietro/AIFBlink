"""Badges: goals met while using the board, kept on this computer.

Asked for by the owner (2026-10-14) as a light game on top of the gauges:
ten ordinary badges, three hard ones and two hidden ones. The rules live
here, in the daemon, rather than on the board, for three reasons:

  - the daemon already sees every fact a badge is about -- session states and
    counts, subagents, usage percentages, window resets, which provider, the
    local clock -- and the board sees only the one message built from them;
  - Python is where this project can test a rule properly, and a badge that
    fires on the wrong day is exactly the kind of quiet wrongness tests are
    for;
  - the collection should outlive a board swap or a firmware update, and
    ~/.blink is what survives both. One collection per computer, on the
    owner's call: a personal Mac and a corporate one are two accounts and two
    collections.

THE IDS ARE A WIRE CONTRACT. The board is sent a bitmask, and bit N means the
badge at index N of BADGES -- in firmware/src/badges.c as well as here. Never
reorder or reuse an index; add new badges at the end.

One principle in choosing them: nothing here rewards spending quota for its
own sake. Several reward the opposite -- this display exists to keep people
inside their limits -- and none can be earned faster by sending messages
that were not going to be sent anyway (CLAUDE.md: never generate usage).

Nothing read here is logged except the names of badges as they are earned.
"""
import datetime
import json
import os
import sys
import tempfile

from pc.providers import base

# (id, name). The words the board shows live in firmware/src/badges.c; the
# names are here for the log line and the tests.
BADGES = (
    ("first_light", "First Light"),
    ("early_bird", "Early Bird"),
    ("night_owl", "Night Owl"),
    ("multitasker", "Multitasker"),
    ("agent_wrangler", "Agent Wrangler"),
    ("polyglot", "Polyglot"),
    ("week_streak", "Week Streak"),
    ("quick_draw", "Quick Draw"),
    ("cool_head", "Cool Head"),
    ("centurion", "Centurion"),
    # The hard ones.
    ("iron_streak", "Iron Streak"),
    ("bullseye", "Bullseye"),
    ("swarm_lord", "Swarm Lord"),
    # The hidden ones: the board shows "???" until they are found.
    ("blacksmith", "Blacksmith"),
    ("dont_panic", "Don't Panic"),
)
INDEX = {bid: i for i, (bid, _) in enumerate(BADGES)}
NAMES = dict(BADGES)

# A provider counts as in use today when it said something this recently.
# Five minutes is the Claude Desktop cache's own refresh while it is open,
# so a desk that is genuinely in use is never missed between two samples.
ACTIVE_WITHIN_S = 300
# Quick Draw: a session that was waiting on its owner, answered this fast.
QUICK_DRAW_S = 10
QUICK_DRAW_TIMES = 10
CENTURION_SESSIONS = 100
# Weekly verdicts (Cool Head, Bullseye) are passed on the LAST reading of a
# window, and only one taken within this long of its end -- a daemon that was
# off for the final four days of a week does not know how the week ended.
WEEK_END_EVIDENCE_S = 24 * 3600
DAYS_KEPT = 40          # enough for Iron Streak's 30 and a little history
EGGS = ("blacksmith",)  # badges the board reports, not the usage stream


def state_path():
    """~/.blink/badges.json -- resolved at call time, as CLAUDE.md asks."""
    return os.path.join(os.path.expanduser("~"), ".blink", "badges.json")


def _empty():
    return {"version": 1, "earned": {}, "finished": 0, "quick": 0,
            "days": [], "codex_days": [], "week": None}


def _streak(days, today):
    """How many consecutive days, ending today or yesterday, are in `days`.

    Ending YESTERDAY counts too: a streak is not broken at 08:00 by a person
    who has not sat down yet.
    """
    have = set(days)
    d = today
    if d.isoformat() not in have:
        d -= datetime.timedelta(days=1)
    n = 0
    while d.isoformat() in have:
        n += 1
        d -= datetime.timedelta(days=1)
    return n


def _display_pct(v):
    """The number the board draws for a percentage: (int)(pct + 0.5)."""
    return int(v + 0.5) if v is not None and v >= 0 else None


class BadgeBook:
    """The collection, and the rules that add to it.

    observe() is called once per poll with the two merged provider frames
    the board is about to be shown. It returns the badges earned by that
    poll, in index order, and the caller announces them.
    """

    def __init__(self, path=None, localtime=None):
        self._path = path
        self._localtime = localtime or (
            lambda t: datetime.datetime.fromtimestamp(t))
        self._s = self._load()
        # Edges, not levels: the previous poll's counts, so a count going up
        # is an event. None until the first poll, which therefore counts
        # nothing -- a daemon restart is not eleven sessions finishing.
        self._prev_idle = None
        self._prev_wait = None
        self._wait_rose_at = None

    # ---------------------------------------------------------------- state

    def path(self):
        return self._path if self._path is not None else state_path()

    def _load(self):
        try:
            with open(self.path(), encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            return _empty()
        if not isinstance(s, dict):
            return _empty()
        out = _empty()
        for k, default in out.items():
            v = s.get(k)
            if k == "week":
                if isinstance(v, dict):
                    out[k] = v
            elif type(v) is type(default):
                out[k] = v
        return out

    def _save(self):
        """Atomically, so a crash mid-write cannot cost the collection."""
        path = self.path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                                       prefix=".badges-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._s, f, indent=1, sort_keys=True)
            os.replace(tmp, path)
        except OSError as e:
            print(f"[badges] could not save: {e}", file=sys.stderr)

    def mask(self):
        """Bit N set when BADGES[N] is earned -- what the board is sent."""
        m = 0
        for bid in self._s["earned"]:
            if bid in INDEX:
                m |= 1 << INDEX[bid]
        return m

    def earned(self):
        return set(self._s["earned"])

    def _earn(self, bid, now, new):
        if bid in self._s["earned"]:
            return
        self._s["earned"][bid] = int(now)
        new.append(bid)
        print(f"[badges] earned: {NAMES[bid]}", file=sys.stderr)

    # ---------------------------------------------------------------- eggs

    def record_egg(self, bid, now):
        """A hidden badge the BOARD found (the wordmark taps). Returns the
        badges earned, like observe(). Anything not an egg is ignored: the
        board must not be able to award the usage badges."""
        new = []
        if bid in EGGS:
            self._earn(bid, now, new)
        if new:
            self._save()
        return new

    # ---------------------------------------------------------------- rules

    def observe(self, primary, secondary, now):
        new = []
        changed = False
        frames = [f for f in (primary, secondary) if f is not None]
        claude = next((f for f in frames if f.provider == "claude"), None)
        codex = next((f for f in frames if f.provider == "codex"), None)
        today = self._localtime(now).date()
        hour = self._localtime(now).hour

        def active(f):
            return (f is not None and f.active_at is not None
                    and now - f.active_at <= ACTIVE_WITHIN_S)

        if any(f.has_usage() for f in frames):
            self._earn("first_light", now, new)

        # --- the moment: what is running right now -------------------------
        n_run = sum(f.n_run for f in frames if active(f))
        n_agents = sum(f.n_agents for f in frames if active(f))
        if n_run >= 1 and hour < 6:
            self._earn("early_bird" if hour >= 4 else "night_owl", now, new)
        if n_run >= 3:
            self._earn("multitasker", now, new)
        if n_agents >= 5:
            self._earn("agent_wrangler", now, new)
        if n_run >= 4 and n_agents >= 10:
            self._earn("swarm_lord", now, new)

        # --- days ----------------------------------------------------------
        iso = today.isoformat()
        for f, key in ((claude, "days"), (codex, "codex_days")):
            if active(f) and iso not in self._s[key]:
                self._s[key] = sorted(self._s[key] + [iso])[-DAYS_KEPT:]
                changed = True
        if iso in self._s["days"] and iso in self._s["codex_days"]:
            self._earn("polyglot", now, new)
        streak = _streak(self._s["days"], today)
        if streak >= 7:
            self._earn("week_streak", now, new)
        if streak >= 30:
            self._earn("iron_streak", now, new)

        # --- edges: sessions finishing, prompts answered --------------------
        idle = sum(f.n_idle for f in frames)
        wait = sum(f.n_wait for f in frames)
        if self._prev_idle is not None and idle > self._prev_idle:
            self._s["finished"] += idle - self._prev_idle
            changed = True
        if self._prev_wait is not None:
            if wait > self._prev_wait:
                self._wait_rose_at = now
            elif (wait < self._prev_wait and self._wait_rose_at is not None
                  and now - self._wait_rose_at <= QUICK_DRAW_S):
                self._s["quick"] += 1
                self._wait_rose_at = None
                changed = True
        self._prev_idle, self._prev_wait = idle, wait
        if self._s["finished"] >= CENTURION_SESSIONS:
            self._earn("centurion", now, new)
        if self._s["quick"] >= QUICK_DRAW_TIMES:
            self._earn("quick_draw", now, new)

        # --- the weekly window ---------------------------------------------
        if (claude is not None and claude.plan == base.PLAN_WINDOWS
                and claude.weekly_pct >= 0
                and claude.weekly_resets_at is not None):
            changed |= self._watch_week(claude, now, new)

        # --- the hidden one the usage stream can find ----------------------
        for f in frames:
            if f.plan != base.PLAN_WINDOWS:
                continue
            if 42 in (_display_pct(f.session_pct), _display_pct(f.weekly_pct)):
                self._earn("dont_panic", now, new)

        if new or changed:
            self._save()
        return [b for b, _ in BADGES if b in new]

    def _watch_week(self, claude, now, new):
        """Judge a weekly window once it has ended, on its last reading.

        A window is identified by its reset time. When a reading arrives for
        a LATER window, the one before it is over, and its last recorded
        percentage is how it ended -- provided that reading was taken close
        enough to the end to know (WEEK_END_EVIDENCE_S).
        """
        resets_at = float(claude.weekly_resets_at)
        week = self._s["week"]
        if week is None or abs(week.get("resets_at", 0) - resets_at) < 3600:
            self._s["week"] = {"resets_at": resets_at,
                               "pct": float(claude.weekly_pct),
                               "seen_at": float(now)}
            # Saved when the number moves, and at least hourly when it does
            # not: `seen_at` is the evidence the verdict needs, and a quiet
            # last day of the week must still count as having been watched.
            return (week is None or week.get("pct") != claude.weekly_pct
                    or now - week.get("seen_at", 0) > 3600)
        if resets_at > week["resets_at"] and week["resets_at"] <= now:
            if week["seen_at"] >= week["resets_at"] - WEEK_END_EVIDENCE_S:
                if week["pct"] < 50:
                    self._earn("cool_head", now, new)
                elif 95 <= week["pct"] < 100:
                    self._earn("bullseye", now, new)
        self._s["week"] = {"resets_at": resets_at,
                           "pct": float(claude.weekly_pct),
                           "seen_at": float(now)}
        return True
