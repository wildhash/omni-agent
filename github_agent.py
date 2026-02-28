"""GitHubAgent: main self-sustaining loop that orchestrates all phases."""

import os
import subprocess
import traceback
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
    poll_interval_seconds:
        Seconds to sleep between successful cycles.
    error_backoff_seconds:
        Initial seconds to back off after an exception.
    max_cycles:
        Optional upper bound on the number of cycles to run.
    max_error_backoff_seconds:
        Maximum seconds to back off after repeated exceptions.
    """

    def __init__(
        self,
        repo_name: str,
        *,
        poll_interval_seconds: int = 3600,
        error_backoff_seconds: int = 60,
        max_cycles: int | None = None,
        max_error_backoff_seconds: int = 3600,
    ) -> None:
        self.repo_name = repo_name
        self.issue_agent = IssueAgent(repo_name)
        self.release_agent = ReleaseAgent(repo_name)
        self.doc_generator = DocGenerator()
        self.poll_interval_seconds = max(1, poll_interval_seconds)
        self.error_backoff_seconds = max(1, error_backoff_seconds)
        self.max_cycles = max_cycles
        self.max_error_backoff_seconds = max(1, max_error_backoff_seconds)

    def run(self) -> None:
        """Main loop: monitor issues, refactor, document, test, and release."""
        print("🤖 GitHubAgent activated. Entering self-sustaining loop...")

        releases_enabled = os.getenv("OMNI_AGENT_ENABLE_RELEASES") == "1"
        if not releases_enabled:
            print(
                "Releases are disabled. Set OMNI_AGENT_ENABLE_RELEASES=1 to enable release creation."
            )

        cycles = 0
        backoff = min(self.error_backoff_seconds, self.max_error_backoff_seconds)

        try:
            while self.max_cycles is None or cycles < self.max_cycles:
                try:
                    print("🔍 Checking for new issues...")
                    self.issue_agent.monitor_issues()

                    print("🔄 Auto-refactoring...")
                    self._auto_refactor()

                    print("📚 Generating documentation...")
                    self.doc_generator.generate()

                    print("🧪 Running tests...")
                    test_result = subprocess.run(["pytest", "tests/"], check=False)
                    if test_result.returncode != 0:
                        print(
                            f"Tests failed (return code {test_result.returncode}); skipping release."
                        )
                    elif releases_enabled and self._should_release():
                        version = self.release_agent.next_version()
                        print(f"🎉 Creating release {version}...")
                        release_url = self.release_agent.create_release(version)
                        print(f"Release created: {release_url}")

                    backoff = min(
                        self.error_backoff_seconds, self.max_error_backoff_seconds
                    )
                    sleep(self.poll_interval_seconds)

                except Exception as exc:
                    print(f"⚠️ Error in main loop: {exc}")
                    traceback.print_exc()
                    sleep(backoff)
                    backoff = min(backoff * 2, self.max_error_backoff_seconds)

                cycles += 1
        except KeyboardInterrupt:
            return

    def _auto_refactor(self) -> None:
        """Placeholder for LLM-based code refactoring logic."""

    def _should_release(self) -> bool:
        """Return True if there are more than 10 commits since the last tag."""
        try:
            tags = list(self.release_agent.repo.get_tags())
            if not tags:
                return False

            default_branch = self.release_agent.repo.default_branch
            comparison = self.release_agent.repo.compare(tags[0].name, default_branch)
            return comparison.total_commits > 10
        except Exception:
            return False


if __name__ == "__main__":
    agent = GitHubAgent("wildhash/omni-agent")
    agent.run()
