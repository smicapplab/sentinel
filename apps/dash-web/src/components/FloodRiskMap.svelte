<script lang="ts">
  import { onMount } from 'svelte';
  import * as L from 'leaflet';
  import 'leaflet/dist/leaflet.css';

  type HazardData = {
    storeNumber: string;
    name: string;
    hazardPolygons: [number, number][][]; // GeoJSON-like array of [lng, lat]
    isHeavyRainfall: boolean;
    isSuspension: boolean;
  };

  let mapContainer = $state<HTMLElement>();
  let hazards = $state<HazardData[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    // We run the fetch once
    const fetchHazards = async () => {
      try {
        const res = await fetch('/api/v1/hazards');
        if (!res.ok) throw new Error('Failed to fetch hazards data');
        const json = await res.json();
        if (json.success) {
          hazards = json.data;
        } else {
          error = json.message || 'Error fetching hazards';
        }
      } catch (e: any) {
        error = e.message;
      } finally {
        loading = false;
      }
    };

    fetchHazards();
  });

  $effect(() => {
    if (!mapContainer || loading) return;
    
    // Initialize Leaflet map
    const map = L.map(mapContainer).setView([14.5995, 120.9842], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Plot hazards
    for (const h of hazards) {
      if (!h.hazardPolygons || h.hazardPolygons.length === 0) continue;

      let color = 'blue';
      if (h.isHeavyRainfall && h.isSuspension) {
        color = 'red';
      } else if (h.isHeavyRainfall) {
        color = 'orange'; // Amber
      }

      for (const polygon of h.hazardPolygons) {
        // Leaflet expects [lat, lng], but the data might be [lng, lat]. 
        // We assume [lng, lat] based on standard GeoJSON, so we reverse it.
        const latLngs = polygon.map(coord => [coord[1], coord[0]] as [number, number]);
        
        L.polygon(latLngs, {
          color,
          fillColor: color,
          fillOpacity: 0.5
        })
        .bindPopup(`<b>${h.name}</b><br>Rainfall: ${h.isHeavyRainfall}<br>Suspension: ${h.isSuspension}`)
        .addTo(map);
      }
    }

    return () => {
      map.remove();
    };
  });
</script>

<div class="flood-map-wrapper">
  {#if loading}
    <p>Loading map data...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else}
    <div bind:this={mapContainer} class="map"></div>
  {/if}
</div>

<style>
  .flood-map-wrapper {
    width: 100%;
    height: 100%;
    min-height: 400px;
  }
  .map {
    width: 100%;
    height: 400px;
    border-radius: 8px;
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  }
  .error {
    color: red;
  }
</style>
