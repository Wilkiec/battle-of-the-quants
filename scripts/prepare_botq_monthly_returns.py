"""Convert the BotQ daily stock export into compact stock-month returns.

The provided .parquet file is CSV text. Daily `return` values are percentage
points, so this script divides them by 100 before compounding. A stock-month is
kept when it has at least 15 valid daily observations. The final incomplete
calendar month is excluded.

Example:
    python prepare_botq_monthly_returns.py \
        --input /path/to/BotQ_2026_data.parquet \
        --output data/botq_monthly_stock_returns.csv.gz
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-days", default=15, type=int)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    partials: list[pd.DataFrame] = []
    max_date: pd.Timestamp | None = None
    for chunk in pd.read_csv(
        args.input,
        usecols=["ticker", "barrid", "date", "return"],
        chunksize=500_000,
        low_memory=False,
    ):
        chunk["ticker"] = chunk["ticker"].astype("string").str.upper()
        chunk["barrid"] = chunk["barrid"].astype("string").str.upper()
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk["daily_return"] = pd.to_numeric(chunk["return"], errors="coerce") / 100
        chunk = chunk.dropna(subset=["ticker", "barrid", "date", "daily_return"])
        chunk = chunk[chunk["daily_return"] >= -1].copy()
        if chunk.empty:
            continue
        chunk_max = chunk["date"].max()
        max_date = chunk_max if max_date is None else max(max_date, chunk_max)
        chunk["month"] = chunk["date"].dt.to_period("M").astype(str)
        chunk["log_return"] = np.log1p(chunk["daily_return"].clip(lower=-0.999999999))
        chunk["total_loss"] = (chunk["daily_return"] <= -1).astype("int8")
        partials.append(
            chunk.groupby(["barrid", "month"], observed=True)
            .agg(
                ticker=("ticker", "last"),
                log_return=("log_return", "sum"),
                total_loss=("total_loss", "max"),
                days=("daily_return", "size"),
            )
            .reset_index()
        )

    if max_date is None:
        raise ValueError("No valid date/return rows were found in the input file.")

    stock_months = pd.concat(partials, ignore_index=True)
    stock_months = (
        stock_months.groupby(["barrid", "month"], as_index=False)
        .agg(ticker=("ticker", "last"), log_return=("log_return", "sum"), total_loss=("total_loss", "max"), days=("days", "sum"))
    )
    stock_months["monthly_return"] = np.where(
        stock_months["total_loss"].eq(1), -1.0, np.expm1(stock_months["log_return"])
    )

    last_month = max_date.to_period("M")
    days_to_month_end = (last_month.end_time.normalize() - max_date.normalize()).days
    last_complete_month = last_month if days_to_month_end <= 3 else last_month - 1
    stock_months["month_period"] = pd.PeriodIndex(stock_months["month"], freq="M")
    stock_months = stock_months[
        (stock_months["days"] >= args.min_days)
        & (stock_months["month_period"] <= last_complete_month)
    ]
    stock_months = stock_months[["ticker", "barrid", "month", "monthly_return", "days"]]
    stock_months.to_csv(args.output, index=False, compression="gzip", float_format="%.10g")

    n_by_month = stock_months.groupby("month")["barrid"].nunique()
    print(f"Saved {len(stock_months):,} stock-months to {args.output}")
    print(f"Months: {n_by_month.index.min()} to {n_by_month.index.max()}")
    print(f"Stocks per month: {n_by_month.min():,}–{n_by_month.max():,}")


if __name__ == "__main__":
    main()
