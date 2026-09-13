"""
Comm-Log Reconciliation — solution script
Computes target_base for merchant 501, October 2026, campaign sends.
Prints a step-by-step reconciliation bridge then asserts the SQL query agrees.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "comm_log.db"
SQL_PATH = Path(__file__).resolve().parent / "query.sql"

ELIGIBLE_STATUSES = {"approved", "aborted", "resumed", "stopped"}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def step1_raw_count(conn):
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM communication_log
        WHERE merchant_id = 501
          AND communication_type = '2'
          AND sent_time >= '2026-10-01 00:00:00'
          AND sent_time <  '2026-11-01 00:00:00'
        """
    ).fetchone()
    return row["n"]


def load_campaigns(conn):
    return {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM campaign").fetchall()
    }


def find_ineligible(campaigns):
    return {
        cid
        for cid, c in campaigns.items()
        if c["creation_status"] not in ELIGIBLE_STATUSES
        or c["processing_status"] != "processed"
    }


def build_root_map(campaigns):
    """Map every campaign id to its chain root id."""
    root = {}

    def get_root(cid):
        if cid in root:
            return root[cid]
        parent = campaigns[cid]["parent_id"]
        root[cid] = cid if parent is None else get_root(parent)
        return root[cid]

    for cid in campaigns:
        get_root(cid)
    return root


def step2_remove_ineligible(conn, ineligible_ids):
    placeholders = ",".join("?" * len(ineligible_ids))
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM communication_log
        WHERE merchant_id = 501
          AND communication_type = '2'
          AND sent_time >= '2026-10-01 00:00:00'
          AND sent_time <  '2026-11-01 00:00:00'
          AND communication_id NOT IN ({placeholders})
        """,
        list(ineligible_ids),
    ).fetchone()
    return row["n"]


def eligible_rows(conn, ineligible_ids):
    placeholders = ",".join("?" * len(ineligible_ids))
    return conn.execute(
        f"""
        SELECT communication_id, customer_id
        FROM communication_log
        WHERE merchant_id = 501
          AND communication_type = '2'
          AND sent_time >= '2026-10-01 00:00:00'
          AND sent_time <  '2026-11-01 00:00:00'
          AND communication_id NOT IN ({placeholders})
        """,
        list(ineligible_ids),
    ).fetchall()


def run_sql_query():
    sql = SQL_PATH.read_text()
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute(sql).fetchone()[0]
    conn.close()
    return result


def main():
    print("=" * 60)
    print("Comm-Log Reconciliation — target_base for merchant 501")
    print("Scope: October 2026, communication_type = '2' (Campaign)")
    print("=" * 60)

    conn = get_conn()
    campaigns = load_campaigns(conn)
    ineligible_ids = find_ineligible(campaigns)
    root_map = build_root_map(campaigns)

    # --- ineligible campaigns ---
    print("\n[Eligibility gate]")
    for cid in sorted(ineligible_ids):
        c = campaigns[cid]
        print(
            f"  Campaign {cid} EXCLUDED — "
            f"creation_status='{c['creation_status']}', "
            f"processing_status='{c['processing_status']}'"
        )

    # --- chain structure ---
    print("\n[Campaign chain structure]")
    roots = sorted({v for v in root_map.values()})
    for root_id in roots:
        chain = sorted(cid for cid, r in root_map.items() if r == root_id)
        label = "INELIGIBLE" if root_id in ineligible_ids or any(
            c in ineligible_ids for c in chain
        ) else ""
        print(f"  Root {root_id}: chain = {chain}  {label}")

    # --- reconciliation bridge ---
    print("\n[Reconciliation bridge]\n")
    header = f"{'Step':<5} {'Description':<55} {'Adj':>6} {'Total':>7}"
    print(header)
    print("-" * len(header))

    raw = step1_raw_count(conn)
    running = raw
    print(f"{'1':<5} {'Raw rows in communication_log (Oct 2026, type=2)':<55} {'—':>6} {running:>7}")

    after_elig = step2_remove_ineligible(conn, ineligible_ids)
    adj2 = after_elig - running
    running = after_elig
    print(f"{'2':<5} {'Remove ineligible campaign rows (9004 approval_awaiting)':<55} {adj2:>+6} {running:>7}")

    rows = eligible_rows(conn, ineligible_ids)

    # Step 3: dedup within each chain (same root, same customer)
    seen_chain = set()
    dedup3 = 0
    for r in rows:
        root_id = root_map[r["communication_id"]]
        key = (root_id, r["customer_id"])
        if key in seen_chain:
            dedup3 += 1
        else:
            seen_chain.add(key)

    running -= dedup3
    print(f"{'3':<5} {'De-dup customers across retry chains (C2×2, C3×3, D1×2)':<55} {-dedup3:>+6} {running:>7}")

    # Verify step 4 & 5 are implicit in step 3 (chain dedup covers both)
    # Show the breakdown for transparency
    chain_a_dedup = sum(
        1 for r in rows
        if root_map[r["communication_id"]] == 9001
        and (9001, r["customer_id"]) in seen_chain
        # already seen means it's a dup
    )

    distinct_by_chain = len(seen_chain)
    adj4_label = "Verify: COUNT(DISTINCT root||customer) from SQL"
    sql_result = run_sql_query()

    print(f"{'✓':<5} {'Final target_base':<55} {'':>6} {distinct_by_chain:>7}")
    print("-" * len(header))
    print(f"\n{'SQL query result':>60}: {sql_result}")

    assert distinct_by_chain == sql_result, (
        f"Mismatch! Python={distinct_by_chain}, SQL={sql_result}"
    )
    assert sql_result == 21, f"Expected 21, got {sql_result}"

    print(f"\n{'target_base = 21':>60}")
    print("\nAll assertions passed.")
    conn.close()


if __name__ == "__main__":
    main()
