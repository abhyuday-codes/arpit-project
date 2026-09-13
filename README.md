# Comm-Log Reconciliation — Take-Home Assignment

**Author:** Arpit | **Scope:** Merchant 501 · October 2026 · Campaign sends (`communication_type = '2'`)

---

## Problem

Given a `campaign` table and a `communication_log` table for a marketing platform, compute
**`target_base`**: the number of distinct customers reached by a merchant in a given month,
where a retry chain (campaign A → B → C, linked via `parent_id`) counts as **one underlying
communication** — so a customer reached at any step of the chain counts only once.

---

## Answer

```
target_base = 21
```

---

## How to Run

```bash
python solution.py
```

Requires Python 3.8+ (stdlib only — `sqlite3`, `pathlib`). Reads from `data/comm_log.db`.

Prints:
- Which campaigns were excluded by the eligibility gate
- The full campaign chain structure
- A step-by-step reconciliation bridge (raw count → 21)
- SQL result assertion

To run the SQL query standalone:

```bash
sqlite3 data/comm_log.db < query.sql
# → 21
```

---

## Key Finding

**Campaign 9004 ("Diwali Cart Recovery - Retry C") is the critical trap.**

It is a child of campaign 9001 in the retry chain, so its 4 customers (C11–C14) appear
in `communication_log` with `delivery_status = 900` (delivered). But the campaign itself
carries `creation_status = 'approval_awaiting'` — meaning the send pipeline ran before
approval bookkeeping caught up.

A naive `COUNT(DISTINCT customer_id)` on all delivered rows returns **25**.
Applying the eligibility gate correctly gives **21**.

This is what makes the problem non-trivial: the data looks clean, the sends were physically
delivered, and the customers are real — but the campaign is not reportable.

---

## Approach

1. **Eligibility gate** — filter campaigns where `creation_status IN ('approved', 'aborted',
   'resumed', 'stopped') AND processing_status = 'processed'`. Campaign 9004 is excluded.

2. **Chain resolution** — walk `parent_id` links recursively to find the root of each
   campaign chain. All campaigns in a chain share one `root_id`.

3. **Distinct count** — count `DISTINCT (root_id, customer_id)` pairs. This naturally
   handles both intra-chain dedup (same customer, multiple retry attempts) and
   standalone re-targeting (same customer, same campaign, different dates).

---

## Files

| File | Purpose |
|---|---|
| [`query.sql`](query.sql) | Single SQL query (recursive CTE) that returns `target_base = 21` |
| [`solution.py`](solution.py) | Step-by-step Python analysis with bridge table and SQL assertion |
| [`reconciliation_bridge.md`](reconciliation_bridge.md) | Human-readable bridge: raw count → each dedup step → 21 |
| [`generate_dataset.py`](generate_dataset.py) | Provided — generates the synthetic dataset |
| [`data/`](data/) | SQLite DB and CSVs |

---

## Dataset Summary

- 7 campaigns across 3 families + 1 standalone
- 30 raw `communication_log` rows
- 1 ineligible campaign (9004) · 4 excluded rows
- 2 retry chains (9001→9002→9003, 9201→9202) · 3 cross-campaign customer dups
- 1 standalone re-target (C20 in 9101 × 2 dates) · 1 within-campaign dup
