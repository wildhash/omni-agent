"""SelfHealer: monitors task errors and attempts automatic recovery."""

import json
import logging
import os
import traceback
from typing import Any, Dict

from omni_agent.agent_generator import AgentGenerator
from omni_agent.mistral_client import MistralClient


class SelfHealer:
    """Diagnoses runtime errors and applies fixes using Mistral.

    Methods
    -------
    monitor(task, context, error):
        Analyse an error and attempt to heal the system.
    """

    def __init__(self, orchestrator: Any) -> None:
        self.orchestrator = orchestrator
        self.mistral = MistralClient()
        self.agent_generator = AgentGenerator()
        self.logger = logging.getLogger("SelfHealer")

    def monitor(self, task: str, context: dict, error: Exception) -> Dict:
        """Analyse *error* that occurred during *task* and attempt self-healing.

        Parameters
        ----------
        task:
            The task that was being executed when the error occurred.
        context:
            The context dictionary passed to the failing agent.
        error:
            The exception that was raised.

        Returns
        -------
        dict
            A status payload describing the healing outcome.
        """
        error_trace = traceback.format_exc()
        self.logger.error("Error in task '%s': %s", task, error_trace)

        diagnosis = self._diagnose_error(task, context, error_trace)
        self.logger.info("Diagnosis: %s", diagnosis)

        if diagnosis.get("fixable", False):
            return self._apply_fix(diagnosis)

        return {
            "status": "unfixable",
            "error": str(error),
            "diagnosis": diagnosis,
        }

    def _diagnose_error(
        self, task: str, context: dict, error_trace: str
    ) -> Dict:
        """Use Mistral to produce a structured diagnosis of the error.

        Parameters
        ----------
        task:
            Task description.
        context:
            Context dictionary.
        error_trace:
            Full traceback string.

        Returns
        -------
        dict
            Diagnosis with keys ``error_type``, ``root_cause``, ``fixable``,
            and ``suggested_fix``.
        """
        prompt = (
            "Omni-Agent encountered an error. Analyse and suggest fixes.\n\n"
            f"Task: {task}\n"
            f"Context: {context}\n"
            f"Error Trace:\n{error_trace}\n\n"
            "Respond with JSON:\n"
            "{\n"
            '    "error_type": "string",\n'
            '    "root_cause": "string",\n'
            '    "fixable": bool,\n'
            '    "suggested_fix": {\n'
            '        "type": "string",\n'
            '        "details": "string",\n'
            '        "code_snippet": "string"\n'
            "    }\n"
            "}"
        )
        try:
            response = self.mistral.generate_code(prompt)
            return self._parse_model_json(response)
        except Exception as exc:
            self.logger.error("Diagnosis failed: %s", exc)
            return {
                "error_type": "DiagnosisFailed",
                "root_cause": str(exc),
                "fixable": False,
            }

    @staticmethod
    def _parse_model_json(text: str) -> Dict[str, Any]:
        def strip_code_fence(value: str) -> str:
            stripped = value.strip()
            if not stripped.startswith("```"):
                return stripped

            lines = stripped.splitlines()
            if lines and lines[0].lstrip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()

        def extract_first_object(value: str) -> str:
            start = value.find("{")
            if start == -1:
                raise ValueError("No JSON object found in model response")

            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(value)):
                ch = value[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue

                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return value[start : i + 1]

            raise ValueError("No complete JSON object found in model response")

        def remove_trailing_commas(value: str) -> str:
            out: list[str] = []
            in_string = False
            escape = False
            i = 0
            while i < len(value):
                ch = value[i]
                if in_string:
                    out.append(ch)
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    i += 1
                    continue

                if ch == '"':
                    in_string = True
                    out.append(ch)
                    i += 1
                    continue

                if ch == ",":
                    j = i + 1
                    while j < len(value) and value[j].isspace():
                        j += 1
                    if j < len(value) and value[j] in ("}", "]"):
                        i += 1
                        continue

                out.append(ch)
                i += 1

            return "".join(out)

        stripped = strip_code_fence(text)
        candidate = extract_first_object(stripped)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = json.loads(remove_trailing_commas(candidate))

        if not isinstance(parsed, dict):
            raise TypeError("Expected a JSON object")

        return parsed

    def _apply_fix(self, diagnosis: Dict) -> Dict:
        """Apply the fix recommended in *diagnosis*.

        Parameters
        ----------
        diagnosis:
            Structured diagnosis dict produced by :meth:`_diagnose_error`.

        Returns
        -------
        dict
            Outcome payload.
        """
        fix = diagnosis.get("suggested_fix", {})
        fix_type = fix.get("type", "")

        if fix_type == "new_agent":
            details = fix.get("details", "")
            parts = details.split()
            if not parts:
                return {"status": "failed", "error": "No agent type specified in fix details."}
            agent_type = parts[-1]
            result = self.agent_generator.register_agent(
                self.orchestrator, agent_type
            )
            return {
                "status": "fixed",
                "action": "generated_new_agent",
                "agent": agent_type,
                "result": result,
            }

        if fix_type == "code_change":
            details = fix.get("details", "")
            parts = details.split()
            if not parts:
                return {"status": "failed", "error": "No file path specified in fix details."}
            file_path = os.path.realpath(parts[0])
            project_root = os.path.realpath(os.getcwd())
            if not file_path.startswith(project_root + os.sep):
                return {"status": "failed", "error": f"Unsafe file path rejected: {parts[0]}"}
            new_code = fix.get("code_snippet", "")
            try:
                with open(file_path, "w") as f:
                    f.write(new_code)
                return {"status": "fixed", "action": "updated_code", "file": file_path}
            except Exception as exc:
                return {"status": "failed", "error": str(exc)}

        if fix_type == "config_update":
            return {"status": "not_implemented", "fix_type": fix_type}

        return {"status": "unknown_fix_type", "fix_type": fix_type}
