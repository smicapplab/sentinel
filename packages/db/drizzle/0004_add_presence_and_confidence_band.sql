-- Mirrors birdseye migration 0008. presence_state partitions the whitespace
-- output (ABSENT / PRESENT / UNKNOWN) instead of weighting it; the band columns
-- ensure a score is never persisted without its uncertainty.
--
-- Also folds in the DDL formerly applied by hand via the untracked
-- alter_sentinel.sql at the workspace root.

ALTER TABLE "whitespace_opportunities"
  ADD COLUMN IF NOT EXISTS "income_data_provenance" text NOT NULL DEFAULT 'MODEL_ESTIMATE';
--> statement-breakpoint
ALTER TABLE "whitespace_opportunities"
  ADD COLUMN IF NOT EXISTS "presence_state" text NOT NULL DEFAULT 'UNKNOWN';
--> statement-breakpoint
ALTER TABLE "whitespace_opportunities"
  ADD COLUMN IF NOT EXISTS "coverage_index" real NOT NULL DEFAULT 0;
--> statement-breakpoint
ALTER TABLE "whitespace_opportunities"
  ADD COLUMN IF NOT EXISTS "confidence_band_halfwidth" real NOT NULL DEFAULT 25;
--> statement-breakpoint
ALTER TABLE "whitespace_opportunities"
  ADD COLUMN IF NOT EXISTS "band_method" text NOT NULL DEFAULT 'COVERAGE_HEURISTIC';
--> statement-breakpoint

-- Consolidates the hand-applied fix_sentinel_*.sql patches.
UPDATE "whitespace_opportunities" SET "lgu_code" = 'PH-074610000' WHERE "lgu_code" = 'PH-074600000';
--> statement-breakpoint
UPDATE "whitespace_opportunities" SET "lgu_code" = 'PH-050506000' WHERE "lgu_code" = 'PH-050500000';
--> statement-breakpoint
UPDATE "whitespace_opportunities" SET "lgu_code" = 'PH-175316000' WHERE "lgu_code" = 'PH-175300000';
--> statement-breakpoint
UPDATE "whitespace_opportunities" SET "lgu_code" = 'PH-112319000' WHERE "lgu_code" = 'PH-112300000';
--> statement-breakpoint
UPDATE "whitespace_opportunities"
   SET "income_data_provenance" = 'PSA_ACTUAL'
 WHERE "lgu_code" IN ('PH-175316000','PH-126303000','PH-160202000','PH-045624000','PH-083747000')
   AND "income_data_provenance" <> 'PSA_ACTUAL';
--> statement-breakpoint
UPDATE "whitespace_opportunities"
   SET "lgu_name" = 'Kalibo (Municipality)'
 WHERE "lgu_code" = 'PH-060408000' AND "lgu_name" <> 'Kalibo (Municipality)';
