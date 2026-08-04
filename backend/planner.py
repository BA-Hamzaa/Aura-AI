"""
planner.py — J.A.R.V.I.S. Planning & Task Decomposition Engine.

Given a complex user request, the planner:
  1. Classifies the request (simple vs complex)
  2. Decomposes complex requests into subtasks
  3. Determines which agent/tool handles each subtask
  4. Returns an execution plan

This prevents blind execution and ensures the assistant thinks before acting.
"""

import re
import json
from typing import List, Dict, Optional, Any
from enum import Enum


class TaskComplexity(Enum):
    SIMPLE    = "simple"     # Single-step, immediate execution
    MODERATE  = "moderate"   # 2-4 steps, sequential
    COMPLEX   = "complex"    # Multi-step, possibly parallel


class RiskLevel(Enum):
    LOW    = "low"     # Safe, execute immediately
    MEDIUM = "medium"  # Confirm before executing
    HIGH   = "high"    # Require explicit approval


class SubTask:
    def __init__(
        self,
        step_id: int,
        description: str,
        agent: str,
        tool: str,
        params: Dict[str, Any],
        depends_on: List[int] = None,
        risk: RiskLevel = RiskLevel.LOW,
    ):
        self.step_id     = step_id
        self.description = description
        self.agent       = agent
        self.tool        = tool
        self.params      = params
        self.depends_on  = depends_on or []
        self.risk        = risk
        self.status      = "pending"   # pending | running | done | failed
        self.result      = None

    def to_dict(self) -> Dict:
        return {
            "step_id":     self.step_id,
            "description": self.description,
            "agent":       self.agent,
            "tool":        self.tool,
            "params":      self.params,
            "depends_on":  self.depends_on,
            "risk":        self.risk.value,
            "status":      self.status,
        }


class ExecutionPlan:
    def __init__(
        self,
        request: str,
        complexity: TaskComplexity,
        subtasks: List[SubTask],
        summary: str = "",
        needs_confirmation: bool = False,
    ):
        self.request             = request
        self.complexity          = complexity
        self.subtasks            = subtasks
        self.summary             = summary
        self.needs_confirmation  = needs_confirmation

    def to_dict(self) -> Dict:
        return {
            "request":            self.request,
            "complexity":         self.complexity.value,
            "summary":            self.summary,
            "needs_confirmation": self.needs_confirmation,
            "steps":              [s.to_dict() for s in self.subtasks],
        }


# ── Risk Classification Table ─────────────────────────────────────────────────

_HIGH_RISK_KEYWORDS = [
    "delete", "remove", "format", "shutdown", "reboot", "restart",
    "kill process", "send email", "transfer", "purchase", "buy",
    "drop database", "rm -rf", "wipe",
]

_MEDIUM_RISK_KEYWORDS = [
    "run script", "execute", "download", "install", "uninstall",
    "close all", "sign out", "logout", "clear history",
    "move files", "rename folder",
]

_DESTRUCTIVE_PATTERNS = [
    r"delete\s+\w*\s*files?",
    r"format\s+(disk|drive|partition)",
    r"rm\s+-rf",
    r"shutdown|reboot",
]


def _assess_risk(text: str) -> RiskLevel:
    t = text.lower()
    if any(kw in t for kw in _HIGH_RISK_KEYWORDS):
        return RiskLevel.HIGH
    if any(re.search(p, t) for p in _DESTRUCTIVE_PATTERNS):
        return RiskLevel.HIGH
    if any(kw in t for kw in _MEDIUM_RISK_KEYWORDS):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


# ── Intent Detection ──────────────────────────────────────────────────────────

_INTENT_PATTERNS: List[Dict] = [
    # Automation
    {"pattern": r"\b(open|launch|start)\s+(\w+)", "agent": "automation", "action": "open_app"},
    {"pattern": r"\b(close|quit|kill)\s+(\w+)", "agent": "automation", "action": "close_app"},
    {"pattern": r"\b(search|google)\s+(.+)", "agent": "automation", "action": "search_google"},
    {"pattern": r"\b(play|youtube)\s+(.+)", "agent": "automation", "action": "youtube"},
    {"pattern": r"\bscreenshot\b", "agent": "automation", "action": "screenshot"},
    {"pattern": r"\bvolume\b.*(set|to)\s*(\d+)", "agent": "automation", "action": "volume"},
    {"pattern": r"\block\s*(screen|pc|computer)", "agent": "automation", "action": "lock"},
    {"pattern": r"\b(sleep|suspend|hibernate)\b", "agent": "automation", "action": "sleep"},
    {"pattern": r"\b(shutdown|turn off)\b", "agent": "automation", "action": "shutdown"},
    {"pattern": r"\b(restart|reboot)\b", "agent": "automation", "action": "restart"},
    {"pattern": r"\bsend\s+email\b", "agent": "automation", "action": "send_email"},
    # Memory
    {"pattern": r"\b(remember|save|note)\s+(.+)", "agent": "memory", "action": "remember"},
    {"pattern": r"\b(recall|what did|find my|remind me)\b", "agent": "memory", "action": "recall"},
    {"pattern": r"\badd\s+(task|todo|reminder)\b", "agent": "memory", "action": "add_task"},
    # Code
    {"pattern": r"\b(write|generate|create)\s+(code|script|function|class)\b", "agent": "coding", "action": "generate"},
    {"pattern": r"\b(debug|fix|refactor)\s+.*(code|bug|error)\b", "agent": "coding", "action": "debug"},
    {"pattern": r"\bexplain\s+(this|the)?\s*(code|function|algorithm)\b", "agent": "coding", "action": "explain"},
    # Vision
    {"pattern": r"\b(analyze|read|ocr|extract text from)\s+(screen|image|screenshot)\b", "agent": "vision", "action": "analyze"},
    # Research
    {"pattern": r"\b(research|find out|look up|what is|who is|explain)\s+", "agent": "research", "action": "research"},
    # Weather
    {"pattern": r"\bweather\b", "agent": "research", "action": "weather"},
    # Calendar
    {"pattern": r"\b(schedule|calendar|appointment|event)\b", "agent": "scheduler", "action": "schedule"},
    # System
    {"pattern": r"\bbattery\b", "agent": "automation", "action": "battery"},
    {"pattern": r"\bwifi\s*(on|off|enable|disable)\b", "agent": "automation", "action": "wifi"},
]


def _detect_intents(request: str) -> List[Dict]:
    found = []
    for p in _INTENT_PATTERNS:
        m = re.search(p["pattern"], request, re.IGNORECASE)
        if m:
            found.append({
                "agent":  p["agent"],
                "action": p["action"],
                "match":  m.group(0),
                "groups": list(m.groups()),
            })
    return found


# ── Multi-step Detection ──────────────────────────────────────────────────────

_CONJUNCTION_PATTERNS = [
    r"\band\s+then\b",
    r"\bafter\s+that\b",
    r"\bthen\b",
    r"\balso\b",
    r"\bfinally\b",
    r"\bnext\b",
    r"\bfollowed by\b",
    r";\s*",
]

def _is_multistep(request: str) -> bool:
    for pat in _CONJUNCTION_PATTERNS:
        if re.search(pat, request, re.IGNORECASE):
            return True
    # Count detected intents
    return len(_detect_intents(request)) >= 2


# ── Planner ───────────────────────────────────────────────────────────────────

class Planner:
    """
    Decomposes user requests into structured execution plans.
    Works independently of the AI model — uses rule-based intent detection.
    The AI model is only called for complex requests to generate subtask details.
    """

    def plan(self, request: str) -> ExecutionPlan:
        request = request.strip()
        intents = _detect_intents(request)
        is_multi = _is_multistep(request)
        risk = _assess_risk(request)

        # Determine complexity
        if not intents or len(intents) == 0:
            complexity = TaskComplexity.SIMPLE
        elif len(intents) == 1 and not is_multi:
            complexity = TaskComplexity.SIMPLE
        elif len(intents) <= 3:
            complexity = TaskComplexity.MODERATE
        else:
            complexity = TaskComplexity.COMPLEX

        # Build subtasks
        subtasks = []
        if intents:
            for idx, intent in enumerate(intents):
                subtask = SubTask(
                    step_id=idx + 1,
                    description=f"{intent['action']}: {intent['match']}",
                    agent=intent["agent"],
                    tool=intent["action"],
                    params={"raw_match": intent["match"], "groups": intent["groups"]},
                    depends_on=[idx] if idx > 0 else [],
                    risk=risk if idx == 0 else RiskLevel.LOW,
                )
                subtasks.append(subtask)
        else:
            # Default: send to AI agent
            subtasks = [SubTask(
                step_id=1,
                description=f"AI response to: {request[:60]}",
                agent="ai",
                tool="ask",
                params={"question": request},
                risk=RiskLevel.LOW,
            )]

        needs_confirm = risk in (RiskLevel.HIGH, RiskLevel.MEDIUM)

        summary = self._build_summary(request, subtasks, complexity)

        return ExecutionPlan(
            request=request,
            complexity=complexity,
            subtasks=subtasks,
            summary=summary,
            needs_confirmation=needs_confirm,
        )

    def _build_summary(self, request: str, subtasks: List[SubTask], complexity: TaskComplexity) -> str:
        if complexity == TaskComplexity.SIMPLE:
            return f"Simple request — handling directly."
        agents = list({s.agent for s in subtasks})
        return (
            f"{complexity.value.title()} request with {len(subtasks)} step(s) "
            f"across agent(s): {', '.join(agents)}."
        )

    def classify_risk(self, request: str) -> RiskLevel:
        return _assess_risk(request)


# Singleton
planner = Planner()
