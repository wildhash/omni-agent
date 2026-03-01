"""DocGenerator: auto-generates Markdown documentation from agent source files."""

import ast
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
        modules: Dict[str, Dict[str, str]] = {
            "orchestrator": {
                "file": "omni_agent/orchestrator.py",
                "import": "omni_agent.orchestrator",
                "class": "AgentOrchestrator",
                "example": 'result = agent.delegate("example task")',
            },
            "web_agent": {
                "file": "omni_agent/agents/web_agent.py",
                "import": "omni_agent.agents.web_agent",
                "class": "WebAgent",
                "example": 'result = agent.execute("example task")',
            },
            "code_agent": {
                "file": "omni_agent/agents/code_agent.py",
                "import": "omni_agent.agents.code_agent",
                "class": "CodeAgent",
                "example": 'result = agent.execute("example task")',
            },
            "voice_agent": {
                "file": "omni_agent/agents/voice_agent.py",
                "import": "omni_agent.agents.voice_agent",
                "class": "VoiceAgent",
                "example": 'result = agent.execute("say hello", {"action": "speak", "text": "hello"})',
            },
        }

        for name, module in modules.items():
            file_path = module["file"]
            if not os.path.exists(file_path):
                continue

            with open(file_path, "r", encoding="utf-8") as fh:
                code = fh.read()

            tree = ast.parse(code)
            docstring = ast.get_docstring(tree) or "No documentation available."
            methods = self._collect_method_signatures(tree)

            class_name = module["class"]
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
                f"from {module['import']} import {class_name}",
                f"agent = {class_name}()",
                module["example"],
                "```",
                "",
            ]

            out_path = os.path.join(self.doc_dir, f"{name}.md")
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(md_lines))

        self._update_docs_index(list(modules.keys()))

    def _collect_method_signatures(self, tree: ast.Module) -> List[str]:
        """Collect signatures for instance methods defined in top-level classes."""
        methods: List[str] = []

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                if not item.args.args or item.args.args[0].arg != "self":
                    continue

                arg_names = [arg.arg for arg in item.args.args[1:]]
                args_str = ", ".join(arg_names)
                prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                methods.append(
                    f"{prefix} {item.name}(self{', ' if args_str else ''}{args_str})"
                )

        return methods

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
