from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from models.model import LikelihoodNetwork
from training.dataset import HandActionDataset


def train(dataset_path: Path, output_path: Path, epochs: int = 8, batch_size: int = 128, learning_rate: float = 1e-3) -> None:
    dataset = HandActionDataset.from_jsonl(dataset_path)
    if len(dataset) == 0:
        raise ValueError("Training dataset is empty.")

    first_features, _ = dataset[0]
    model = LikelihoodNetwork(input_dim=int(first_features.numel()))
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    criterion = nn.BCELoss()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model.train()
    for _ in range(epochs):
        for features, labels in loader:
            optimizer.zero_grad()
            predictions = model(features)
            loss = criterion(predictions, labels)
            loss.backward()
            optimizer.step()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a neural likelihood model for poker range inference.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/likelihood.pt"))
    parser.add_argument("--epochs", type=int, default=8)
    args = parser.parse_args()
    train(args.dataset, args.output, epochs=args.epochs)


if __name__ == "__main__":
    main()
