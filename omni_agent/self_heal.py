"""SelfHealer: monitors task errors and attempts automatic recovery."""

import json
import logging
import os
import traceback
from pathlib import Path
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
        self.project_root = Path(__file__).resolve().parents[1]
        self.allowed_write_roots = (
            self.project_root / "omni_agent",
            self.project_root / "tests",
        )

    def _resolve_write_path(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError("file_path must be relative")

        resolved = (self.project_root / candidate).resolve()
        for allowed in self.allowed_write_roots:
            allowed_resolved = allowed.resolve()
            if resolved == allowed_resolved or allowed_resolved in resolved.parents:
                return resolved
        raise ValueError(f"Unsafe file path rejected: {relative_path}")

    def monitor(self, task: str, context: dict, error: Exception) -> Dict:
        """Analyse *error* that occurred during *task* and attempt self-healing."""
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

    def _diagnose_error(self, task: str, context: dict, error_trace: str) -> Dict:
        """Use Mistral to produce a structured diagnosis of the error."""
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
            '        "agent_type": "string",\n'
            '        "file_path": "string",\n'
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
            lines = value.splitlines()
            for idx, line in enumerate(lines):
                if line.lstrip().startswith("{"):
                    value = "\n".join(lines[idx:])
                    break

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

        stripped = strip_code_fence(text)
        candidate = extract_first_object(stripped)
        parsed = json.loads(candidate)

        if not isinstance(parsed, dict):
            raise TypeError("Expected a JSON object")

        return parsed

    def _apply_fix(self, diagnosis: Dict) -> Dict:
        """Apply the fix recommended in *diagnosis*."""
        fix = diagnosis.get("suggested_fix", {})
        fix_type = fix.get("type", "")

        if fix_type == "new_agent":
            agent_type = fix.get("agent_type")
            if not agent_type:
                details = fix.get("details", "")
                parts = details.split()
                agent_type = parts[-1] if parts else ""

            if not agent_type:
                return {
                    "status": "failed",
                    "error": "No agent type specified in suggested_fix.",
                }

            result = self.agent_generator.register_agent(
                self.orchestrator,
                agent_type,
                requirements=fix.get("details", ""),
            )

            status = "fixed" if result.get("status") == "success" else "proposed"
            return {
                "status": status,
                "action": "generated_new_agent",
                "agent": agent_type,
                "result": result,
            }

        if fix_type == "code_change":
            file_path = fix.get("file_path")
            if not file_path:
                details = fix.get("details", "")
                parts = details.split()
                file_path = parts[0] if parts else ""

            if not file_path:
                return {
                    "status": "failed",
                    "error": "No file path specified in suggested_fix.",
                }

            new_code = fix.get("code_snippet", "")
            try:
                resolved = self._resolve_write_path(file_path)
            except Exception as exc:
                return {"status": "failed", "error": str(exc)}

            if os.getenv("OMNI_AGENT_ENABLE_SELF_HEAL_APPLY") != "1":
                return {
                    "status": "proposed",
                    "action": "update_code",
                    "file": str(resolved),
                    "message": "Set OMNI_AGENT_ENABLE_SELF_HEAL_APPLY=1 to allow SelfHealer to write files.",
                    "code": new_code,
                }

            try:
                compile(new_code, str(resolved), "exec")
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(new_code, encoding="utf-8")
                return {
                    "status": "fixed",
                    "action": "updated_code",
                    "file": str(resolved),
                }
            except Exception as exc:
                return {"status": "failed", "error": str(exc)}

        if fix_type == "config_update":
            return {"status": "not_implemented", "fix_type": fix_type}

        return {"status": "unknown_fix_type", "fix_type": fix_type}
