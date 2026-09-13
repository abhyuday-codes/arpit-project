-- target_base: distinct customers reached per underlying communication (chain), Oct 2026, merchant 501
-- A retry chain (A -> B -> C) counts as ONE communication; a customer reached at any step counts once.
-- Campaigns with creation_status = 'approval_awaiting' are excluded even if messages were delivered.

WITH RECURSIVE chain AS (
    -- Base: campaigns with no parent are their own root
    SELECT id, id AS root_id
    FROM campaign
    WHERE parent_id IS NULL

    UNION ALL

    -- Recursive: children inherit root from their parent
    SELECT c.id, chain.root_id
    FROM campaign c
    JOIN chain ON c.parent_id = chain.id
)
SELECT COUNT(DISTINCT chain.root_id || '|' || cl.customer_id) AS target_base
FROM chain
JOIN campaign cam ON cam.id = chain.id
JOIN communication_log cl ON cl.communication_id = chain.id
WHERE cam.creation_status IN ('approved', 'aborted', 'resumed', 'stopped')
  AND cam.processing_status = 'processed'
  AND cl.merchant_id = 501
  AND cl.communication_type = '2'
  AND cl.sent_time >= '2026-10-01 00:00:00'
  AND cl.sent_time <  '2026-11-01 00:00:00';
