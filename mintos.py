import re
from csv import DictReader
from decimal import Decimal
from pathlib import Path

import openpyxl

OPERATION_ACQUISITION = "A"
OPERATION_MODIFICATION = "M"
OPERATION_CANCELLATION = "C"

REQUIRED_COMMON_COLUMNS = ("Issuer name", "ISIN")
REQUIRED_ISSUER_REGISTRATION_COLUMNS = ("Issuer Registration number",)
LOANS_AMOUNT_COLUMN = "Outstanding investments LOC"
BONDS_AMOUNT_COLUMN = "Amount"
BONDS_TYPE_COLUMN = "Type"
BONDS_INVESTMENT_TYPE = "investment"

# Algunos issuers no tienen el registration number en el extracto.
ISSUER_NAMES_TO_REGISTRATION_NUMBERS = {
    "SIA Mintos Finance No.47": "50203493941",
    "SIA Mintos Finance No.49": "40203515541",
}

## CONFIGURACIÓN – cambiar con tus datos
INPUT_DIR = "input"
OUTPUT_DIR = "output"
CURRENT_YEAR = 2025
PREVIOUS_YEAR = 2024
OUTPUT_FILENAME = "modelo_720.720"
CSV_DELIMITER = ","  # ";" o "," según cómo exportes

NAME = "APELLIDO1 APELLIDO2 NOMBRE"
DNI = "21928208P"
PHONE = "600112233"
## FIN CONFIGURACIÓN


def comma_to_dot(value):
    """
    Converts a number string from Spanish (12.345,67) or English (12,345.67) format
    into a normalized string (12345.67). Also accepts numbers (returns str).
    """
    if value is None or value == "":
        return "0"
    if isinstance(value, (int, float)):
        return str(value)
    value = str(value).strip()
    if re.search(r"\b\d{1,3}(?:\.\d{3})*(?:,\d+)?\b", value):
        value = value.replace(".", "").replace(",", ".")
    elif re.search(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", value):
        value = value.replace(",", "")
    return value


def to_decimal(value):
    return Decimal(comma_to_dot(value))


def read_csv(path, delimiter=None):
    delimiter = delimiter or CSV_DELIMITER
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = DictReader(f, delimiter=delimiter)
        return [row for row in reader]


def read_excel(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [
        dict(zip(headers, row))
        for row in rows[1:]
        if any(cell is not None for cell in row)
    ]


def read_file(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return read_excel(path)
    if suffix == ".csv":
        return read_csv(path)
    return []


def _normalize_header(name):
    return str(name).strip().casefold()


def _normalized_headers(headers):
    return {_normalize_header(h) for h in headers if h}


def _row_get_case_insensitive(row, *candidates, default=""):
    normalized_to_key = {_normalize_header(key): key for key in row.keys() if key}
    for candidate in candidates:
        key = normalized_to_key.get(_normalize_header(candidate))
        if key is not None:
            value = row.get(key)
            if value is not None:
                return value
    return default


def detect_year_from_filename(path):
    name = Path(path).stem
    if str(CURRENT_YEAR) in name:
        return CURRENT_YEAR
    if str(PREVIOUS_YEAR) in name:
        return PREVIOUS_YEAR
    return None


def is_loans_file(rows):
    if not rows:
        return False
    headers = _normalized_headers(rows[0].keys())
    return (
        _normalize_header(LOANS_AMOUNT_COLUMN) in headers
        and _normalize_header("ISIN") in headers
    )


def is_bonds_file(rows):
    if not rows:
        return False
    headers = _normalized_headers(rows[0].keys())
    return (
        _normalize_header(BONDS_AMOUNT_COLUMN) in headers
        and _normalize_header("ISIN") in headers
        and _normalize_header(LOANS_AMOUNT_COLUMN) not in headers
    )


def get_issuer_registration_number(row):
    value = _row_get_case_insensitive(row, *REQUIRED_ISSUER_REGISTRATION_COLUMNS)
    if value:
        return str(value).strip()
    return ""


def validate_input_files(input_dir):
    files = gather_input_files(input_dir)
    if not files:
        return

    errors = []
    for path, _year in files:
        rows = read_file(path)
        if not rows:
            errors.append(f"{path.name}: empty file or unsupported format")
            continue

        headers = _normalized_headers(rows[0].keys())
        missing_common = [
            col
            for col in REQUIRED_COMMON_COLUMNS
            if _normalize_header(col) not in headers
        ]
        has_registration_col = any(
            _normalize_header(col) in headers
            for col in REQUIRED_ISSUER_REGISTRATION_COLUMNS
        )
        has_amount_col = (
            _normalize_header(LOANS_AMOUNT_COLUMN) in headers
            or _normalize_header(BONDS_AMOUNT_COLUMN) in headers
        )
        has_bonds_type_col = _normalize_header(BONDS_TYPE_COLUMN) in headers

        file_errors = []
        if missing_common:
            file_errors.append(f"missing columns: {', '.join(sorted(missing_common))}")
        if not has_registration_col:
            file_errors.append("missing column: Issuer Registration number")
        if not has_amount_col:
            file_errors.append(
                f"missing amount column: expected '{LOANS_AMOUNT_COLUMN}' or '{BONDS_AMOUNT_COLUMN}'"
            )
        if (
            _normalize_header(BONDS_AMOUNT_COLUMN) in headers
            and _normalize_header(LOANS_AMOUNT_COLUMN) not in headers
            and not has_bonds_type_col
        ):
            file_errors.append(
                f"missing column: {BONDS_TYPE_COLUMN} (required for bonds transaction filtering)"
            )

        if file_errors:
            errors.append(f"{path.name}: " + "; ".join(file_errors))

    if errors:
        raise SystemExit("Input validation failed:\n- " + "\n- ".join(errors))


def get_assets_from_loans_rows(rows):
    assets = {}
    for row in rows:
        try:
            amount = to_decimal(
                _row_get_case_insensitive(row, LOANS_AMOUNT_COLUMN, default=0)
            )
        except Exception:
            continue
        if amount == 0:
            continue
        isin = str(_row_get_case_insensitive(row, "ISIN") or "").strip()
        if not isin:
            continue
        if isin in assets:
            assets[isin]["amount"] += amount
        else:
            issuer_name = str(
                _row_get_case_insensitive(row, "Issuer name") or ""
            ).strip()
            reg = get_issuer_registration_number(row)
            reg = reg or ISSUER_NAMES_TO_REGISTRATION_NUMBERS.get(issuer_name, "")
            assets[isin] = {
                "amount": amount,
                "issuer_name": issuer_name,
                "issuer_registration_number": reg,
            }
    return assets


def get_assets_from_bonds_rows(rows):
    by_isin = {}
    for row in rows:
        tx_type = str(_row_get_case_insensitive(row, BONDS_TYPE_COLUMN) or "").strip()
        if tx_type.casefold() != BONDS_INVESTMENT_TYPE:
            continue
        try:
            amount = abs(
                to_decimal(
                    _row_get_case_insensitive(row, BONDS_AMOUNT_COLUMN, default=0)
                )
            )
        except Exception:
            continue
        isin = str(_row_get_case_insensitive(row, "ISIN") or "").strip()
        if not isin:
            continue
        if isin not in by_isin:
            by_isin[isin] = {
                "amount": Decimal(0),
                "issuer_name": "",
                "issuer_registration_number": "",
            }

        by_isin[isin]["amount"] += amount

        issuer_name = str(_row_get_case_insensitive(row, "Issuer name") or "").strip()
        issuer_registration_number = get_issuer_registration_number(row)
        if issuer_name and not by_isin[isin]["issuer_name"]:
            by_isin[isin]["issuer_name"] = issuer_name
        if (
            issuer_registration_number
            and not by_isin[isin]["issuer_registration_number"]
        ):
            by_isin[isin]["issuer_registration_number"] = issuer_registration_number

    assets = {}
    for isin, data in by_isin.items():
        total = data["amount"]
        if total <= 0:
            continue
        assets[isin] = {
            "amount": total,
            "issuer_name": data["issuer_name"] or "Unknown",
            "issuer_registration_number": data["issuer_registration_number"] or "",
        }
    return assets


def merge_assets(*asset_dicts):
    merged = {}
    for d in asset_dicts:
        for isin, data in d.items():
            if isin in merged:
                merged[isin]["amount"] += data["amount"]
            else:
                merged[isin] = {**data}
    return merged


def gather_input_files(input_dir):
    input_path = Path(input_dir)
    if not input_path.is_dir():
        return []
    files = []
    for f in input_path.iterdir():
        if f.is_file() and f.suffix.lower() in (".csv", ".xlsx", ".xls"):
            year = detect_year_from_filename(f)
            if year is not None:
                files.append((f, year))
    return files


def load_assets_by_year(input_dir):
    current_loans = {}
    current_bonds = {}
    previous_loans = {}
    previous_bonds = {}
    for path, year in gather_input_files(input_dir):
        rows = read_file(path)
        if not rows:
            continue
        if is_loans_file(rows):
            if year == CURRENT_YEAR:
                current_loans = merge_assets(
                    current_loans, get_assets_from_loans_rows(rows)
                )
            else:
                previous_loans = merge_assets(
                    previous_loans, get_assets_from_loans_rows(rows)
                )
        elif is_bonds_file(rows):
            if year == CURRENT_YEAR:
                current_bonds = merge_assets(
                    current_bonds, get_assets_from_bonds_rows(rows)
                )
            else:
                previous_bonds = merge_assets(
                    previous_bonds, get_assets_from_bonds_rows(rows)
                )
    current = merge_assets(current_loans, current_bonds)
    previous = merge_assets(previous_loans, previous_bonds)
    return current, previous


# --- 720 file format ---
YEAR_STR = str(CURRENT_YEAR)
LINE_1 = "1720{YEAR}{DNI}{NAME:40}T{PHONE}{NAME:40}7200000000000  {n_entries:0>22} {total_amount_cents:0>17.0f} 00000000000000000                                                                                                                                                                                                                                                                                                                                \n"
LINE_N = "2720{YEAR}{DNI}{DNI}         {NAME:40}1                         V2                         LV1{isin}                                              {issuer_name:24}                 {issuer_registration_number}                                                                                                                                                                           LV00000000{operation}00000000 {amount_cents:0>14.0f} 00000000000000A{n_values_cents:0>12.0f} 10000                    \n"


def write_720_file_from_assets(filepath, assets, assets_previous_exercise=None):
    if assets_previous_exercise is None:
        assets_previous_exercise = {}
    isins = set(assets.keys())
    isins_previous = set(assets_previous_exercise.keys())
    all_isins = isins | isins_previous
    new_isins = isins - isins_previous
    modified_isins = isins & isins_previous
    cancelled_isins = isins_previous - isins

    # Build data lines first so we use the same rounded amount per line for the header total
    data_lines = []
    total_amount_cents = 0
    for isin in sorted(all_isins):
        if isin in new_isins:
            operation = OPERATION_ACQUISITION
            value = assets[isin]
            amount_cents = max(round(value["amount"] * 100), 1)
        elif isin in modified_isins:
            operation = OPERATION_MODIFICATION
            value = assets[isin]
            amount_cents = max(round(value["amount"] * 100), 1)
        elif isin in cancelled_isins:
            operation = OPERATION_CANCELLATION
            value = assets_previous_exercise[isin]
            amount_cents = 1
        else:
            raise RuntimeError(f"ISIN {isin} not found")
        total_amount_cents += amount_cents
        line = LINE_N.format(
            YEAR=YEAR_STR,
            DNI=DNI,
            NAME=NAME,
            isin=isin,
            issuer_name=value["issuer_name"],
            issuer_registration_number=value["issuer_registration_number"],
            amount_cents=amount_cents,
            n_values_cents=amount_cents * 100,
            operation=operation,
        )
        data_lines.append(line)

    n_entries = len(data_lines)
    lines = [
        LINE_1.format(
            YEAR=YEAR_STR,
            DNI=DNI,
            NAME=NAME,
            PHONE=PHONE,
            n_entries=n_entries,
            total_amount_cents=total_amount_cents,
        )
    ]
    lines.extend(data_lines)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    input_dir = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR) / OUTPUT_FILENAME
    validate_input_files(input_dir)
    current, previous = load_assets_by_year(input_dir)
    if not current and not previous:
        raise SystemExit(
            f"No valid Mintos files found in '{input_dir}'. "
            "Add CSV or Excel files whose names contain the year (e.g. 2025, 2024)."
        )
    write_720_file_from_assets(output_path, current, previous)
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
