"""No-network tests for AP GAS v10.2 durable queue behavior.

CHANGE GAS-QUEUE-SAFETY: verify locked enqueue, persistent job payloads,
bounded pre-persistence retry, post-persistence dead-letter, and private diagnostics.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GAS_SOURCE = REPO / "scripts" / "GAS" / "AntiqueAnalysis_AI.md"


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", script, str(GAS_SOURCE)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_queue_reliability_contract_is_wired():
    gas = GAS_SOURCE.read_text(encoding="utf-8")
    assert "CHANGE GAS-QUEUE-SAFETY" in gas
    assert "const JOB_MAX_ATTEMPTS = 3" in gas
    assert "function persistJobPayload_(" in gas
    assert "props.setProperty(JOB_PAYLOAD_PREFIX + jobId, payload)" in gas
    assert "function enqueueJob_(" in gas
    assert "function decideJobFailureDisposition_(" in gas
    assert "function deadLetterJob_(" in gas
    assert "function diagQueueHealth()" in gas
    assert 'mode = "READ_ONLY"' in gas
    assert "fastEnqueue" not in gas
    assert "Discord reset_queue 已停用" in gas
    assert 'processingPhase = "drive_and_sheet_persistence"' in gas
    assert "persistenceStarted = true" in gas

    poll = gas.split("function pollDiscordChannel()", 1)[1].split(
        "function fetchDiscordMessages", 1
    )[0]
    assert poll.index("persistJobPayload_(jobId") < poll.index("enqueueJob_(jobId")
    enqueue_index = poll.index("enqueueJob_(jobId")
    assert poll.find("newLastId = msg.id", enqueue_index) > enqueue_index

    worker = gas.split("function processJobAsync()", 1)[1].split(
        "// ============================================================\n// 📤 Discord", 1
    )[0]
    assert worker.index("persistenceStarted = true") < worker.index("saveArtifactMedia_(")
    assert worker.index("writeMediaRows_(") < worker.index("writeToSheet(")
    assert worker.index("writeToSheet(") < worker.index("markJobDone_(")


def test_failure_disposition_retries_only_transient_pre_persistence_errors():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {getProperty() { return 'x'; }}}}
};
vm.createContext(context);
vm.runInContext(source, context);

const first503 = context.decideJobFailureDisposition_(new Error('HTTP 503 unavailable'), 1, false);
assert.strictEqual(first503.action, 'RETRY');
assert.strictEqual(first503.nextAttempt, 2);
assert.strictEqual(first503.classification.code, 'TRANSIENT');

const exhausted = context.decideJobFailureDisposition_(new Error('HTTP 503 unavailable'), 3, false);
assert.strictEqual(exhausted.action, 'DEAD_LETTER');
assert.strictEqual(exhausted.reason, 'RETRY_NOT_ALLOWED_OR_EXHAUSTED');

const auth = context.decideJobFailureDisposition_(new Error('HTTP 403 permission denied'), 1, false);
assert.strictEqual(auth.action, 'DEAD_LETTER');
assert.strictEqual(auth.classification.code, 'AUTH_OR_CONTRACT');

const partial = context.decideJobFailureDisposition_(new Error('HTTP 503 unavailable'), 1, true);
assert.strictEqual(partial.action, 'DEAD_LETTER');
assert.strictEqual(partial.reason, 'PERSISTENCE_MAY_HAVE_STARTED');

const redacted = context.classifyJobFailure_(new Error('Discord 圖片獲取失敗 HTTP 404，URL: https://cdn.example/private?token=SECRET'));
assert.strictEqual(redacted.code, 'SOURCE_UNRECOVERABLE');
assert.ok(!redacted.message.includes('https://'));
assert.ok(!redacted.message.includes('SECRET'));
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = _run_node(harness)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


def test_locked_enqueue_is_idempotent_and_corrupt_queue_fails_closed():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const values = {
  DISCORD_BOT_TOKEN: 'token',
  GEMINI_API_KEY: 'key',
  pending_jobs: '[]'
};
let waits = 0;
let releases = 0;
const removedCacheKeys = [];
const props = {
  getProperty(key) { return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : ''; },
  setProperty(key, value) { values[key] = String(value); },
  deleteProperty(key) { delete values[key]; },
  getProperties() { return Object.assign({}, values); }
};
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return props; }},
  CacheService: {getScriptCache() { return {remove(key) { removedCacheKeys.push(key); }}; }},
  LockService: {getScriptLock() { return {
    waitLock() { waits += 1; },
    releaseLock() { releases += 1; }
  }; }}
};
vm.createContext(context);
vm.runInContext(source, context);
context.enqueueJob_('job-a');
context.enqueueJob_('job-a');
context.enqueueJob_('job-b', 2);
assert.deepStrictEqual(JSON.parse(values.pending_jobs), ['job-a', 'job-b']);
assert.strictEqual(values['job_attempt_job-b'], '2');
assert.strictEqual(waits, 3);
assert.strictEqual(releases, 3);

values.pending_jobs = '{broken';
assert.throws(() => context.enqueueJob_('job-c'), /拒絕自動清空/);
assert.strictEqual(values.pending_jobs, '{broken');

values.pending_jobs = '[]';
values.job_payload_retryable = '{"jobId":"retryable"}';
values.job_attempt_retryable = '3';
values.job_dead_retryable = JSON.stringify({jobId: 'retryable', reason: 'RETRY_NOT_ALLOWED_OR_EXHAUSTED'});
assert.strictEqual(context.safeEnqueue('retryable'), true);
assert.strictEqual(JSON.stringify(JSON.parse(values.pending_jobs)), JSON.stringify(['retryable']));
assert.strictEqual(values.job_attempt_retryable, '1');
assert.ok(!Object.prototype.hasOwnProperty.call(values, 'job_dead_retryable'));
assert.strictEqual(removedCacheKeys[0], 'done_retryable');

values.job_payload_partial = '{"jobId":"partial"}';
values.job_dead_partial = JSON.stringify({jobId: 'partial', reason: 'PERSISTENCE_MAY_HAVE_STARTED'});
assert.strictEqual(context.safeEnqueue('partial'), false);
assert.ok(!JSON.parse(values.pending_jobs).includes('partial'));

values.job_payload_orphan = '{"jobId":"orphan"}';
assert.strictEqual(context.safeEnqueue('orphan'), false);
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = _run_node(harness)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


def test_durable_payload_fallback_cleanup_and_queue_health_redaction():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const values = {DISCORD_BOT_TOKEN: 'token', GEMINI_API_KEY: 'key', pending_jobs: '["job-a"]'};
const cacheValues = {};
const props = {
  getProperty(key) { return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : ''; },
  setProperty(key, value) { values[key] = String(value); },
  deleteProperty(key) { delete values[key]; },
  getProperties() { return Object.assign({}, values); }
};
const cache = {
  get(key) { return cacheValues[key] || ''; },
  put(key, value) { cacheValues[key] = String(value); }
};
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return props; }},
  CacheService: {getScriptCache() { return cache; }}
};
vm.createContext(context);
vm.runInContext(source, context);

const payload = JSON.stringify({jobId: 'job-a', url: 'https://cdn.example/PRIVATE-SIGNED-URL'});
context.persistJobPayload_('job-a', payload, cache);
delete cacheValues['job_job-a'];
assert.strictEqual(context.loadJobPayload_('job-a', cache), payload);
assert.strictEqual(cacheValues['job_job-a'], payload);

values.job_payload_dead = JSON.stringify({secret: 'PRIVATE-DEAD-PAYLOAD'});
values.job_attempt_dead = '3';
values.job_dead_dead = JSON.stringify({
  jobId: 'dead', attempt: 3, phase: 'analysis', code: 'TRANSIENT',
  reason: 'RETRY_NOT_ALLOWED_OR_EXHAUSTED', error: 'HTTP 503', failedAt: '2026-08-31T00:00:00Z'
});
values.job_payload_orphan = JSON.stringify({secret: 'PRIVATE-ORPHAN-PAYLOAD'});
const health = context.buildQueueHealthReport_(values);
assert.strictEqual(health.status, 'WARN');
assert.strictEqual(health.pendingCount, 1);
assert.strictEqual(health.deadCount, 1);
assert.strictEqual(JSON.stringify(health.orphanPayloadJobIds), JSON.stringify(['orphan']));
const serialized = JSON.stringify(health);
assert.ok(!serialized.includes('PRIVATE-SIGNED-URL'));
assert.ok(!serialized.includes('PRIVATE-DEAD-PAYLOAD'));
assert.ok(!serialized.includes('PRIVATE-ORPHAN-PAYLOAD'));

context.markJobDone_('job-a', cache, 'completed');
assert.ok(!Object.prototype.hasOwnProperty.call(values, 'job_payload_job-a'));
assert.ok(!Object.prototype.hasOwnProperty.call(values, 'job_attempt_job-a'));
assert.strictEqual(cacheValues['done_job-a'], 'completed');

const broken = Object.assign({}, values, {pending_jobs: '["missing"]'});
const brokenHealth = context.buildQueueHealthReport_(broken);
assert.strictEqual(brokenHealth.status, 'FAIL');
assert.strictEqual(JSON.stringify(brokenHealth.missingPayloadJobIds), JSON.stringify(['missing']));
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = _run_node(harness)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}
