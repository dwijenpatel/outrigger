"""Cross-vendor instruction-surface parity guard.

The repo serves two coding agents: Claude Code (reads CLAUDE.md, scans
.claude/skills/) and Codex CLI (reads AGENTS.md natively, scans
.agents/skills/ and follows symlinks — learn.chatgpt.com/docs/build-skills,
verified 2026-07-13). One canonical source per surface; these tests keep the
two discovery paths pointing at the same bytes.

Run: python3 -m unittest tests.test_agent_surfaces -q
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InstructionSurfaces(unittest.TestCase):
    def test_agents_md_is_the_shared_source(self):
        path = os.path.join(ROOT, "AGENTS.md")
        self.assertTrue(os.path.isfile(path), "root AGENTS.md must exist (Codex reads it natively)")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        # the portable standing directives live here, not in CLAUDE.md
        for sentinel in ("feature branch", "ff-only", "corpus guard", "evidence-gated"):
            self.assertIn(sentinel, body, f"AGENTS.md lost the {sentinel!r} directive")
        # vendor-specific instructions must NOT leak into the shared file
        self.assertNotIn("Fable", body, "model-routing guidance is Claude-specific; keep it in CLAUDE.md")

    def test_claude_md_imports_agents_md(self):
        path = os.path.join(ROOT, "CLAUDE.md")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertRegex(body, re.compile(r"^@AGENTS\.md\s*$", re.M),
                         "CLAUDE.md must import AGENTS.md (the documented interoperability pattern)")
        self.assertIn("Opus 4.8", body, "the sub-agent model directive is Claude-specific and stays here")

    def test_skills_are_one_canonical_directory(self):
        canonical = os.path.join(ROOT, ".claude", "skills")
        mirror = os.path.join(ROOT, ".agents", "skills")
        self.assertTrue(os.path.islink(mirror), ".agents/skills must be a symlink (no content drift)")
        self.assertEqual(os.path.realpath(mirror), os.path.realpath(canonical))
        skill = os.path.join(mirror, "spec-interview", "SKILL.md")
        with open(skill, encoding="utf-8") as fh:
            head = fh.read(600)
        self.assertIn("name: spec-interview", head)
        self.assertIn("description:", head)


if __name__ == "__main__":
    unittest.main(verbosity=2)
