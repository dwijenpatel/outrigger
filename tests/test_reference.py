"""The corpus stays navigable: every relative markdown link must resolve.

Repurposed at the 2026-07-11 reincarnation from the v1 API-reference honesty
test (which asserted `harness.*` symbols — modules deleted from HEAD, see tag
`v1-attic`). The corpus and the design plan are now the repo's product; this
guards them the way the old test guarded the code.

Run: python3 -m unittest tests.test_reference -q
"""

import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+?)(?:#[^)]*)?\)")


def tracked_markdown():
    out = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "*.md"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return [f for f in out if os.path.exists(os.path.join(ROOT, f))]


class CorpusLinkTests(unittest.TestCase):
    def test_corpus_is_present(self):
        files = tracked_markdown()
        self.assertGreater(len(files), 50, "the corpus lost its content?")
        for anchor in (
            "docs/design/evidence-based-harness.md",
            "docs/research/distilled/external.md",
            "docs/research/distilled/internal.md",
            "docs/reincarnation-plan.md",
        ):
            self.assertIn(anchor, files, f"load-bearing document missing: {anchor}")

    def test_every_relative_link_resolves(self):
        broken = []
        for f in tracked_markdown():
            base = os.path.dirname(os.path.join(ROOT, f))
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                body = fh.read()
            for m in LINK.finditer(body):
                target = m.group(1)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if not os.path.exists(os.path.join(base, target)):
                    broken.append(f"{f} -> {target}")
        self.assertEqual(broken, [], "broken relative links:\n" + "\n".join(broken))


if __name__ == "__main__":
    unittest.main()
