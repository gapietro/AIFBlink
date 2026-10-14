"""Which Claude account is signed in, and what that does to the claude page.

Two kinds of account meter usage in two different ways, and one person can
hold both on the same machine:

  - Claude Pro and Max have a five-hour session window and a seven-day one,
    and Claude Code reports both on its status line.
  - Claude Enterprise bills by SPEND: a dollar cap per day, week or month
    that the organisation's admin sets, with no five-hour window at all.
    Claude Code reports it only behind a Claude apps gateway, as
    `rate_limits.spend_limit`; a plain claude.ai Enterprise login gets no
    `rate_limits` whatever (code.claude.com/docs/en/statusline).

The person this was built for switches between a Max login and a corporate
one with /login, several times a day, to keep the corporate allowance for
corporate work. That makes the switch the dangerous moment rather than
either account on its own: every file this daemon reads keeps the previous
account's numbers until something overwrites them, so straight after a
switch to the corporate login the Max session window is still in the status
line, still in Claude Desktop's cache, still in the weekly anchor -- and the
page would go on drawing it under whatever the new account turns out to be.

So this module answers two questions and nothing else:

  1. Which account is signed in now, and since when? Read from
     `oauthAccount` in ~/.claude.json, which Claude Code rewrites on every
     /login. That is Claude Code's cached copy of the account PROFILE --
     names, an organisation type, a seat tier -- and not a credential: the
     token lives in the macOS Keychain or in ~/.claude/.credentials.json,
     neither of which this project opens. pc/statusline_source's promise
     that "this project handles no Anthropic credential" still holds.

  2. Given that, which of this poll's claude frames may reach the panel?
     See select().

Nothing read from the profile is ever logged -- not the organisation type,
not the account id it is compared by. The file also holds per-project
history for every directory Claude Code has opened, which is somebody's
work, and it is read for one key and dropped.
"""
import json
import os

from pc.providers import base

PROVIDER_ID = "claude"

# The organisation types that mean "this account has no session window".
#
# Measured on one Max desk ("claude_max"); the two below are Claude Code's
# spellings for the other two organisation kinds, and they are the only
# values that change behaviour here. An unrecognised value -- a new plan,
# a renamed one -- is treated as a consumer account, which is the panel as
# it was before 1.4.0: windows when there are windows, and nothing invented
# when there are not. Guessing "enterprise" for an unknown type would put
# "not reported" over a Max account's perfectly good numbers.
ACCOUNT_KINDS = {
    "claude_enterprise": "enterprise",
    "claude_team": "team",
}


def profile_path() -> str:
    """Where Claude Code keeps its account profile.

    A function, not a module constant -- see CLAUDE.md on module-level
    expanduser and the test sandbox. CLAUDE_CONFIG_DIR moves the file, and
    Claude Code honours it, so this does too; without it a desk that keeps
    its profile elsewhere would read as "no account" for ever.
    """
    base_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if base_dir:
        return os.path.join(os.path.expanduser(base_dir), ".claude.json")
    return os.path.join(os.path.expanduser("~"), ".claude.json")


def read_profile(path=None):
    """(kind, identity) for the signed-in account, or None.

    `kind` is "enterprise", "team" or "consumer". `identity` is an opaque
    tuple that changes when the account does, compared and never shown.

    None for every way of not knowing: no file, no oauthAccount (an API-key
    login, or a machine that has never signed in), a file mid-rewrite. The
    caller treats None as "nothing has changed", which is the safe reading
    of a file that could not be read for a second.
    """
    if path is None:
        path = profile_path()
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    acct = doc.get("oauthAccount") if isinstance(doc, dict) else None
    if not isinstance(acct, dict):
        return None
    org_type = acct.get("organizationType")
    kind = ACCOUNT_KINDS.get(org_type, "consumer") if isinstance(
        org_type, str) else "consumer"
    identity = (acct.get("accountUuid"), acct.get("organizationUuid"))
    if identity == (None, None):
        return None
    return kind, identity


class AccountWatch:
    """The signed-in account, and the moment this daemon saw it change.

    ~/.claude.json is rewritten constantly -- Claude Code records project
    history in it -- so its mtime says nothing about when anybody logged in.
    The switch time is therefore the moment THIS process first saw a
    different account, which on a daemon that polls every two seconds is
    within two seconds of the /login.

    It is also why the first reading after the daemon starts sets no switch
    time at all. A daemon that has just started has seen no switch, and it
    cannot date one it did not see; treating "the account I found at
    startup" as a switch that happened now would throw away every reading on
    the machine on each restart, including the ones that are this account's.
    The cost is narrow: a switch made while the daemon was not running is
    not noticed until the next one, and select() still prefers the freshest
    reading, which is the switched-to account's as soon as it uses anything.

    The file can be large and is read only when its (size, mtime) moves.
    """

    def __init__(self, path=None):
        self._path = path
        self._stat = None
        self._profile = None
        self.kind = ""
        self.since = None
        # The profile's mtime, which IS a measure of something: Claude Code
        # rewrites the file as it works, so this is when it last did. It is
        # the active_at of a PLAN_UNREPORTED frame -- see select().
        self.touched_at = None

    def poll(self, now_epoch):
        path = self._path if self._path is not None else profile_path()
        try:
            st = os.stat(path)
            key = (st.st_size, st.st_mtime)
        except OSError:
            return
        if key == self._stat:
            return
        self._stat = key
        self.touched_at = st.st_mtime
        prof = read_profile(path)
        if prof is None:
            return
        kind, identity = prof
        if self._profile is not None and identity != self._profile[1]:
            self.since = now_epoch
        self._profile = prof
        self.kind = kind


def _is_usage(f):
    return f.has_usage() or f.plan == base.PLAN_UNREPORTED


def select(frames, kind="", since=None, now_epoch=None, touched_at=None):
    """The frames that may describe the claude page, given the account.

    Frames from other providers, and claude frames that carry no usage --
    the hook's session state -- pass through untouched: which account is
    signed in has nothing to say about whether a session is waiting.

    For the claude usage frames, three rules, in order:

      1. Nothing from before a switch. A reading taken before `since`
         belongs to the account that was signed in then.

      2. One plan, never a blend. If the freshest reading is a spend
         reading, every window reading goes, and the other way round. The
         normalizer merges field by field by recency, and left to itself it
         would put a Max weekly figure beside an Enterprise spend figure on
         one page -- each true of a different account, together true of
         nothing.

      3. An Enterprise or Team login with nothing left to show gets a
         PLAN_UNREPORTED frame, so the page says that in words instead of
         falling back to dashes that look like a fault. A Team or seat-based
         Enterprise account that DOES report windows is shown as windows:
         rule 2 has already kept them, and a frame that carries numbers is
         never replaced by one that says there are none.

    That frame is dated NOW, because "this account reports nothing" is true
    as of this poll and must not be captioned as an hours-old reading. Its
    `active_at` is not now, though: that field is what the board dozes on,
    and a statement this daemon makes on its own every two seconds is not
    evidence that anybody is at the desk. It takes the profile's mtime
    instead, which Claude Code moves when it works.
    """
    keep, usage = [], []
    for f in frames:
        if f is None:
            continue
        if f.provider == PROVIDER_ID and _is_usage(f):
            if since is None or f.observed_at >= since:
                usage.append(f)
        else:
            keep.append(f)

    if usage:
        newest = max(usage, key=lambda f: f.observed_at)
        if newest.plan == base.PLAN_SPEND:
            usage = [f for f in usage if f.plan == base.PLAN_SPEND]
        else:
            usage = [f for f in usage if f.plan != base.PLAN_SPEND]
    if not usage and kind in ("enterprise", "team"):
        now = now_epoch if now_epoch is not None else 0.0
        usage = [base.NormalizedUsageFrame(
            provider=PROVIDER_ID, src="account", observed_at=now,
            active_at=min(now, touched_at) if touched_at is not None else now,
            plan=base.PLAN_UNREPORTED, account=kind)]
    return keep + usage
