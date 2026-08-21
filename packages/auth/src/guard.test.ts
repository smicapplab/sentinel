import { describe, it, expect } from 'vitest';
import { Hono } from 'hono';
import { requireRole, requireFranchiseScope } from './guard.js';

describe('Sentinel Auth Guards & Scope Enforcement', () => {
  it('allows request when user possesses required role', async () => {
    const app = new Hono();
    app.use('*', async (c, next) => {
      c.set('session' as any, {
        userId: '123',
        email: 'admin@pizzahut.com.ph',
        franchiseId: 'f-1',
        role: 'franchise_admin',
      });
      return next();
    });
    app.get('/admin-only', requireRole(['franchise_admin', 'super_admin']), (c) => c.json({ ok: true }));

    const res = await app.request('/admin-only');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
  });

  it('blocks request with HTTP 403 when user lacks required role', async () => {
    const app = new Hono();
    app.use('*', async (c, next) => {
      c.set('session' as any, {
        userId: '123',
        email: 'clerk@pizzahut.com.ph',
        franchiseId: 'f-1',
        role: 'store_manager',
      });
      return next();
    });
    app.get('/admin-only', requireRole(['franchise_admin']), (c) => c.json({ ok: true }));

    const res = await app.request('/admin-only');
    expect(res.status).toBe(403);
  });

  it('throws error when requireFranchiseScope is called without session', () => {
    const fakeContext = {
      get: () => null,
    } as any;

    expect(() => requireFranchiseScope(fakeContext)).toThrow('Security violation');
  });
});
