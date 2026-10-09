const POLICY_PATH = typeof __dirname !== 'undefined'
  ? require('path').resolve(__dirname, '../../tools/release_gate/release_policy.json')
  : 'tools/release_gate/release_policy.json';
const policy = JSON.parse(require('fs').readFileSync(POLICY_PATH, 'utf8'));
for (const key of ['evidence_wait_minutes', 'evidence_poll_seconds']) {
  if (!Number.isInteger(policy[key]) || policy[key] <= 0) throw new Error(`HOLD: invalid policy ${key}`);
}
const deadline = Date.now() + policy.evidence_wait_minutes * 60 * 1000;
const CANDIDATE_JOBS = ['clean-room-sandbox', 'clean-room-hosted'];
while (Date.now() < deadline) {
  let jobs;
  try {
    jobs = await github.paginate(github.rest.actions.listJobsForWorkflowRunAttempt, {
      ...context.repo, run_id: context.runId,
      attempt_number: Number(process.env.GITHUB_RUN_ATTEMPT || 1), per_page: 100
    });
  } catch (err) {
    throw new Error(`HOLD: GitHub API error: ${err?.message || err}`);
  }
  if (!Array.isArray(jobs) || jobs.length === 0) {
    throw new Error('HOLD: malformed or empty job list');
  }
  const candidates = jobs.filter(job => CANDIDATE_JOBS.includes(job?.name));
  const pass = candidates.find(job => job?.status === 'completed' && job?.conclusion === 'success');
  if (pass) {
    core.info('PASS: Sandbox completed successfully');
    return;
  }
  if (candidates.length > 0 && !candidates.some(job => job?.status !== 'completed')) {
    const failed = candidates.find(job => job?.conclusion) || candidates[0];
    throw new Error(`HOLD: Sandbox concluded ${failed?.conclusion || 'failure'}`);
  }
  await new Promise(resolve => setTimeout(resolve, Math.min(policy.evidence_poll_seconds * 1000, deadline - Date.now())));
}
throw new Error(`HOLD: Sandbox runner unavailable or evidence deadline exceeded (${policy.evidence_wait_minutes} minutes)`);
