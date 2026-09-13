# Reconciliation Bridge — target_base for Merchant 501, October 2026

## Summary

**target_base = 21**

Starting from 30 raw rows in `communication_log`, four adjustments reach the correct answer.

---

## Bridge Table

| Step | Description | Adjustment | Running Total |
|:----:|---|:---:|:---:|
| 1 | Raw row count in `communication_log` (merchant 501, type=2, Oct 2026) | — | 30 |
| 2 | Remove rows belonging to ineligible campaign 9004 (`approval_awaiting`) — customers C11–C14 | −4 | 26 |
| 3 | De-duplicate C2 appearing in two campaigns (9001, 9002) of the same retry chain | −1 | 25 |
| 4 | De-duplicate C3 appearing in three campaigns (9001, 9002, 9003) of the same retry chain | −2 | 23 |
| 5 | De-duplicate D1 appearing in two campaigns (9201, 9202) of the same retry chain | −1 | 22 |
| 6 | De-duplicate C20 appearing twice in standalone campaign 9101 (re-targeted on different dates) | −1 | 21 |
| ✅ | **Final `target_base`** | | **21** |

---

## Step-by-Step Explanation

### Step 2 — The ineligibility trap (campaign 9004)

Campaign 9004 ("Diwali Cart Recovery - Retry C") has `creation_status = 'approval_awaiting'`.
Even though its 4 rows exist in `communication_log` with `delivery_status = 900` (delivered),
this campaign was never formally approved. The send pipeline ran ahead of the approval
bookkeeping. A campaign is reportable only when **both** conditions are met:

```
creation_status IN ('approved', 'aborted', 'resumed', 'stopped')
AND processing_status = 'processed'
```

Campaign 9004 fails the first condition. Customers C11–C14 are physically reached but not
counted. A naive `COUNT(DISTINCT customer_id)` on delivered rows would produce **25**, not 21.
This is the sharpest trap in the dataset.

### Steps 3–5 — Retry chain de-duplication

Campaigns 9001 → 9002 → 9003 form a single retry chain — the same underlying communication,
re-attempted for customers who did not respond. Customer C2 received attempts in 9001 (failed)
and 9002 (delivered). Customer C3 received attempts in all three campaigns before delivery.
Within a retry chain, every attempt at a customer counts as **one reach**, not multiple.

The SQL recursive CTE walks `parent_id` links to find the root of each chain, then counts
`DISTINCT (root_id, customer_id)` pairs — so C2 and C3 each contribute exactly 1 regardless
of how many campaigns in the chain they appear in. D1, similarly, appears in both 9201 and
9202 and counts once.

### Step 6 — Standalone re-targeting (campaign 9101)

Customer C20 appears twice in campaign 9101 ("Diwali Flash Sale - Standalone") with sends on
2026-10-10 and 2026-10-20. This is not a retry (there is no child campaign) — it is a legitimate
re-target: the customer fell back into the audience and was sent the same campaign again.
Because 9101 has no `parent_id` and no child campaigns, it is its own chain root. Within that
root, C20 still counts once. The two distinct send dates do not change this.

---

## Final Verification

Running `python solution.py` prints the bridge above and asserts:

1. Python count (set-based dedup) == SQL recursive CTE result
2. Both == 21

Running the SQL directly:

```bash
sqlite3 data/comm_log.db < query.sql
# → 21
```
