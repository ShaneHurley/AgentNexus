from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from daily_coder.github_remote import (
    GitHubRemoteError,
    clone_github_repo,
    parse_github_https_url,
    resolve_clone_destination,
)


class GitHubRemoteTests(unittest.TestCase):
    def test_parse_ok(self):
        owner, repo, canonical = parse_github_https_url("https://github.com/octocat/Hello-World.git")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")
        self.assertEqual(canonical, "https://github.com/octocat/Hello-World")

    def test_parse_rejects_http_and_creds(self):
        with self.assertRaises(GitHubRemoteError):
            parse_github_https_url("http://github.com/a/b")
        with self.assertRaises(GitHubRemoteError):
            parse_github_https_url("https://user:token@github.com/a/b")
        with self.assertRaises(GitHubRemoteError):
            parse_github_https_url("https://evil.example/a/b")

    def test_dest_must_be_under_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jail"
            root.mkdir()
            dest = resolve_clone_destination(
                owner="o", repo="r", dest=None, allowed_roots=[root]
            )
            self.assertTrue(str(dest).startswith(str(root.resolve())))
            outside = Path(tmp) / "outside" / "r"
            with self.assertRaises(GitHubRemoteError):
                resolve_clone_destination(
                    owner="o", repo="r", dest=outside, allowed_roots=[root]
                )

    def test_clone_invokes_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jail"
            root.mkdir()

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            with patch("daily_coder.github_remote.subprocess.run", return_value=Result()) as run:
                out = clone_github_repo(
                    "https://github.com/octocat/Hello-World",
                    allowed_roots=[root],
                    token=None,
                )
            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "clone")
            args = run.call_args[0][0]
            self.assertEqual(args[0], "git")
            self.assertEqual(args[1], "clone")
            self.assertIn("https://github.com/octocat/Hello-World.git", args)


if __name__ == "__main__":
    unittest.main()
