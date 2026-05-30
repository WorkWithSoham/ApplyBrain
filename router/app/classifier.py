"""
Task Classifier
Categorises a prompt into one of: simple | code | reasoning

Starts with fast keyword heuristics (no model needed, zero cost).
There's a clear hook to upgrade to embedding-based classification later.
"""

import re

TASK_TYPES = ["simple", "code", "reasoning"]

# Keyword signals — extend these as you learn what your users send
CODE_SIGNALS = [
    r"\bcode\b",
    r"\bfunction\b",
    r"\bclass\b",
    r"\bscript\b",
    r"\bpython\b",
    r"\bjava\b",
    r"\bsql\b",
    r"\bbug\b",
    r"\bdebug\b",
    r"\bimplementt?\b",
    r"\brefactor\b",
    r"\bapi\b",
    r"\balgorithm\b",
    r"```",
    r"\bdef \b",
    r"\bpublic static\b",
]

REASONING_SIGNALS = [
    r"\bexplain\b",
    r"\bwhy\b",
    r"\bhow does\b",
    r"\banalyse\b",
    r"\banalyze\b",
    r"\bcompare\b",
    r"\bpros and cons\b",
    r"\btradeoffs?\b",
    r"\bdesign\b",
    r"\barchitecture\b",
    r"\bstrategy\b",
    r"\bshould i\b",
    r"\bwhat if\b",
]

SIMPLE_SIGNALS = [
    r"\bwhat is\b",
    r"\bdefine\b",
    r"\bwho is\b",
    r"\bwhen was\b",
    r"\btranslate\b",
    r"\bsummarise\b",
    r"\bsummarize\b",
    r"\blist\b",
]


class TaskClassifier:
    """
    Classifies a prompt by task type using regex heuristics.

    Upgrade path:
      1. Collect misclassifications in request_log (add a 'correct_task_type' column).
      2. Fine-tune a small sentence-transformer on those pairs.
      3. Replace _heuristic_classify() with an embedding similarity call.
         The public classify() interface stays the same.
    """

    def __init__(self):
        # Pre-compile patterns for better performance
        self.code_patterns = [re.compile(p, re.IGNORECASE) for p in CODE_SIGNALS]
        self.reasoning_patterns = [
            re.compile(p, re.IGNORECASE) for p in REASONING_SIGNALS
        ]
        self.simple_patterns = [re.compile(p, re.IGNORECASE) for p in SIMPLE_SIGNALS]

    def classify(self, prompt: str) -> str:
        return self._heuristic_classify(prompt.lower())

    def _heuristic_classify(self, prompt: str) -> str:
        code_score = self._score(prompt, self.code_patterns)
        reasoning_score = self._score(prompt, self.reasoning_patterns)
        simple_score = self._score(prompt, self.simple_patterns)

        scores = {
            "code": code_score,
            "reasoning": reasoning_score,
            "simple": simple_score,
        }

        best = max(scores, key=scores.get)
        # Default to 'simple' when nothing fires (short prompts, greetings, etc.)
        return best if scores[best] > 0 else "simple"

    @staticmethod
    def _score(text: str, compiled_patterns: list[re.Pattern]) -> int:
        return sum(1 for p in compiled_patterns if p.search(text))

    def _embedding_classify(self, prompt: str) -> str:
        """
        Zero-shot classification using semantic similarity.
        Requires: pip install sentence-transformers
        """
        from sentence_transformers import SentenceTransformer, util
        import torch

        model = SentenceTransformer("all-MiniLM-L6-v2")
        prompt_emb = model.encode(prompt, convert_to_tensor=True)
        label_embs = model.encode(TASK_TYPES, convert_to_tensor=True)
        scores = util.cos_sim(prompt_emb, label_embs)[0]
        return TASK_TYPES[torch.argmax(scores).item()]
