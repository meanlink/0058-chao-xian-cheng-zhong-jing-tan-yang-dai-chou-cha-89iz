-- 清运单更正：同一轮次保留多版清运单，每版固定当时采用的样袋重量依据。
ALTER TABLE coast_haul DROP CONSTRAINT coast_haul_pkey;
ALTER TABLE coast_haul ADD COLUMN version int NOT NULL DEFAULT 1;
ALTER TABLE coast_haul ADD COLUMN correction_id bigint;
ALTER TABLE coast_haul ADD COLUMN basis jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE coast_haul ADD PRIMARY KEY (round, version);

-- 历史清运单补全取证依据，与出单时见证通过的样袋保持一致。
UPDATE coast_haul h SET basis = sub.basis
FROM (
  SELECT p.round, jsonb_agg(jsonb_build_object(
           'segment', w.segment, 'bag', w.bag, 'accepted_kg', w.accepted_kg,
           'source', w.source, 'witness', w.witness, 'note', w.note
         ) ORDER BY w.segment, w.bag) AS basis
  FROM coast_witness w
  JOIN coast_segments p ON p.code = w.segment
  GROUP BY p.round
) sub
WHERE h.round = sub.round;

ALTER TABLE coast_rounds ADD COLUMN current_version int NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS coast_haul_correction(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 round text NOT NULL REFERENCES coast_rounds(code),
 base_version int NOT NULL CHECK (base_version >= 1),
 reason text NOT NULL,
 evidence jsonb NOT NULL,
 created_by text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 status text NOT NULL DEFAULT 'queued'
   CHECK (status IN ('queued','succeeded','stale')),
 UNIQUE(round, id)
);

ALTER TABLE coast_haul
  ADD CONSTRAINT coast_haul_correction_fk
  FOREIGN KEY (round, correction_id) REFERENCES coast_haul_correction(round, id);

-- 并发兜底：主键 (round, version) 天然保证每个轮次的每个版本只有一张清运单；
-- 重算事务在 coast_rounds 上的表级锁串行，配合版本检查，后到者只会被判为 stale。
