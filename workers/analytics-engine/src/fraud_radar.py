import polars as pl
import numpy as np
from uuid import uuid4
from datetime import datetime
from .db import get_connection

def run_fraud_radar(franchise_id: str, z_threshold: float = 2.5):
    """
    Project #7: Discount & Void Fraud Anomaly Radar
    1. Reads strictly from versioned view `v_fraud_radar_stream`.
    2. Clusters baselines by demographic / hospital proximity (prevents false-positive flags).
    3. Calculates cashier-level Z-Scores for SC/PWD discounts and transaction voids.
    4. Writes flagged statistical anomalies back to `discount_void_anomalies`.
    """
    print(f"[Fraud Radar] Starting anomaly detection run for franchise: {franchise_id}...")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Query versioned view boundary
            query = """
                SELECT franchise_id, branch, cluster, is_hospital_or_retirement_area,
                       cashier_id, cashier_name, repdate, rsontype, void_flg, amount
                FROM v_fraud_radar_stream
                WHERE franchise_id = %s
            """
            cur.execute(query, (franchise_id,))
            rows = cur.fetchall()

            if not rows:
                print("[Fraud Radar] Zero discount/void records found in stream. Run complete.")
                return []

            df = pl.DataFrame(
                rows,
                schema=[
                    "franchise_id", "branch", "cluster", "is_hospital_area",
                    "cashier_id", "cashier_name", "repdate", "rsontype", "void_flg", "amount"
                ],
                orient="row"
            )

            # Cast numeric amount
            df = df.with_columns(pl.col("amount").cast(pl.Float64))

            # Aggregate total discount/void metrics per cashier per day
            cashier_daily = df.group_by([
                "franchise_id", "branch", "cluster", "is_hospital_area",
                "cashier_id", "cashier_name", "repdate"
            ]).agg([
                pl.col("amount").sum().alias("total_discount_void_amount"),
                pl.col("amount").count().alias("flagged_event_count"),
            ])

            # Compute peer cluster baseline (Mean & StdDev per cluster group)
            cluster_stats = cashier_daily.group_by("cluster").agg([
                pl.col("total_discount_void_amount").mean().alias("cluster_mean"),
                pl.col("total_discount_void_amount").std().alias("cluster_std"),
            ]).fill_null(0.0)

            # Join stats back and calculate Z-Score
            scored_df = cashier_daily.join(cluster_stats, on="cluster", how="left")
            scored_df = scored_df.with_columns(
                pl.when(pl.col("cluster_std") > 0)
                .then((pl.col("total_discount_void_amount") - pl.col("cluster_mean")) / pl.col("cluster_std"))
                .otherwise(0.0)
                .alias("z_score")
            )

            # Filter for statistical outliers exceeding threshold
            anomalies = scored_df.filter(pl.col("z_score") >= z_threshold)
            print(f"[Fraud Radar] Detected {len(anomalies)} statistical anomaly events (Z >= {z_threshold}).")

            if len(anomalies) == 0:
                return []

            # Write-back to discount_void_anomalies table
            insert_query = """
                INSERT INTO discount_void_anomalies (
                    id, franchise_id, branch, cashier_id, cashier_name, repdate,
                    anomaly_type, z_score, peer_cluster, observed_value,
                    expected_cluster_mean, estimated_peso_exposure, is_reviewed, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            insert_rows = []
            for row in anomalies.iter_rows(named=True):
                observed = float(row["total_discount_void_amount"])
                expected = float(row["cluster_mean"] or 0.0)
                exposure = max(0.0, observed - expected)
                
                insert_rows.append((
                    str(uuid4()),
                    row["franchise_id"],
                    row["branch"],
                    row["cashier_id"],
                    row["cashier_name"],
                    row["repdate"],
                    "HIGH_SC_PWD_DISCOUNT_OUTLIER",
                    round(float(row["z_score"]), 2),
                    row["cluster"] or "DEFAULT_CLUSTER",
                    round(observed, 2),
                    round(expected, 2),
                    round(exposure, 2),
                    False,
                    datetime.utcnow(),
                ))

            cur.executemany(insert_query, insert_rows)
            conn.commit()
            print(f"[Fraud Radar] Successfully inserted {len(insert_rows)} anomaly records into database.")
            return insert_rows
