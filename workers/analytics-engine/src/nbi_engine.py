import polars as pl
from uuid import uuid4
from datetime import datetime
from itertools import combinations
from collections import defaultdict
from .db import get_connection

def run_nbi_analysis(
    franchise_id: str,
    min_support: float = 0.005,
    min_confidence: float = 0.10,
    min_lift: float = 1.10
):
    """
    Project #4: Next-Best-Item (NBI) Market Basket Analysis
    1. Reads strictly from versioned view `v_nbi_basket_stream`.
    2. Mines frequent itemsets and association rules (Support, Confidence, Lift).
    3. Optimizes for Incremental Gross Margin Pesos (Δ Margin ₱), not just raw basket size.
    4. Writes recommendations to `nbi_recommendations` table.
    """
    print(f"[NBI Engine] Running Association Rule Basket Analysis for franchise: {franchise_id}...")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Query versioned view boundary
            query = """
                SELECT transact, branch, channel, prodcode, proddesc, amount
                FROM v_nbi_basket_stream
                WHERE franchise_id = %s
            """
            cur.execute(query, (franchise_id,))
            rows = cur.fetchall()

            if not rows:
                print("[NBI Engine] Zero line items found in stream. Run complete.")
                return []

            df = pl.DataFrame(
                rows,
                schema=["transact", "branch", "channel", "prodcode", "proddesc", "amount"],
                orient="row"
            )

            # Group transactions into baskets
            baskets_df = df.group_by(["transact", "channel"]).agg(
                pl.col("prodcode").unique().alias("items")
            )

            total_transactions = len(baskets_df)
            if total_transactions < 2:
                print("[NBI Engine] Insufficient transactions for association rule mining.")
                return []
            
            # Fetch real SKU margins for this franchise
            margin_query = "SELECT prodcode, gross_margin_peso FROM sku_margins WHERE franchise_id = %s"
            cur.execute(margin_query, (franchise_id,))
            margin_rows = cur.fetchall()
            margin_lookup = {row[0]: float(row[1]) for row in margin_rows}

            # 1. Count individual item frequencies (Antecedents & Consequents)
            item_counts = defaultdict(int)
            pair_counts = defaultdict(int)

            for items in baskets_df["items"]:
                item_list = list(items)
                for item in item_list:
                    item_counts[item] += 1
                for a, b in combinations(item_list, 2):
                    pair_counts[(a, b)] += 1
                    pair_counts[(b, a)] += 1

            # 2. Mine Association Rules: (A -> B)
            rules = []
            for (ant, con), pair_freq in pair_counts.items():
                support_ab = pair_freq / total_transactions
                if support_ab < min_support:
                    continue

                support_a = item_counts[ant] / total_transactions
                support_b = item_counts[con] / total_transactions
                confidence = support_ab / support_a if support_a > 0 else 0
                lift = confidence / support_b if support_b > 0 else 0

                if confidence >= min_confidence and lift >= min_lift:
                    # Real margin from consequent SKU, fallback to 0.0 if not found
                    consequent_margin = margin_lookup.get(con, 0.0)
                    real_margin_peso = float(pair_freq) * consequent_margin

                    rules.append({
                        "channel": "ALL_CHANNELS",
                        "daypart": "ALL",
                        "antecedent": ant,
                        "consequent": con,
                        "support": round(support_ab, 4),
                        "confidence": round(confidence, 4),
                        "lift": round(lift, 2),
                        "incremental_margin": round(real_margin_peso, 2),
                    })

            # Sort rules by highest Lift and Incremental Margin
            rules.sort(key=lambda r: (r["lift"], r["incremental_margin"]), reverse=True)
            print(f"[NBI Engine] Generated {len(rules)} high-affinity upsell rules.")

            if not rules:
                return []

            # Write-back to nbi_recommendations table
            insert_query = """
                INSERT INTO nbi_recommendations (
                    id, franchise_id, channel, daypart, antecedent_sku,
                    consequent_sku, support, confidence, lift,
                    incremental_margin_peso, rank_priority, is_active, computed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            insert_rows = []
            for idx, r in enumerate(rules[:50], start=1):
                insert_rows.append((
                    str(uuid4()),
                    franchise_id,
                    r["channel"],
                    r["daypart"],
                    r["antecedent"],
                    r["consequent"],
                    r["support"],
                    r["confidence"],
                    r["lift"],
                    r["incremental_margin"],
                    idx,
                    True,
                    datetime.utcnow(),
                ))

            cur.executemany(insert_query, insert_rows)
            conn.commit()
            print(f"[NBI Engine] Successfully stored {len(insert_rows)} top NBI pairings in database.")
            return insert_rows
