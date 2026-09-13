-- target_base for merchant 501, October 2026, campaign sends
--
-- Two counting rules:
--   Retry chain  (campaign has a parent OR has children):
--       COUNT DISTINCT (chain_root, customer) — retries of the same customer count once
--   Standalone campaign (no parent, no children):
--       COUNT every send row — each re-send is its own qualifying event

WITH RECURSIVE chain AS (
    -- Base: root campaigns (no parent)
    SELECT id, id AS root_id
    FROM campaign
    WHERE parent_id IS NULL

    UNION ALL

    -- Recursive: children inherit root from their parent
    SELECT c.id, chain.root_id
    FROM campaign c
    JOIN chain ON c.parent_id = chain.id
),
in_chain AS (
    -- A campaign is "in a chain" if it has a parent OR has at least one child
    SELECT id FROM campaign WHERE parent_id IS NOT NULL
    UNION
    SELECT DISTINCT parent_id FROM campaign WHERE parent_id IS NOT NULL
),
eligible AS (
    SELECT
        chain.id,
        chain.root_id,
        CASE WHEN ic.id IS NULL THEN 1 ELSE 0 END AS is_standalone
    FROM chain
    JOIN campaign cam ON cam.id = chain.id
    LEFT JOIN in_chain ic ON ic.id = chain.id
    WHERE cam.creation_status IN ('approved', 'aborted', 'resumed', 'stopped')
      AND cam.processing_status = 'processed'
),
log_rows AS (
    SELECT e.root_id, e.is_standalone, cl.customer_id, cl.id AS log_id
    FROM eligible e
    JOIN communication_log cl ON cl.communication_id = e.id
    WHERE cl.merchant_id = 501
      AND cl.communication_type = '2'
      AND cl.sent_time >= '2026-10-01 00:00:00'
      AND cl.sent_time <  '2026-11-01 00:00:00'
)
SELECT
    (SELECT COUNT(DISTINCT root_id || '|' || customer_id) FROM log_rows WHERE is_standalone = 0)
    +
    (SELECT COUNT(*) FROM log_rows WHERE is_standalone = 1)
    AS target_base;
