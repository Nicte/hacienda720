#!/usr/bin/env python3
"""
Validates the generated Modelo 720 file against the input Mintos files.
Compares total amount, number of entries, and per-record data (ISIN, operation, amount).
"""

from collections import Counter
import re
import sys
from pathlib import Path

# Use same config and load logic as mintos
from mintos import (
    INPUT_DIR,
    OUTPUT_DIR,
    OUTPUT_FILENAME,
    load_assets_by_year,
)


BLOCK_LENGTH = 500


def parse_720_header(line):
    """Extract n_entries and total_amount_cents from first line of .720 file."""
    m = re.search(r"720\d{10}\s+(\d{22})\s+(\d{17})", line)
    if not m:
        return None, None
    n_entries = int(m.group(1))
    total_cents = int(m.group(2))
    return n_entries, total_cents


def parse_720_data_line(line):
    """Extract (isin, operation, amount_cents) from a data line. Returns None if not parsed."""
    m = re.search(
        r"LV1([A-Z0-9]{12}).*?LV00000000([ACM])00000000\s+(\d{14})",
        line,
    )
    if not m:
        return None
    return {
        "isin": m.group(1),
        "operation": m.group(2),
        "amount_cents": int(m.group(3)),
    }


def build_expected_records(current, previous):
    isins = set(current.keys())
    isins_previous = set(previous.keys())
    all_isins = isins | isins_previous
    new_isins = isins - isins_previous
    modified_isins = isins & isins_previous
    cancelled_isins = isins_previous - isins

    records = []
    for isin in sorted(all_isins):
        if isin in new_isins:
            operation = "A"
            value = current[isin]
            amount_cents = max(round(value["amount"] * 100), 1)
        elif isin in modified_isins:
            operation = "M"
            value = current[isin]
            amount_cents = max(round(value["amount"] * 100), 1)
        elif isin in cancelled_isins:
            operation = "C"
            amount_cents = 1
        else:
            raise RuntimeError(f"ISIN {isin} not found")

        records.append(
            {
                "isin": isin,
                "operation": operation,
                "amount_cents": amount_cents,
            }
        )
    return records


def block_length_errors(lines):
    """Return human-readable errors for lines that are not exactly BLOCK_LENGTH chars."""
    errors = []
    bad = []
    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        if len(line) != BLOCK_LENGTH:
            bad.append((idx, len(line)))

    if bad:
        sample = ", ".join(
            f"line {line_no}: {line_len}" for line_no, line_len in bad[:10]
        )
        suffix = "" if len(bad) <= 10 else f" ... (+{len(bad) - 10} more)"
        errors.append(
            f"Invalid block length: expected {BLOCK_LENGTH} chars. "
            f"Found {len(bad)} malformed line(s): {sample}{suffix}"
        )

    return errors


def validate():
    input_dir = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR) / OUTPUT_FILENAME

    if not output_path.exists():
        print(f"Error: Output file not found: {output_path}")
        print("Run mintos.py first to generate the .720 file.")
        sys.exit(1)

    # Expected from input files (use same rounding as generator: per-line then sum)
    current, previous = load_assets_by_year(input_dir)
    expected_records = build_expected_records(current, previous)
    expected_entries = len(expected_records)
    expected_total_cents = sum(r["amount_cents"] for r in expected_records)

    # Parse output file
    with open(output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print("Error: Output file is empty.")
        sys.exit(1)

    errors = []
    errors.extend(block_length_errors(lines))

    n_entries_file, total_cents_file = parse_720_header(lines[0])
    if n_entries_file is None:
        header_len = len(lines[0].rstrip("\r\n"))
        errors.append(
            "Could not parse header line of .720 file. "
            f"Header length is {header_len} (expected {BLOCK_LENGTH})."
        )

    if errors:
        print("Validation FAILED:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    data_lines = [line_text for line_text in lines[1:] if line_text.startswith("2")]
    parsed_records = []
    unparsable_data_lines = 0
    for line in data_lines:
        record = parse_720_data_line(line)
        if record is None:
            unparsable_data_lines += 1
            continue
        parsed_records.append(record)

    sum_data_cents = sum(r["amount_cents"] for r in parsed_records)

    if unparsable_data_lines:
        errors.append(
            f"Found {unparsable_data_lines} data lines that could not be parsed"
        )
    if len(data_lines) != n_entries_file:
        errors.append(
            f"Header entry count ({n_entries_file}) does not match number of data lines ({len(data_lines)})"
        )
    if expected_entries != n_entries_file:
        errors.append(
            f"Entry count: expected {expected_entries} (from input), file has {n_entries_file}"
        )
    if expected_total_cents != total_cents_file:
        errors.append(
            f"Total amount (cents): expected {expected_total_cents}, file header has {total_cents_file}"
        )
    if sum_data_cents != total_cents_file:
        errors.append(
            f"Total amount: sum of data lines ({sum_data_cents}) does not match header ({total_cents_file})"
        )

    expected_counter = Counter(
        (r["isin"], r["operation"], r["amount_cents"]) for r in expected_records
    )
    file_counter = Counter(
        (r["isin"], r["operation"], r["amount_cents"]) for r in parsed_records
    )
    if expected_counter != file_counter:
        missing = list((expected_counter - file_counter).elements())[:5]
        extra = list((file_counter - expected_counter).elements())[:5]
        if missing:
            errors.append(f"Missing expected records (sample): {missing}")
        if extra:
            errors.append(f"Unexpected records in file (sample): {extra}")

    if errors:
        print("Validation FAILED:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    print("Validation OK:")
    print(f"  Entries: {expected_entries}")
    print(f"  Total amount (cents): {expected_total_cents}")
    print(f"  Total amount (EUR):  {expected_total_cents / 100:.2f}")
    op_counts = Counter(r["operation"] for r in parsed_records)
    print(
        "  Operations: "
        f"A={op_counts.get('A', 0)} "
        f"M={op_counts.get('M', 0)} "
        f"C={op_counts.get('C', 0)}"
    )


if __name__ == "__main__":
    validate()
