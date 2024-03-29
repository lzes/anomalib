"""Tools for CDF normalization."""

# Copyright (C) 2022-2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


import numpy as np
import torch
from scipy.stats import norm
from torch.distributions import Normal


def standardize(
    targets: np.ndarray | torch.Tensor,
    mean: float | np.ndarray | torch.Tensor,
    std: float | np.ndarray | torch.Tensor,
    center_at: float | None = None,
) -> np.ndarray | torch.Tensor:
    """Standardize the targets to the z-domain."""
    if isinstance(targets, np.ndarray):
        targets = np.log(targets)
    elif isinstance(targets, torch.Tensor):
        targets = torch.log(targets)
    else:
        msg = f"Targets must be either Tensor or Numpy array. Received {type(targets)}"
        raise TypeError(msg)
    standardized = (targets - mean) / std
    if center_at:
        standardized -= (center_at - mean) / std
    return standardized


def normalize(
    targets: np.ndarray | torch.Tensor,
    threshold: float | np.ndarray | torch.Tensor,
) -> np.ndarray | torch.Tensor:
    """Normalize the targets by using the cumulative density function."""
    if isinstance(targets, torch.Tensor):
        return normalize_torch(targets, threshold)
    if isinstance(targets, np.ndarray):
        return normalize_numpy(targets, threshold)
    msg = f"Targets must be either Tensor or Numpy array. Received {type(targets)}"
    raise TypeError(msg)


def normalize_torch(targets: torch.Tensor, threshold: torch.Tensor) -> torch.Tensor:
    """Normalize the targets by using the cumulative density function, PyTorch version."""
    device = targets.device
    image_threshold = threshold.cpu()

    dist = Normal(torch.Tensor([0]), torch.Tensor([1]))
    return dist.cdf(targets.cpu() - image_threshold).to(device)


def normalize_numpy(targets: np.ndarray, threshold: float | np.ndarray) -> np.ndarray:
    """Normalize the targets by using the cumulative density function, Numpy version."""
    return norm.cdf(targets - threshold)
