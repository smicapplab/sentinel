import { pgTable, text, timestamp, uuid, date, numeric, integer, smallint, char, index, jsonb, unique } from 'drizzle-orm/pg-core';
import { stores, franchises } from './tenants.js';

// Granular raw POS line items stream (TLOGRCP)
export const tlogrcp = pgTable('tlogrcp', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  repdate: date('repdate').notNull(),
  branch: text('branch').references(() => stores.storeNumber).notNull(),
  transact: text('transact').notNull(),
  lineid: smallint('lineid').notNull(),
  trandesc: text('trandesc'), // 'Grab', 'Dine-In', 'Kiosk 1', 'Slice'
  voidFlg: char('void_flg', { length: 1 }).default('N').notNull(),
  trandate: date('trandate'),
  trantime: text('trantime'),
  receipt: text('receipt'),
  cashierId: text('cashier_id'),
  cashierName: text('cashier_name'),
  rowtype: text('rowtype').notNull(), // 'ITEM', 'DISC', 'TAX', 'PAY'
  prodcode: text('prodcode'),
  proddesc: text('proddesc'),
  prodprice: numeric('prodprice', { precision: 12, scale: 2 }),
  amount: numeric('amount', { precision: 14, scale: 2 }).notNull(),
  diners: smallint('diners'),
  scguestcnt: smallint('scguestcnt'),
  rsontype: text('rsontype'), // 'SENIOR_CITIZEN', 'PWD', 'PROMO'
  apprvlCode: text('apprvl_code'),
  voidtrans: text('voidtrans'),
  ingestedAt: timestamp('ingested_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index('tlogrcp_branch_repdate_idx').on(table.branch, table.repdate),
  index('tlogrcp_franchise_repdate_idx').on(table.franchiseId, table.repdate),
  index('tlogrcp_transact_idx').on(table.transact),
  unique('tlogrcp_idempotency_idx').on(table.franchiseId, table.branch, table.transact, table.lineid),
]);

// Dead-letter queue for failed POS ingestions
export const posDeadLetters = pgTable('pos_dead_letters', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  payload: jsonb('payload').notNull(),
  errorReason: text('error_reason').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

// Pre-aggregated Daily Store Sales Rollup
export const posDailyStoreSales = pgTable('pos_daily_store_sales', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  repdate: date('repdate').notNull(),
  branch: text('branch').references(() => stores.storeNumber).notNull(),
  grossSales: numeric('gross_sales', { precision: 14, scale: 2 }).notNull(),
  netSales: numeric('net_sales', { precision: 14, scale: 2 }).notNull(),
  discounts: numeric('discounts', { precision: 14, scale: 2 }).notNull(),
  transactionCount: integer('transaction_count').notNull(),
  voidCount: integer('void_count').notNull(),
  voidAmount: numeric('void_amount', { precision: 14, scale: 2 }).notNull(),
  guestCount: integer('guest_count').notNull(),
  scGuestCount: integer('sc_guest_count').notNull(),
  dineinSales: numeric('dinein_sales', { precision: 14, scale: 2 }).default('0').notNull(),
  deliverySales: numeric('delivery_sales', { precision: 14, scale: 2 }).default('0').notNull(),
  takeoutSales: numeric('takeout_sales', { precision: 14, scale: 2 }).default('0').notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index('daily_sales_franchise_date_idx').on(table.franchiseId, table.repdate),
  index('daily_sales_branch_date_idx').on(table.branch, table.repdate),
]);

// Pre-aggregated Hourly Sales Summary
export const posHourlySalesSummary = pgTable('pos_hourly_sales_summary', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  repdate: date('repdate').notNull(),
  branch: text('branch').references(() => stores.storeNumber).notNull(),
  hourOfDay: integer('hour_of_day').notNull(), // 0-23
  daypart: text('daypart'), // 'LUNCH', 'MERIENDA', 'DINNER', 'LATE_NIGHT'
  netSales: numeric('net_sales', { precision: 14, scale: 2 }).notNull(),
  transactionCount: integer('transaction_count').notNull(),
  guestCount: integer('guest_count').notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index('hourly_sales_franchise_date_idx').on(table.franchiseId, table.repdate),
  index('hourly_sales_branch_hour_idx').on(table.branch, table.repdate, table.hourOfDay),
]);

export const skuMargins = pgTable('sku_margins', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  prodcode: text('prodcode').notNull(),
  proddesc: text('proddesc'),
  unitCost: numeric('unit_cost', { precision: 14, scale: 4 }).notNull(),
  unitPrice: numeric('unit_price', { precision: 14, scale: 4 }).notNull(),
  grossMarginPeso: numeric('gross_margin_peso', { precision: 14, scale: 4 }).notNull(),
  marginPct: numeric('margin_pct', { precision: 6, scale: 4 }).notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index('sku_margins_franchise_prodcode_idx').on(table.franchiseId, table.prodcode),
]);
