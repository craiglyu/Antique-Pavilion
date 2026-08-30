"""No-network contract tests for the AP GAS Gemini model fallback.

CHANGE GAS-GEMINI-FALLBACK: keep the deployable GAS source credential-free and
verify routing/cooldown semantics with a mocked Apps Script runtime.
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


def test_gas_source_is_valid_javascript_and_has_no_embedded_credentials():
    source = GAS_SOURCE.read_text(encoding="utf-8")
    assert "gemini-3.1-flash-lite-preview" not in source
    assert "gemini-3-flash-preview" not in source
    assert source.index('model: "gemini-3.7-flash"') < source.index('model: "gemini-3.6-flash"')
    assert source.index('model: "gemini-3.6-flash"') < source.index('model: "gemini-3.5-flash"')
    assert source.index('model: "gemini-3.5-flash"') < source.index('model: "gemini-3.5-flash-lite"')
    assert 'getProperty("GEMINI_API_KEY")' in source
    assert 'getProperty("DISCORD_BOT_TOKEN")' in source
    assert 'getProperty("AP_INGEST_SECRET")' in source
    assert "AIza" not in source

    result = _run_node(
        "const fs=require('fs'),vm=require('vm');"
        "new vm.Script(fs.readFileSync(process.argv[1],'utf8'));"
        "process.stdout.write('GAS syntax OK');"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "GAS syntax OK"


def test_fallback_retry_cooldown_and_auth_fail_closed_without_network():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');

const cacheValues = new Map();
let responseQueue = [];
let fetchModels = [];
const successBody = JSON.stringify({
  candidates: [{content: {parts: [{text: '{"ok":true}'}]}}],
  usageMetadata: {promptTokenCount: 10, candidatesTokenCount: 4}
});

const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {
    getScriptProperties() {
      return {
        getProperty(key) {
          if (key === 'GEMINI_API_KEY') return 'test-key';
          if (key === 'DISCORD_BOT_TOKEN') return 'test-token';
          return '';
        }
      };
    }
  },
  CacheService: {
    getScriptCache() {
      return {
        get(key) { return cacheValues.get(key) || null; },
        put(key, value) { cacheValues.set(key, value); }
      };
    }
  },
  Utilities: {sleep() {}},
  UrlFetchApp: {
    fetch(url) {
      fetchModels.push(decodeURIComponent(url).match(/models\/([^:]+):/)[1]);
      const next = responseQueue.shift();
      if (!next) throw new Error('mock response queue exhausted');
      return {
        getResponseCode() { return next.code; },
        getContentText() { return next.body || ''; }
      };
    }
  }
};
vm.createContext(context);
vm.runInContext(source, context);

const payload = {contents: [{parts: [{text: 'canary'}]}], generationConfig: {}};
const validator = result => JSON.parse(result.candidates[0].content.parts[0].text);

// 3.7 transient failure is retried once, then 3.6 succeeds.
responseQueue = [
  {code: 503, body: '{}'},
  {code: 503, body: '{}'},
  {code: 200, body: successBody}
];
let routed = context.fetchGeminiWithFallback_(payload, validator, {bypassCooldown: true});
assert.strictEqual(routed.receipt.selectedModel, 'gemini-3.6-flash');
assert.strictEqual(routed.receipt.fallbackUsed, true);
assert.deepStrictEqual(fetchModels, [
  'gemini-3.7-flash',
  'gemini-3.7-flash',
  'gemini-3.6-flash'
]);

// A subsequent production call skips cooled-down 3.7 and goes directly to 3.6.
fetchModels = [];
responseQueue = [{code: 200, body: successBody}];
routed = context.fetchGeminiWithFallback_(payload, validator);
assert.strictEqual(routed.receipt.selectedModel, 'gemini-3.6-flash');
assert.strictEqual(routed.receipt.attempts[0].status, 'cooldown_skip');
assert.deepStrictEqual(fetchModels, ['gemini-3.6-flash']);

// Free-tier quota exhaustion falls through immediately; it is not retried on
// the same model and therefore cannot double-spend a scarce route quota.
cacheValues.clear();
fetchModels = [];
responseQueue = [
  {code: 429, body: '{}'},
  {code: 200, body: successBody}
];
routed = context.fetchGeminiWithFallback_(payload, validator, {bypassCooldown: true});
assert.strictEqual(routed.receipt.selectedModel, 'gemini-3.6-flash');
assert.deepStrictEqual(fetchModels, ['gemini-3.7-flash', 'gemini-3.6-flash']);

// Shared-key authentication errors fail closed instead of wasting calls on every model.
cacheValues.clear();
fetchModels = [];
responseQueue = [{code: 403, body: '{}'}];
assert.throws(
  () => context.fetchGeminiWithFallback_(payload, validator, {bypassCooldown: true}),
  /認證失敗 HTTP 403/
);
assert.deepStrictEqual(fetchModels, ['gemini-3.7-flash']);

process.stdout.write(JSON.stringify({ok: true}));
"""
    result = _run_node(harness)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}
