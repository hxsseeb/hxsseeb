#!/usr/bin/env python3
"""The house rules a machine can check. .github/workflows/rules.yml runs it on every PR and push to main.

Usage: python3 .github/scripts/house_rules.py <base> <head>
Checks the files at <head> for em dashes, and the commits in <base>..<head> (and the PR body in $PR_BODY, when set)
for AI attribution. Secrets are gitleaks' job, in the same workflow.
"""
import os
import re
import subprocess
import sys

EM_DASH = chr(0x2014)
# Verbatim third-party text: the pinned Humanizer skill quotes the character in its rules. Keep this list in the PR
# body that changes it.
EM_DASH_EXCEPTIONS = ("skills/humanizer/", ".claude/skills/humanizer/")
# Byte-identical to the pattern in dot_local/bin/executable_hearth-guard, so CI and the local hook agree; change both.
ATTRIBUTION = re.compile(r"(co-authored-by|assisted-by):[^\n]*(claude|anthropic)|(generated (with|by)|made with)\W{0,4}(claude|anthropic)|noreply@anthropic\.com", re.I)
AI_AUTHOR = re.compile(r"claude|anthropic", re.I)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def em_dashes(head):
    found = []
    for path in git("ls-tree", "-r", "--name-only", head).splitlines():
        if path.startswith(EM_DASH_EXCEPTIONS):
            continue
        raw = subprocess.run(["git", "show", f"{head}:{path}"], capture_output=True).stdout
        if b"\0" in raw:
            continue
        for number, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            if EM_DASH in line:
                found.append(f"{path}:{number}: em dash; use a hyphen or recast the sentence")
    return found


def attribution(base, head):
    found = []
    log = git("log", "--format=%H%x00%an <%ae>%x00%cn <%ce>%x00%B%x01", f"{base}..{head}")
    for entry in filter(str.strip, log.split("\x01")):
        sha, author, committer, body = entry.strip().split("\0", 3)
        if ATTRIBUTION.search(body):
            found.append(f"{sha[:7]}: AI attribution in the commit message")
        if AI_AUTHOR.search(author) or AI_AUTHOR.search(committer):
            found.append(f"{sha[:7]}: authored or committed as {author if AI_AUTHOR.search(author) else committer}")
    if ATTRIBUTION.search(os.environ.get("PR_BODY", "")):
        found.append("PR body: AI attribution")
    return found


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2])
        return 2
    base, head = argv[1], argv[2]
    problems = em_dashes(head) + attribution(base, head)
    print("\n".join(problems) or "House rules: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
