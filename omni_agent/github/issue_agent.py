"""IssueAgent: monitors GitHub issues and responds or resolves them autonomously."""

import os
from typing import Any

from github import Github  # type: ignore


class IssueAgent:
    """Monitors a GitHub repository for open issues and responds to them.

    Parameters
    ----------
    repo_name:
        Full repository name in ``owner/repo`` format.
    """

    def __init__(self, repo_name: str) -> None:
        token = os.getenv("GITHUB_TOKEN")
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)

    def monitor_issues(self) -> None:
        """Check for open issues and triage / respond to each one."""
        open_issues = self.repo.get_issues(state="open")
        for issue in open_issues:
            label_names = [lbl.name for lbl in issue.labels]
            if "bug" in label_names:
                self._handle_bug(issue)
            elif "feature" in label_names:
                self._handle_feature(issue)
            else:
                issue.create_comment(
                    "🤖 GitHubAgent here! I've seen this issue. "
                    "Please label it as `bug` or `feature` for faster resolution."
                )

    def _handle_bug(self, issue: Any) -> None:
        """Attempt to provide a fix suggestion for a bug issue.

        Parameters
        ----------
        issue:
            A PyGithub ``Issue`` object.
        """
        issue.create_comment(
            f"🤖 Bug acknowledged: **{issue.title}**.\n\n"
            "I'm analysing the codebase for a fix. Stay tuned!"
        )

    def _handle_feature(self, issue: Any) -> None:
        """Propose an implementation plan for a feature request.

        Parameters
        ----------
        issue:
            A PyGithub ``Issue`` object.
        """
        issue.create_comment(
            f"🤖 Feature request noted: **{issue.title}**.\n\n"
            "I'll draft an implementation plan and open a PR shortly."
        )


if __name__ == "__main__":
    agent = IssueAgent("wildhash/omni-agent")
    agent.monitor_issues()
