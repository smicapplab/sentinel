import { describe, it, expect, vi, beforeEach } from 'vitest';
import { hazardsRouter } from './hazards.js';
import { Hono } from 'hono';

// Mock DB
vi.mock('@sentinel/db', () => {
  const queryBuilder = {
    from: vi.fn().mockReturnThis(),
    where: vi.fn().mockResolvedValue([
      { storeNumber: 'STORE_001', name: 'Store 1', hazardPolygons: [[ [1, 1], [2, 2] ]] }
    ])
  };
  return {
    db: {
      select: vi.fn().mockReturnValue(queryBuilder),
    },
    eq: vi.fn(),
    and: vi.fn(),
  };
});
vi.mock('@sentinel/db/schema', () => ({
  stores: {
    storeNumber: 'storeNumber',
    name: 'name',
    hazardPolygons: 'hazardPolygons',
    franchiseId: 'franchiseId'
  }
}));

vi.mock('@sentinel/auth', () => ({
  requireFranchiseScope: vi.fn().mockReturnValue('test-franchise')
}));

describe('GET /api/v1/hazards', () => {
  let app: Hono;

  beforeEach(() => {
    app = new Hono();
    app.route('/api/v1/hazards', hazardsRouter);
    // Reset fetch mock
    vi.stubGlobal('fetch', vi.fn(async () => {
      return {
        ok: true,
        json: async () => ({
          success: true,
          data: {
            weather: [{ storeNumber: 'STORE_001', isHeavyRainfall: true }],
            events: [{ storeNumber: 'STORE_001', isSuspension: true }],
            pagasaAlerts: [{ storeNumber: 'STORE_001', maxSignalLevel: 3, cycloneNames: ['PILANDOK'], rainfallWarningLevels: ['RED'] }]
          }
        })
      };
    }));
  });

  it('should fetch hazards from Birdseye and join with local DB including PAGASA alerts', async () => {
    const res = await app.request('/api/v1/hazards');
    expect(res.status).toBe(200);
    const body = await res.json();
    
    expect(body.success).toBe(true);
    expect(body.data.length).toBe(1);
    expect(body.data[0].storeNumber).toBe('STORE_001');
    expect(body.data[0].hazardPolygons).toBeDefined();
    expect(body.data[0].isHeavyRainfall).toBe(true);
    expect(body.data[0].pagasaAlert).toEqual({
      maxSignalLevel: 3,
      cycloneNames: ['PILANDOK'],
      rainfallWarningLevels: ['RED']
    });
  });
});
