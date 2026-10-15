"""The release check for the two screens the fleet cannot open.

pc/screen_gate.py reads bridge.log for the board's "[mem] lvgl pool" lines
and refuses a release unless the version being tagged was seen with Settings
and Badges open, with headroom. Most of this module is one test per way it
could say yes when it should say no.

The logs are built here, line by line, in the shape bridge.log has on
2026-10-14 -- never copied from a real one.

Nothing here touches the real ~/.blink: tmp_path throughout.
"""
import pathlib
import subprocess
import sys

import pytest

from pc import screen_gate
from pc.screen_gate import gate

POOL = 40960
# What 1.7.1 measured: used + free is 88 bytes under the pool.
TOTAL = POOL - 88


def hello(fw):
    return ("2026-10-14 15:10:18 [bridge] <- {'t': 'hello', 'v': 2,"
            " 'board': 'cyd', 'board_id': '000000000000', 'fw': '%s',"
            " 'reset': '0x8'}" % fw)


def mem(where, used, peak=None, free=None):
    free = TOTAL - used if free is None else free
    peak = used if peak is None else peak
    return (f"2026-10-14 15:10:42 [mem] lvgl pool {where}: {used} used,"
            f" {free} free, peak {peak}")


GOOD = [hello("1.7.2"),
        mem("at the gauges", 20952),
        mem("with settings open", 23480),
        mem("with badges open", 30120, peak=31520)]


def files(tmp_path, lines, pool=POOL):
    log = tmp_path / "bridge.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    conf = tmp_path / "prj.conf"
    conf.write_text(f"CONFIG_LVGL=y\nCONFIG_LV_Z_MEM_POOL_SIZE={pool}\n",
                    encoding="utf-8")
    return str(log), str(conf)


def test_both_screens_opened_with_headroom_passes(tmp_path):
    assert gate("1.7.2", *files(tmp_path, GOOD)) is None


def test_settings_never_opened_refuses(tmp_path):
    lines = [l for l in GOOD if "settings" not in l]
    why = gate("1.7.2", *files(tmp_path, lines))
    assert "Settings" in why and "Badges" not in why


def test_badges_never_opened_refuses(tmp_path):
    lines = [l for l in GOOD if "badges" not in l]
    assert "Badges" in gate("1.7.2", *files(tmp_path, lines))


def test_gauges_alone_refuses(tmp_path):
    why = gate("1.7.2", *files(tmp_path, GOOD[:2]))
    assert "Settings and Badges were never opened" in why


def test_readings_from_the_previous_version_do_not_count(tmp_path):
    """The case the gate exists for: 1.7.1 was checked, 1.7.2 was not."""
    lines = [l.replace("1.7.2", "1.7.1") for l in GOOD] + [hello("1.7.2")]
    assert "No board has reported running 1.7.2" in gate(
        "1.7.2", *files(tmp_path, lines))


def test_a_reading_belongs_to_the_last_hello_before_it(tmp_path):
    """A flash reboots the board, so a later hello ends the old version's run."""
    lines = [hello("1.7.2"), mem("with settings open", 23480),
             hello("1.7.1"), mem("with badges open", 30120)]
    assert "Badges" in gate("1.7.2", *files(tmp_path, lines))


def test_only_the_latest_run_of_the_version_counts(tmp_path):
    """1.7.0 was built with two pool sizes under one number. Readings from
    before the board last moved onto the version can neither vouch for this
    build nor block it."""
    stale = [hello("1.7.2"), mem("with settings open", 23480, free=0)]
    lines = stale + [hello("1.7.1")] + GOOD
    assert gate("1.7.2", *files(tmp_path, lines)) is None


def test_a_reboot_on_the_same_version_keeps_its_readings(tmp_path):
    """Opening Settings, a reboot, then Badges is one run of one version."""
    lines = [hello("1.7.2"), mem("with settings open", 23480),
             hello("1.7.2"), mem("with badges open", 30120)]
    assert gate("1.7.2", *files(tmp_path, lines)) is None


def test_a_version_that_only_shares_a_prefix_is_not_the_same(tmp_path):
    lines = [l.replace("1.7.2", "1.7.20") for l in GOOD]
    assert gate("1.7.2", *files(tmp_path, lines)) is not None


def test_a_peak_inside_the_headroom_refuses(tmp_path):
    tight = TOTAL - screen_gate.HEADROOM_B + 1
    lines = GOOD + [mem("with badges open", 30120, peak=tight)]
    assert "less than" in gate("1.7.2", *files(tmp_path, lines))


def test_a_peak_exactly_at_the_headroom_passes(tmp_path):
    edge = TOTAL - screen_gate.HEADROOM_B
    lines = GOOD + [mem("with badges open", 30120, peak=edge)]
    assert gate("1.7.2", *files(tmp_path, lines)) is None


def test_the_pool_comes_from_prj_conf_not_from_the_board(tmp_path):
    """A pool shrunk in prj.conf makes the same report fail to add up."""
    why = gate("1.7.2", *files(tmp_path, GOOD, pool=30720))
    assert "does not add up" in why


@pytest.mark.parametrize("free", [0, 999999, TOTAL - 23480 - 2000])
def test_numbers_that_are_not_a_heap_report_refuse(tmp_path, free):
    """What the board printed with heap stats off: whatever the stack held."""
    lines = GOOD + [mem("with settings open", 23480, free=free)]
    assert "does not add up" in gate("1.7.2", *files(tmp_path, lines))


def test_a_peak_bigger_than_the_pool_refuses(tmp_path):
    lines = GOOD + [mem("with badges open", 30120, peak=TOTAL + 1)]
    assert gate("1.7.2", *files(tmp_path, lines)) is not None


def test_missing_log_refuses(tmp_path):
    _, conf = files(tmp_path, GOOD)
    assert "Cannot read" in gate("1.7.2", str(tmp_path / "nope.log"), conf)


def test_missing_prj_conf_refuses(tmp_path):
    log, _ = files(tmp_path, GOOD)
    assert "Cannot read" in gate("1.7.2", log, str(tmp_path / "nope.conf"))


def test_prj_conf_without_a_pool_size_refuses(tmp_path):
    log, conf = files(tmp_path, GOOD)
    (tmp_path / "prj.conf").write_text("CONFIG_LVGL=y\n", encoding="utf-8")
    assert "sets no" in gate("1.7.2", log, conf)


def test_refusals_never_echo_the_boards_numbers(tmp_path):
    """Nothing read off the serial line is repeated (CLAUDE.md)."""
    tight = TOTAL - screen_gate.HEADROOM_B + 1
    lines = GOOD + [mem("with badges open", 30120, peak=tight)]
    why = gate("1.7.2", *files(tmp_path, lines))
    for n in ("30120", str(tight), str(TOTAL - 30120)):
        assert n not in why


def test_main_exit_codes(tmp_path, capsys):
    log, conf = files(tmp_path, GOOD)
    assert screen_gate.main(["1.7.2", log, conf]) == 0
    assert screen_gate.main(["1.7.3", log, conf]) == 1
    assert "1.7.3" in capsys.readouterr().err
    assert screen_gate.main(["1.7.2"]) == 2


def test_main_turns_a_crash_into_a_refusal(tmp_path, capsys, monkeypatch):
    def boom(*_a):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(screen_gate, "gate", boom)
    assert screen_gate.main(["1.7.2", "a", "b"]) == 1
    assert "refuses" in capsys.readouterr().err


def test_the_gate_imports_nothing_else_from_pc():
    """It runs under whatever python3 a release shell has, as fleet_gate does."""
    src = (pathlib.Path(__file__).resolve().parents[2] / "pc"
           / "screen_gate.py").read_text(encoding="utf-8")
    assert "from pc" not in src and "import pc" not in src


def test_run_as_a_module_refuses_with_status_one(tmp_path):
    """The whole path release.sh takes: `python3 -m pc.screen_gate`."""
    log, conf = files(tmp_path, GOOD)
    done = subprocess.run(
        [sys.executable, "-m", "pc.screen_gate", "1.7.3", log, conf],
        cwd=str(pathlib.Path(__file__).resolve().parents[2]),
        capture_output=True, text=True)
    assert done.returncode == 1
    assert "1.7.3" in done.stderr and done.stdout == ""


def test_the_firmware_still_prints_what_the_gate_reads():
    """The gate is only as good as the lines it matches. If the board stops
    printing them, or words them differently, every release would refuse --
    loudly, but better to hear it here than at release time."""
    src =pathlib.Path(__file__).resolve().parents[2] / "firmware" / "src"
    text = ((src / "main.c").read_text(encoding="utf-8")
            + (src / "ui_settings.c").read_text(encoding="utf-8"))
    for words in ("at the gauges", "with settings open", "with badges open"):
        assert f"[mem] lvgl pool {words}: %u used, %u free" in text
