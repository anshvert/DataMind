"""Seed dataset generation for NaturalLangData operational and analytics stores."""
from pathlib import Path
import sqlite3
import duckdb
import pandas as pd


def get_base_dir() -> Path:
    """Return the base directory for data storage."""
    return Path(__file__).resolve().parent


def seed_sqlite_database(db_path: Path) -> None:
    """Create and seed the operational SQLite database with customers and orders."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            signup_date TEXT NOT NULL,
            region TEXT NOT NULL,
            is_active INTEGER NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
        """
    )

    customers_data = [
        (1, "Alice Smith", "2023-01-15", "NA", 1),
        (2, "Bob Jones", "2023-02-20", "EMEA", 1),
        (3, "Carlos Diaz", "2023-03-10", "LATAM", 0),
        (4, "Diana Prince", "2023-04-05", "EMEA", 1),
        (5, "Evan Wright", "2023-05-18", "APAC", 1),
        (6, "Fiona Gallagher", "2023-06-22", "NA", 0),
        (7, "George Clark", "2023-07-09", "APAC", 1),
        (8, "Hannah Abbott", "2023-08-30", "EMEA", 1),
        (9, "Ian Malcolm", "2023-09-14", "NA", 1),
        (10, "Julia Roberts", "2023-10-01", "LATAM", 1),
    ]

    cursor.executemany(
        "INSERT INTO customers (customer_id, full_name, signup_date, region, is_active) VALUES (?, ?, ?, ?, ?)",
        customers_data,
    )

    orders_data = [
        (101, 1, "2023-11-01", "completed", 1250.00),
        (102, 2, "2023-11-05", "completed", 450.50),
        (103, 1, "2023-11-12", "completed", 890.00),
        (104, 4, "2023-11-15", "refunded", 320.00),
        (105, 5, "2023-11-20", "completed", 2100.00),
        (106, 7, "2023-11-25", "pending", 640.00),
        (107, 8, "2023-12-02", "completed", 1750.25),
        (108, 9, "2023-12-10", "completed", 980.00),
        (109, 10, "2023-12-15", "cancelled", 150.00),
        (110, 2, "2023-12-20", "completed", 1320.00),
        (111, 4, "2024-01-05", "completed", 2400.00),
        (112, 5, "2024-01-18", "completed", 1150.00),
        (113, 1, "2024-01-22", "completed", 3100.50),
        (114, 9, "2024-02-01", "pending", 720.00),
        (115, 8, "2024-02-14", "completed", 1950.00),
    ]

    cursor.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, total_amount) VALUES (?, ?, ?, ?, ?)",
        orders_data,
    )

    conn.commit()
    conn.close()


def seed_analytics_data(analytics_dir: Path) -> None:
    """Create and seed analytical flat files in Parquet and CSV formats."""
    analytics_dir.mkdir(parents=True, exist_ok=True)

    arr_data = [
        {"quarter": "2023-Q1", "region": "NA", "gross_arr": 520000.0, "churned_arr": 32000.0, "net_arr": 488000.0},
        {"quarter": "2023-Q1", "region": "EMEA", "gross_arr": 410000.0, "churned_arr": 25000.0, "net_arr": 385000.0},
        {"quarter": "2023-Q1", "region": "APAC", "gross_arr": 290000.0, "churned_arr": 18000.0, "net_arr": 272000.0},
        {"quarter": "2023-Q1", "region": "LATAM", "gross_arr": 150000.0, "churned_arr": 12000.0, "net_arr": 138000.0},
        {"quarter": "2023-Q2", "region": "NA", "gross_arr": 580000.0, "churned_arr": 28000.0, "net_arr": 552000.0},
        {"quarter": "2023-Q2", "region": "EMEA", "gross_arr": 460000.0, "churned_arr": 22000.0, "net_arr": 438000.0},
        {"quarter": "2023-Q2", "region": "APAC", "gross_arr": 330000.0, "churned_arr": 15000.0, "net_arr": 315000.0},
        {"quarter": "2023-Q2", "region": "LATAM", "gross_arr": 175000.0, "churned_arr": 11000.0, "net_arr": 164000.0},
        {"quarter": "2023-Q3", "region": "NA", "gross_arr": 650000.0, "churned_arr": 31000.0, "net_arr": 619000.0},
        {"quarter": "2023-Q3", "region": "EMEA", "gross_arr": 510000.0, "churned_arr": 24000.0, "net_arr": 486000.0},
        {"quarter": "2023-Q3", "region": "APAC", "gross_arr": 380000.0, "churned_arr": 14000.0, "net_arr": 366000.0},
        {"quarter": "2023-Q3", "region": "LATAM", "gross_arr": 200000.0, "churned_arr": 13000.0, "net_arr": 187000.0},
        {"quarter": "2023-Q4", "region": "NA", "gross_arr": 740000.0, "churned_arr": 35000.0, "net_arr": 705000.0},
        {"quarter": "2023-Q4", "region": "EMEA", "gross_arr": 590000.0, "churned_arr": 26000.0, "net_arr": 564000.0},
        {"quarter": "2023-Q4", "region": "APAC", "gross_arr": 440000.0, "churned_arr": 16000.0, "net_arr": 424000.0},
        {"quarter": "2023-Q4", "region": "LATAM", "gross_arr": 230000.0, "churned_arr": 14000.0, "net_arr": 216000.0},
        {"quarter": "2024-Q1", "region": "NA", "gross_arr": 830000.0, "churned_arr": 33000.0, "net_arr": 797000.0},
        {"quarter": "2024-Q1", "region": "EMEA", "gross_arr": 660000.0, "churned_arr": 27000.0, "net_arr": 633000.0},
        {"quarter": "2024-Q1", "region": "APAC", "gross_arr": 490000.0, "churned_arr": 15000.0, "net_arr": 475000.0},
        {"quarter": "2024-Q1", "region": "LATAM", "gross_arr": 260000.0, "churned_arr": 12000.0, "net_arr": 248000.0},
    ]
    df_arr = pd.DataFrame(arr_data)
    duckdb.sql("SELECT * FROM df_arr").write_parquet(str(analytics_dir / "quarterly_arr.parquet"))

    inventory_data = [
        {"sku": "SKU-1001", "product_name": "Cloud Server Pro", "category": "Infrastructure", "stock_count": 85, "unit_price": 1200.0},
        {"sku": "SKU-1002", "product_name": "Edge Gateway X", "category": "Hardware", "stock_count": 240, "unit_price": 450.0},
        {"sku": "SKU-1003", "product_name": "Database Cluster Engine", "category": "Software", "stock_count": 500, "unit_price": 2800.0},
        {"sku": "SKU-1004", "product_name": "Secure Vault Module", "category": "Security", "stock_count": 60, "unit_price": 3100.0},
        {"sku": "SKU-1005", "product_name": "Load Balancer Appliance", "category": "Hardware", "stock_count": 130, "unit_price": 890.0},
        {"sku": "SKU-1006", "product_name": "API Gateway Enterprise", "category": "Software", "stock_count": 420, "unit_price": 1750.0},
        {"sku": "SKU-1007", "product_name": "Telemetry Node", "category": "IoT", "stock_count": 310, "unit_price": 220.0},
        {"sku": "SKU-1008", "product_name": "Backup Storage Unit", "category": "Infrastructure", "stock_count": 95, "unit_price": 1450.0},
    ]
    df_inv = pd.DataFrame(inventory_data)
    df_inv.to_csv(analytics_dir / "product_inventory.csv", index=False)

    churn_data = [
        {"event_id": 1, "customer_id": 3, "event_date": "2023-06-15", "reason": "Pricing", "loss_amount": 4500.0},
        {"event_id": 2, "customer_id": 6, "event_date": "2023-09-20", "reason": "Competitor", "loss_amount": 8200.0},
    ]
    df_churn = pd.DataFrame(churn_data)
    duckdb.sql("SELECT * FROM df_churn").write_parquet(str(analytics_dir / "churn_events.parquet"))


def seed_all() -> None:
    """Run full dataset initialization for SQLite and analytics flat files."""
    base_dir = get_base_dir()
    db_path = base_dir / "operational.db"
    analytics_dir = base_dir / "analytics"

    seed_sqlite_database(db_path)
    seed_analytics_data(analytics_dir)


if __name__ == "__main__":
    seed_all()
