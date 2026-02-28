"""GitHubAgent: main self-sustaining loop that orchestrates all phases."""

import subprocess
from time import sleep

from omni_agent.docs.generator import DocGenerator
from omni_agent.github.issue_agent import IssueAgent
from omni_agent.github.release_agent import ReleaseAgent


class GitHubAgent:
    """Orchestrates issue monitoring, refactoring, documentation, testing, and releases.

    Parameters
    ----------
    repo_name:
        Full repository name in ``owner/repo`` format.
    """

    def __init__(self, repo_name: str) -> None:
        self.repo_name = repo_name
        self.issue_agent = IssueAgent(repo_name)
        self.release_agent = ReleaseAgent(repo_name)
        self.doc_generator = DocGenerator()

    def run(self) -> None:
        """Main loop: monitor issues, refactor, document, test, and release."""
        print("🤖 GitHubAgent activated. Entering self-sustaining loop...")

        while True:
            try:
                print("🔍 Checking for new issues...")
                self.issue_agent.monitor_issues()

                print("🔄 Auto-refactoring...")
                self._auto_refactor()

                print("📚 Generating documentation...")
                self.doc_generator.generate()

                print("🧪 Running tests...")
                subprocess.run(["pytest", "tests/"], check=False)

                if self._should_release():
                    version = self.release_agent.next_version()
                    print(f"🎉 Creating release {version}...")
                    release_url = self.release_agent.create_release(version)
                    print(f"Release created: {release_url}")

                sleep(3600)

            except Exception as exc:
                print(f"⚠️ Error in main loop: {exc}")
                sleep(60)

    def _auto_refactor(self) -> None:
        """Placeholder for LLM-based code refactoring logic."""

    def _should_release(self) -> bool:
        """Return True if there are more than 10 commits since the last tag."""
        try:
            tags = list(self.release_agent.repo.get_tags())
            if not tags:
                return False
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{tags[0].name}..HEAD"],
                capture_output=True,
                text=True,
            )
            return int(result.stdout.strip()) > 10
        except Exception:
            return False


if __name__ == "__main__":
    agent = GitHubAgent("wildhash/omni-agent")
    agent.run()
