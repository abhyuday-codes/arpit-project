# Comm-Log Reconciliation — Take-Home Assignment

**Author:** Arpit | **Scope:** Merchant 501 · October 2026 · Campaign sends (`communication_type = '2'`)

---

## Problem

Given a `campaign` table and a `communication_log` table for a marketing platform, compute
**`target_base`**: the number of qualifying sends for a merchant in a given month, where:

- A **retry chain** (campaign A → B → C, linked via `parent_id`) counts as one underlying
  communication — a customer reached at any step of the chain counts **once**.
- A **standalone** campaign (no parent, no children) treats every send as its own event —
  the same customer targeted on two different dates counts **twice**.

---

## Answer

```
target_base = 22
```

---

## How to Run

```bash
python solution.py
```

Requires Python 3.8+ (stdlib only — `sqlite3`, `pathlib`). Reads from `data/comm_log.db`.

Prints:
- Which campaigns are excluded by the eligibility gate
- Campaign chain/standalone classification
- A step-by-step reconciliation bridge (raw count → 22)
- SQL result assertion

To run the SQL query standalone:

```bash
sqlite3 data/comm_log.db < query.sql
# → 22
```

---

## Key Findings

### 1 — The eligibility trap (campaign 9004)

Campaign 9004 ("Diwali Cart Recovery - Retry C") carries `creation_status = 'approval_awaiting'`
yet its 4 rows appear in `communication_log` with `delivery_status = 900` (delivered). The send
pipeline ran before approval bookkeeping caught up. The eligibility gate:

```
creation_status IN ('approved', 'aborted', 'resumed', 'stopped')
AND processing_status = 'processed'
```

excludes these 4 customers (C11–C14) entirely. A naive count on delivered rows gives **25**;
after the eligibility gate it is **26**.

### 2 — Standalone campaigns count rows, not distinct customers

Campaign 9101 is standalone (no parent, no children). Customer C20 was sent on both 2026-10-10
and 2026-10-20 — two independent re-targeting events, not a retry. Both count toward
`target_base`. A `COUNT(DISTINCT customer_id)` for this campaign returns 6; the correct
contribution is **7**.

---

## Approach

1. **Eligibility gate** — exclude campaigns where `creation_status = 'approval_awaiting'`
   (or other non-finalized statuses) or `processing_status != 'processed'`.

2. **Chain classification** — walk `parent_id` links recursively to find the root of each chain.
   Campaigns with no parent and no children are standalone.

3. **Dual counting** — for chain campaigns: `COUNT DISTINCT (root_id, customer_id)`.
   For standalone campaigns: `COUNT(*)` (every row is its own event).

---

## Files

| File | Purpose |
|---|---|
| [`query.sql`](query.sql) | SQL query (recursive CTE + dual count) → `target_base = 22` |
| [`solution.py`](solution.py) | Step-by-step Python analysis with bridge table and SQL assertion |
| [`reconciliation_bridge.md`](reconciliation_bridge.md) | Human-readable bridge: raw count → each dedup step → 22 |
| [`generate_dataset.py`](generate_dataset.py) | Provided — generates the synthetic dataset |
| [`data/`](data/) | SQLite DB and CSVs |

---

## Dataset Summary

- 7 campaigns across 2 retry chains + 1 standalone + 1 ineligible branch
- 30 raw `communication_log` rows
- 1 ineligible campaign (9004) · 4 excluded rows
- 2 retry chains (9001→9002→9003, 9201→9202) · 4 cross-campaign customer dups removed
- 1 standalone re-target (C20 in 9101 × 2 dates) · both sends qualify
