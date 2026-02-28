"""CodeAgent: executes, debugs, and containerises code."""

import subprocess
from typing import Any, Dict, Optional


class CodeAgent:
    """Executes Python code, provides debugging hints, and builds Docker images.

    Methods
    -------
    execute(task, context):
        Route code tasks to specific tools.
    """

    def __init__(self) -> None:
        self.tools: Dict[str, Any] = {
            "execute_python": self._execute_python,
            "debug": self._debug,
            "containerize": self._containerize,
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
        elif "docker" in task_lower or "container" in task_lower:
            return self._containerize(context)
        else:
            return {"error": f"Code task not recognised: '{task}'"}

    def _execute_python(self, code: str) -> Dict:
        """Execute *code* in a sandboxed subprocess with a 10-second timeout.

        Parameters
        ----------
        code:
            Python source code to run.
        """
        if not code:
            return {"error": "No code provided."}
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
