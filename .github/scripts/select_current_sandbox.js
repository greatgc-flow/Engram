const names = ['windows-sandbox', 'hosted-ephemeral-vm'].map(
  provider => `sandbox-evidence-${provider}-${context.runId}-${process.env.GITHUB_RUN_ATTEMPT}`);
const artifacts = await github.paginate(github.rest.actions.listWorkflowRunArtifacts, {
  ...context.repo, run_id: context.runId, per_page: 100
});
const selected = artifacts.filter(artifact => names.includes(artifact.name) && !artifact.expired);
if (!selected.length) throw new Error('HOLD: missing current-attempt Sandbox evidence');
core.setOutput('artifact_ids', selected.map(artifact => artifact.id).join(','));
