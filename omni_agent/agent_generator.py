"""AgentGenerator: dynamically create and register new agents via Mistral."""

import ast
import importlib.util
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from omni_agent.mistral_client import MistralClient


class AgentGenerator:
    """Uses Mistral to generate new agent classes on demand.

    Methods
    -------
    generate_agent(agent_type, requirements):
        Write and persist a new agent module to disk.
    register_agent(orchestrator, agent_type):
        Generate a new agent and register it with *orchestrator*.
    """

    _AGENT_TYPE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        mistral: Optional[MistralClient] = None,
    ) -> None:
        self.base_dir = (base_dir or Path(__file__).resolve().parents[1]).resolve()
        self.mistral = mistral or MistralClient()

    def _normalize_agent_type(self, agent_type: str) -> str:
        agent_type = agent_type.strip()
        if agent_type.endswith("Agent"):
            agent_type = agent_type[: -len("Agent")]
        if not self._AGENT_TYPE_RE.fullmatch(agent_type):
            raise ValueError(
                "Invalid agent_type. Expected a CamelCase identifier like 'Voice' or 'VoiceAgent'."
            )
        return agent_type

    def _extract_python_code(self, text: str) -> str:
        text = text.strip()
        if not text.startswith("```"):
            return text

        lines = text.splitlines()
        if not lines:
            return ""

        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()

    def _validate_generated_module(self, source: str, expected_class_name: str) -> None:
        module = ast.parse(source)

        body = module.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]

        if len(body) != 1 or not isinstance(body[0], ast.ClassDef):
            raise ValueError(
                "Generated agent must contain exactly one top-level class definition."
            )
        if body[0].name != expected_class_name:
            raise ValueError(
                f"Generated agent class name must be '{expected_class_name}'."
            )

    def _agent_file_path(self, agent_type: str) -> Path:
        return self.base_dir / "omni_agent" / "agents" / f"{agent_type.lower()}_agent.py"

    def generate_agent(self, agent_type: str, requirements: str = "") -> Dict:
        """Dynamically generate and persist a new agent class.

        Parameters
        ----------
        agent_type:
            CamelCase name for the new agent (e.g. ``"VoiceAgent"``).
        requirements:
            Free-form description of what the agent must do.

        Returns
        -------
        dict
            Status payload with ``status``, ``agent_type``, ``file``,
            ``class``, and ``module`` keys on success.
        """
        try:
            normalized_type = self._normalize_agent_type(agent_type)
            class_name = f"{normalized_type}Agent"

            prompt = (
                f"Create a new Omni-Agent agent class named: {class_name}.\n"
                f"Requirements: {requirements}.\n\n"
                "Constraints:\n"
                f"- The output MUST define `class {class_name}:`\n"
                "- The class MUST include `execute(task: str, context: dict) -> dict`\n"
                "- Include error handling and logging\n"
                "- Use type hints and docstrings\n"
                "- Do not include any other top-level code (no imports, no helper functions)\n\n"
                "Return ONLY the Python source code."
            )

            raw = self.mistral.generate_code(prompt)
            agent_code = self._extract_python_code(raw)
            self._validate_generated_module(agent_code, class_name)

            file_path = self._agent_file_path(normalized_type)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(agent_code, encoding="utf-8")

            module_name = f"omni_agent_generated_{normalized_type.lower()}_agent"
            return {
                "status": "success",
                "agent_type": normalized_type,
                "file": str(file_path),
                "class": class_name,
                "module": module_name,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def activate_agent(self, agent_type: str) -> Dict:
        """Load a generated agent module and return its class.

        Activation is disabled by default and must be explicitly enabled by
        setting ``OMNI_AGENT_ENABLE_GENERATED_AGENTS=1``.
        """
        if os.getenv("OMNI_AGENT_ENABLE_GENERATED_AGENTS") != "1":
            return {
                "status": "pending_approval",
                "message": "Set OMNI_AGENT_ENABLE_GENERATED_AGENTS=1 to activate generated agents.",
            }

        try:
            normalized_type = self._normalize_agent_type(agent_type)
            class_name = f"{normalized_type}Agent"
            file_path = self._agent_file_path(normalized_type)
            if not file_path.exists():
                return {
                    "status": "error",
                    "message": f"Generated agent file does not exist: {file_path}",
                }

            source = file_path.read_text(encoding="utf-8")
            self._validate_generated_module(source, class_name)

            module_name = f"omni_agent_generated_{normalized_type.lower()}_agent"
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if spec is None or spec.loader is None:
                return {"status": "error", "message": "Failed to load module spec."}

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            agent_class = getattr(module, class_name)

            return {
                "status": "success",
                "agent_type": normalized_type,
                "file": str(file_path),
                "class": class_name,
                "agent_class": agent_class,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def register_agent(
        self,
        orchestrator: Any,
        agent_type: str,
        requirements: str = "",
        agent_key: Optional[str] = None,
    ) -> Dict:
        """Generate a new agent and register it with *orchestrator*.

        Parameters
        ----------
        orchestrator:
            An :class:`~omni_agent.orchestrator.AgentOrchestrator` instance.
        agent_type:
            CamelCase name for the new agent (e.g. ``"VoiceAgent"``).

        Returns
        -------
        dict
            Status payload.
        """
        result = self.generate_agent(agent_type, requirements=requirements)
        if result["status"] != "success":
            return result

        activation = self.activate_agent(result["agent_type"])
        if activation["status"] != "success":
            return {
                **result,
                "status": activation["status"],
                "message": activation.get("message", "Generated agent requires activation."),
            }

        key = agent_key or result["agent_type"].lower()
        agent_class = activation["agent_class"]
        agent_instance = agent_class()
        orchestrator.add_agent(key, agent_instance)
        return {"status": "success", "agent": result["agent_type"], "key": key}
