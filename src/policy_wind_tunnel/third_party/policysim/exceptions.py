# Vendored from https://github.com/opencausality/PolicySim @ 3d3d3d4 (MIT declared in pyproject.toml; no LICENSE file present). See third_party/policysim/NOTICE.md.
"""PolicySim custom exception hierarchy.

All exceptions derive from ``PolicySimError`` so callers can catch the base
class or specific subclasses as needed.
"""

from __future__ import annotations


class PolicySimError(Exception):
    """Base exception for all PolicySim errors.

    Catching this class will catch any PolicySim-specific error.
    """


class ProviderError(PolicySimError):
    """Raised when no LLM provider is reachable or a call fails after retries.

    Examples
    --------
    - Ollama is not running and no cloud key is configured.
    - All retry attempts to the configured provider failed.
    """


class PolicyParseError(PolicySimError):
    """Raised when LLM output cannot be parsed into a valid policy structure.

    Examples
    --------
    - The LLM returned malformed JSON.
    - Parsed JSON does not match the expected Pydantic schema.
    - Retried extraction still fails to produce parseable output.
    """


class SimulationError(PolicySimError):
    """Raised when a causal simulation cannot be completed.

    Examples
    --------
    - The changed rule does not exist in the model.
    - The causal graph has no outgoing edges from the changed rule.
    - Numeric propagation produces invalid (NaN / Inf) values.
    """


class InsufficientDataError(PolicySimError):
    """Raised when the provided outcome data is insufficient for calibration.

    Examples
    --------
    - The CSV has fewer rows than the minimum required for correlation.
    - Required outcome columns are missing from the data file.
    - All outcome values for a metric are identical (zero variance).
    """
