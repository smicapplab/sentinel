<script lang="ts">
  import { onMount } from 'svelte';
  import { TrendingUp, ShieldCheck, DollarSign } from 'lucide-svelte';

  let healthStatus = $state('Checking...');

  onMount(async () => {
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        healthStatus = 'Online (Hono Core API)';
      }
    } catch {
      healthStatus = 'Offline';
    }
  });
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="h-8 w-8 rounded bg-red-600 flex items-center justify-center font-bold text-white tracking-wider">
        S
      </div>
      <div>
        <h1 class="text-lg font-semibold tracking-tight">Sentinel Operational Intelligence</h1>
        <p class="text-xs text-slate-400">300-Store Enterprise Platform — Pizza Hut (PPI)</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        System: {healthStatus}
      </span>
    </div>
  </header>

  <!-- Main Content -->
  <main class="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
    <!-- Top Levers Overview -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="p-5 rounded-lg border border-slate-800 bg-slate-900/40 space-y-2">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-sm font-medium">Next-Best-Item (AOV)</span>
          <TrendingUp class="w-4 h-4 text-emerald-400" />
        </div>
        <div class="text-2xl font-bold text-slate-50">+₱25 Target AOV</div>
        <p class="text-xs text-slate-400">Projected ₱375M gross lift across 15M annual transactions.</p>
      </div>

      <div class="p-5 rounded-lg border border-slate-800 bg-slate-900/40 space-y-2">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-sm font-medium">Discount / Void Fraud Radar</span>
          <ShieldCheck class="w-4 h-4 text-amber-400" />
        </div>
        <div class="text-2xl font-bold text-slate-50">₱60M Target Recovery</div>
        <p class="text-xs text-slate-400">Statistical outlier detection across hospital & store clusters.</p>
      </div>

      <div class="p-5 rounded-lg border border-slate-800 bg-slate-900/40 space-y-2">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-sm font-medium">Araneta Event & Weather Surge</span>
          <DollarSign class="w-4 h-4 text-blue-400" />
        </div>
        <div class="text-2xl font-bold text-slate-50">Pre-Event Demand Trigger</div>
        <p class="text-xs text-slate-400">Automated prep & localized aggregator boost for 25k event nights.</p>
      </div>
    </div>

    <!-- Active POC Modules -->
    <div class="p-6 rounded-lg border border-slate-800 bg-slate-900/20 space-y-4">
      <h2 class="text-base font-semibold text-slate-200">Active Proof-of-Concept Candidate Modules</h2>
      <div class="text-sm text-slate-400 space-y-2">
        <p>Sentinel core services and Drizzle database schemas are initialized.</p>
        <p>Data science worker located in <code class="text-emerald-400">workers/analytics-engine</code> runs Polars-based market basket association rules and Z-score outlier detection models.</p>
      </div>
    </div>
  </main>
</div>
