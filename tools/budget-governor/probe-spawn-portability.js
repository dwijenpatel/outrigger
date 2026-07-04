export const meta = {
  name: 'probe-spawn-portability',
  description: 'Verify per-agent effort and model overrides on the Workflow spawn path (design doc open question #3)',
  phases: [
    { title: 'Effort probe' },
    { title: 'Model probe' },
    { title: 'Invalid-id probe' },
  ],
}

// Re-run via: Workflow({ scriptPath: 'tools/budget-governor/probe-spawn-portability.js' })
// Record Claude Code version (`claude --version`) + date + results in a new dated file
// alongside probe-spawn-portability-2026-07-04.md. See that file for the baseline result
// and why the invalid-id checks below use both a try/catch AND a null-result check.

const SCHEMA = {
  type: 'object',
  properties: { reply: { type: 'string' } },
  required: ['reply'],
}

phase('Effort probe')
const efforts = ['low', 'medium', 'high', 'xhigh', 'max']
const effortResults = await parallel(efforts.map(e => () =>
  agent('Reply with exactly: OK', { label: `effort:${e}`, phase: 'Effort probe', schema: SCHEMA, effort: e })
    .then(r => ({ effort: e, ok: !!r, reply: r?.reply ?? null }))
    .catch(err => ({ effort: e, ok: false, error: String(err && err.message ? err.message : err) }))
))

phase('Model probe')
const models = ['haiku', 'sonnet']
const modelResults = await parallel(models.map(m => () =>
  agent('Reply with exactly: OK', { label: `model:${m}`, phase: 'Model probe', schema: SCHEMA, model: m })
    .then(r => ({ model: m, ok: !!r, reply: r?.reply ?? null }))
    .catch(err => ({ model: m, ok: false, error: String(err && err.message ? err.message : err) }))
))

phase('Invalid-id probe')
// NOTE: bad ids do not always throw -- agent() can resolve to null instead (see the dated
// probe writeup). Check both the exception path and the null-result path.
let invalidEffortResult
try {
  const r = await agent('Reply with exactly: OK', { label: 'effort:invalid', phase: 'Invalid-id probe', schema: SCHEMA, effort: 'ultra-mega' })
  invalidEffortResult = r
    ? { ok: true, reply: r.reply ?? null, note: 'did NOT fail loud -- invalid effort id silently accepted' }
    : { ok: false, note: 'failed loud (null result) as expected' }
} catch (err) {
  invalidEffortResult = { ok: false, error: String(err && err.message ? err.message : err), note: 'failed loud (thrown) as expected' }
}

let invalidModelResult
try {
  const r = await agent('Reply with exactly: OK', { label: 'model:invalid', phase: 'Invalid-id probe', schema: SCHEMA, model: 'gpt-99-turbo' })
  invalidModelResult = r
    ? { ok: true, reply: r.reply ?? null, note: 'did NOT fail loud -- invalid model id silently accepted' }
    : { ok: false, note: 'failed loud (null result) as expected -- check workflow failures log for the message' }
} catch (err) {
  invalidModelResult = { ok: false, error: String(err && err.message ? err.message : err), note: 'failed loud (thrown) as expected' }
}

return { effortResults, modelResults, invalidEffortResult, invalidModelResult }
