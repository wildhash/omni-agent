"""AgentGenerator: dynamically create and register new agents via Mistral."""

import importlib
import importlib.util
import os
from typing import Any, Dict

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

    def __init__(self) -> None:
        self.mistral = MistralClient()

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
        prompt = (
            f"Create a new Omni-Agent agent of type: {agent_type}.\n"
            f"Requirements: {requirements}.\n\n"
            "The agent must:\n"
            "1. Be a Python class with an `execute(task: str, context: dict) -> dict` method.\n"
            "2. Include error handling and logging.\n"
            "3. Integrate with Omni-Agent's orchestrator.\n"
            "4. Use type hints and docstrings.\n\n"
            "Return ONLY the Python class definition."
        )

        try:
            agent_code = self.mistral.generate_code(prompt)

            filename = os.path.join(
                "omni_agent", "agents", f"{agent_type.lower()}_agent.py"
            )
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w") as f:
                f.write(agent_code)

            module_name = f"omni_agent.agents.{agent_type.lower()}_agent"
            spec = importlib.util.spec_from_file_location(module_name, filename)
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]

            agent_class = getattr(module, f"{agent_type}Agent")
            return {
                "status": "success",
                "agent_type": agent_type,
                "file": filename,
                "class": agent_class.__name__,
                "module": module_name,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def register_agent(self, orchestrator: Any, agent_type: str) -> Dict:
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
        result = self.generate_agent(agent_type)
        if result["status"] == "success":
            module = importlib.import_module(
                f"omni_agent.agents.{agent_type.lower()}_agent"
            )
            agent_class = getattr(module, f"{agent_type}Agent")
            agent_instance = agent_class()
            orchestrator.add_agent(agent_type.lower(), agent_instance)
            return {"status": "success", "agent": agent_type}
        return result
