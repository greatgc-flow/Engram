const deadline = Date.now() + 45 * 60 * 1000;
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
  const sandbox = jobs.find(job => job?.name === 'clean-room-sandbox');
  if (sandbox?.status === 'completed') {
    if (sandbox.conclusion !== 'success') {
      throw new Error(`HOLD: Sandbox concluded ${sandbox.conclusion}`);
    }
    core.info('PASS: Sandbox completed successfully');
    return;
  }
  await new Promise(resolve => setTimeout(resolve, 15000));
}
throw new Error('HOLD: Sandbox runner unavailable or evidence deadline exceeded (45 minutes)');
