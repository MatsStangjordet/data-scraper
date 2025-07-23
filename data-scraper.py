##
# A data-scraper that takes refreshed testdata from mainframe and PAC and creates a lookup for customer ease
# Dependancy A set of mainframe files, and an export from PAC, these are provided by other technicians
#Created by Mats O. Stangjordet 2025.07.06 -- third iteration
#Change log:
#
##
import pandas as pd
import os
import re
import argparse
import sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Globals
summary_report = defaultdict(lambda: {"merged": [], "errors": [], "columns": [], "missing": []})
LOG_FILE = None
verbose = False

# Utilities

def log(message, verbose=False, newline=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

    if verbose:
        if newline:
            print(formatted)
        else:
            print(formatted, end="")

def format_list(lst, indent=4):
    indent_space = " " * indent
    return "\n" + "\n".join(f"{indent_space}- {item}" for item in sorted(lst))

# Core Functions

def scan_bank_files(directory):
    bank_file_map = defaultdict(list)
    pattern = re.compile(r'\.B(\d{4})\.')
    for fname in os.listdir(directory):
        match = pattern.search(fname)
        if match:
            bank_id = match.group(1)
            bank_file_map[bank_id].append(fname)
    return bank_file_map

def check_bank_file_consistency(bank_file_map):
    reference_bank = next(iter(bank_file_map))
    reference_files = {
        re.sub(r'\.B\d{4}\.', '.B####.', f) for f in bank_file_map[reference_bank]
    }
    log(f"Using bank {reference_bank} as reference with {len(reference_files)} file types.", verbose=verbose)
    for bank_id, files in bank_file_map.items():
        base_filenames = {
            re.sub(r'\.B\d{4}\.', '.B####.', f) for f in files
        }
        if base_filenames != reference_files:
            log(f"\n❌ Inconsistency detected for bank {bank_id}", verbose=verbose)
            log(f"Expected ({reference_bank}):{format_list(reference_files)}", verbose=verbose)
            log(f"Found ({bank_id}):          {format_list(base_filenames)}", verbose=verbose)
            raise ValueError(f"Bank file inconsistency: {bank_id} ≠ {reference_bank}")
    log("✅ All banks have consistent file sets.", verbose=verbose)

def list_bank_files_by_type(bank_file_map, bank_id, file_ext=".CSV", exclude_obs=True):
    all_files = bank_file_map.get(bank_id, [])
    return [f for f in all_files if f.endswith(file_ext) and (not exclude_obs or "OBS" not in f.upper())]

def process_csv_files_for_bank(directory, file_list, bank_id):
    merged_df = pd.DataFrame()
    for filename in file_list:
        file_path = os.path.join(directory, filename)
        try:
            df = pd.read_csv(file_path, sep=";", encoding="latin1", dtype=str)
            if df.empty:
                raise ValueError("Bank does not have category types (no data)")
            category_value = df.iloc[0, 2].strip()
            df[category_value] = "J"
            df.drop(columns=[df.columns[2]], inplace=True)
            for col in merged_df.columns:
                if col not in df.columns:
                    df[col] = "N"
            for col in df.columns:
                if col not in merged_df.columns:
                    merged_df[col] = "N"
            df = df[merged_df.columns] if not merged_df.empty else df
            merged_df = pd.concat([merged_df, df], ignore_index=True)
            print(f"✅ Merged: {filename} as '{category_value}'")
            summary_report[bank_id]["merged"].append(category_value)
        except Exception as e:
            error_text = str(e).lower()
            if any(msg in error_text for msg in ["no columns to parse", "out of bounds", "no data"]):
                print(f"⚠️ Skipped: {filename} — no data: Bank does not have category types")
                summary_report[bank_id]["missing"].append(filename)
            else:
                print(f"❌ Error in {filename}: {e}")
                summary_report[bank_id]["errors"].append(filename)
    return merged_df

def identify_dynamic_columns(df, sample_size=100):
    sample = df if len(df) <= sample_size else df.sample(n=sample_size, random_state=42)
    return [col for col in df.columns if set(sample[col].dropna().unique()).issubset({"J", "N", ""})]

def merge_grouped_duplicates(df, key_column="Kundenummer"):
    df = df.copy()
    dynamic_cols = identify_dynamic_columns(df)
    fixed_cols = [col for col in df.columns if col not in dynamic_cols]
    def merge_group(group):
        base = group.iloc[0].copy()
        for col in dynamic_cols:
            base[col] = "J" if (group[col] == "J").any() else "N"
        for col in fixed_cols:
            if group[col].notna().any():
                base[col] = group[col].dropna().iloc[0]
        return base
    df_sorted = df.sort_values(by=key_column)
    return df_sorted.groupby(key_column, as_index=False, group_keys=False).apply(merge_group)

def summarize_dataset(df, bank_id, key_column="Kundenummer"):
    total_rows, total_columns = len(df), len(df.columns)
    dynamic_cols = [col for col in df.columns if df[col].dropna().isin(["J", "N"]).all()]
    static_cols = [col for col in df.columns if col not in dynamic_cols]
    df["Category_Count"] = df[dynamic_cols].apply(lambda row: (row == "J").sum(), axis=1)
    multi_category = (df["Category_Count"] > 1).sum()

    print("📊 Dataset Summary")
    print(f"   - Total rows: {total_rows}")
    print(f"   - Total columns: {total_columns}")
    print(f"   - Static columns: {len(static_cols)} → {static_cols}")
    print(f"   - Dynamic category columns: {len(dynamic_cols)}")
    print(f"   - Rows with multiple categories: {multi_category}")

    summary_report[bank_id]["columns"] = dynamic_cols + static_cols
    summary_report[bank_id]["stats"] = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "static_cols": static_cols,
        "dynamic_cols": dynamic_cols,
        "multi_category": multi_category,
    }

def enrich_with_pac_data(df, bank_id, pac_file):
    pac_data = pd.read_excel(pac_file, dtype=str)
    pac_data["BANK_ID"] = pac_data["BANK_ID"].astype(str)
    pac_data["FORETAKSNR"] = pac_data["FORETAKSNR"].astype(str).str.zfill(11)
    pac_data["PERSONNR"] = pac_data["PERSONNR"].astype(str)
    pac_data["AVTALE_ID"] = pac_data["AVTALE_ID"].astype(str)

    if str(bank_id) not in pac_data["BANK_ID"].unique():
        log(f"ℹ️ No PAC data found for bank {bank_id}", verbose=verbose)
        return df

    pac_subset = pac_data[pac_data["BANK_ID"] == str(bank_id)]
    pac_grouped = pac_subset.groupby("FORETAKSNR")
    avtale_lookup = {}
    users_lookup = {}
    for foretak, group in pac_grouped:
        avtale_ids = sorted(set(group["AVTALE_ID"]))
        user_strings = [f"{row['PERSONNR']}:{row['BRUKERTYPE']}" for _, row in group.iterrows()]
        avtale_lookup[foretak] = "|".join(avtale_ids)
        users_lookup[foretak] = "|".join(user_strings)

    df["AVTALE_IDs"] = df["Kundenummer"].map(avtale_lookup).fillna("")
    df["Users_PERSONNR:BRUKERTYPE"] = df["Kundenummer"].map(users_lookup).fillna("")
    log(f"✅ Enriched BM data with PAC for bank {bank_id}", verbose=verbose)
    return df

def run_pm_flow(bank_id, base_dir, bank_files, output_dir):
    pm_files = list_bank_files_by_type(bank_files, bank_id, ".CSV")
    if not pm_files:
        log(f"⚠️ No PM (.CSV) files found for bank {bank_id}", verbose=verbose)
        return
    merged_df = process_csv_files_for_bank(base_dir, pm_files, bank_id)
    merged_df = merge_grouped_duplicates(merged_df)
    summarize_dataset(merged_df, bank_id)
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"{bank_id}_{date_str}.xlsx")
    os.makedirs(output_dir, exist_ok=True)
    merged_df.to_excel(output_file, index=False)
    log(f"✅ Saved PM Excel: {output_file}", verbose=verbose)

def run_bm_flow(bank_id, base_dir, bank_files, output_dir, pac_file):
    bm_files = list_bank_files_by_type(bank_files, bank_id, ".CSV.BM")
    if not bm_files:
        log(f"⚠️ No BM (.CSV.BM) files found for bank {bank_id}", verbose=verbose)
        return
    merged_df = process_csv_files_for_bank(base_dir, bm_files, bank_id)
    merged_df = merge_grouped_duplicates(merged_df)
    merged_df = enrich_with_pac_data(merged_df, bank_id, pac_file)
    summarize_dataset(merged_df, bank_id)
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"{bank_id}_BM_{date_str}.xlsx")
    os.makedirs(output_dir, exist_ok=True)
    merged_df.to_excel(output_file, index=False)
    log(f"✅ Saved BM Excel: {output_file}", verbose=verbose)

def print_final_summary():
    summary_text = []
    summary_text.append("\n📦 Script Summary")
    summary_text.append(f"   - Processed {len(summary_report)} banks\n")
    for bank, info in summary_report.items():
        summary_text.append(f"🏦 Bank {bank}:")
        summary_text.append(f"   - Categories merged: {len(info['merged'])}")
        for cat in sorted(info['merged']):
            summary_text.append(f"      ✅ {cat}")
        summary_text.append(f"   - Bank does not have category types: {len(info['missing'])}")
        for fname in sorted(info['missing']):
            summary_text.append(f"      ⚠️ {fname}")
        summary_text.append(f"   - Files with errors: {len(info['errors'])}")
        for err in sorted(info['errors']):
            summary_text.append(f"      ❌ {err}")
        summary_text.append(f"   - Final columns: {len(info['columns'])} columns")

        # ➕ Insert dataset summary if available
        stats = info.get("stats")
        if stats:
            summary_text.append(f"\n📊 Dataset Summary")
            summary_text.append(f"   - Total rows: {stats['total_rows']}")
            summary_text.append(f"   - Total columns: {stats['total_columns']}")
            summary_text.append(f"   - Static columns: {len(stats['static_cols'])} → {stats['static_cols']}")
            summary_text.append(f"   - Dynamic category columns: {len(stats['dynamic_cols'])}")
            summary_text.append(f"   - Rows with multiple categories: {stats['multi_category']}")

        summary_text.append("")  # Spacing between banks

    final_output = "\n".join(summary_text)
    print(final_output)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(final_output + "\n")

def main():
    global LOG_FILE, verbose
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--base-dir", required=True, help="Directory with bank files")
    parser.add_argument("-p", "--pac-file", required=True, help="PAC Excel file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose mode")
    parser.add_argument("--only-bank", help="Process only one bank")
    parser.add_argument("--skip-pm", action="store_true", help="Skip PM processing")
    parser.add_argument("--skip-bm", action="store_true", help="Skip BM processing")
    args = parser.parse_args()

    base_dir = args.base_dir
    pac_file = args.pac_file
    verbose = args.verbose
    only_bank = args.only_bank
    skip_pm = args.skip_pm
    skip_bm = args.skip_bm

    script_dir = Path(__file__).resolve().parent
    date_str = datetime.now().strftime("%Y%m%d")
    LOG_FILE = str(script_dir / f"script_{date_str}.log")
    output_dir = str(script_dir / f"Out_Exel_Exports_{date_str}")

    try:
        bank_files = scan_bank_files(base_dir)
        check_bank_file_consistency(bank_files)

        for bank_id in sorted(bank_files.keys()):
            if only_bank and bank_id != only_bank:
                continue
            try:
                if not skip_pm:
                    run_pm_flow(bank_id, base_dir, bank_files, output_dir)
            except Exception as e:
                log(f"❌ Error during PM flow for bank {bank_id}: {e}", verbose=True)
            try:
                if not skip_bm:
                    run_bm_flow(bank_id, base_dir, bank_files, output_dir, pac_file)
            except Exception as e:
                log(f"❌ Error during BM flow for bank {bank_id}: {e}", verbose=True)

        print_final_summary()

    except Exception as e:
        log(f"❌ Critical error: {e}", verbose=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
