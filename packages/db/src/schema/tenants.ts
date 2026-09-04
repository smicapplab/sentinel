import { pgTable, text, timestamp, uuid, boolean, jsonb } from 'drizzle-orm/pg-core';

export const franchises = pgTable('franchises', {
  id: uuid('id').defaultRandom().primaryKey(),
  code: text('code').notNull().unique(),
  name: text('name').notNull(),
  isActive: boolean('is_active').default(true).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const stores = pgTable('stores', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  storeNumber: text('store_number').notNull().unique(),
  name: text('name').notNull(),
  city: text('city'),
  lguCode: text('lgu_code'),
  cluster: text('cluster'),
  region: text('region'),
  isHospitalOrRetirementArea: boolean('is_hospital_or_retirement_area').default(false).notNull(),
  hazardPolygons: jsonb('hazard_polygons'),
  isActive: boolean('is_active').default(true).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const users = pgTable('users', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').references(() => franchises.id).notNull(),
  email: text('email').notNull().unique(),
  role: text('role').notNull(), // 'super_admin' | 'franchise_admin' | 'store_manager' | 'auditor'
  storeId: uuid('store_id').references(() => stores.id),
  fullName: text('full_name').notNull(),
  isActive: boolean('is_active').default(true).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const sessions = pgTable('sessions', {
  id: text('id').primaryKey(), // The opaque token
  userId: uuid('user_id').references(() => users.id).notNull(),
  expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});
