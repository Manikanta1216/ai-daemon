"""
JARVIS AI — Intelligent Agent Core
Decomposes compound/multi-step commands into ordered task lists.
Uses LLM when available, falls back to NLP-style rule splitting.

Example:
  "open whatsapp and message prasad where are you"
  → [
      Task(action="open_app", target="whatsapp"),
      Task(action="send_message", contact="Prasad", message="where are you")
    ]
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("jarvis.agent")


@dataclass
class Task:
    """A single decomposed task."""
    action: str
    target: str = ""
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending | running | done | failed
    result: str = ""

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "target": self.target,
            "params": self.params,
            "status": self.status,
        }


# ============================================
# COMPOUND COMMAND SPLITTERS (offline)
# ============================================

# Conjunctions that split commands
_SPLIT_WORDS = [" and then ", " then ", " after that ", " also ", " and "]

# Patterns for common compound commands
_COMPOUND_PATTERNS = [
    # "open X and message Y Z"
    (
        r"open\s+(\w+)\s+(?:and\s+)?(?:message|msg|text)\s+(\w+)\s+(.+)",
        lambda m: [
            Task(action="open_app", target=m.group(1)),
            Task(
                action="send_message",
                target=m.group(1),
                params={"contact": m.group(2), "message": m.group(3)},
            ),
        ],
    ),
    # "create file X" / "create file named X"
    (
        r"create\s+file\s+(?:named\s+)?([\w\.]+)",
        lambda m: [
            Task(action="file_operation", target=m.group(1), params={"action": "create_file", "filename": m.group(1)})
        ],
    ),
    # "open X and create file Y"
    (
        r"open\s+(\w+)\s+and\s+create\s+file\s+(?:named\s+)?([\w\.]+)",
        lambda m: [
            Task(action="open_app", target=m.group(1)),
            Task(action="file_operation", target=m.group(2), params={"action": "create_file", "filename": m.group(2)})
        ],
    ),
    # "open youtube play X" / "open youtube and play X"
    (
        r"open\s+youtube\s+(?:and\s+)?play\s+(.+)",
        lambda m: [
            Task(action="open_website", target="youtube"),
            Task(action="play_media", params={"query": m.group(1)}),
        ],
    ),
]


def decompose_command(command: str, llm=None) -> list[Task]:
    """
    Decompose a user command into a list of Tasks.
    GOD MODE: Supports workflow discovery, LLM decomposition, and self-correction.
    """
    if not command or not command.strip():
        return []

    command_clean = command.strip().lower()

    # 1. Try Workflow Discovery (Golden Recipes)
    # Check for complex workflows like "youtube search and play"
    if "youtube" in command_clean and "search" in command_clean and "play" in command_clean:
        query = command_clean.split("search for")[-1].split("and play")[0].strip()
        if not query:
            query = command_clean.split("search")[-1].split("play")[0].strip()
        
        return [
            Task(action="open_website", target="youtube.com"),
            Task(action="automation", params={"type": "wait", "value": "4"}),
            Task(action="automation", params={"type": "press_key", "value": "/"}),
            Task(action="automation", params={"type": "type_text", "value": query}),
            Task(action="automation", params={"type": "press_key", "value": "enter"}),
            Task(action="automation", params={"type": "wait", "value": "4"}),
            Task(action="automation", params={"type": "press_key", "value": "tab"}),
            Task(action="automation", params={"type": "press_key", "value": "enter"}),
            Task(action="chat", params={"query": f"I am now playing the first video for {query} on YouTube."})
        ]

    if "github" in command_clean and "login" in command_clean:
        return [
            Task(action="open_website", target="github.com/login"),
            Task(action="automation", params={"type": "wait", "value": "3"}),
            Task(action="chat", params={"query": "Navigating to GitHub login page. Ready to type credentials."})
        ]

    # 2. Try LLM decomposition (Dynamic Generation)
    if llm:
        try:
            tasks = _llm_decompose(command_clean, llm)
            if tasks and len(tasks) > 0:
                logger.info(f"LLM decomposed '{command_clean}' into {len(tasks)} tasks")
                return tasks
        except Exception as e:
            logger.warning(f"LLM decomposition failed: {e}")

    # 2. Try compound pattern matching
    tasks = _pattern_decompose(command_clean)
    if tasks and len(tasks) > 0:
        logger.info(f"Pattern decomposed '{command_clean}' into {len(tasks)} tasks")
        return tasks

    # 3. Try conjunction splitting
    tasks = _conjunction_decompose(command_clean)
    if tasks and len(tasks) > 1:
        logger.info(f"Conjunction decomposed '{command_clean}' into {len(tasks)} tasks")
        return tasks

    # 4. Single task — return as-is (will be handled by normal classifier)
    return []  # Empty means "use normal single-task pipeline"


def _llm_decompose(command: str, llm) -> list[Task]:
    """Use LLM to decompose a compound command into tasks."""
    system_prompt = """You are JARVIS, a Demi-God level Autonomous System Daemon. 
Your goal is to control the user's Windows 11 laptop with seamless, multi-threaded efficiency.
Break user commands into granular, sequential, or parallel tasks.

ACTIONS:
- "open_app": target=app_name
- "open_website": target=url
- "send_message": params={"contact": name, "message": text}
- "play_media": params={"query": text, "platform": "youtube|spotify"}
- "automation": params={"type": "type_text|press_key|click|wait|focus", "value": text/key}
- "file_operation": params={"action": "create_file|delete|move", "filename": text}
- "system_control": params={"action": "kill_process|volume|brightness", "target": text}

WORKFLOW LOGIC:
If user says "search youtube for movie and play first", break it into:
1. {"action":"open_website","target":"youtube.com"}
2. {"action":"automation","params":{"type":"wait","value":"3"}}
3. {"action":"automation","params":{"type":"press_key","value":"/"}}  # Focus search
4. {"action":"automation","params":{"type":"type_text","value":"telugu movies"}}
5. {"action":"automation","params":{"type":"press_key","value":"enter"}}
6. {"action":"automation","params":{"type":"wait","value":"3"}}
7. {"action":"automation","params":{"type":"press_key","value":"tab"}}
8. {"action":"automation","params":{"type":"press_key","value":"enter"}}

If user says "kill app from task manager", use "system_control" with "kill_process".

Return ONLY a valid JSON array."""

    response = llm.chat(command, system=system_prompt)

    # Parse JSON array
    try:
        tasks_data = json.loads(response)
    except json.JSONDecodeError:
        # Try extracting JSON from response
        brace_start = response.find("[")
        brace_end = response.rfind("]") + 1
        if brace_start != -1 and brace_end > brace_start:
            try:
                tasks_data = json.loads(response[brace_start:brace_end])
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(tasks_data, list):
        return []

    tasks = []
    for td in tasks_data:
        if isinstance(td, dict) and "action" in td:
            tasks.append(
                Task(
                    action=td["action"],
                    target=td.get("target", ""),
                    params=td.get("params", {}),
                )
            )
    return tasks


def _pattern_decompose(command: str) -> list[Task]:
    """Try compound regex patterns."""
    command_lower = command.lower().strip()
    for pattern, builder in _COMPOUND_PATTERNS:
        m = re.match(pattern, command_lower, re.IGNORECASE)
        if m:
            return builder(m)
    return []


def _conjunction_decompose(command: str) -> list[Task]:
    """Split on conjunctions and create individual tasks."""
    command_lower = command.lower().strip()

    # Find the best split point
    parts = None
    for splitter in _SPLIT_WORDS:
        if splitter in command_lower:
            idx = command_lower.index(splitter)
            parts = [
                command[:idx].strip(),
                command[idx + len(splitter):].strip(),
            ]
            break

    if not parts or len(parts) < 2:
        return []

    # Convert each part into a basic task
    tasks = []
    for part in parts:
        if not part:
            continue
        task = _classify_single_part(part)
        if task:
            tasks.append(task)

    return tasks


def _classify_single_part(text: str) -> Task | None:
    """Classify a single command fragment into a Task."""
    text_lower = text.lower().strip()

    # "open X"
    m = re.match(r"open\s+(.+)", text_lower)
    if m:
        target = m.group(1).strip()
        if "." in target or "http" in target:
            return Task(action="open_website", target=target)
        return Task(action="open_app", target=target)

    # "message/text X Y"
    m = re.match(r"(?:message|msg|text)\s+(\w+)\s*(.*)", text_lower)
    if m:
        return Task(
            action="send_message",
            params={"contact": m.group(1), "message": m.group(2).strip()},
        )

    # "play X"
    m = re.match(r"play\s+(.+)", text_lower)
    if m:
        return Task(action="play_media", params={"query": m.group(1).strip()})

    # "search X"
    m = re.match(r"search\s+(?:for\s+)?(.+)", text_lower)
    if m:
        return Task(action="search", params={"query": m.group(1).strip()})

    # "tell me X" / "what is X"
    if text_lower.startswith(("tell me", "what is", "what are", "explain", "who is")):
        return Task(action="chat", params={"query": text})

    # Fallback: treat as chat
    return Task(action="chat", params={"query": text})
