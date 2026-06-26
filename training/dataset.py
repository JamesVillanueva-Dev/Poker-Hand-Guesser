from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import Dataset


@dataclass(frozen=True)
class TrainingExample:
    features: list[float]
    label: float


class HandActionDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, examples: list[TrainingExample]) -> None:
        self.examples = examples

    @classmethod
    def from_jsonl(cls, path: Path) -> "HandActionDataset":
        import json

        examples: list[TrainingExample] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            examples.append(TrainingExample(features=payload["features"], label=float(payload["label"])))
        return cls(examples)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        example = self.examples[index]
        return torch.tensor(example.features, dtype=torch.float32), torch.tensor(example.label, dtype=torch.float32)
