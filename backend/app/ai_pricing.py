"""
What a model call actually costs us, to the thousandth of a cent.

The included assistant allowance is denominated in money, not tokens: every
workspace gets $5 of usage at the price we pay Anthropic, and can buy more at
the same price. That only works if what a call costs is computed from the real
per-model rates and the real token counts, rather than from an averaged
tokens-per-dollar figure that drifts the moment the model changes.

Why thousandths of a cent
-------------------------
One question to the business assistant costs about 1.4 cents on a small
workspace and 20 cents on a large one; one question to the employee assistant
costs a fraction of a cent. Rounding each call to whole cents would round most
employee questions to zero and make the meter lie in the customer's favour
until it suddenly did not.

So costs are integers in thousandths of a cent — `*_milli`, the same convention
`quantity_milli` already uses elsewhere in this codebase. $5.00 is 500,000.

Caching
-------
Cached input is charged at a tenth of the input rate, and writing to the cache
costs a quarter more than reading it fresh once. Both are counted here because
the assistant re-sends the same business context on every turn, so cache reads
are expected to become most of the input volume.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Thousandths of a cent in one dollar. 1 dollar = 100 cents = 100,000 milli.
MILLI_PER_DOLLAR = 100_000
MILLI_PER_CENT = 1_000


@dataclass(frozen=True)
class Rates:
    """Dollars per million tokens, as Anthropic publishes them."""

    input: float
    output: float

    @property
    def cache_read(self) -> float:
        """Cached input is a tenth of the input rate."""
        return self.input * 0.1

    @property
    def cache_write(self) -> float:
        """Writing the cache costs a quarter more than reading that input once."""
        return self.input * 1.25


# Published rates. A model missing from here is a model we cannot price, which
# is treated as an error rather than silently charged at somebody else's rate.
MODEL_RATES: dict[str, Rates] = {
    "claude-opus-5": Rates(input=5.00, output=25.00),
    "claude-sonnet-5": Rates(input=2.00, output=10.00),
    "claude-haiku-4-5": Rates(input=1.00, output=5.00),
    # Kept because ANTHROPIC_MODEL is an environment variable and a deployment
    # may still be pinned to one of these.
    "claude-opus-4-8": Rates(input=5.00, output=25.00),
    "claude-sonnet-4-6": Rates(input=3.00, output=15.00),
}

DEFAULT_MODEL = "claude-sonnet-5"


def rates_for(model: str) -> Rates:
    """
    The rates for a model, falling back to the default with the name recorded.

    A fallback is correct here rather than an exception: the alternative is an
    assistant that stops working because somebody set ANTHROPIC_MODEL to a
    newer model than this table knows about. Undercharging for a month is
    recoverable; an outage on the feature the product is sold on is not.
    """
    return MODEL_RATES.get(model) or MODEL_RATES[DEFAULT_MODEL]


def cost_milli(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> int:
    """
    What this call cost us, in thousandths of a cent, rounded up.

    Rounded up rather than to nearest, deliberately: the rounding error on a
    single call is a hundred-thousandth of a dollar, and it should fall on our
    side of the line rather than the customer's. Across a million calls that is
    ten dollars, which is the correct size for a rounding decision.
    """
    rate = rates_for(model)
    dollars = (
        input_tokens / 1e6 * rate.input
        + output_tokens / 1e6 * rate.output
        + cache_read_tokens / 1e6 * rate.cache_read
        + cache_write_tokens / 1e6 * rate.cache_write
    )
    if dollars <= 0:
        return 0
    # math.ceil rather than -(-x // 1), which returns a float and quietly makes
    # every downstream sum a float too — in a column declared as an integer.
    return max(1, math.ceil(dollars * MILLI_PER_DOLLAR))


def format_milli(milli: int) -> str:
    """For an interface. $0.0140, not 1400."""
    return f"${milli / MILLI_PER_DOLLAR:,.4f}".rstrip("0").rstrip(".")


def dollars(milli: int) -> float:
    return round(milli / MILLI_PER_DOLLAR, 5)
