#!/usr/bin/env python3
"""Pooled lease-based worktree lifecycle (G1, design §6.2 — Stage-2 machinery).

A warm pool of detached-HEAD worktrees kills per-pipeline *environment*
cold-start (an O2 win only — the §6.2 cache-warmup admission cost stays).
Prior-art hardening rules (unattended-operation-prior-art.md §4):

- **Durable leases** — a lease lives in the pool state file, not in a process:
  a pipeline that dies mid-run keeps its worktree for the disk-resume; an
  acquired member is never handed out again until released, even with zero
  live processes inside.
- **Fail-closed teardown with precise "landed" semantics** — a member is
  destroyed only when its work is landed: HEAD an ancestor of base, **or
  patch-id contained** (`git cherry` — survives squash-merge-then-delete), or
  the tree clean at base. No blanket force flag exists; each risk is accepted
  by its own named flag (``include_unlanded``, ``include_leased``).
- Dirty members are never reused silently — reuse requires a clean reset onto
  the requested ref; untracked build caches survive (that is the point).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess


class WorktreeError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(cwd: str, *args, check=True) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                         text=True, timeout=120)
    if check and out.returncode != 0:
        raise WorktreeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out


def landed(repo: str, ref: str, base: str = "main") -> dict:
    """Precise 'landed' semantics: ancestor of base, or every commit patch-id
    contained in base (squash-merge survivor)."""
    if _git(repo, "rev-parse", "--verify", ref, check=False).returncode != 0:
        raise WorktreeError(f"ref {ref!r} does not exist")
    ancestor = _git(repo, "merge-base", "--is-ancestor", ref, base,
                    check=False).returncode == 0
    if ancestor:
        return {"landed": True, "how": "ancestor"}
    cherry = _git(repo, "cherry", base, ref)
    lines = [ln for ln in cherry.stdout.splitlines() if ln.strip()]
    if lines and all(ln.startswith("-") for ln in lines):
        return {"landed": True, "how": "patch-id containment (post-squash)"}
    unlanded = sum(1 for ln in lines if ln.startswith("+"))
    return {"landed": False,
            "how": f"{unlanded} commit(s) with no equivalent on {base}"}


class Pool:
    """Worktree pool for one repo. State is a JSON file (durable leases)."""

    def __init__(self, repo: str, pool_dir: str, max_members: int = 4):
        if max_members < 1:
            raise WorktreeError(f"max_members must be >= 1, got {max_members}")
        self.repo = os.path.abspath(repo)
        self.pool_dir = os.path.abspath(pool_dir)
        self.max_members = max_members
        self.state_path = os.path.join(self.pool_dir, "pool-state.json")

    # -- state ------------------------------------------------------------------

    def _read_state(self) -> dict:
        try:
            with open(self.state_path) as fh:
                doc = json.load(fh)
        except FileNotFoundError:
            return {"members": {}}
        except json.JSONDecodeError as exc:
            raise WorktreeError(
                f"pool state {self.state_path} corrupt: {exc} — refusing to "
                f"guess at leases") from None
        if not isinstance(doc.get("members"), dict):
            raise WorktreeError(f"pool state {self.state_path}: malformed")
        return doc

    def _write_state(self, doc: dict) -> None:
        os.makedirs(self.pool_dir, exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.state_path)

    # -- lifecycle ---------------------------------------------------------------

    def acquire(self, ref: str, lease_holder: str) -> str:
        """Lease a warm member reset to ``ref``, or grow the pool. Refuses when
        every member is leased and the pool is at cap (the caller's concurrency
        problem, not ours to solve by over-provisioning)."""
        if not lease_holder:
            raise WorktreeError("lease_holder must be non-empty")
        state = self._read_state()
        members = state["members"]

        for path, meta in sorted(members.items()):
            if meta.get("leased_by"):
                continue
            if not os.path.isdir(path):
                continue  # vanished member; skip (prune cleans state)
            dirty = _git(path, "status", "--porcelain").stdout.strip()
            if dirty:
                continue  # never silently reuse a dirty member
            _git(path, "checkout", "-q", "--detach", ref)
            meta.update(leased_by=lease_holder, leased_at=_utcnow_iso(),
                        last_ref=ref)
            self._write_state(state)
            return path

    # no free member: grow if under cap
        if len(members) >= self.max_members:
            raise WorktreeError(
                f"pool at cap ({self.max_members}) with no free clean member — "
                f"release or teardown first")
        path = os.path.join(self.pool_dir,
                            f"member-{len(members) + 1}")
        _git(self.repo, "worktree", "add", "--detach", path, ref)
        members[path] = {"created_at": _utcnow_iso(),
                         "leased_by": lease_holder,
                         "leased_at": _utcnow_iso(), "last_ref": ref}
        self._write_state(state)
        return path

    def release(self, path: str) -> None:
        state = self._read_state()
        meta = state["members"].get(os.path.abspath(path))
        if meta is None:
            raise WorktreeError(f"{path} is not a pool member")
        meta["leased_by"] = None
        meta["released_at"] = _utcnow_iso()
        self._write_state(state)

    def status(self) -> dict:
        state = self._read_state()
        leased = {p: m["leased_by"] for p, m in state["members"].items()
                  if m.get("leased_by")}
        return {"members": len(state["members"]), "leased": leased,
                "free": len(state["members"]) - len(leased),
                "cap": self.max_members}

    def teardown(self, path: str, base: str = "main",
                 include_unlanded: bool = False,
                 include_leased: bool = False) -> dict:
        """Destroy one member, fail-closed. Refusals name the exact risk and
        the exact flag that accepts it — no blanket force."""
        path = os.path.abspath(path)
        state = self._read_state()
        meta = state["members"].get(path)
        if meta is None:
            raise WorktreeError(f"{path} is not a pool member")
        if meta.get("leased_by") and not include_leased:
            raise WorktreeError(
                f"{path} is leased by {meta['leased_by']!r} — a lease survives "
                f"its process by design; pass include_leased to accept "
                f"destroying leased work")
        risks = []
        if os.path.isdir(path):
            dirty = _git(path, "status", "--porcelain").stdout.strip()
            if dirty:
                risks.append(f"dirty ({len(dirty.splitlines())} entries)")
            head_landed = landed(self.repo, meta.get("last_ref", "HEAD"),
                                 base=base) if meta.get("last_ref") else \
                {"landed": True, "how": "no ref recorded"}
            head = _git(path, "rev-parse", "HEAD").stdout.strip()
            head_state = landed(self.repo, head, base=base)
            if not head_state["landed"]:
                risks.append(f"unlanded HEAD ({head_state['how']})")
            del head_landed
        if risks and not include_unlanded:
            raise WorktreeError(
                f"{path} holds work that is not landed on {base!r}: "
                f"{'; '.join(risks)} — pass include_unlanded to accept the "
                f"loss")
        if os.path.isdir(path):
            _git(self.repo, "worktree", "remove", "--force", path)
        del state["members"][path]
        self._write_state(state)
        return {"removed": path, "accepted_risks": risks}
