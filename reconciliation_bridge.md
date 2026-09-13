# Reconciliation Bridge — target_base for Merchant 501, October 2026

## Summary

**target_base = 22**

Starting from 30 raw rows in `communication_log`, four adjustments reach the correct answer.

---

## Counting Rules

| Campaign type | Rule |
|---|---|
| **Retry chain** (has parent OR has children) | COUNT DISTINCT customers per chain root — multiple attempts at the same customer count once |
| **Standalone** (no parent, no children) | COUNT every send row — each re-send is its own qualifying event |

---

## Bridge Table

| Step | Description | Adjustment | Running Total |
|:----:|---|:---:|:---:|
| 1 | Raw row count in `communication_log` (merchant 501, type=2, Oct 2026) | — | 30 |
| 2 | Remove rows belonging to ineligible campaign 9004 (`approval_awaiting`) — customers C11–C14 | −4 | 26 |
| 3 | De-duplicate C2 appearing in two campaigns (9001, 9002) of the same retry chain | −1 | 25 |
| 4 | De-duplicate C3 appearing in three campaigns (9001, 9002, 9003) of the same retry chain | −2 | 23 |
| 5 | De-duplicate D1 appearing in two campaigns (9201, 9202) of the same retry chain | −1 | 22 |
| ✅ | **Standalone 9101: C20's two sends on different dates are two qualifying events — no adjustment** | 0 | **22** |

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
counted. A naive `COUNT(DISTINCT customer_id)` on all delivered rows would produce **25** — but
even after applying the eligibility gate, there are further dedup steps.

### Steps 3–5 — Retry chain de-duplication

Campaigns 9001 → 9002 → 9003 form a single retry chain — the same underlying communication,
re-attempted for customers who did not respond. Customer C2 received attempts in 9001 (failed)
and 9002 (delivered). Customer C3 received attempts in all three campaigns before delivery.
Within a retry chain, every attempt at a customer counts as **one reach**, not multiple.

The SQL recursive CTE walks `parent_id` links to find the root of each chain, then counts
`DISTINCT (root_id, customer_id)` pairs — so C2 and C3 each contribute exactly 1 regardless
of how many campaigns in the chain they appear in. D1, similarly, appears in both 9201 and
9202 and counts once.

### Step 6 (no adjustment) — Standalone re-targeting (campaign 9101)

Customer C20 appears twice in campaign 9101 ("Diwali Flash Sale - Standalone") with sends on
2026-10-10 and 2026-10-20. This is NOT a retry — there is no child campaign. It is a
legitimate re-target: the customer fell back into the audience and was sent the same campaign
again on a separate date.

Critically, campaign 9101 is **standalone** (no parent, no children). For standalone campaigns,
**every send row is its own qualifying event**. C20's two sends count as 2, not 1. A naive
`COUNT(DISTINCT customer_id)` would give 6 for this campaign — but the correct count is 7.

---

## Final Verification

Running `python solution.py` prints the bridge above and asserts:

1. Python count == SQL result
2. Both == 22

Running the SQL directly:

```bash
sqlite3 data/comm_log.db < query.sql
# → 22
```
