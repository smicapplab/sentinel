import { db } from './client.js';
import { franchises, stores } from './schema/index.js';
import { eq } from 'drizzle-orm';

async function seed() {
  console.log('Seeding Sentinel database...');
  
  const franchiseCode = 'SAMPLE_FRANCHISE';
  let franchise = await db.query.franchises.findFirst({
    where: eq(franchises.code, franchiseCode)
  });

  if (!franchise) {
    const [inserted] = await db.insert(franchises).values({
      code: franchiseCode,
      name: 'Sample Franchise',
    }).returning();
    franchise = inserted;
  }

  // Define some realistic polygon arrays (longitude, latitude for Leaflet/GeoJSON)
  const storeData = [
    {
      storeNumber: 'STORE_001',
      name: 'Manila Bay Branch',
      franchiseId: franchise.id,
      hazardPolygons: [
        [[120.98, 14.58], [120.99, 14.58], [120.99, 14.59], [120.98, 14.59]]
      ]
    },
    {
      storeNumber: 'STORE_002',
      name: 'Makati Branch',
      franchiseId: franchise.id,
      hazardPolygons: [
        [[121.02, 14.55], [121.03, 14.55], [121.03, 14.56], [121.02, 14.56]]
      ]
    }
  ];

  for (const data of storeData) {
    await db.insert(stores).values(data).onConflictDoUpdate({
      target: stores.storeNumber,
      set: {
        name: data.name,
        hazardPolygons: data.hazardPolygons
      }
    });
  }
  
  console.log('Database seeded.');
  process.exit(0);
}

seed().catch(console.error);
