import { pgTable, text, timestamp, uuid, date, numeric, integer, boolean, index } from 'drizzle-orm/pg-core';
import { stores, franchises } from './tenants.js';

// Project #7: Discount & Void Fraud Anomaly Radar Output Table
export const discountVoidAnomalies = pgTable('discount_void_anomalies', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  branch: text('branch').references(() => stores.storeNumber).notNull(),
  cashierId: text('cashier_id').notNull(),
  cashierName: text('cashier_name'),
  repdate: date('repdate').notNull(),
  anomalyType: text('anomaly_type').notNull(), // 'HIGH_SC_PWD_DISCOUNT' | 'HIGH_TRANSACTION_VOID' | 'UNAUTHORIZED_OVERRIDE'
  zScore: numeric('z_score', { precision: 8, scale: 2 }).notNull(),
  peerCluster: text('peer_cluster').notNull(), // Demographic / Hospital baseline
  observedValue: numeric('observed_value', { precision: 12, scale: 2 }).notNull(),
  expectedClusterMean: numeric('expected_cluster_mean', { precision: 12, scale: 2 }).notNull(),
  estimatedPesoExposure: numeric('estimated_peso_exposure', { precision: 12, scale: 2 }).notNull(),
  isReviewed: boolean('is_reviewed').default(false).notNull(),
  reviewedBy: text('reviewed_by'),
  reviewedAt: timestamp('reviewed_at', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index('fraud_anomalies_franchise_idx').on(table.franchiseId, table.repdate),
  index('fraud_anomalies_branch_idx').on(table.branch, table.repdate),
]);

// Project #4: Next-Best-Item (NBI) Recommendation Output Table
export const nbiRecommendations = pgTable('nbi_recommendations', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  channel: text('channel').notNull(), // 'DINE_IN' | 'KIOSK' | 'WEB' | 'AGGREGATOR'
  daypart: text('daypart').notNull(), // 'LUNCH' | 'MERIENDA' | 'DINNER' | 'ALL'
  antecedentSku: text('antecedent_sku').notNull(), // Anchor SKU (e.g. 'PB FAVEPAIR 7')
  consequentSku: text('consequent_sku').notNull(), // Recommended Pairing (e.g. 'GARLIC BREAD')
  support: numeric('support', { precision: 6, scale: 4 }).notNull(),
  confidence: numeric('confidence', { precision: 6, scale: 4 }).notNull(),
  lift: numeric('lift', { precision: 8, scale: 2 }).notNull(),
  incrementalMarginPeso: numeric('incremental_margin_peso', { precision: 10, scale: 2 }).notNull(),
  rankPriority: integer('rank_priority').notNull(),
  isActive: boolean('is_active').default(true).notNull(),
  computedAt: timestamp('computed_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index('nbi_franchise_channel_idx').on(table.franchiseId, table.channel, table.daypart),
]);
