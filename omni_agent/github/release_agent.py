"""ReleaseAgent: automates versioned GitHub releases with auto-generated changelogs."""

import os
from typing import List

from github import Github  # type: ignore


class ReleaseAgent:
    """Creates versioned GitHub releases with auto-generated changelogs.

    Parameters
    ----------
    repo_name:
        Full repository name in ``owner/repo`` format.
    """

    def __init__(self, repo_name: str) -> None:
        token = os.getenv("GITHUB_TOKEN")
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)

    def create_release(self, version: str) -> str:
        """Create a GitHub release tagged *version*.

        Parameters
        ----------
        version:
            Semantic version string, e.g. ``v0.1.0``.

        Returns
        -------
        str
            URL of the newly created release.
        """
        default_branch = self.repo.default_branch
        main_sha = self.repo.get_branch(default_branch).commit.sha

        tags = list(self.repo.get_tags())
        last_tag = tags[0].name if tags else None

        if last_tag:
            commits = self.repo.compare(last_tag, main_sha).commits
        else:
            commits = list(self.repo.get_commits(sha=main_sha))

        changelog = "\n".join(
            f"- {commit.commit.message.splitlines()[0]}" for commit in commits
        )

        release = self.repo.create_git_release(
            tag=version,
            name=f"Omni-Agent {version}",
            message=f"## Changelog\n\n{changelog}",
            target_commitish=main_sha,
        )
        return release.html_url

    def next_version(self) -> str:
        """Compute the next patch-level semantic version.

        Returns
        -------
        str
            Next version string, e.g. ``v0.1.1``.
        """
        tags: List = list(self.repo.get_tags())
        if not tags:
            return "v0.1.0"
        last_tag = tags[0].name.lstrip("v")
        parts = last_tag.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return f"v{'.'.join(parts)}"


if __name__ == "__main__":
    agent = ReleaseAgent("wildhash/omni-agent")
    version = agent.next_version()
    url = agent.create_release(version)
    print(f"Release created: {url}")
