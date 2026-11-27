"""Credit tracking: how much of the money loaded on each provider is left.

Neither provider has an API for the prepaid balance. The user copies the balance from the
console into the app (web UI or `cli.py budget --set`); the moment it is saved is recorded,
and every cost the app records after that is subtracted. After each sync the estimate is
exact again. Stored in runs/credit.json (local, not in git).
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import PRICES, Settings
from .llm import AIError

SERVICES = ("claude", "gemini")
CONSOLES = {"claude": "https://console.anthropic.com/settings/billing",
            "gemini": "https://aistudio.google.com/billing"}

# Typical cost of a phase (USD), from real runs; a phase does not start without this much left
PHASE_ESTIMATES = {
    "analysis": {"claude": 0.6},
    "plan": {"claude": 0.4},
    "review": {"claude": 0.5},
}
MIN_CLAUDE_CALL = 0.05  # no Claude call is made below this remaining balance


class BudgetExceeded(AIError):
    pass


@dataclass
class Account:
    balance: float | None  # from the console, None = not set (no limit)
    balance_at: str | None
    spent_since: float

    @property
    def remaining(self) -> float | None:
        return None if self.balance is None else round(self.balance - self.spent_since, 4)

    def as_dict(self) -> dict:
        return {"balance": self.balance, "balance_at": self.balance_at,
                "spent_since": round(self.spent_since, 4), "remaining": self.remaining}


def _now() -> str:
    # With the UTC offset: the containers run in UTC, the user reads the console in local time
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _credit_file(settings: Settings) -> Path:
    return settings.runs_dir / "credit.json"


def load_balances(settings: Settings) -> dict:
    path = _credit_file(settings)
    return json.loads(path.read_text()) if path.exists() else {}


def set_balance(settings: Settings, service: str, balance: float | None) -> None:
    """Save the balance read from the console now (None removes the limit)."""
    if service not in SERVICES:
        raise ValueError(f"Unknown service '{service}', expected one of {SERVICES}")
    balances = load_balances(settings)
    if balance is None:
        balances.pop(service, None)
    else:
        balances[service] = {"balance": round(balance, 2), "at": _now()}
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    _credit_file(settings).write_text(json.dumps(balances, indent=2))


def spending(settings: Settings) -> dict[str, Account]:
    balances = load_balances(settings)
    read_at = {s: datetime.fromisoformat(balances[s]["at"]) for s in balances}
    spent = dict.fromkeys(SERVICES, 0.0)
    for state_file in settings.runs_dir.glob("*/state.json"):
        for event in json.loads(state_file.read_text()).get("cost_events", []):
            at = datetime.fromisoformat(event["at"])
            for service in read_at:
                if at > read_at[service]:
                    spent[service] += event.get(f"{service}_cost_usd", 0)
    return {s: Account(balances.get(s, {}).get("balance"), balances.get(s, {}).get("at"), spent[s])
            for s in SERVICES}


def ensure(settings: Settings, service: str, needed: float, what: str) -> None:
    """Raise if the remaining balance of a provider is lower than what the next step needs."""
    account = spending(settings)[service]
    if account.remaining is not None and account.remaining < needed:
        raise BudgetExceeded(
            f"Not enough {service.capitalize()} credit for {what}: about ${account.remaining:.2f} left, "
            f"${needed:.2f} needed. Top up the account, then enter the new balance from the console "
            f"in the app (credit in the top bar, or: python cli.py budget --set {service}=<amount>)."
        )


def check_phase(settings: Settings, phase: str, images: int = 0) -> None:
    for service, needed in PHASE_ESTIMATES.get(phase, {}).items():
        ensure(settings, service, needed, f"the {phase} phase")
    if images:
        ensure(settings, "gemini", images * PRICES["image"].get(settings.image_size, 0.1), f"{images} images")
