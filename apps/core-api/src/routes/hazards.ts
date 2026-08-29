import { Hono } from 'hono';
import { db } from '@sentinel/db';
import { stores } from '@sentinel/db/schema';
import { requireFranchiseScope } from '@sentinel/auth';
import { eq, and } from 'drizzle-orm';

export const hazardsRouter = new Hono();

// Note: In-memory cache is no longer practical to share across tenants
// without namespacing by franchiseId.
const hazardsCache = new Map<string, { data: any, timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

hazardsRouter.get('/', async (c) => {
  const franchiseId = requireFranchiseScope(c);
  const now = Date.now();
  
  const cached = hazardsCache.get(franchiseId);
  if (cached && now - cached.timestamp < CACHE_TTL) {
    return c.json({ success: true, data: cached.data });
  }

  try {
    // 1. Fetch from Birdseye internal API
    const birdseyeUrl = process.env.BIRDSEYE_URL || 'http://localhost:5173';
    const secret = process.env.INTERNAL_API_SECRET || '';
    
    const response = await fetch(`${birdseyeUrl}/api/internal/weather/active-hazards?companyId=${franchiseId}`, {
      headers: {
        'x-internal-secret': secret
      }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch from Birdseye: ${response.statusText}`);
    }

    const birdseyeData = await response.json();
    const weatherData = birdseyeData.data.weather || [];
    const eventsData = birdseyeData.data.events || [];

    // 2. Fetch local stores with hazard polygons for this franchise
    const storeRecords = await db.select({
      storeNumber: stores.storeNumber,
      name: stores.name,
      hazardPolygons: stores.hazardPolygons
    })
    .from(stores)
    .where(eq(stores.franchiseId, franchiseId));

    // 3. Join data
    const joinedData = storeRecords.map(store => {
      const storeWeather = weatherData.find((w: any) => w.storeNo === store.storeNumber || w.storeNo === 'global');
      const storeEvent = eventsData.find((e: any) => e.storeNo === store.storeNumber || e.storeNo === 'all');

      return {
        ...store,
        isHeavyRainfall: storeWeather?.isHeavyRainfall || false,
        isSuspension: storeEvent?.isSuspension || false
      };
    });

    hazardsCache.set(franchiseId, { data: joinedData, timestamp: now });

    return c.json({ success: true, data: joinedData });
  } catch (error) {
    console.error('Error in /api/v1/hazards:', error);
    return c.json({ success: false, message: 'Internal Server Error' }, 500);
  }
});
