"""Anomaly Map Generator for the PaDiM model implementation."""

# Copyright (C) 2022-2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


import torch
from omegaconf import ListConfig
from torch import nn
from torch.nn import functional as F  # noqa: N812

from anomalib.models.components import GaussianBlur2d


class AnomalyMapGenerator(nn.Module):
    """Generate Anomaly Heatmap.

    Args:
        image_size (ListConfig, tuple): Size of the input image. The anomaly map is upsampled to this dimension.
        sigma (int, optional): Standard deviation for Gaussian Kernel.
            Defaults to ``4``.
    """

    def __init__(self, image_size: ListConfig | tuple, sigma: int = 4) -> None:
        super().__init__()
        self.image_size = image_size if isinstance(image_size, tuple) else tuple(image_size)
        kernel_size = 2 * int(4.0 * sigma + 0.5) + 1
        self.blur = GaussianBlur2d(kernel_size=(kernel_size, kernel_size), sigma=(sigma, sigma), channels=1)

    @staticmethod
    def compute_distance(embedding: torch.Tensor, stats: list[torch.Tensor]) -> torch.Tensor:
        """Compute anomaly score to the patch in position(i,j) of a test image.

        Ref: Equation (2), Section III-C of the paper.

        Args:
            embedding (torch.Tensor): Embedding Vector
            stats (list[torch.Tensor]): Mean and Covariance Matrix of the multivariate Gaussian distribution

        Returns:
            Anomaly score of a test image via mahalanobis distance.
        """
        batch, channel, height, width = embedding.shape
        embedding = embedding.reshape(batch, channel, height * width)

        # calculate mahalanobis distances
        mean, inv_covariance = stats
        delta = (embedding - mean).permute(2, 0, 1)

        distances = (torch.matmul(delta, inv_covariance) * delta).sum(2).permute(1, 0)
        distances = distances.reshape(batch, 1, height, width)
        return distances.clamp(0).sqrt()

    def up_sample(self, distance: torch.Tensor) -> torch.Tensor:
        """Up sample anomaly score to match the input image size.

        Args:
            distance (torch.Tensor): Anomaly score computed via the mahalanobis distance.

        Returns:
            Resized distance matrix matching the input image size
        """
        return F.interpolate(
            distance,
            size=self.image_size,
            mode="bilinear",
            align_corners=False,
        )

    def smooth_anomaly_map(self, anomaly_map: torch.Tensor) -> torch.Tensor:
        """Apply gaussian smoothing to the anomaly map.

        Args:
            anomaly_map (torch.Tensor): Anomaly score for the test image(s).

        Returns:
            Filtered anomaly scores
        """
        return self.blur(anomaly_map)

    def compute_anomaly_map(
        self,
        embedding: torch.Tensor,
        mean: torch.Tensor,
        inv_covariance: torch.Tensor,
    ) -> torch.Tensor:
        """Compute anomaly score.

        Scores are calculated based on embedding vector, mean and inv_covariance of the multivariate gaussian
        distribution.

        Args:
            embedding (torch.Tensor): Embedding vector extracted from the test set.
            mean (torch.Tensor): Mean of the multivariate gaussian distribution
            inv_covariance (torch.Tensor): Inverse Covariance matrix of the multivariate gaussian distribution.

        Returns:
            Output anomaly score.
        """
        score_map = self.compute_distance(
            embedding=embedding,
            stats=[mean.to(embedding.device), inv_covariance.to(embedding.device)],
        )
        up_sampled_score_map = self.up_sample(score_map)
        return self.smooth_anomaly_map(up_sampled_score_map)

    def forward(self, **kwargs) -> torch.Tensor:
        """Return anomaly_map.

        Expects `embedding`, `mean` and `covariance` keywords to be passed explicitly.

        Example:
            >>> anomaly_map_generator = AnomalyMapGenerator(image_size=input_size)
            >>> output = anomaly_map_generator(embedding=embedding, mean=mean, covariance=covariance)

        Raises:
            ValueError: `embedding`. `mean` or `covariance` keys are not found

        Returns:
            torch.Tensor: anomaly map
        """
        if not ("embedding" in kwargs and "mean" in kwargs and "inv_covariance" in kwargs):
            msg = f"Expected keys `embedding`, `mean` and `covariance`. Found {kwargs.keys()}"
            raise ValueError(msg)

        embedding: torch.Tensor = kwargs["embedding"]
        mean: torch.Tensor = kwargs["mean"]
        inv_covariance: torch.Tensor = kwargs["inv_covariance"]

        return self.compute_anomaly_map(embedding, mean, inv_covariance)
