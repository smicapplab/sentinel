CREATE TABLE "franchises" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "franchises_code_unique" UNIQUE("code")
);
--> statement-breakpoint
CREATE TABLE "sessions" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" uuid NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "stores" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"store_number" text NOT NULL,
	"name" text NOT NULL,
	"cluster" text,
	"region" text,
	"is_hospital_or_retirement_area" boolean DEFAULT false NOT NULL,
	"hazard_polygons" jsonb,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "stores_store_number_unique" UNIQUE("store_number")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"email" text NOT NULL,
	"role" text NOT NULL,
	"full_name" text NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "pos_daily_store_sales" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"repdate" date NOT NULL,
	"branch" text NOT NULL,
	"gross_sales" numeric(14, 2) NOT NULL,
	"net_sales" numeric(14, 2) NOT NULL,
	"discounts" numeric(14, 2) NOT NULL,
	"transaction_count" integer NOT NULL,
	"void_count" integer NOT NULL,
	"void_amount" numeric(14, 2) NOT NULL,
	"guest_count" integer NOT NULL,
	"sc_guest_count" integer NOT NULL,
	"dinein_sales" numeric(14, 2) DEFAULT '0' NOT NULL,
	"delivery_sales" numeric(14, 2) DEFAULT '0' NOT NULL,
	"takeout_sales" numeric(14, 2) DEFAULT '0' NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "pos_hourly_sales_summary" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"repdate" date NOT NULL,
	"branch" text NOT NULL,
	"hour_of_day" integer NOT NULL,
	"daypart" text,
	"net_sales" numeric(14, 2) NOT NULL,
	"transaction_count" integer NOT NULL,
	"guest_count" integer NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "sku_margins" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"prodcode" text NOT NULL,
	"proddesc" text,
	"unit_cost" numeric(14, 4) NOT NULL,
	"unit_price" numeric(14, 4) NOT NULL,
	"gross_margin_peso" numeric(14, 4) NOT NULL,
	"margin_pct" numeric(6, 4) NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "tlogrcp" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"repdate" date NOT NULL,
	"branch" text NOT NULL,
	"transact" text NOT NULL,
	"lineid" smallint NOT NULL,
	"trandesc" text,
	"void_flg" char(1) DEFAULT 'N' NOT NULL,
	"trandate" date,
	"trantime" text,
	"receipt" text,
	"cashier_id" text,
	"cashier_name" text,
	"rowtype" text NOT NULL,
	"prodcode" text,
	"proddesc" text,
	"prodprice" numeric(12, 2),
	"amount" numeric(14, 2) NOT NULL,
	"diners" smallint,
	"scguestcnt" smallint,
	"rsontype" text,
	"apprvl_code" text,
	"voidtrans" text,
	"ingested_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "discount_void_anomalies" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"branch" text NOT NULL,
	"cashier_id" text NOT NULL,
	"cashier_name" text,
	"repdate" date NOT NULL,
	"anomaly_type" text NOT NULL,
	"z_score" numeric(8, 2) NOT NULL,
	"peer_cluster" text NOT NULL,
	"observed_value" numeric(12, 2) NOT NULL,
	"expected_cluster_mean" numeric(12, 2) NOT NULL,
	"estimated_peso_exposure" numeric(12, 2) NOT NULL,
	"is_reviewed" boolean DEFAULT false NOT NULL,
	"reviewed_by" text,
	"reviewed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "nbi_recommendations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"channel" text NOT NULL,
	"daypart" text NOT NULL,
	"antecedent_sku" text NOT NULL,
	"consequent_sku" text NOT NULL,
	"support" numeric(6, 4) NOT NULL,
	"confidence" numeric(6, 4) NOT NULL,
	"lift" numeric(8, 2) NOT NULL,
	"incremental_margin_peso" numeric(10, 2) NOT NULL,
	"rank_priority" integer NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"computed_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "stores" ADD CONSTRAINT "stores_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "pos_daily_store_sales" ADD CONSTRAINT "pos_daily_store_sales_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "pos_daily_store_sales" ADD CONSTRAINT "pos_daily_store_sales_branch_stores_store_number_fk" FOREIGN KEY ("branch") REFERENCES "public"."stores"("store_number") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "pos_hourly_sales_summary" ADD CONSTRAINT "pos_hourly_sales_summary_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "pos_hourly_sales_summary" ADD CONSTRAINT "pos_hourly_sales_summary_branch_stores_store_number_fk" FOREIGN KEY ("branch") REFERENCES "public"."stores"("store_number") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sku_margins" ADD CONSTRAINT "sku_margins_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tlogrcp" ADD CONSTRAINT "tlogrcp_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tlogrcp" ADD CONSTRAINT "tlogrcp_branch_stores_store_number_fk" FOREIGN KEY ("branch") REFERENCES "public"."stores"("store_number") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "discount_void_anomalies" ADD CONSTRAINT "discount_void_anomalies_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "discount_void_anomalies" ADD CONSTRAINT "discount_void_anomalies_branch_stores_store_number_fk" FOREIGN KEY ("branch") REFERENCES "public"."stores"("store_number") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "nbi_recommendations" ADD CONSTRAINT "nbi_recommendations_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "daily_sales_franchise_date_idx" ON "pos_daily_store_sales" USING btree ("franchise_id","repdate");--> statement-breakpoint
CREATE INDEX "daily_sales_branch_date_idx" ON "pos_daily_store_sales" USING btree ("branch","repdate");--> statement-breakpoint
CREATE INDEX "hourly_sales_franchise_date_idx" ON "pos_hourly_sales_summary" USING btree ("franchise_id","repdate");--> statement-breakpoint
CREATE INDEX "hourly_sales_branch_hour_idx" ON "pos_hourly_sales_summary" USING btree ("branch","repdate","hour_of_day");--> statement-breakpoint
CREATE INDEX "sku_margins_franchise_prodcode_idx" ON "sku_margins" USING btree ("franchise_id","prodcode");--> statement-breakpoint
CREATE INDEX "tlogrcp_branch_repdate_idx" ON "tlogrcp" USING btree ("branch","repdate");--> statement-breakpoint
CREATE INDEX "tlogrcp_franchise_repdate_idx" ON "tlogrcp" USING btree ("franchise_id","repdate");--> statement-breakpoint
CREATE INDEX "tlogrcp_transact_idx" ON "tlogrcp" USING btree ("transact");--> statement-breakpoint
CREATE INDEX "fraud_anomalies_franchise_idx" ON "discount_void_anomalies" USING btree ("franchise_id","repdate");--> statement-breakpoint
CREATE INDEX "fraud_anomalies_branch_idx" ON "discount_void_anomalies" USING btree ("branch","repdate");--> statement-breakpoint
CREATE INDEX "nbi_franchise_channel_idx" ON "nbi_recommendations" USING btree ("franchise_id","channel","daypart");--> statement-breakpoint
CREATE VIEW "public"."v_fraud_radar_stream" AS (select "tlogrcp"."franchise_id", "tlogrcp"."branch", "stores"."cluster", "stores"."is_hospital_or_retirement_area", "tlogrcp"."cashier_id", "tlogrcp"."cashier_name", "tlogrcp"."repdate", "tlogrcp"."transact", "tlogrcp"."rowtype", "tlogrcp"."rsontype", "tlogrcp"."void_flg", "tlogrcp"."amount" from "tlogrcp" inner join "stores" on "tlogrcp"."branch" = "stores"."store_number" where "tlogrcp"."rsontype" IN ('SENIOR_CITIZEN', 'PWD') OR "tlogrcp"."void_flg" = 'Y');--> statement-breakpoint
CREATE VIEW "public"."v_nbi_basket_stream" AS (select "franchise_id", "repdate", "transact", "branch", "trandesc", "prodcode", "proddesc", "prodprice", "amount" from "tlogrcp" where "tlogrcp"."rowtype" = 'ITEM' AND "tlogrcp"."void_flg" = 'N' AND "tlogrcp"."prodcode" IS NOT NULL);