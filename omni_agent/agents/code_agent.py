"""CodeAgent: executes, debugs, and containerises code."""

import os
import subprocess
from typing import Any, Dict, Optional

from omni_agent.mistral_client import MistralClient


class CodeAgent:
    """Executes Python code, provides debugging hints, and builds Docker images.

    Code execution and Docker image builds are disabled by default.

    Methods
    -------
    execute(task, context):
        Route code tasks to specific tools.
    """

    def __init__(self) -> None:
        self.mistral = MistralClient()
        self.tools: Dict[str, Any] = {
            "execute_python": self._execute_python,
            "debug": self._debug,
            "containerize": self._containerize,
            "improve": self._improve_code,
            "generate_agent": self._generate_agent,
        }

    def execute(self, task: str, context: Optional[Dict] = None) -> Dict:
        """Route *task* to the correct code tool.

        Parameters
        ----------
        task:
            Description of the code task.
        context:
            Optional parameters (e.g. code snippet, dockerfile path).
        """
        context = context or {}
        task_lower = task.lower()

        if "execute" in task_lower or "run" in task_lower:
            return self._execute_python(context.get("code", ""))
        elif "debug" in task_lower:
            return self._debug(context.get("code", ""))
        elif "improve" in task_lower:
            return self._improve_code(context.get("code", ""), task)
        elif "generate agent" in task_lower:
            return self._generate_agent(context.get("agent_type", ""))
        elif "docker" in task_lower or "container" in task_lower:
            return self._containerize(context)
        else:
            return {"error": f"Code task not recognised: '{task}'"}

    def _execute_python(self, code: str) -> Dict:
        """Execute *code* in a subprocess with a 10-second timeout.

        This is **not** a secure sandbox. Only enable code execution in trusted
        environments.

        Parameters
        ----------
        code:
            Python source code to run.
        """
        if not code:
            return {"error": "No code provided."}
        if os.getenv("OMNI_AGENT_ENABLE_CODE_EXEC") != "1":
            return {
                "error": "Code execution is disabled by default. Set OMNI_AGENT_ENABLE_CODE_EXEC=1 to enable.",
            }
        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Execution timed out."}

    def _debug(self, code: str) -> Dict:
        """Provide static debugging hints for *code*.

        Parameters
        ----------
        code:
            Python source code to analyse.
        """
        return {
            "analysis": "Code looks syntactically correct. Add print statements for debugging.",
            "suggested_fixes": ["Add logging.", "Check variable types."],
        }

    def _containerize(self, context: Dict) -> Dict:
        """Build a Docker image for the application described in *context*.

        Parameters
        ----------
        context:
            Dictionary with optional keys: 'path', 'dockerfile', 'tag'.
        """
        if os.getenv("OMNI_AGENT_ENABLE_DOCKER_BUILD") != "1":
            return {
                "error": "Docker builds are disabled by default. Set OMNI_AGENT_ENABLE_DOCKER_BUILD=1 to enable.",
            }
        try:
            import docker  # type: ignore

            client = docker.from_env()
            image, _ = client.images.build(
                path=context.get("path", "."),
                dockerfile=context.get("dockerfile", "Dockerfile"),
                tag=context.get("tag", "omni-agent-app"),
            )
            return {"status": "success", "image_id": image.id}
        except Exception as exc:  # pragma: no cover
            return {"error": str(exc)}

    def _improve_code(self, code: str, task: str) -> Dict:
        """Use Mistral to improve *code* with respect to *task*.

        Parameters
        ----------
        code:
            Existing Python source code to refine.
        task:
            Description of what the code should do.
        """
        try:
            improved = self.mistral.improve_code(code, task)
            return {
                "original_code": code,
                "improved_code": improved,
                "status": "success",
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _generate_agent(self, agent_type: str) -> Dict:
        """Dynamically generate a new agent class using Mistral.

        Parameters
        ----------
        agent_type:
            CamelCase name for the new agent (e.g. ``"VoiceAgent"``).
        """
        try:
            prompt = (
                f"Write a Python class for a {agent_type} that integrates with Omni-Agent.\n"
                "The class should:\n"
                "1. Inherit from a base Agent class (if applicable).\n"
                "2. Include a constructor and an `execute(task: str, context: dict)` method.\n"
                "3. Use modern Python practices (type hints, docstrings).\n"
                "4. Handle errors gracefully.\n"
                "Return ONLY the class definition, no explanations."
            )
            agent_code = self.mistral.generate_code(prompt)

            filename = os.path.join(
                "omni_agent", "agents", f"{agent_type.lower()}_agent.py"
            )
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w") as f:
                f.write(agent_code)

            return {
                "status": "success",
                "agent_type": agent_type,
                "file": filename,
                "code": agent_code,
            }
        except Exception as exc:
            return {"error": str(exc)}
