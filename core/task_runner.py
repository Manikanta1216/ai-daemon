"""
JARVIS AI — Multi-Task Execution Engine
Runs decomposed tasks sequentially, tracks status, and builds natural responses.
"""

import logging
from core.agent import Task

logger = logging.getLogger("jarvis.task_runner")


class TaskRunner:
    """
    Executes a list of Tasks sequentially.
    Each task runs independently and reports status.
    Builds a unified natural language response.
    """

    def __init__(self):
        self._executor = None
        self._resolver = None

    @property
    def executor(self):
        """Lazy-load the task executor."""
        if self._executor is None:
            from core.executor import get_executor
            self._executor = get_executor()
        return self._executor

    @property
    def resolver(self):
        """Lazy-load the app resolver."""
        if self._resolver is None:
            from core.app_resolver import resolve_target
            self._resolver = resolve_target
        return self._resolver

    def run(self, tasks: list[Task]) -> str:
        """
        Execute all tasks sequentially with real-time voice feedback.
        """
        if not tasks:
            return ""

        results = []
        from core.speech import speak

        for i, task in enumerate(tasks):
            # Real-time feedback for significant tasks
            desc = self._describe_task(task)
            if i == 0:
                speak(f"Starting your request. I will {desc} first.")
            elif task.action not in ("automation", "wait"):
                speak(f"Next, I will {desc}.")

            logger.info(f"Running task {i + 1}/{len(tasks)}: {task.action} → {task.target}")
            task.status = "running"

            try:
                result = self._execute_single_task(task)
                task.status = "done"
                task.result = result
                results.append(result)
            except Exception as e:
                task.status = "failed"
                task.result = f"Failed: {e}"
                results.append(f"Failed to {self._describe_task(task)}")
                speak(f"Sorry, I encountered an error while trying to {desc}.")

        # Build final summary
        return self._build_response(tasks, results)

    def _execute_single_task(self, task: Task) -> str:
        """Execute a single task by routing to the appropriate handler."""
        action = task.action
        target = task.target
        params = task.params

        # Build intent_data compatible with executor
        if action == "open_app":
            resolved = self.resolver(target)
            if resolved["type"] == "website":
                intent_data = {
                    "intent": "open_website",
                    "entities": {"url": resolved["url"], "app": resolved["name"]},
                    "confidence": 0.95,
                }
            else:
                intent_data = {
                    "intent": "open_app",
                    "entities": {"app": target},
                    "confidence": 0.95,
                }

        elif action == "open_website":
            from core.app_resolver import resolve_website
            resolved = resolve_website(target)
            if resolved:
                intent_data = {
                    "intent": "open_website",
                    "entities": {"url": resolved["url"], "app": resolved["name"]},
                    "confidence": 0.95,
                }
            else:
                intent_data = {
                    "intent": "open_website",
                    "entities": {"url": f"https://{target}", "app": target},
                    "confidence": 0.7,
                }

        elif action == "send_message":
            contact = params.get("contact", "")
            message = params.get("message", "")
            intent_data = {
                "intent": "send_whatsapp",
                "entities": {"recipient": contact, "body": message},
                "confidence": 0.9,
            }

        elif action == "play_media":
            intent_data = {
                "intent": "play_media",
                "entities": {"query": params.get("query", "")},
                "confidence": 0.9,
            }

        elif action == "search":
            intent_data = {
                "intent": "search",
                "entities": {
                    "query": params.get("query", ""),
                    "engine": params.get("engine", "google"),
                },
                "confidence": 0.9,
            }

        elif action == "chat":
            intent_data = {
                "intent": "chat",
                "entities": {"query": params.get("query", "")},
                "confidence": 0.9,
            }

        elif action == "weather":
            intent_data = {
                "intent": "weather",
                "entities": {"city": params.get("city", "")},
                "confidence": 0.9,
            }

        elif action == "system_control":
            intent_data = {
                "intent": "system_control",
                "entities": {"action": params.get("action", target)},
                "confidence": 0.9,
            }

        elif action == "volume_control":
            intent_data = {
                "intent": "volume_control",
                "entities": {"action": params.get("action", target)},
                "confidence": 0.9,
            }

        elif action == "screenshot":
            intent_data = {
                "intent": "screenshot",
                "entities": {},
                "confidence": 0.95,
            }

        elif action == "get_info":
            intent_data = {
                "intent": "get_info",
                "entities": {"query": params.get("query", target)},
                "confidence": 0.9,
            }

        elif action == "send_email":
            intent_data = {
                "intent": "send_email",
                "entities": params,
                "confidence": 0.9,
            }

        elif action == "file_operation":
            intent_data = {
                "intent": "file_operation",
                "entities": params,
                "confidence": 0.9,
            }

        elif action == "automation":
            intent_data = {
                "intent": "automation",
                "entities": params,
                "confidence": 0.95,
            }

        else:
            # Unknown action — try as chat
            intent_data = {
                "intent": "chat",
                "entities": {"query": f"{action} {target} {params}".strip()},
                "confidence": 0.5,
            }

        return self.executor.execute(intent_data)

    def _describe_task(self, task: Task) -> str:
        """Generate a human-readable description of a task."""
        descriptions = {
            "open_app": f"open {task.target}",
            "open_website": f"open {task.target}",
            "send_message": f"send message to {task.params.get('contact', 'contact')}",
            "play_media": f"play {task.params.get('query', 'media')}",
            "search": f"search for {task.params.get('query', 'something')}",
            "chat": "respond to your question",
            "weather": "get the weather",
            "system_control": f"{task.params.get('action', 'control')} the system",
            "screenshot": "take a screenshot",
        }
        return descriptions.get(task.action, task.action)

    def _build_response(self, tasks: list[Task], results: list[str]) -> str:
        """
        Build a single natural language response from multiple task results.
        Concise for long automation workflows.
        """
        if len(tasks) > 3:
            # Check if it's mostly automation
            automation_tasks = [t for t in tasks if t.action == "automation"]
            if len(automation_tasks) > len(tasks) / 2:
                # Return a high-level summary
                main_task = tasks[0].target or tasks[0].action
                return f"Automation workflow for {main_task} completed successfully."

        if len(results) == 1:
            return results[0]

        # Filter out "Done", "Waited", "Pressed" etc. for cleaner speech
        silent_results = ["Done.", "Waited", "Pressed:", "Typed:", "Focused window:"]
        meaningful = []
        for r in results:
            if not r or r.strip() == "Done.":
                continue
            if any(r.startswith(s) for s in silent_results):
                continue
            meaningful.append(r)

        if not meaningful:
            return "Workflow completed."

        if len(meaningful) == 1:
            return meaningful[0]

        # Join naturally
        parts = meaningful[:-1]
        last = meaningful[-1]
        return ", ".join(parts) + f", and {last.lower() if last[0].isupper() else last}"


# ============================================
# SINGLETON
# ============================================
_runner = None


def get_task_runner() -> TaskRunner:
    """Get or create global task runner."""
    global _runner
    if _runner is None:
        _runner = TaskRunner()
    return _runner
