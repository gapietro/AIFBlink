"""Decides whether this firmware version has been seen with every screen open.

The fleet cannot open Settings or Badges. Both are reached with a finger, and
tools/fleet/run.py drives a board over its cable. That gap is how 1.7.0 came
within a release of shipping a crash: the LVGL pool ran dry drawing the
settings panel once the badges row was on it, and LVGL NULL-derefs a failed
glyph buffer (lv_draw_label.c:610) -- on the first tap, on a build the fleet
had passed. It was caught on the owner's desk and withdrawn (2026-10-14).
Nothing made that run-through happen except remembering to do it.

The board already reports what each screen costs. main.c and ui_settings.c
print "[mem] lvgl pool ..." at the gauges, with Settings open and with Badges
open, and the daemon copies the board's console into bridge.log. So the
evidence a release needs is already on this machine, and this reads it. It
refuses unless, for the version being released:

  - Settings and Badges were each opened at least once, and
  - the pool's peak still left HEADROOM_B free.

A reading is credited to the version in the last hello before it. The board
says hello on every boot and again when the gauges come up, and a flash always
reboots it, so a reading cannot be credited to the image it replaced.

The numbers are checked against prj.conf as well as against the floor. With
CONFIG_SYS_HEAP_RUNTIME_STATS off, lvgl_heap_stats() writes nothing and the
board prints whatever the stack held -- prj.conf records the first attempt
doing exactly that -- and garbage that happened to clear the floor would pass.
So used + free has to land just under CONFIG_LV_Z_MEM_POOL_SIZE.

What it does not prove: that anything looked right, or that any screen but
these three was drawn. And it reports which check failed, never the board's
numbers: they came in over the serial line, and nothing read from there is
echoed. The [mem] lines in bridge.log are where to look.

Stdlib only, and nothing from the rest of pc/, for the reason fleet_gate gives:
it runs under whatever interpreter the release shell happens to have.
"""
import re
import sys
from pathlib import Path

# The free bytes the pool's PEAK must still leave. The peak is the board's own
# high-water mark since boot, so it already includes the transient draw
# buffers a screen allocates while rendering -- the allocations that failed in
# 1.7.0. Measured on 1.7.1 (2026-10-14): Badges at 30120 used with a peak of
# 31520, so about 1.4 KB of transients on top of the screen itself, and 9440
# free at the peak. 4096 is about three of those bursts, and well under what
# 1.7.1 leaves.
HEADROOM_B = 4096

# sys_heap keeps some of the pool for its own bookkeeping, so used + free is a
# little under the configured size: 88 bytes short of 40960 on 1.7.1. Anything
# further off than this is not a heap report.
POOL_SLACK_B = 1024

# The two screens the fleet cannot reach, by the words the board uses.
SCREENS = {"with settings open": "Settings", "with badges open": "Badges"}

USAGE = ("usage: python3 -m pc.screen_gate"
         " <version> <bridge.log> <firmware/prj.conf>")

_HELLO = re.compile(r"'t': 'hello'.*?'fw': '([^']*)'")
_MEM = re.compile(r"\[mem\] lvgl pool (at the gauges|with settings open"
                  r"|with badges open): (\d+) used, (\d+) free, peak (\d+)")
_POOL = re.compile(r"^CONFIG_LV_Z_MEM_POOL_SIZE=(\d+)\s*$", re.M)


def _pool_size(prj_conf):
    """CONFIG_LV_Z_MEM_POOL_SIZE from prj.conf, or None if it is not there."""
    m = _POOL.search(Path(prj_conf).read_text(encoding="utf-8"))
    return int(m.group(1)) if m else None


def readings(log_text, version):
    """[(where, used, free, peak)] from the board's latest run of version.

    Only the latest stretch: readings from before the board last moved onto
    this version are dropped. Development reuses a version number across
    builds -- 1.7.0 was built with a 30 KB pool before the 40 KB one -- and an
    older build's numbers would otherwise vouch for, or block, this one. Two
    builds flashed back to back under one number are still one stretch; the
    fleet gate is what pins the commit.
    """
    out = []
    fw = None
    for line in log_text.splitlines():
        h = _HELLO.search(line)
        if h:
            if h.group(1) == version and fw != version:
                out = []
            fw = h.group(1)
            continue
        m = _MEM.search(line)
        if m and fw == version:
            out.append((m.group(1),) + tuple(int(g) for g in m.groups()[1:]))
    return out


def gate(version, log_path, prj_conf):
    """None if this version may be released; otherwise the reason it may not."""
    try:
        pool = _pool_size(prj_conf)
    except (OSError, UnicodeDecodeError) as e:
        return (f"Cannot read {prj_conf} ({e.__class__.__name__}), so the"
                f" board's memory reports cannot be checked. Not releasing.")
    if pool is None:
        return (f"{prj_conf} sets no CONFIG_LV_Z_MEM_POOL_SIZE, so the board's"
                f" memory reports have nothing to be checked against.")
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return (f"Cannot read {log_path} ({e.__class__.__name__}). That log is"
                f" the only evidence that {version} was used with Settings and"
                f" Badges open.")

    seen = readings(text, version)
    if not seen:
        return (f"No board has reported running {version} with any screen up"
                f" ({log_path}). Flash it with tools/burn.sh, then open"
                f" Settings and Badges on the board.")
    missing = [name for words, name in SCREENS.items()
               if not any(where == words for where, *_ in seen)]
    if missing:
        return (f"{version} has been on the board, but {' and '.join(missing)}"
                f" {'was' if len(missing) == 1 else 'were'} never opened on"
                f" it. The fleet cannot tap a screen; open"
                f" {' and '.join(missing)} on the board, then release.")
    for where, used, free, peak in seen:
        if not pool - POOL_SLACK_B <= used + free <= pool:
            return (f"The board's memory report for {version} does not add up"
                    f" to CONFIG_LV_Z_MEM_POOL_SIZE={pool} in prj.conf. Either"
                    f" the board is running a build with a different pool --"
                    f" flash this one -- or CONFIG_SYS_HEAP_RUNTIME_STATS is"
                    f" off and the numbers are not a heap report.")
        if peak > used + free:
            return (f"The board reported a peak larger than the pool for"
                    f" {version}, so its memory report cannot be trusted.")
        if used + free - peak < HEADROOM_B:
            return (f"On {version} the display pool's peak left less than"
                    f" {HEADROOM_B} bytes free -- the edge 1.7.0 crashed at."
                    f" The [mem] lines in {log_path} have the numbers.")
    return None


def main(argv=None):
    """Exit 0 to release, 1 with the reason on stderr to refuse.

    The same contract as fleet_gate.main, for the same reasons: release.sh
    prints its own FATAL line to stderr straight after, and anything
    unexpected is a check that could not be completed -- a refusal, said in a
    sentence rather than a traceback.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 3:
        print(USAGE, file=sys.stderr)
        return 2
    version, log_path, prj_conf = argv
    try:
        reason = gate(version, log_path, prj_conf)
    except Exception as e:  # noqa: BLE001 - a refusal, not a crash
        print(f"The screen gate could not complete its check"
              f" ({e.__class__.__name__}), so it refuses. Nothing has been"
              f" released.", file=sys.stderr)
        return 1
    if reason is not None:
        print(reason, file=sys.stderr)
        return 1
    print(f"Screen gate: {version} was seen with Settings and Badges open,"
          f" with headroom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
