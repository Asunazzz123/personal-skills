---
name: coding-standard
description: Use when creating, modifying, refactoring, or reviewing Python code and when checking imports, type annotations, docstrings, error handling, state management, prompts, or structured LLM outputs.
---

# Coding Standard

## Overview

Apply a strict, consistent, and LLM-friendly Python coding standard. Treat
`MUST`, `SHOULD`, and `MAY` as mandatory, recommended, and optional
requirements.

Follow more specific repository instructions when they intentionally override
this standard. Preserve established public APIs and local conventions unless the
task explicitly requires changing them.

## Quick Reference

| Area | Requirement |
|---|---|
| Imports | Group standard library, third-party packages, and local modules with blank lines |
| Type annotations | Annotate all function parameters and return values |
| Docstrings | Document public functions, classes, and methods |
| Error handling | Catch specific exceptions and preserve their causes |
| Structure | Prefer small, explicit, independently testable units |
| LLM output | Request and validate structured output before using it |

## Imports

Organize imports in this order:

1. Python standard library, including `typing`
2. Third-party packages
3. Local project modules

Separate groups with one blank line. Sort imports within each group
alphabetically when practical.

Import groups MUST NOT contain category comments such as
`# Standard library`, `# Third-party packages`, or `# Local modules`. Use blank
lines alone to express the grouping.

```python
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from decouple import config
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client
from src.utils.logger import setup_logger
```

Remove unused and wildcard imports. Keep imports at module scope unless delayed
loading or dependency isolation provides a concrete benefit.

## Functions and Types

- Add explicit type annotations to every function parameter and return value.
- Use the narrowest useful type; avoid `Any` when a more precise type is
  practical.
- Use `Optional[T]` only when `None` is a valid value.
- Give each function one clearly defined responsibility.
- Prefer explicit inputs and return values over global state.
- Keep business logic inside functions or classes rather than executing it at
  module import time.

## Docstrings

Write descriptive docstrings for public functions, classes, and methods. Use
one format consistently within the repository, preferably Google style.

Document:

- Purpose
- Parameters
- Return value
- Expected exceptions
- Relevant side effects or external dependencies

```python
def analyze_frequency(
    data: np.ndarray,
    sampling_rate: int,
) -> Dict[str, float]:
    """Calculate the dominant frequency and spectral energy.

    Args:
        data: One-dimensional time-series data.
        sampling_rate: Sampling frequency in hertz.

    Returns:
        The dominant frequency and total spectral energy.

    Raises:
        ValueError: If the input data is empty or the sampling rate is invalid.
    """
    if data.size == 0:
        raise ValueError("data must not be empty")

    if sampling_rate <= 0:
        raise ValueError("sampling_rate must be greater than zero")

    spectrum = np.abs(np.fft.rfft(data))
    frequencies = np.fft.rfftfreq(data.size, d=1.0 / sampling_rate)
    dominant_index = int(np.argmax(spectrum))

    return {
        "dominant_freq": float(frequencies[dominant_index]),
        "spectral_energy": float(np.sum(spectrum**2)),
    }
```

## Error Handling

Handle expected failures explicitly at system boundaries such as API calls,
file access, model requests, and database operations.

- Catch specific exceptions instead of using a bare `except`.
- Add actionable context when translating an exception.
- Preserve the original cause with `raise ... from exc`.
- Never silently ignore a failure.
- Do not add `try`/`except` when the code cannot recover, translate, or add
  meaningful context.

```python
from pathlib import Path


def load_text(path: Path) -> str:
    """Read a UTF-8 text file.

    Args:
        path: File to read.

    Returns:
        The file contents.

    Raises:
        RuntimeError: If the file cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read file: {path}") from exc
```

## State and Structure

- Prefer pure functions for calculations and transformations.
- Pass dependencies explicitly instead of creating hidden global dependencies.
- Store necessary shared state in clearly defined objects.
- Keep configuration separate from business logic.
- Avoid mutable module-level variables.
- Separate external I/O from data processing and decision logic.
- Introduce classes only when they provide meaningful state, lifecycle, or
  behavior grouping.

## Prompts and LLM Interactions

Context is king; structure is queen.

Prompts SHOULD define:

- Objective
- Available inputs
- Constraints
- Expected output structure
- Relevant domain terminology
- Failure and uncertainty behavior

Require structured output, preferably JSON backed by a typed schema, whenever
application code consumes the response. Validate required fields, types, and
allowed values before using model output. Never assume raw model output is
valid.

## General Quality

- Use descriptive names and avoid duplicated logic.
- Validate inputs at system boundaries.
- Produce actionable error messages.
- Keep implementation details separate from public interfaces.
- Use the repository's configured formatter, linter, and type checker.
- Write comments for intent, constraints, and non-obvious decisions; do not
  restate the code.
- Add or update focused tests for behavior changes.

## Common Mistakes

| Avoid | Prefer |
|---|---|
| Category comments between import groups | Blank lines between import groups |
| Broad `except Exception` without a boundary reason | Specific exceptions with context |
| Undocumented `Any` and implicit return types | Precise annotations |
| Mutable globals and hidden dependencies | Explicit parameters and state objects |
| Parsing unvalidated free-form model output | Typed, validated structured output |
| Large functions with mixed I/O and logic | Small units with clear boundaries |

## Verification

Before completing a Python change:

1. Check import grouping and remove category comments.
2. Check type annotations and public docstrings.
3. Check exception scope and preserved causes.
4. Check state ownership and function responsibilities.
5. Validate structured model output at its boundary.
6. Run the repository's relevant formatter, linter, type checker, and tests.
