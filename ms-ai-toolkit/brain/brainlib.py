#!/usr/bin/env python3
"""Path, repo and stopword resolution for every brain script.

One module so the rule exists once. Two components that must agree diverge if each restates
the rule -- measured: capture_rate_pct disagreed with the capture nudge on both what counts as
learning and what counts as a write, and each divergence pushed the number down independently.
The fix was not re-syncing them but making one READ the other. Everything here is that one.
"""
import os, re, subprocess

HOME = os.path.expanduser(os.environ.get("BRAIN_HOME", "~/.agent-brain"))
DB = os.path.expanduser(os.environ.get("BRAIN_DB", os.path.join(HOME, "brain.db")))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

# Where a repo named by a code_map row lives. Unset (the portable default) means "ask git":
# scope is the basename of the session's git toplevel, and a row's repo is resolved by
# searching the sibling directories of the current checkout. Set it to a directory holding
# your checkouts (e.g. ~/src) to resolve every repo name under one root instead.
REPO_ROOT = os.path.expanduser(os.environ["BRAIN_REPO_ROOT"]) if os.environ.get("BRAIN_REPO_ROOT") else None


def state_dir(name):
    """A bounded marker directory under BRAIN_HOME. Callers must prune -- see prune_markers."""
    d = os.path.join(HOME, name)
    os.makedirs(d, exist_ok=True)
    return d


def prune_markers(d, keep=400):
    """Keep a marker directory bounded. One file per session forever is ~3,650 files a year at
    ten sessions a day. Nothing breaks at that size, which is exactly why nobody would notice."""
    try:
        fs = [os.path.join(d, x) for x in os.listdir(d)]
        if len(fs) <= keep:
            return
        fs.sort(key=os.path.getmtime)
        for old in fs[:-keep]:
            os.remove(old)
    except Exception:
        pass


def git_toplevel(cwd=None):
    try:
        r = subprocess.run(["git", "-C", cwd or os.getcwd(), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except Exception:
        return None


def scope_for(cwd=None):
    """The scope name for a session working in `cwd`: the repo directory's basename.

    Under BRAIN_REPO_ROOT, the first path segment below the root -- so a session anywhere
    inside a checkout still scopes to the checkout, not to the subdirectory it happens to
    be sitting in.
    """
    cwd = os.path.abspath(cwd or os.getcwd())
    if REPO_ROOT:
        rel = os.path.relpath(cwd, REPO_ROOT)
        if not rel.startswith(".."):
            seg = rel.split(os.sep)[0]
            return seg if seg not in (".", "") else None
        return None
    top = git_toplevel(cwd)
    return os.path.basename(top) if top else None


def repo_path(repo, cwd=None):
    """Absolute path of a checkout named `repo`, or None if it is not on disk.

    Returning None matters: a code_map row pointing at a repo that no longer exists is
    definitively wrong, not unknown, and the recall hook flags it [STALE] rather than
    handing it over silently.
    """
    if not repo:
        return None
    if REPO_ROOT:
        p = os.path.join(REPO_ROOT, repo)
        return p if os.path.isdir(p) else None
    top = git_toplevel(cwd)
    if not top:
        return None
    if os.path.basename(top) == repo:
        return top
    sibling = os.path.join(os.path.dirname(top), repo)   # checkouts usually sit side by side
    return sibling if os.path.isdir(sibling) else None


def extra_stop():
    """Corpus-specific stopwords, comma-separated in BRAIN_STOP_EXTRA.

    Your org name belongs here: every path on the machine contains it, so it matches
    everything and carries no signal. Add only words that are broad in YOUR corpus -- the
    packaged list already covers ordinary English. Freeing concrete technical nouns that had
    been stopped as generic (local, hook, table, repo, column) cut unretrievable rows from
    8/321 to 4/327; stopping a real domain noun is the costlier mistake of the two.
    """
    return {w.strip().lower() for w in re.split(r"[,\s]+", os.environ.get("BRAIN_STOP_EXTRA", ""))
            if w.strip()}
