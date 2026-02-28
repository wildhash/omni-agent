"""Agent orchestrator: routes tasks to the appropriate specialist agent."""

from typing import Any, Dict, Optional


class AgentOrchestrator:
    """Routes incoming tasks to the correct agent based on keywords."""

    def __init__(self) -> None:
        from omni_agent.agents.web_agent import WebAgent
        from omni_agent.agents.code_agent import CodeAgent
        from omni_agent.self_heal import SelfHealer

        self.agents: Dict[str, Any] = {
            "web": WebAgent(),
            "code": CodeAgent(),
        }
        self.self_healer = SelfHealer(self)

    def delegate(self, task: str, context: Optional[Dict] = None) -> Dict:
        """Delegate *task* to the most appropriate agent.

        Parameters
        ----------
        task:
            Plain-text description of the work to be done.
        context:
            Optional dictionary of additional parameters for the agent.

        Returns
        -------
        dict
            The agent's result payload.
        """
        context = context or {}
        task_lower = task.lower()

        agent = None
        if any(kw in task_lower for kw in ("flight", "book", "scrape", "browse", "web")):
            agent = self.agents.get("web")
        elif any(
            kw in task_lower
            for kw in ("code", "run", "execute", "debug", "docker", "container")
        ):
            agent = self.agents.get("code")

        if agent is None:
            return {"error": f"No agent available for task: '{task}'"}

        try:
            return agent.execute(task, context)
        except Exception as exc:
            return self.self_healer.monitor(task, context, exc)

    def add_agent(self, name: str, agent: Any) -> str:
        """Dynamically register a new agent.

        Parameters
        ----------
        name:
            Key used to identify the agent.
        agent:
            Agent instance to register.
        """
        self.agents[name] = agent
        return f"Added {name} agent."
