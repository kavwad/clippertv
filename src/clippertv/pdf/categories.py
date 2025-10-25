"""Declarative categorization rules for PDF trip ingestion."""

from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class RuleCondition(BaseModel):
    """Single column-level predicate for a categorization rule."""

    model_config = ConfigDict(frozen=True)

    column: str
    equals: str | None = None
    regex: str | None = None
    endswith: str | None = None
    isin: Sequence[str] | None = None
    isna: bool | None = None

    def build_mask(self, df: pd.DataFrame) -> pd.Series:
        """Return a boolean mask for rows that satisfy this condition."""
        series = df[self.column]
        mask = pd.Series(True, index=df.index, dtype=bool)

        if self.equals is not None:
            mask &= series == self.equals

        if self.isin is not None:
            mask &= series.isin(self.isin)

        if self.regex is not None:
            text_values = series.astype("string").fillna("")
            mask &= text_values.str.contains(self.regex, regex=True, na=False)

        if self.endswith is not None:
            text_values = series.astype("string").fillna("")
            mask &= text_values.str.endswith(self.endswith, na=False)

        if self.isna is True:
            mask &= series.isna()
        elif self.isna is False:
            mask &= series.notna()

        return mask


class CategorizationRule(BaseModel):
    """Declarative descriptor for deriving a category."""

    model_config = ConfigDict(frozen=True)

    category: str
    precedence: int = Field(default=0, ge=0)
    conditions: Sequence[RuleCondition]

    def build_mask(self, df: pd.DataFrame) -> pd.Series:
        """Return the mask for rows matched by all rule conditions."""
        mask = pd.Series(True, index=df.index, dtype=bool)
        for condition in self.conditions:
            mask &= condition.build_mask(df)
        return mask


def _rule(
    category: str,
    precedence: int,
    conditions: Iterable[dict[str, object]],
) -> CategorizationRule:
    """Helper to keep the rule declarations succinct."""
    return CategorizationRule(
        category=category,
        precedence=precedence,
        conditions=[RuleCondition(**condition) for condition in conditions],
    )


CATEGORIZATION_RULES: tuple[CategorizationRule, ...] = (
    _rule(
        category="Caltrain Entrance",
        precedence=100,
        conditions=(
            {
                "column": "Transaction Type",
                "regex": r"Dual-tag entry transaction.*purse debit",
            },
            {"column": "Route", "isna": True},
        ),
    ),
    _rule(
        category="Caltrain Exit",
        precedence=95,
        conditions=(
            {
                "column": "Transaction Type",
                "regex": r"Dual-tag exit transaction.*fare adjustment",
            },
            {"column": "Route", "isna": True},
        ),
    ),
    _rule(
        category="Ferry Entrance",
        precedence=90,
        conditions=(
            {
                "column": "Transaction Type",
                "regex": r"Dual-tag entry transaction.*purse debit",
            },
            {"column": "Route", "equals": "FERRY"},
        ),
    ),
    _rule(
        category="Ferry Entrance",
        precedence=85,
        conditions=(
            {"column": "Location", "endswith": "(GGF)"},
        ),
    ),
    _rule(
        category="Ferry Exit",
        precedence=80,
        conditions=(
            {
                "column": "Transaction Type",
                "regex": r"Dual-tag exit transaction.*fare adjustment",
            },
            {"column": "Route", "equals": "FERRY"},
        ),
    ),
    _rule(
        category="BART Entrance",
        precedence=70,
        conditions=(
            {
                "column": "Transaction Type",
                "regex": r"Dual-tag entry transaction, no fare deduction",
            },
        ),
    ),
    _rule(
        category="BART Exit",
        precedence=65,
        conditions=(
            {
                "column": "Transaction Type",
                "regex": r"Dual-tag exit transaction, fare payment",
            },
        ),
    ),
    _rule(
        category="Cable Car",
        precedence=60,
        conditions=(
            {"column": "Route", "equals": "CC60"},
        ),
    ),
    _rule(
        category="AC Transit",
        precedence=55,
        conditions=(
            {"column": "Location", "equals": "ACT bus"},
        ),
    ),
    _rule(
        category="Muni Bus",
        precedence=50,
        conditions=(
            {"column": "Location", "equals": "SFM bus"},
        ),
    ),
    _rule(
        category="Muni Metro",
        precedence=45,
        conditions=(
            {"column": "Route", "equals": "NONE"},
        ),
    ),
    _rule(
        category="SamTrans",
        precedence=40,
        conditions=(
            {"column": "Location", "equals": "SAM bus"},
        ),
    ),
    _rule(
        category="Reload",
        precedence=30,
        conditions=(
            {
                "column": "Transaction Type",
                "isin": (
                    "Threshold auto-load at a TransLink Device",
                    "Add value at TOT or TVM",
                    "Remote create of new pass",
                ),
            },
        ),
    ),
)

SORTED_CATEGORIZATION_RULES: tuple[CategorizationRule, ...] = tuple(
    sorted(CATEGORIZATION_RULES, key=lambda rule: rule.precedence, reverse=True)
)
