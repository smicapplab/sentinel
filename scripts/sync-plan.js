#!/usr/bin/env node

/**
 * Sentinel Plan Sync tool
 * Automatically parses a spec or plan Markdown file and publishes it to Stratos
 * as an Epic + Stories via the Stratos Bulk Tasks API.
 * Automatically tags all tasks with a module-specific tag (e.g., sentinel-inventory).
 * Saves a sync mapping file (<plan-name>.sync.json) to enable status updates during execution.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Load environment variables from .env if present
let env = {
  STRATOS_API_URL: 'http://localhost:5173/api/v1',
  STRATOS_API_TOKEN: '',
  STRATOS_STAGE_ID: ''
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
        // Remove quotes if present
        if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
        if (value.startsWith("'") && value.endsWith("'")) value = value.slice(1, -1);
        env[key] = value;
      }
    });
    break;
  }
}

// Override with process.env if set
env.STRATOS_API_URL = process.env.STRATOS_API_URL || env.STRATOS_API_URL;
env.STRATOS_API_TOKEN = process.env.STRATOS_API_TOKEN || env.STRATOS_API_TOKEN;
env.STRATOS_STAGE_ID = process.env.STRATOS_STAGE_ID || env.STRATOS_STAGE_ID;

if (!env.STRATOS_API_TOKEN) {
  console.error('[ERROR] STRATOS_API_TOKEN is not set in environment or .env file.');
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error('[ERROR] Please specify the path to the plan or spec markdown file.');
  console.error('Usage: node sync-plan.js <path_to_markdown_file> [stage_id]');
  process.exit(1);
}

const filePath = path.resolve(process.cwd(), args[0]);
if (!fs.existsSync(filePath)) {
  console.error(`[ERROR] File not found at ${filePath}`);
  process.exit(1);
}

// Parse markdown file
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');
let epicTitle = '';
let epicDescription = '';
const stories = [];
let currentStory = null;
let currentStoryDescLines = [];
const introLines = [];
let foundFirstH2 = false;

for (const line of lines) {
  if (line.startsWith('# ')) {
    epicTitle = line.substring(2).trim();
  } else if (line.startsWith('## ')) {
    foundFirstH2 = true;
    if (currentStory) {
      currentStory.description = currentStoryDescLines.join('\n').trim();
      stories.push(currentStory);
    }
    currentStory = {
      title: line.substring(3).trim(),
      description: ''
    };
    currentStoryDescLines = [];
  } else {
    if (!foundFirstH2) {
      if (!line.startsWith('# ')) {
        introLines.push(line);
      }
    } else {
      currentStoryDescLines.push(line);
    }
  }
}

if (currentStory) {
  currentStory.description = currentStoryDescLines.join('\n').trim();
  stories.push(currentStory);
}

epicDescription = introLines.join('\n').trim();

// Fallbacks
if (!epicTitle) {
  epicTitle = `Plan: ${path.basename(filePath, '.md')}`;
}

const fileHash = crypto.createHash('sha256').update(content).digest('hex').substring(0, 16);
const sourceId = `sentinel-plan-${path.basename(filePath)}-${fileHash}`;

// Extract module-specific tag name (e.g. 04-inventory-plan.md -> sentinel-inventory)
const baseName = path.basename(filePath, '.md');
const cleanedName = baseName.replace(/^\d+-/, '').replace(/-(plan|spec)$/, '');
const tagName = `sentinel-${cleanedName}`;

async function main() {
  let stageId = args[1] || env.STRATOS_STAGE_ID;
  let projectId = '';

  // 1. Fetch boards to pick a default stage and resolve projectId
  console.log('[INFO] Querying Stratos boards...');
  try {
    const response = await fetch(`${env.STRATOS_API_URL}/boards`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch boards: ${response.status} ${response.statusText}`);
    }

    const boards = await response.json();
    if (!Array.isArray(boards) || boards.length === 0) {
      throw new Error('No boards found in Stratos.');
    }

    // Resolve stage and projectId
    let board = boards[0];
    if (stageId) {
      const matchedBoard = boards.find(b => b.stages && b.stages.some(s => s.id === stageId));
      if (matchedBoard) board = matchedBoard;
    } else {
      if (!board.stages || board.stages.length === 0) {
        throw new Error(`Board "${board.name}" has no stages.`);
      }
      stageId = board.stages[0].id;
    }

    projectId = board.projectId;
    console.log(`[INFO] Target Project ID: ${projectId}`);
    console.log(`[INFO] Target Stage: "${board.stages.find(s => s.id === stageId)?.name || 'Backlog'}" (${stageId})`);
  } catch (err) {
    console.error(`[ERROR] Failed to automatically resolve Stratos board/stage: ${err.message}`);
    process.exit(1);
  }

  // 2. Resolve or create module Tag in Stratos
  let tagId = '';
  console.log(`[INFO] Resolving tag "${tagName}" in Stratos...`);
  try {
    const tagResponse = await fetch(`${env.STRATOS_API_URL}/projects/${projectId}/tags`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
      },
      body: JSON.stringify({ name: tagName, color: 'indigo' })
    });

    if (!tagResponse.ok) {
      throw new Error(`Tag registration failed: ${tagResponse.status}`);
    }

    const tagData = await tagResponse.json();
    tagId = tagData.id;
    console.log(`[PASS] Tag resolved: "${tagName}" (${tagId})`);
  } catch (err) {
    console.warn(`[WARN] Could not resolve tag in Stratos: ${err.message}`);
  }

  // 3. Format payload for bulk task import
  const payload = {
    epic: {
      title: epicTitle,
      description: epicDescription,
      stageId: stageId
    },
    stories: stories.map(s => ({
      title: s.title,
      description: s.description
    })),
    sourceId: sourceId
  };

  console.log(`[INFO] Sending plan to Stratos bulk API...`);
  console.log(`       Epic: "${epicTitle}" (${stories.length} stories)`);
  console.log(`       Source ID: ${sourceId}`);

  try {
    const response = await fetch(`${env.STRATOS_API_URL}/tasks/bulk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
      },
      body: JSON.stringify(payload)
    });

    const mappingFilePath = filePath.replace(/\.md$/, '.sync.json');

    if (response.status === 409) {
      console.log('[SKIP] Plan is already synchronized with Stratos (idempotency key matched).');
      if (!fs.existsSync(mappingFilePath)) {
        console.log('[WARN] Sync mapping file missing locally. Cannot perform inline task updates without it.');
      }
      process.exit(0);
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(`Bulk API error: ${response.status} - ${errorBody.error || response.statusText}`);
    }

    const result = await response.json();
    console.log(`[PASS] Plan tasks created in Stratos.`);
    console.log(`       Created Epic ID: ${result.epic.id}`);
    console.log(`       Created Stories count: ${result.stories.length}`);

    // 4. Attach Tag to Epic & Stories sequentially (to avoid parallel request limit)
    if (tagId) {
      console.log(`[INFO] Attaching tag "${tagName}" to created tasks...`);
      const allTasks = [result.epic, ...result.stories];
      for (const t of allTasks) {
        try {
          const assocResponse = await fetch(`${env.STRATOS_API_URL}/tasks/${t.id}/tags`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${env.STRATOS_API_TOKEN}`
            },
            body: JSON.stringify({ tagId })
          });
          if (!assocResponse.ok) {
            console.warn(`[WARN] Failed to tag task "${t.title}": ${assocResponse.status}`);
          }
        } catch (assocErr) {
          console.warn(`[WARN] Tag association network error: ${assocErr.message}`);
        }
      }
      console.log('[PASS] Tagging completed.');
    }

    // 5. Create a local mapping file to track IDs per story
    const syncMapping = {
      epicId: result.epic.id,
      boardId: result.epic.boardId,
      tagId: tagId || null,
      tagName: tagId ? tagName : null,
      stories: {}
    };

    result.stories.forEach((story, idx) => {
      const parsedStoryTitle = stories[idx] ? stories[idx].title : story.title;
      syncMapping.stories[parsedStoryTitle] = story.id;
    });

    fs.writeFileSync(mappingFilePath, JSON.stringify(syncMapping, null, 2), 'utf8');
    console.log(`[PASS] Saved local sync mapping to ${mappingFilePath}`);
  } catch (err) {
    console.error(`[ERROR] Sync failed: ${err.message}`);
    process.exit(1);
  }
}

main();
