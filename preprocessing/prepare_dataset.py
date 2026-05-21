import argparse
import csv
import random
from pathlib import Path

import pandas as pd
import yaml

# waxaad import ka samaynaysaa cleaning function-kaaga
from preprocessing.utils.text_cleaner import clean_text


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def stratified_split(df: pd.DataFrame, label_col: str, seed: int,
                     train_ratio: float, val_ratio: float):
    """
    df -> (train_df, val_df, test_df) iyadoo label ratio la ilaalinayo.
    """
    random.seed(seed)

    train_parts = []
    val_parts = []
    test_parts = []

    for label_value, group in df.groupby(label_col):
        idx = group.index.tolist()
        random.shuffle(idx)

        n = len(idx)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))

        train_idx = idx[:n_train]
        val_idx = idx[n_train:n_train + n_val]
        test_idx = idx[n_train + n_val:]

        train_parts.append(df.loc[train_idx])
        val_parts.append(df.loc[val_idx])
        test_parts.append(df.loc[test_idx])

    train_df = pd.concat(train_parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    val_df = pd.concat(val_parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    test_df = pd.concat(test_parts).sample(frac=1, random_state=seed).reset_index(drop=True)

    return train_df, val_df, test_df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)

    seed = int(cfg["project"]["seed"])
    labeled_path = cfg["data"]["dataset_labeled"]
    text_col = cfg["data"]["text_column"]
    label_col = cfg["data"]["label_column"]

    processed_dir = Path(cfg["paths"]["data_processed_dir"])
    train_name = cfg["data"]["train_file"]
    val_name = cfg["data"]["val_file"]
    test_name = cfg["data"]["test_file"]

    train_ratio = float(cfg["split"]["train_ratio"])
    val_ratio = float(cfg["split"]["val_ratio"])
    # test_ratio = cfg["split"]["test_ratio"]  # optional, implicit remainder
    stratify = bool(cfg["split"]["stratify"])

    # 1) load
    df = pd.read_csv(labeled_path)

    # 2) keep only needed columns
    df = df[[text_col, label_col]].copy()

    # 3) drop empty rows
    df = df.dropna(subset=[text_col, label_col])

    # 4) clean text
    df[text_col] = df[text_col].map(clean_text)

    # 5) drop empty after cleaning
    df = df[df[text_col].str.len() > 0]

    # 6) normalize label (tusaale: uppercase)
    df[label_col] = df[label_col].astype(str).str.strip().str.upper()

    # 7) dedup on cleaned text
    df = df.drop_duplicates(subset=[text_col], keep="first").reset_index(drop=True)

    # 8) split
    if stratify:
        train_df, val_df, test_df = stratified_split(
            df, label_col, seed, train_ratio, val_ratio
        )
    else:
        df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
        n = len(df)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        train_df = df.iloc[:n_train]
        val_df = df.iloc[n_train:n_train + n_val]
        test_df = df.iloc[n_train + n_val:]

    # 9) save outputs (standardize column names to Text/Label if you want)
    processed_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(processed_dir / train_name, index=False)
    val_df.to_csv(processed_dir / val_name, index=False)
    test_df.to_csv(processed_dir / test_name, index=False)

    print("Done:", len(train_df), len(val_df), len(test_df))


if __name__ == "__main__":
    main()