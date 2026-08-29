CREATE TABLE "pos_dead_letters" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"franchise_id" uuid NOT NULL,
	"payload" jsonb NOT NULL,
	"error_reason" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "users" ADD COLUMN "store_id" uuid;--> statement-breakpoint
ALTER TABLE "pos_dead_letters" ADD CONSTRAINT "pos_dead_letters_franchise_id_franchises_id_fk" FOREIGN KEY ("franchise_id") REFERENCES "public"."franchises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_store_id_stores_id_fk" FOREIGN KEY ("store_id") REFERENCES "public"."stores"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tlogrcp" ADD CONSTRAINT "tlogrcp_idempotency_idx" UNIQUE("franchise_id","branch","transact","lineid");