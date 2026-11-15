"""Small-sample intervals and paired differences for scripted measurements."""

from math import sqrt

from ldp.experiment import boot_ci


def wilson(k: int, n: int) -> tuple[float | None, float | None, float | None]:
    if not 0 <= k <= n:
        raise ValueError("expected 0 <= successes <= sample size")
    if not n:
        return None, None, None
    z = 1.959963984540054
    p = k / n
    adjusted = 1 + z * z / n
    center = (p + z * z / (2 * n)) / adjusted
    margin = z / adjusted * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, center - margin), min(1.0, center + margin)


def paired_boot(a, b, *, n=399, seed=7):
    """Bootstrap differences for pairs sharing the same scenario and seed."""
    if len(a) != len(b) or n < 1:
        raise ValueError("expected equally sized paired samples and a positive repeat count")
    return boot_ci([x - y for x, y in zip(a, b)], n=n, seed=seed)
