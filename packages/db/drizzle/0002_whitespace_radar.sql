ALTER TABLE "stores" ADD COLUMN IF NOT EXISTS "city" text;--> statement-breakpoint
ALTER TABLE "stores" ADD COLUMN IF NOT EXISTS "lgu_code" text;--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "whitespace_opportunities" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"company_id" text NOT NULL,
	"lgu_code" text NOT NULL,
	"lgu_name" text NOT NULL,
	"province" text NOT NULL,
	"region" text NOT NULL,
	"income_classification" text NOT NULL,
	"socio_economic_tier" text NOT NULL,
	"population" integer NOT NULL,
	"avg_family_income_annual" integer DEFAULT 0 NOT NULL,
	"median_family_income_annual" integer NOT NULL,
	"demand_gap_score" numeric(5, 2) NOT NULL,
	"predicted_capture_score" numeric(5, 2) NOT NULL,
	"opportunity_score" integer NOT NULL,
	"brand_fit" text DEFAULT 'Pizza Hut' NOT NULL,
	"has_existing_store" boolean DEFAULT false NOT NULL,
	"competitor_counts" jsonb DEFAULT '{"pizza": 0, "fastfood": 0, "anchors": 0}'::jsonb NOT NULL,
	"flood_risk_level" text DEFAULT 'LOW' NOT NULL,
	"golden_polygon_geojson" jsonb,
	"layers_geojson" jsonb,
	"summary_rationale" text,
	"data_source" text DEFAULT 'ESTIMATED_BASELINE' NOT NULL,
	"is_calibrated_estimate" boolean DEFAULT true NOT NULL,
	"computed_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "uq_whitespace_opportunities_comp_lgu" UNIQUE("company_id","lgu_code")
);
