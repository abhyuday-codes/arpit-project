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


def load_campaigns(conn):
    return {r["id"]: dict(r) for r in conn.execute("SELECT * FROM campaign").fetchall()}


def find_ineligible(campaigns):
    return {
        cid
        for cid, c in campaigns.items()
        if c["creation_status"] not in ELIGIBLE_STATUSES
        or c["processing_status"] != "processed"
    }


def find_standalone(campaigns):
    """Campaigns with no parent AND no children — each send row is its own event."""
    has_children = {c["parent_id"] for c in campaigns.values() if c["parent_id"] is not None}
    return {
        cid
        for cid, c in campaigns.items()
        if c["parent_id"] is None and cid not in has_children
    }


def build_root_map(campaigns):
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


def raw_count(conn):
    return conn.execute(
        """
        SELECT COUNT(*) FROM communication_log
        WHERE merchant_id = 501 AND communication_type = '2'
          AND sent_time >= '2026-10-01 00:00:00' AND sent_time < '2026-11-01 00:00:00'
        """
    ).fetchone()[0]


def eligible_rows(conn, ineligible_ids):
    ph = ",".join("?" * len(ineligible_ids))
    return conn.execute(
        f"""
        SELECT communication_id, customer_id FROM communication_log
        WHERE merchant_id = 501 AND communication_type = '2'
          AND sent_time >= '2026-10-01 00:00:00' AND sent_time < '2026-11-01 00:00:00'
          AND communication_id NOT IN ({ph})
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
    standalone_ids = find_standalone(campaigns)
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

    # --- campaign classification ---
    print("\n[Campaign classification]")
    for cid in sorted(campaigns):
        c = campaigns[cid]
        if cid in ineligible_ids:
            kind = "INELIGIBLE"
        elif cid in standalone_ids:
            kind = "standalone (count all rows)"
        else:
            kind = f"chain (root={root_map[cid]}, dedup by customer)"
        print(f"  Campaign {cid}: {kind}")

    # --- reconciliation bridge ---
    print("\n[Reconciliation bridge]\n")
    hdr = f"{'Step':<5} {'Description':<58} {'Adj':>5} {'Total':>6}"
    print(hdr)
    print("-" * len(hdr))

    running = raw_count(conn)
    print(f"{'1':<5} {'Raw rows in communication_log (Oct 2026, type=2)':<58} {'—':>5} {running:>6}")

    rows = eligible_rows(conn, ineligible_ids)
    adj2 = len(rows) - running
    running = len(rows)
    print(f"{'2':<5} {'Remove ineligible campaign 9004 rows (C11–C14)':<58} {adj2:>+5} {running:>6}")

    # Chain dedup: count distinct (root, customer) per chain campaign
    chain_seen = set()
    standalone_count = 0
    chain_dups = {}  # customer -> list of campaigns seen in

    for r in rows:
        cid = r["communication_id"]
        if cid in standalone_ids:
            standalone_count += 1
        else:
            root_id = root_map[cid]
            key = (root_id, r["customer_id"])
            chain_seen.add(key)

    # Show individual dedup steps for chain customers
    # Reconstruct per-customer appearances within each chain
    from collections import defaultdict
    chain_appearances = defaultdict(set)  # (root, customer) -> set of campaign ids
    for r in rows:
        cid = r["communication_id"]
        if cid not in standalone_ids:
            key = (root_map[cid], r["customer_id"])
            chain_appearances[key].add(cid)

    # Group multi-appearance customers by chain root for display
    multi = [(k, v) for k, v in chain_appearances.items() if len(v) > 1]
    multi.sort(key=lambda x: (x[0][0], x[0][1]))

    step = 3
    for (root_id, customer), campaign_set in multi:
        n = len(campaign_set)
        adj = -(n - 1)
        running += adj
        desc = f"De-dup {customer} in chain {root_id} ({n} campaigns → 1 customer)"
        print(f"{step:<5} {desc:<58} {adj:>+5} {running:>6}")
        step += 1

    standalone_label = (
        f"Standalone 9101: each send is own event — no customer dedup"
    )
    print(f"{'✅':<5} {standalone_label:<58} {'0':>5} {running:>6}")

    total = len(chain_seen) + standalone_count
    print("-" * len(hdr))
    print(f"\n{'target_base (Python)':>40}: {total}")

    sql_result = run_sql_query()
    print(f"{'target_base (SQL)':>40}: {sql_result}")

    assert total == sql_result, f"Mismatch! Python={total}, SQL={sql_result}"
    assert sql_result == 22, f"Expected 22, got {sql_result}"

    print(f"\n{'target_base = 22':>40}")
    print("\nAll assertions passed.")
    conn.close()


if __name__ == "__main__":
    main()
