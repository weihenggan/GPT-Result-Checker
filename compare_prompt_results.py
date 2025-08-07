#!/usr/bin/env python3
"""Compare GPT extraction prompt results across environments.

This script reads a CSV file containing GPT extraction results for multiple
prompts under different environments (e.g., "NPR" for the old prompt and
"Sandbox" for the new prompt). It compares the JSON results for each prompt
between the two environments for every case, reports whether they are the same
or different, and writes an Excel report summarizing the findings.

The Excel report includes:
    * A sheet named "Comparison" listing the comparison result for each case
      pair and prompt. For each prompt column there are two subcolumns: one
      indicating whether the values are the same and another containing the
      diff or old/new values when they differ.
    * A sheet named "Summary" counting how many prompts are identical or
      different across all cases.

Usage::

    python compare_prompt_results.py input.csv output.xlsx

The script is designed to be easily extended: simply add additional prompt
column names to the ``PROMPT_COLUMNS`` list.
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
from typing import Dict, Iterable, List, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Columns that contain prompt results. To add new prompts, append their column
# names to this list.
PROMPT_COLUMNS: List[str] = [
    "SoldToCodeExtractor",
    "InputValidator",
    "FlagsProvider",
    "PartNumberInfo",
    "QuantityInfo",
    "CurrencyExtractor",
    "ProjectInfo",
    "ResultValidator",
    "Response",
    "TranslatorZhToEng",
    "TranslatorEngToZh",
    "TranslationValidator",
]

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def load_data(csv_path: str) -> pd.DataFrame:
    """Load the CSV file into a pandas DataFrame.

    Parameters
    ----------
    csv_path: str
        Path to the CSV file containing extraction results.

    Returns
    -------
    pd.DataFrame
        Loaded DataFrame with all rows from the CSV.
    """

    logging.info("Loading data from %s", csv_path)
    return pd.read_csv(csv_path)

def _normalize_json(value: object) -> str:
    """Return a normalized JSON string or the original string.

    The function attempts to parse ``value`` as JSON. If successful, the
    resulting object is dumped with sorted keys and consistent indentation,
    which makes string comparison deterministic. If JSON parsing fails, the
    original string representation is returned.

    Parameters
    ----------
    value: object
        The value to normalize. Typically a JSON string or plain text.

    Returns
    -------
    str
        Normalized string for comparison.
    """

    if pd.isna(value):
        return ""
    try:
        parsed = json.loads(value)
        return json.dumps(parsed, sort_keys=True, indent=2)
    except (TypeError, ValueError):
        return str(value)

def compare_values(old: object, new: object) -> Tuple[str, str]:
    """Compare two values that may contain JSON strings.

    Parameters
    ----------
    old: object
        Value from the old environment (e.g., NPR).
    new: object
        Value from the new environment (e.g., Sandbox).

    Returns
    -------
    Tuple[str, str]
        A tuple ``(status, detail)`` where ``status`` is either "SAME" or
        "DIFFERENT". ``detail`` contains a diff string if the values differ,
        otherwise it is empty.
    """

    old_norm = _normalize_json(old)
    new_norm = _normalize_json(new)

    if old_norm == new_norm:
        return "SAME", ""

    diff = "\n".join(
        difflib.unified_diff(
            old_norm.splitlines(),
            new_norm.splitlines(),
            fromfile="NPR",
            tofile="Sandbox",
            lineterm="",
        )
    )
    return "DIFFERENT", diff

def compare_group(group: pd.DataFrame) -> Dict[str, object]:
    """Compare prompt results for a single case group.

    Each ``group`` represents rows for the same ``casenumber`` and
    ``attachment_name``. Only groups containing both "NPR" and "Sandbox"
    environments are considered.

    Parameters
    ----------
    group: pd.DataFrame
        Subset of the main DataFrame for a single case/attachment pair.

    Returns
    -------
    Dict[str, object]
        Dictionary summarizing comparison results for the case. If the group
        does not contain both environments, an empty dictionary is returned.
    """

    try:
        npr_row = group[group["environment"] == "NPR"].iloc[0]
        sandbox_row = group[group["environment"] == "Sandbox"].iloc[0]
    except IndexError:
        logging.warning(
            "Skipping case %s / %s: missing NPR or Sandbox row",
            group["casenumber"].iloc[0],
            group["attachment_name"].iloc[0],
        )
        return {}

    result: Dict[str, object] = {
        "casenumber": npr_row["casenumber"],
        "attachment_name": npr_row["attachment_name"],
    }

    for column in PROMPT_COLUMNS:
        status, detail = compare_values(npr_row.get(column, ""), sandbox_row.get(column, ""))
        result[f"{column}_status"] = status
        result[f"{column}_detail"] = detail

    return result

def generate_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Generate a DataFrame with comparison results for all cases.

    Parameters
    ----------
    df: pd.DataFrame
        Full DataFrame containing rows for multiple cases and environments.

    Returns
    -------
    pd.DataFrame
        Comparison DataFrame where each row corresponds to a case/attachment
        pair and includes comparison results for all prompts.
    """

    records: List[Dict[str, object]] = []
    groups = df.groupby(["casenumber", "attachment_name"], sort=False)
    for _, group in groups:
        record = compare_group(group)
        if record:
            records.append(record)
    return pd.DataFrame(records)

def generate_summary(comp_df: pd.DataFrame) -> pd.DataFrame:
    """Create a summary count of SAME/DIFFERENT statuses for each prompt.

    Parameters
    ----------
    comp_df: pd.DataFrame
        DataFrame produced by :func:`generate_comparison`.

    Returns
    -------
    pd.DataFrame
        Summary DataFrame with counts for each prompt.
    """

    summaries: List[Dict[str, object]] = []
    for column in PROMPT_COLUMNS:
        status_col = f"{column}_status"
        same_count = (comp_df[status_col] == "SAME").sum()
        diff_count = (comp_df[status_col] == "DIFFERENT").sum()
        summaries.append({
            "prompt": column,
            "SAME": int(same_count),
            "DIFFERENT": int(diff_count),
        })
    return pd.DataFrame(summaries)

def write_report(comp_df: pd.DataFrame, summary_df: pd.DataFrame, output_path: str) -> None:
    """Write the comparison and summary DataFrames to an Excel file.

    Parameters
    ----------
    comp_df: pd.DataFrame
        Comparison results DataFrame.
    summary_df: pd.DataFrame
        Summary counts DataFrame.
    output_path: str
        Path to the Excel file to be created.
    """

    logging.info("Writing report to %s", output_path)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        comp_df.to_excel(writer, sheet_name="Comparison", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

def parse_args(args: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    args: Iterable[str], optional
        Iterable of argument strings. If ``None``, ``sys.argv`` is parsed.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with ``input_csv`` and ``output_excel`` attributes.
    """

    parser = argparse.ArgumentParser(
        description="Compare GPT extraction results between NPR and Sandbox environments."
    )
    parser.add_argument("input_csv", help="Path to the CSV file containing results")
    parser.add_argument(
        "output_excel", help="Path to the Excel file to write the comparison report"
    )
    return parser.parse_args(args)

def main(args: Iterable[str] | None = None) -> None:
    """Main entry point for the script."""

    parsed_args = parse_args(args)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    df = load_data(parsed_args.input_csv)
    comp_df = generate_comparison(df)
    summary_df = generate_summary(comp_df)
    write_report(comp_df, summary_df, parsed_args.output_excel)
    logging.info("Comparison completed for %d case(s)", len(comp_df))

if __name__ == "__main__":
    main()
