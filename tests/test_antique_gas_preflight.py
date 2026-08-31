"""No-network tests for the AP GAS v10.1 deployment gates.

CHANGE GAS-PREFLIGHT: verify read-only diagnostics, secret redaction, Catalog / AP_MEDIA
integrity rules, and the zero-Gemini postdeploy canary contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GAS_SOURCE = REPO / "scripts" / "GAS" / "AntiqueAnalysis_AI.md"
REVIEW_CODE = REPO / "scripts" / "GAS" / "review_desk" / "Code.gs"
DEPLOYMENT = REPO / "scripts" / "GAS" / "DEPLOYMENT.md"


def _run_node(script: str, *paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", script, *(str(path) for path in paths)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_gas_sources_parse_and_deployment_contract_is_documented():
    script = r"""
const fs = require('fs');
const vm = require('vm');
for (const path of process.argv.slice(1)) {
  new vm.Script(fs.readFileSync(path, 'utf8'), {filename: path});
}
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = _run_node(script, GAS_SOURCE, REVIEW_CODE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}

    gas = GAS_SOURCE.read_text(encoding="utf-8")
    review = REVIEW_CODE.read_text(encoding="utf-8")
    runbook = DEPLOYMENT.read_text(encoding="utf-8")
    assert "function diagPredeployAudit()" in gas
    assert "function diagMediaReconcilePlan()" in gas
    assert "function diagPostdeployCanary()" in gas
    assert "geminiCalls: 0" in gas
    assert "ScriptApp.getService()" in gas
    assert "service.getUrl()" in gas
    assert "function diagReviewDeskPreflight()" in review
    assert "Catalog A:M 與凍結契約不一致；停止 setup" in review
    assert "diagTestGeminiFallbackCanary()" in runbook
    assert "CHANGE GAS-PREFLIGHT" in gas
    assert "CHANGE GAS-PREFLIGHT" in review
    assert "CHANGE GAS-PREFLIGHT" in runbook


def test_catalog_and_media_integrity_rules_without_network():
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

function catalog(uuid, status) {
  return [uuid, '2026-08-31', 'caption', 'item', '陶瓷', '清朝', 'story', '', '',
    'https://drive.google.com/file/d/file-' + uuid + '/view', '', status, 'display'];
}
function media(uuid, mediaId, order, primary, status) {
  return [uuid, mediaId, 'file-' + mediaId, 'https://drive.google.com/file/d/file-' + mediaId + '/view',
    'front', order, primary, status, 'attachment', 'message', 'image/jpeg', 1000, '2026-08-31'];
}

const cleanCatalog = context.auditCatalogRows_([
  catalog('published', '完成'),
  catalog('pending', '待人工覆核')
], 2);
assert.strictEqual(cleanCatalog.issues.length, 0);
const cleanMedia = context.auditMediaRows_(cleanCatalog, [
  media('published', 'm1', 1, true, 'approved'),
  media('pending', 'm2', 1, true, 'pending')
], 2);
assert.strictEqual(cleanMedia.issues.length, 0);

const badCatalog = context.auditCatalogRows_([
  catalog('duplicate', '完成'),
  catalog('duplicate', '待人工覆核'),
  catalog('', '未知狀態')
], 10);
const catalogCodes = badCatalog.issues.map(issue => issue.code);
assert.ok(catalogCodes.includes('CATALOG_UUID_DUPLICATE'));
assert.ok(catalogCodes.includes('CATALOG_UUID_MISSING'));

const referenceCatalog = context.auditCatalogRows_([
  catalog('published', '完成'),
  catalog('pending', '待人工覆核')
], 2);
const badMedia = context.auditMediaRows_(referenceCatalog, [
  media('orphan', 'orphan-media', 1, true, 'pending'),
  media('pending', 'privacy-media', 1, true, 'approved'),
  media('published', 'p1', 1, true, 'pending'),
  media('published', 'p2', 1, true, 'pending')
], 20);
const mediaCodes = badMedia.issues.map(issue => issue.code);
assert.ok(mediaCodes.includes('MEDIA_ORPHAN'));
assert.ok(mediaCodes.includes('MEDIA_PRIVACY_STATE_MISMATCH'));
assert.ok(mediaCodes.includes('PUBLISHED_WITHOUT_APPROVED_MEDIA'));
assert.ok(mediaCodes.includes('MEDIA_PRIMARY_COUNT'));
assert.ok(mediaCodes.includes('MEDIA_SORT_ORDER_DUPLICATE'));
process.stdout.write(JSON.stringify({ok: true, issues: badMedia.issues.length}));
"""
    result = _run_node(harness, GAS_SOURCE)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["ok"] is True
    assert output["issues"] >= 5


def test_preflight_returns_only_secret_presence_not_values():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const secrets = {
  DISCORD_BOT_TOKEN: 'discord-super-secret',
  GEMINI_API_KEY: 'gemini-super-secret',
  AP_INGEST_SECRET: 'ingest-super-secret',
  pending_jobs: '[]'
};
const catalogHeaders = ['UUID','入庫時間','用戶描述','品名','分類','年代','故事','拍賣參考品','參考價格','Drive URL','標籤','狀態','展示建議'];
const mediaHeaders = ['artifactUuid','mediaId','driveFileId','driveUrl','viewRole','sortOrder','isPrimary','status','sourceAttachmentId','sourceMessageId','mimeType','sizeBytes','createdAt'];
function sheet(name, header, rows) {
  return {
    getName() { return name; },
    getLastRow() { return rows.length + 1; },
    getRange(row, column, rowCount) {
      return {
        getDisplayValues() { return row === 1 ? [header] : rows; },
        getValues() { return row === 1 ? [header] : rows; }
      };
    }
  };
}
const catalog = sheet('Catalog', catalogHeaders, []);
const media = sheet('AP_MEDIA', mediaHeaders, []);
const spreadsheet = {
  getName() { return 'AP Test'; },
  getSheets() { return [catalog]; },
  getSheetByName(name) { return name === 'AP_MEDIA' ? media : null; }
};
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {
    getProperty(key) { return secrets[key] || ''; },
    getProperties() { return Object.assign({}, secrets); }
  }}},
  DriveApp: {getFolderById() { return {getName() { return 'AP Root'; }}; }},
  SpreadsheetApp: {openById() { return spreadsheet; }},
  ScriptApp: {getProjectTriggers() { return [{getHandlerFunction() { return 'mainTick'; }}]; }}
};
vm.createContext(context);
vm.runInContext(source, context);
const report = context.diagPredeployAudit();
assert.strictEqual(report.status, 'PASS');
const serialized = JSON.stringify(report);
Object.values(secrets).filter(value => value !== '[]').forEach(secret => assert.ok(!serialized.includes(secret)));
assert.ok(serialized.includes('已設定（值不回傳）'));
process.stdout.write(JSON.stringify({ok: true, status: report.status}));
"""
    result = _run_node(harness, GAS_SOURCE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "status": "PASS"}


def test_diagnostics_are_structurally_read_only():
    gas = GAS_SOURCE.read_text(encoding="utf-8")
    preflight = gas.split("function diagPredeployAudit()", 1)[1].split(
        "/** Controlled setup.", 1
    )[0]
    reconcile = gas.split("function diagMediaReconcilePlan()", 1)[1].split(
        "function discordReadOnlyCanary_()", 1
    )[0]
    postdeploy = gas.split("function diagPostdeployCanary()", 1)[1].split(
        "// ============================================================\n// 🧹 Trigger", 1
    )[0]
    assert "ScriptApp.getService()" in postdeploy
    assert "UrlFetchApp.fetch(serviceUrl" in postdeploy
    assert "doGet({" not in postdeploy
    forbidden_mutations = (
        ".setValues(",
        ".appendRow(",
        ".deleteFile(",
        ".setSharing(",
        ".setProperty(",
        "setupTrigger(",
        "fetchGeminiWithFallback_(",
    )
    for function_source in (preflight, reconcile, postdeploy):
        for forbidden in forbidden_mutations:
            assert forbidden not in function_source
