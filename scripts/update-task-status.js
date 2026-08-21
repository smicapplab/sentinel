#!/usr/bin/env node

/**
 * Sentinel Task Status Update tool
 * Updates the stage (status) and adds comments to synced Stratos tasks during execution.
 */

const fs = require('fs');
const path = require('path');

// Load environment variables from .env if present
let env = {
  STRATOS_API_URL: 'http://localhost:5173/api/v1',
  STRATOS_API_TOKEN: ''
};

const dotEnvPath = path.resolve(process.cwd(), '.env');
const parentDotEnvPath = path.resolve(process.cwd(), '..', '.env');
const searchPaths = [dotEnvPath, parentDotEnvPath];

for (const envPath of searchPaths) {
  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, 'utf8');
    content.split('\n').forEach(line => {
      const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        const key = match[1];
        let value = match[2] || '';
        if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
        if (value.startsWith("'") && value.endsWith("'")) value = value.slice(1, -1);
        env[key] = value;
      }
    });
    break;
  }
}

env.STRATOS_API_URL = process.env.STRATOS_API_URL || env.STRATOS_API_URL;
env.STRATOS_API_TOKEN = process.env.STRATOS_API_TOKEN || env.STRATOS_API_TOKEN;

if (!env.STRATOS_API_TOKEN) {
  console.error('[ERROR] STRATOS_API_TOKEN is not set in environment or .env file.');
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length < 3) {
  console.error('[ERROR] Missing required arguments.');
  console.error('Usage: node update-task-status.js <path_to_plan_file> <story_title_or_epic> <status> [comment_content]');
  console.error('Example: node update-task-status.js superpowers/plan/04-inventory-plan.md "1. Backend: Realtime Sync" completed "Tests passed successfully"');
  process.exit(1);
}

const planFilePath = path.resolve(process.cwd(), args[0]);
const targetTitle = args[1];
const targetStatus = args[2].toLowerCase(); // 'in-progress' or 'completed'
const commentContent = args[3] || '';

const mappingFilePath = planFilePath.replace(/\.md$/, '.sync.json');
if (!fs.existsSync(mappingFilePath)) {
  console.error(`[ERROR] Sync mapping file not found at ${mappingFilePath}`);
  console.error('Please run sync-plan.js on the plan file first to synchronize it with Stratos.');
  process.exit(1);
}

const mapping = JSON.parse(fs.readFileSync(mappingFilePath, 'utf8'));

// Resolve taskId
let taskId = '';
if (targetTitle.toLowerCase() === 'epic') {
  taskId = mapping.epicId;
} else {
  // Direct match or partial match on story titles
  const matchingKeys = Object.keys(mapping.stories).filter(k =>
    k.toLowerCase().includes(targetTitle.toLowerCase())
  );

  if (matchingKeys.length === 0) {
    console.error(`[ERROR] No matching story found in sync mapping for query: "${targetTitle}"`);
    console.error(`Available stories:`, Object.keys(mapping.stories));
    process.exit(1);
  }

  if (matchingKeys.length > 1) {
    console.warn(`[WARN] Multiple matching stories found:`, matchingKeys);
    console.log(`[INFO] Using first match: "${matchingKeys[0]}"`);
  }

  taskId = mapping.stories[matchingKeys[0]];
}

if (!taskId) {
  console.error('[ERROR] Task ID could not be resolved from sync mapping.');
  process.exit(1);
}

async function main() {
  try {
    // 1. Fetch board stages to resolve the target status to a stageId
    const response = await fetch(`${env.STRATOS_API_URL}/boards`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch boards from Stratos: ${response.status} ${response.statusText}`);
    }

    const boards = await response.json();
    const board = boards.find(b => b.id === mapping.boardId) || boards[0];
    if (!board || !board.stages || board.stages.length === 0) {
      throw new Error(`Stratos board not found or has no stages.`);
    }

    let stageId = '';
    if (targetStatus === 'in-progress' || targetStatus === 'doing' || targetStatus === 'active') {
      const stage = board.stages.find(s =>
        s.name.toLowerCase().includes('progress') ||
        s.name.toLowerCase().includes('doing') ||
        s.name.toLowerCase().includes('active')
      );
      stageId = stage ? stage.id : (board.stages[1] ? board.stages[1].id : board.stages[0].id);
    } else if (targetStatus === 'completed' || targetStatus === 'done' || targetStatus === 'closed') {
      const stage = board.stages.find(s =>
        s.isCompleted === true ||
        s.name.toLowerCase().includes('done') ||
        s.name.toLowerCase().includes('completed') ||
        s.name.toLowerCase().includes('closed')
      );
      stageId = stage ? stage.id : board.stages[board.stages.length - 1].id;
    } else {
      // Direct Stage ID lookup or name match
      const stage = board.stages.find(s => s.id === targetStatus || s.name.toLowerCase() === targetStatus);
      if (!stage) {
        throw new Error(`Unknown status/stage: "${targetStatus}". Supported presets: 'in-progress', 'completed'`);
      }
      stageId = stage.id;
    }

    console.log(`[INFO] Updating task ID "${taskId}" to stage ID "${stageId}"...`);

    // 2. PATCH stageId
    const patchResponse = await fetch(`${env.STRATOS_API_URL}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
      },
      body: JSON.stringify({ stageId })
    });

    if (!patchResponse.ok) {
      const errBody = await patchResponse.json().catch(() => ({}));
      throw new Error(`PATCH task failed: ${patchResponse.status} - ${errBody.error || patchResponse.statusText}`);
    }

    console.log(`[PASS] Task status updated successfully.`);

    // 3. POST comment if provided
    if (commentContent) {
      console.log(`[INFO] Adding progress comment to task...`);
      const commentResponse = await fetch(`${env.STRATOS_API_URL}/tasks/${taskId}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
        },
        body: JSON.stringify({ content: commentContent })
      });

      if (!commentResponse.ok) {
        const errBody = await commentResponse.json().catch(() => ({}));
        console.warn(`[WARN] Failed to add comment: ${errBody.error || commentResponse.statusText}`);
      } else {
        console.log(`[PASS] Comment added.`);
      }
    }

  } catch (err) {
    console.error(`[ERROR] Status update failed: ${err.message}`);
    process.exit(1);
  }
}

main();
