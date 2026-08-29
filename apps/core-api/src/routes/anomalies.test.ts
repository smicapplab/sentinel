import { describe, it, expect, vi, beforeEach } from 'vitest';
import { anomaliesRouter } from './anomalies.js';
import { Hono } from 'hono';

// Mock DB
const mockRows = [
  {
    id: 'anom-1',
    franchiseId: 'f-1',
    branch: 'STORE_001',
    cashierName: 'Juan Dela Cruz',
    zScore: 3.5,
  },
  {
    id: 'anom-2',
    franchiseId: 'f-1',
    branch: 'STORE_002',
    cashierName: 'Maria Santos',
    zScore: 2.1,
  },
];

vi.mock('@sentinel/db', () => {
  const queryBuilder = {
    from: vi.fn().mockReturnThis(),
    where: vi.fn().mockReturnThis(),
    orderBy: vi.fn().mockReturnThis(),
    limit: vi.fn().mockImplementation(() => Promise.resolve(mockRows)),
  };
  return {
    db: {
      select: vi.fn().mockReturnValue(queryBuilder),
    },
    discountVoidAnomalies: {
      franchiseId: 'franchiseId',
      branch: 'branch',
      zScore: 'zScore',
    },
    nbiRecommendations: {
      franchiseId: 'franchiseId',
      channel: 'channel',
      incrementalMarginPeso: 'incrementalMarginPeso',
    },
    withFranchiseScope: vi.fn((col, val, additional) => additional || true),
  };
});

vi.mock('@sentinel/auth', () => ({
  requireFranchiseScope: vi.fn().mockReturnValue('f-1'),
}));

describe('anomaliesRouter /fraud-radar', () => {
  it('redacts cashierName for unprivileged store_manager role (SN-05) and forces branch scope (SN-02)', async () => {
    const app = new Hono();
    app.use('*', (c, next) => {
      c.set('session', {
        userId: 'u-1',
        email: 'manager@araneta.com.ph',
        franchiseId: 'f-1',
        storeNumber: 'STORE_001',
        role: 'store_manager',
      });
      return next();
    });
    app.route('/api/v1/anomalies', anomaliesRouter);

    // Call without branch - should succeed and be scoped to STORE_001
    const res = await app.request('/api/v1/anomalies/fraud-radar');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.data).toBeDefined();
    // cashierName must be masked
    expect(body.data[0].cashierName).toBe('Cashier ****');
  });

  it('rejects store_manager without assigned storeNumber with 403 (SN-02)', async () => {
    const app = new Hono();
    app.use('*', (c, next) => {
      c.set('session', {
        userId: 'u-2',
        email: 'unassigned@araneta.com.ph',
        franchiseId: 'f-1',
        storeNumber: null,
        role: 'store_manager',
      });
      return next();
    });
    app.route('/api/v1/anomalies', anomaliesRouter);

    const res = await app.request('/api/v1/anomalies/fraud-radar');
    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.error).toContain('Store Manager lacks store assignment');
  });

  it('reveals full cashierName for privileged auditor or franchise_admin role (SN-05)', async () => {
    const app = new Hono();
    app.use('*', (c, next) => {
      c.set('session', {
        userId: 'u-3',
        email: 'auditor@araneta.com.ph',
        franchiseId: 'f-1',
        storeNumber: null,
        role: 'auditor',
      });
      return next();
    });
    app.route('/api/v1/anomalies', anomaliesRouter);

    const res = await app.request('/api/v1/anomalies/fraud-radar');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.data[0].cashierName).toBe('Juan Dela Cruz');
  });
});
