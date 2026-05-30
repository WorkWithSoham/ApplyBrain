"""
Model Selector
Picks which LLM backend to call based on routing weights from PostgreSQL.

Uses weighted random selection so lower-weight models still get some traffic —
this keeps the feedback engine collecting data on all models, not just the
current winner. (Think: multi-armed bandit with epsilon-greedy exploration.)
"""

import random


class ModelSelector:
    """
    Given a list of (model_name, weight) records, picks one model.

    The higher a model's weight, the more likely it is to be chosen.
    Weights are floats updated nightly by the feedback engine.
    """

    FALLBACK_MODEL = "ollama/phi3"

    def select(self, weight_records: list) -> str:
        """
        weight_records: asyncpg Records with keys 'model_name' and 'weight'.
        Returns the chosen model name string.
        """
        if not weight_records:
            return self.FALLBACK_MODEL

        models  = [r["model_name"] for r in weight_records]
        weights = [max(r["weight"], 0.01) for r in weight_records]  # floor at 0.01

        # Epsilon-greedy: 10% of the time pick a random model for exploration
        if random.random() < 0.10:
            return random.choice(models)

        # Weighted random selection
        chosen = random.choices(models, weights=weights, k=1)[0]
        return chosen

    def select_top(self, weight_records: list) -> str:
        """Always pick the highest-weight model. Use for deterministic routing."""
        if not weight_records:
            return self.FALLBACK_MODEL
        return max(weight_records, key=lambda r: r["weight"])["model_name"]
