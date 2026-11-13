"""Deterministic data cleaning and validation pipeline for ByteTrip transit datasets.

Applies standard normalization to Bangladesh district names, scales historical fare anomalies,
resolves undirected bidirectional conflicting edge metrics via maximum values,
and verifies schema constraints (no self-loops, no negative values, integer fields).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_PATH = BASE_DIR / "route_infos.csv"
CLEAN_PATH = BASE_DIR / "route_infos_clean.csv"

NUMERIC_COLUMNS: List[str] = ["cost", "distance_km", "time_minutes"]

DISTRICT_RENAMES: Dict[str, str] = {
    "Borguna": "Barguna",
    "Coxsbazar": "Cox's Bazar",
    "Comilla": "Cumilla",
    "Jessore": "Jashore",
    "Jhalokathi": "Jhalokati",
    "Laksmipur": "Lakshmipur",
    "Lalmonir": "Lalmonirhat",
    "Narshingdi": "Narsingdi",
    "Panchagar": "Panchagarh",
    "Shariyatpur": "Shariatpur",
}


def clean_routes(
    source_path: Path | str = RAW_PATH,
    output_path: Path | str = CLEAN_PATH,
    quiet: bool = False,
) -> pd.DataFrame:
    """Clean raw transit CSV data and write normalized undirected dataset.

    Args:
        source_path: Path to the raw input CSV.
        output_path: Path where cleaned CSV should be saved.
        quiet: If True, suppress stdout summary output.

    Returns:
        The cleaned pandas DataFrame.

    Raises:
        ValueError: If data fails integrity checks (missing columns, self-loops, negative numbers).
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found at: {source_path}")

    routes = pd.read_csv(source_path)
    required_columns = {"from", "to", *NUMERIC_COLUMNS}
    missing_columns = required_columns.difference(routes.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns in route data: {sorted(missing_columns)}")

    routes = routes[["from", "to", *NUMERIC_COLUMNS]].copy()
    routes["from"] = routes["from"].astype(str).str.strip().replace(DISTRICT_RENAMES)
    routes["to"] = routes["to"].astype(str).str.strip().replace(DISTRICT_RENAMES)
    routes[NUMERIC_COLUMNS] = routes[NUMERIC_COLUMNS].apply(pd.to_numeric)

    if routes.isna().any().any():
        raise ValueError("Route data contains missing / NaN values")
    if (routes["from"] == routes["to"]).any():
        raise ValueError("Route data contains an invalid self-loop (from == to)")
    if (routes[NUMERIC_COLUMNS] < 0).any().any():
        raise ValueError("Route data contains negative values in numeric columns")

    for column in NUMERIC_COLUMNS:
        if not (routes[column] % 1 == 0).all():
            raise ValueError(f"Column {column!r} contains a non-integer value")
        routes[column] = routes[column].astype(int)

    # Scale historical raw fares that were inflated by 10x
    high_costs = routes["cost"] >= 500
    routes.loc[high_costs, "cost"] //= 10

    # Deterministically aggregate undirected pairs (A -> B and B -> A) taking max
    routes["pair"] = routes.apply(
        lambda row: tuple(sorted((row["from"], row["to"]))), axis=1
    )
    cleaned = (
        routes.groupby("pair", sort=True)[NUMERIC_COLUMNS]
        .max()
        .reset_index()
    )
    cleaned[["from", "to"]] = pd.DataFrame(
        cleaned.pop("pair").tolist(), index=cleaned.index
    )
    cleaned = cleaned[["from", "to", *NUMERIC_COLUMNS]]

    cleaned.to_csv(output_path, index=False)
    suspicious = cleaned[cleaned["cost"] > 500]

    if not quiet:
        distinct_districts = len(set(cleaned["from"]).union(cleaned["to"]))
        print(f"Successfully cleaned route data:")
        print(f" - Total undirected edges: {len(cleaned)}")
        print(f" - Unique districts covered: {distinct_districts}")
        print(f" - Output file written: {output_path}")
        if suspicious.empty:
            print(" - Outlier fares (> 500 Tk): None")
        else:
            print(f" - Notice: {len(suspicious)} routes have fares > 500 Tk for manual review:")
            print(suspicious.to_string(index=False))

    return cleaned


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ByteTrip Route Dataset Sanitizer")
    parser.add_argument("--source", type=Path, default=RAW_PATH, help="Path to raw CSV file")
    parser.add_argument("--output", type=Path, default=CLEAN_PATH, help="Path to cleaned CSV output")
    parser.add_argument("--quiet", action="store_true", help="Suppress status output")
    return parser.parse_args(args)


if __name__ == "__main__":
    cli_args = parse_args()
    clean_routes(source_path=cli_args.source, output_path=cli_args.output, quiet=cli_args.quiet)
