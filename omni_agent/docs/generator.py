"""DocGenerator: auto-generates Markdown documentation from agent source files."""

import os
from typing import Dict, List


class DocGenerator:
    """Auto-generates Markdown documentation for all Omni-Agent components.

    Methods
    -------
    generate():
        Create Markdown docs for every registered agent.
    """

    def __init__(self) -> None:
        self.doc_dir = os.path.join(os.path.dirname(__file__))

    def generate(self) -> None:
        """Auto-generate Markdown docs for all agents and update the index."""
        agents: Dict[str, str] = {
            "orchestrator": "omni_agent/orchestrator.py",
            "web_agent": "omni_agent/agents/web_agent.py",
            "code_agent": "omni_agent/agents/code_agent.py",
        }

        for name, file_path in agents.items():
            if not os.path.exists(file_path):
                continue

            with open(file_path, "r", encoding="utf-8") as fh:
                code = fh.read()

            # Extract the module-level docstring
            parts = code.split('"""')
            docstring = parts[1].strip() if len(parts) >= 3 else "No documentation available."

            # Collect method signatures
            methods = [
                line.strip()
                for line in code.splitlines()
                if line.strip().startswith("def ") and "self" in line
            ]

            class_name = "".join(w.capitalize() for w in name.split("_"))
            md_lines = [
                f"# {name.replace('_', ' ').title()}",
                "",
                docstring,
                "",
                "## Methods",
                "",
            ]
            for method in methods:
                md_lines.append(f"- `{method}`")

            md_lines += [
                "",
                "## Example Usage",
                "",
                "```python",
                f"from omni_agent.agents.{name} import {class_name}",
                f"agent = {class_name}()",
                'result = agent.execute("example task")',
                "```",
                "",
            ]

            out_path = os.path.join(self.doc_dir, f"{name}.md")
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(md_lines))

        self._update_docs_index(list(agents.keys()))

    def _update_docs_index(self, agent_names: List[str]) -> None:
        """Regenerate the docs index README.

        Parameters
        ----------
        agent_names:
            List of agent module names to include in the index.
        """
        lines = [
            "# Omni-Agent Documentation",
            "",
            "## 🤖 Agents",
            "",
        ]
        for name in agent_names:
            lines.append(f"- [{name.replace('_', ' ').title()}]({name}.md)")
        lines.append("")

        index_path = os.path.join(self.doc_dir, "README.md")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))


if __name__ == "__main__":
    generator = DocGenerator()
    generator.generate()
