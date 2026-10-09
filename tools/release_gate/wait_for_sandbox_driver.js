#!/usr/bin/env node
/**
 * Driver for testing .github/scripts/wait_for_sandbox.js with fake timers and stubbed GitHub API.
 *
 * Simulates the promotion job step in .github/workflows/sandbox-gate.yml:
 *   const wait = new Function('github', 'context', 'core',
 *     'return (async () => {' + fs.readFileSync('.github/scripts/wait_for_sandbox.js', 'utf8') + '})()');
 *   await wait(github, context, core);
 */
const fs = require('fs');
const path = require('path');

// CLI options
const args = process.argv.slice(2);
let scenario = 'success';
let config = null;
let scriptPath = path.resolve(__dirname, '../../.github/scripts/wait_for_sandbox.js');
let jsonOutput = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--scenario' && i + 1 < args.length) {
    scenario = args[++i];
  } else if (args[i] === '--config' && i + 1 < args.length) {
    config = JSON.parse(args[++i]);
  } else if (args[i] === '--script' && i + 1 < args.length) {
    scriptPath = path.resolve(args[++i]);
  } else if (args[i] === '--json') {
    jsonOutput = true;
  } else if (!args[i].startsWith('--')) {
    scenario = args[i];
  }
}

// Fake timers: override Date.now and setTimeout globally
let fakeNow = 1000000;
const initialTime = fakeNow;

Date.now = () => fakeNow;

global.setTimeout = (callback, delay, ...cbArgs) => {
  fakeNow += Number(delay) || 0;
  if (typeof callback === 'function') {
    return setImmediate(callback, ...cbArgs);
  }
};
global.clearTimeout = (id) => clearImmediate(id);

// Stubbed GitHub environment
let pollCount = 0;
const MAX_POLLS = 1000;
const infoMessages = [];

const context = {
  repo: { owner: 'test-org', repo: 'engram' },
  runId: 123456789,
};

const core = {
  info: (msg) => {
    infoMessages.push(msg);
  },
  warning: (msg) => {},
  error: (msg) => {},
  setFailed: (msg) => {},
};

if (!process.env.GITHUB_RUN_ATTEMPT) {
  process.env.GITHUB_RUN_ATTEMPT = '1';
}

function getMockJobsForPoll(pollIndex) {
  if (config && Array.isArray(config.responses)) {
    const resp = config.responses[Math.min(pollIndex, config.responses.length - 1)];
    if (resp && typeof resp === 'object' && resp.__error) {
      throw new Error(resp.__error);
    }
    return resp;
  }

  switch (scenario) {
    case 'success':
      return [{ name: 'clean-room-sandbox', status: 'completed', conclusion: 'success' }];
    case 'failure':
      return [{ name: 'clean-room-sandbox', status: 'completed', conclusion: 'failure' }];
    case 'cancelled':
      return [{ name: 'clean-room-sandbox', status: 'completed', conclusion: 'cancelled' }];
    case 'skipped':
      return [{ name: 'clean-room-sandbox', status: 'completed', conclusion: 'skipped' }];
    case 'sandbox_skipped_hosted_in_progress':
      if (pollIndex === 0) {
        return [
          { name: 'clean-room-sandbox', status: 'completed', conclusion: 'skipped' },
          { name: 'clean-room-hosted', status: 'in_progress' },
        ];
      }
      return [
        { name: 'clean-room-sandbox', status: 'completed', conclusion: 'skipped' },
        { name: 'clean-room-hosted', status: 'completed', conclusion: 'success' },
      ];
    case 'sandbox_skipped_hosted_success':
      return [
        { name: 'clean-room-sandbox', status: 'completed', conclusion: 'skipped' },
        { name: 'clean-room-hosted', status: 'completed', conclusion: 'success' },
      ];
    case 'sandbox_skipped_hosted_failure':
      return [
        { name: 'clean-room-sandbox', status: 'completed', conclusion: 'skipped' },
        { name: 'clean-room-hosted', status: 'completed', conclusion: 'failure' },
      ];
    case 'runner_never_picks_up':
      return [{ name: 'clean-room-sandbox', status: 'queued' }];
    case 'job_never_appears':
    case 'deadline_timeout':
      return [{ name: 'build-candidate', status: 'completed', conclusion: 'success' }];
    case 'late_success':
    case 'appears_late':
      if (pollIndex === 0) {
        return [{ name: 'build-candidate', status: 'completed' }, { name: 'clean-room-sandbox', status: 'queued' }];
      } else if (pollIndex === 1) {
        return [{ name: 'build-candidate', status: 'completed' }, { name: 'clean-room-sandbox', status: 'in_progress' }];
      }
      return [{ name: 'build-candidate', status: 'completed' }, { name: 'clean-room-sandbox', status: 'completed', conclusion: 'success' }];
    case 'api_error':
      throw new Error('GitHub API 500: Internal Server Error');
    case 'malformed_list':
      return { invalid: true };
    case 'null_list':
      return null;
    case 'empty_list':
      return [];
    default:
      throw new Error(`Unknown scenario: ${scenario}`);
  }
}

const listJobsMock = function() {};
const github = {
  rest: {
    actions: {
      listJobsForWorkflowRunAttempt: listJobsMock,
    },
  },
  paginate: async (method, params) => {
    pollCount++;
    if (pollCount > MAX_POLLS) {
      throw new Error(`Driver safety guard: exceeded MAX_POLLS (${MAX_POLLS})`);
    }
    return getMockJobsForPoll(pollCount - 1);
  },
};

(async () => {
  try {
    const scriptContent = fs.readFileSync(scriptPath, 'utf8');
    const wait = new Function('github', 'context', 'core',
      'return (async () => {' + scriptContent + '})()');
    await wait(github, context, core);

    if (jsonOutput) {
      console.log(JSON.stringify({
        status: 'PASS',
        polls: pollCount,
        elapsed_ms: fakeNow - initialTime,
        info_messages: infoMessages,
        error: null,
      }));
    } else {
      console.log('PASS');
    }
    process.exitCode = 0;
  } catch (err) {
    const errMsg = err?.message || String(err);
    if (jsonOutput) {
      console.log(JSON.stringify({
        status: 'HOLD',
        polls: pollCount,
        elapsed_ms: fakeNow - initialTime,
        info_messages: infoMessages,
        error: errMsg,
      }));
    } else {
      console.error(errMsg);
    }
    process.exitCode = 1;
  }
})();
