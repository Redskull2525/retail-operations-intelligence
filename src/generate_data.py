"""
generate_data.py
----------------
Creates SYNTHETIC (fake) retail data for this portfolio project.

Nothing here comes from a real company. A fixed random seed (42) means
everyone who runs this script gets exactly the same files.

Output files (written to data/raw/ by default):
    product_catalog.csv         20 products, 4 categories, prices in INR
    sales_transactions_raw.csv  ~6,000 order lines for the year 2025
    inventory_snapshot.csv      on-hand stock per product per region on 2025-12-31

To make the cleaning step realistic, a small, DOCUMENTED set of data-quality
problems is injected into the raw sales file on purpose:

    Issue                         Rows   What it looks like
    ----------------------------  -----  -----------------------------------
    Exact duplicate rows             60  same row appears twice (~1%)
    Missing region                   15  region is blank
    Messy region text                60  " west", "NORTH ", "south"
    Messy channel text               60  "ONLINE", " retail store", "marketplace "
    Negative quantity (returns)      40  quantity = -1 ... -3
    Date outside 2025                12  dates in Dec-2024 or Jan-2026

Each issue is applied to a DIFFERENT set of rows, so the counts above are
exact and the tests can check them.

Run:  python src/generate_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_SALES_ROWS = 6000
REGIONS = ["West", "North", "South", "East"]
CHANNELS = ["Online", "Retail Store", "Marketplace"]

# How many rows get each injected issue (kept here so tests can import them).
N_DUPLICATES = 60
N_MISSING_REGION = 15
N_MESSY_REGION = 60
N_MESSY_CHANNEL = 60
N_RETURNS = 40
N_BAD_DATES = 12

PRODUCT_NAMES = {
    "Electronics": ["Wireless Mouse", "USB-C Hub", "Bluetooth Speaker", "Webcam", "Keyboard"],
    "Home": ["Desk Lamp", "Storage Box", "Water Bottle", "Bedsheet Set", "Air Purifier"],
    "Office": ["Notebook Pack", "Office Chair", "Monitor Stand", "Pen Set", "Paper Ream"],
    "Lifestyle": ["Backpack", "Travel Mug", "Yoga Mat", "Lunch Box", "Fitness Band"],
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def make_product_catalog(rng):
    """Build a table of 20 products with cost, price and stock rules."""
    rows = []
    for category, names in PRODUCT_NAMES.items():
        for name in names:
            product_number = len(rows) + 1
            unit_cost = int(rng.integers(120, 2500))           # INR
            markup = rng.uniform(1.25, 1.85)                    # price = cost x 1.25 to 1.85
            unit_price = int(round(unit_cost * markup))
            rows.append({
                "product_id": f"P{product_number:03d}",
                "product_name": name,
                "category": category,
                "unit_cost": unit_cost,
                "unit_price": unit_price,
                "reorder_point": int(rng.integers(12, 35)),
                "target_stock": int(rng.integers(50, 120)),
            })
    return pd.DataFrame(rows)


def make_clean_sales(rng, products):
    """Build 6,000 clean order lines (one product per order)."""
    dates = pd.date_range("2025-01-01", "2025-12-31", freq="D")

    # Simple seasonality: the festive months Oct-Dec sell more than other months.
    month_weight = {1: 0.9, 2: 0.85, 3: 0.95, 4: 0.9, 5: 0.95, 6: 0.9,
                    7: 0.95, 8: 1.0, 9: 1.05, 10: 1.3, 11: 1.4, 12: 1.35}
    date_weights = np.array([month_weight[d.month] for d in dates])
    date_weights = date_weights / date_weights.sum()

    region_weights = [0.32, 0.26, 0.24, 0.18]      # West, North, South, East
    channel_weights = [0.45, 0.35, 0.20]           # Online, Retail Store, Marketplace

    rows = []
    for i in range(N_SALES_ROWS):
        product = products.iloc[int(rng.integers(0, len(products)))]
        order_date = dates[rng.choice(len(dates), p=date_weights)]
        rows.append({
            "order_id": f"O{i + 1:06d}",
            "order_date": order_date.strftime("%Y-%m-%d"),
            "region": REGIONS[rng.choice(4, p=region_weights)],
            "channel": CHANNELS[rng.choice(3, p=channel_weights)],
            "product_id": product["product_id"],
            "quantity": int(rng.integers(1, 6)),
            "unit_price": int(product["unit_price"]),
            "discount_pct": float(rng.choice([0.0, 0.0, 0.0, 0.05, 0.10, 0.15])),
        })
    return pd.DataFrame(rows)


def inject_quality_issues(rng, sales):
    """Damage a few rows on purpose so the pipeline has something to clean.

    We shuffle the row positions once and then take separate, non-overlapping
    slices for each issue. That way every count is exact.
    """
    sales = sales.copy()
    positions = rng.permutation(len(sales))

    start = 0

    def take(count):
        nonlocal start
        chosen = positions[start:start + count]
        start = start + count
        return chosen

    missing_region_rows = take(N_MISSING_REGION)
    messy_region_rows = take(N_MESSY_REGION)
    messy_channel_rows = take(N_MESSY_CHANNEL)
    return_rows = take(N_RETURNS)
    bad_date_rows = take(N_BAD_DATES)
    duplicate_rows = take(N_DUPLICATES)

    # 1) Missing region
    sales.loc[missing_region_rows, "region"] = None

    # 2) Messy region text: wrong case and extra spaces
    for row in messy_region_rows:
        clean_value = sales.loc[row, "region"]
        style = row % 3
        if style == 0:
            sales.loc[row, "region"] = " " + clean_value.lower()      # " west"
        elif style == 1:
            sales.loc[row, "region"] = clean_value.upper() + " "      # "NORTH "
        else:
            sales.loc[row, "region"] = clean_value.lower()            # "south"

    # 3) Messy channel text
    for row in messy_channel_rows:
        clean_value = sales.loc[row, "channel"]
        style = row % 3
        if style == 0:
            sales.loc[row, "channel"] = clean_value.upper()           # "ONLINE"
        elif style == 1:
            sales.loc[row, "channel"] = " " + clean_value.lower()     # " retail store"
        else:
            sales.loc[row, "channel"] = clean_value.lower() + " "     # "marketplace "

    # 4) Returns recorded as negative quantity
    for row in return_rows:
        sales.loc[row, "quantity"] = -int(rng.integers(1, 4))

    # 5) Dates outside 2025 (typing / system-clock errors)
    outside_dates = ["2024-12-28", "2024-12-30", "2024-12-31", "2026-01-01", "2026-01-02", "2026-01-05"]
    for k, row in enumerate(bad_date_rows):
        sales.loc[row, "order_date"] = outside_dates[k % len(outside_dates)]

    # 6) Exact duplicates: copy some untouched rows and append them
    duplicates = sales.loc[duplicate_rows]
    sales = pd.concat([sales, duplicates], ignore_index=True)

    # Shuffle so duplicates are not all at the bottom
    shuffled_order = rng.permutation(len(sales))
    sales = sales.iloc[shuffled_order].reset_index(drop=True)
    return sales


def make_inventory_snapshot(rng, products):
    """Stock on hand for every product in every region on 2025-12-31.

    Bug fix compared with the first version of this project: on_hand used to be
    drawn from 0..target_stock, so "Overstock" (on_hand > target_stock) could
    never happen. Now it is drawn from 0..1.5 x target_stock, so Reorder,
    Healthy and Overstock all appear.
    """
    rows = []
    for _, product in products.iterrows():
        upper_limit = int(product["target_stock"] * 1.5)
        for region in REGIONS:
            rows.append({
                "snapshot_date": "2025-12-31",
                "region": region,
                "product_id": product["product_id"],
                "on_hand_units": int(rng.integers(0, upper_limit + 1)),
            })
    return pd.DataFrame(rows)


def generate(raw_dir=DEFAULT_RAW_DIR, seed=SEED):
    """Create all three raw CSV files. Returns the folder they were written to."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    products = make_product_catalog(rng)
    clean_sales = make_clean_sales(rng, products)
    raw_sales = inject_quality_issues(rng, clean_sales)
    inventory = make_inventory_snapshot(rng, products)

    products.to_csv(raw_dir / "product_catalog.csv", index=False)
    raw_sales.to_csv(raw_dir / "sales_transactions_raw.csv", index=False)
    inventory.to_csv(raw_dir / "inventory_snapshot.csv", index=False)

    print(f"Wrote {len(products)} products, {len(raw_sales)} raw sales rows, "
          f"{len(inventory)} inventory rows to {raw_dir}")
    return raw_dir


if __name__ == "__main__":
    generate()
