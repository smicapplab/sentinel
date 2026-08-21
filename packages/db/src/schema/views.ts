import { pgView } from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';
import { tlogrcp } from './pos.js';
import { stores } from './tenants.js';

/**
 * Versioned View Contract: NBI Market Basket Analysis Source
 * Provides schema stability for Python data science workers.
 */
export const vNbiBasketStream = pgView('v_nbi_basket_stream').as((qb) =>
  qb
    .select({
      franchiseId: tlogrcp.franchiseId,
      repdate: tlogrcp.repdate,
      transact: tlogrcp.transact,
      branch: tlogrcp.branch,
      channel: tlogrcp.trandesc,
      prodcode: tlogrcp.prodcode,
      proddesc: tlogrcp.proddesc,
      prodprice: tlogrcp.prodprice,
      amount: tlogrcp.amount,
    })
    .from(tlogrcp)
    .where(sql`${tlogrcp.rowtype} = 'ITEM' AND ${tlogrcp.voidFlg} = 'N' AND ${tlogrcp.prodcode} IS NOT NULL`)
);

/**
 * Versioned View Contract: Discount & Void Fraud Anomaly Radar Source
 * Joins store demographic / hospital baseline clusters with transaction discount/void logs.
 */
export const vFraudRadarStream = pgView('v_fraud_radar_stream').as((qb) =>
  qb
    .select({
      franchiseId: tlogrcp.franchiseId,
      branch: tlogrcp.branch,
      cluster: stores.cluster,
      isHospitalOrRetirementArea: stores.isHospitalOrRetirementArea,
      cashierId: tlogrcp.cashierId,
      cashierName: tlogrcp.cashierName,
      repdate: tlogrcp.repdate,
      transact: tlogrcp.transact,
      rowtype: tlogrcp.rowtype,
      rsontype: tlogrcp.rsontype,
      voidFlg: tlogrcp.voidFlg,
      amount: tlogrcp.amount,
    })
    .from(tlogrcp)
    .innerJoin(stores, sql`${tlogrcp.branch} = ${stores.storeNumber}`)
    .where(sql`${tlogrcp.rsontype} IN ('SENIOR_CITIZEN', 'PWD') OR ${tlogrcp.voidFlg} = 'Y'`)
);
