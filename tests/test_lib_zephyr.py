"""tools/lib_zephyr.sh: finding the workspace from any shell, failing early.

Run in real shells against a fake workspace under tmp_path, never the real
~/zephyrproject: HOME is set explicitly for every child, on top of the
redirect tests/conftest.py already makes.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "tools" / "lib_zephyr.sh"

needs_zsh = pytest.mark.skipif(shutil.which("zsh") is None,
                               reason="zsh is not installed here")


def _workspace(home):
    """A directory blink_zephyr_ws() accepts: .venv/bin/activate and zephyr/."""
    ws = home / "zephyrproject"
    (ws / ".venv" / "bin").mkdir(parents=True)
    (ws / ".venv" / "bin" / "activate").write_text("", encoding="utf-8")
    (ws / "zephyr").mkdir()
    (ws / "zephyr" / "zephyr-env.sh").write_text("", encoding="utf-8")
    return ws


def _run(shell, script, home, path=None):
    env = {"HOME": str(home), "PATH": path or os.environ["PATH"]}
    return subprocess.run([shell, "-c", f'. "{LIB}"; {script}'],
                          env=env, capture_output=True, text=True, timeout=30)


@needs_zsh
def test_zsh_finds_the_workspace_when_other_candidates_are_absent(tmp_path):
    """Only ~/zephyrproject exists, so ~/zephyr-v* matches nothing -- which
    zsh used to answer with "no matches found" and abort the command."""
    ws = _workspace(tmp_path)
    r = _run("zsh", "blink_zephyr_ws; echo exit=$?", tmp_path)
    assert "no matches found" not in r.stderr
    assert r.stdout.splitlines() == [str(ws), "exit=0"]


@needs_zsh
def test_zsh_reports_no_workspace_instead_of_aborting(tmp_path):
    r = _run("zsh", "blink_zephyr_ws; echo exit=$?", tmp_path)
    assert "no matches found" not in r.stderr
    assert r.stdout.strip() == "exit=1"


@needs_zsh
def test_zsh_globbing_is_left_as_it_was(tmp_path):
    """localoptions: the caller's shell keeps its own glob behaviour."""
    _workspace(tmp_path)
    r = _run("zsh", "blink_zephyr_ws >/dev/null; [[ -o nullglob ]] && echo on || echo off",
             tmp_path)
    assert r.stdout.strip() == "off"


@pytest.mark.skipif(os.name == "nt", reason="Git Bash's sh prints /c/... for"
                                         " C:\\..., so the path cannot match")
def test_sh_still_finds_the_workspace(tmp_path):
    ws = _workspace(tmp_path)
    r = _run("sh", "blink_zephyr_ws", tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == str(ws)


def _path_without_esptool(tmp_path):
    """A PATH holding the basic tools but no esptool, wherever this runs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("sh", "cat", "dirname", "printf", "echo"):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    return str(bin_dir)


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell and symlinks")
def test_activate_stops_before_the_build_without_esptool(tmp_path):
    _workspace(tmp_path)
    r = _run("sh", "blink_zephyr_activate; echo exit=$?", tmp_path,
             path=_path_without_esptool(tmp_path))
    assert r.stdout.strip() == "exit=1"
    assert "esptool is not on PATH" in r.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell and symlinks")
def test_activate_succeeds_with_esptool_on_path(tmp_path):
    _workspace(tmp_path)
    path = _path_without_esptool(tmp_path)
    fake = tmp_path / "bin" / "esptool"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    r = _run("sh", "blink_zephyr_activate; echo exit=$?", tmp_path, path=path)
    assert r.stdout.strip() == "exit=0", r.stderr


def test_the_suggested_versions_are_the_pinned_ones():
    """The fix the message prints must install what pc/requirements.txt pins,
    or following it would rebuild the bitstring-5 failure it is meant to cure."""
    pins = dict(re.findall(r"^([A-Za-z0-9_-]+)==(\S+)",
                           (ROOT / "pc" / "requirements.txt").read_text(),
                           re.M))
    text = LIB.read_text(encoding="utf-8")
    suggested = dict(re.findall(r"\b(esptool|bitstring)==([0-9][0-9.]*)", text))
    assert suggested == {"esptool": pins["esptool"],
                         "bitstring": pins["bitstring"]}
