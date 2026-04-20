from __future__ import annotations

from unittest.mock import patch

import pytest

from podcast_llm.transcriber import detect_device


class TestDetectDevice:
    @patch("podcast_llm.transcriber.torch")
    def test_prefers_cuda_when_available(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.backends.mps.is_available.return_value = False
        assert detect_device() == "cuda"

    @patch("podcast_llm.transcriber.torch")
    def test_falls_back_to_mps_on_apple(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True
        assert detect_device() == "mps"

    @patch("podcast_llm.transcriber.torch")
    def test_falls_back_to_cpu(self, mock_torch) -> None:
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        assert detect_device() == "cpu"
