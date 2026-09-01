"""No-network tests for the AP GAS v10.4 deployment and migration gates.

CHANGE GAS-PREFLIGHT: verify read-only diagnostics, secret redaction, Catalog / AP_MEDIA
integrity rules, and the zero-Gemini postdeploy canary contract.
CHANGE GAS-CATALOG-PREVIEW: verify the redacted Catalog layout classifier distinguishes
stale headers from genuinely legacy-positioned rows without returning cell contents.
CHANGE GAS-DD105-HEADERS: verify the Craig-approved migration only writes A1:M1,
is idempotent, rejects drift, and restores the legacy header after failed verification.
CHANGE GAS-LOCAL-BRIDGE: verify GAS has no Discord egress/trigger requirement and the
local bridge secret is a fail-closed deployment prerequisite.
CHANGE GAS-DURABLE-ASYNC: require exactly one non-Discord background worker.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GAS_SOURCE = REPO / "scripts" / "GAS" / "AntiqueAnalysis_AI.md"
REVIEW_CODE = REPO / "scripts" / "GAS" / "review_desk" / "Code.gs"
DEPLOYMENT = REPO / "scripts" / "GAS" / "DEPLOYMENT.md"
AGENTS = REPO / "AGENTS.md"


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
    agents = AGENTS.read_text(encoding="utf-8")
    assert "function diagPredeployAudit()" in gas
    assert "function diagCatalogContractPreview()" in gas
    assert "function applyDd105CatalogHeaderMigration()" in gas
    assert "function diagMediaReconcilePlan()" in gas
    assert "function diagBridgeReconcilePlan()" in gas
    assert "function diagBridgeMessageDuplicates()" in gas
    assert "function applyDd108KnownTestDuplicateQuarantine()" in gas
    assert "function processBridgeQueue()" in gas
    assert "ScriptApp.newTrigger(BRIDGE_WORKER_FUNCTION)" in gas
    assert '.everyMinutes(1)' in gas
    assert '"bridge.partial_write"' in gas
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
    assert "CHANGE GAS-CATALOG-PREVIEW" in gas
    assert "CHANGE GAS-CATALOG-PREVIEW" in runbook
    assert "CHANGE GAS-DD105-HEADERS" in gas
    assert "CHANGE GAS-DD105-HEADERS" in runbook
    assert "CHANGE GAS-DD105-HEADERS" in agents
    assert "DD-105 — Catalog 標題契約正規化" in agents
    assert "CHANGE GAS-LOCAL-BRIDGE" in gas
    assert "CHANGE GAS-LOCAL-BRIDGE" in runbook
    assert "CHANGE GAS-LOCAL-BRIDGE" in agents
    assert "DD-106 — Local Discord Intake Bridge" in agents


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
  AP_INGEST_SECRET: 'ingest-super-secret-32-chars',
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
  ScriptApp: {getProjectTriggers() { return [{getHandlerFunction() { return 'processBridgeQueue'; }}]; }}
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


def test_catalog_contract_preview_classifies_layout_without_leaking_cells():
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

const legacyHeaders = ['ID','上傳時間','用戶描述','品名','分類','年代/斷代','商品描述',
  '參考商品','參考成交價','參考網頁','雲端圖檔','標籤','審核狀態'];
function row(j, k, l, m) {
  return ['id','time','PRIVATE-ARTIFACT-NAME','item','category','era','story','ref','price',j,k,l,m];
}
function formulas(j, k) {
  return ['','','','','','','','','',j,k,'',''];
}

const currentRows = [
  row('查看圖片', '青銅，鼎', '完成', '適合獨立櫃位展示'),
  row('查看圖片', '陶瓷，瓶', '待人工覆核', '建議柔和側光展示')
];
const currentFormulas = [
  formulas('=HYPERLINK("https://drive.google.com/file/d/PRIVATE-DRIVE-ONE/view","查看")', ''),
  formulas('=HYPERLINK("https://drive.google.com/file/d/PRIVATE-DRIVE-TWO/view","查看")', '')
];
const current = context.buildCatalogContractPreview_(legacyHeaders, currentRows, currentFormulas);
assert.strictEqual(current.classification, 'STALE_LEGACY_HEADERS_CURRENT_POSITIONAL_DATA');
assert.strictEqual(current.confidence, 'high');
assert.strictEqual(current.writesPerformed, 0);

const legacyRows = [
  row('https://auction.example/PRIVATE-LOT-ONE', '查看圖片', '青銅，鼎', '完成'),
  row('https://auction.example/PRIVATE-LOT-TWO', '查看圖片', '陶瓷，瓶', '待人工覆核')
];
const legacyFormulas = [
  formulas('', '=HYPERLINK("https://drive.google.com/file/d/PRIVATE-LEGACY-ONE/view","查看")'),
  formulas('', '=HYPERLINK("https://drive.google.com/file/d/PRIVATE-LEGACY-TWO/view","查看")')
];
const legacy = context.buildCatalogContractPreview_(legacyHeaders, legacyRows, legacyFormulas);
assert.strictEqual(legacy.classification, 'LEGACY_HEADERS_LEGACY_POSITIONAL_DATA');
assert.strictEqual(legacy.confidence, 'high');

const serialized = JSON.stringify({current, legacy});
['PRIVATE-ARTIFACT-NAME','PRIVATE-DRIVE-ONE','PRIVATE-LOT-ONE','PRIVATE-LEGACY-ONE']
  .forEach(value => assert.ok(!serialized.includes(value)));
assert.ok(serialized.includes('不回傳儲存格原文'));
process.stdout.write(JSON.stringify({ok: true, current: current.classification, legacy: legacy.classification}));
"""
    result = _run_node(harness, GAS_SOURCE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ok": True,
        "current": "STALE_LEGACY_HEADERS_CURRENT_POSITIONAL_DATA",
        "legacy": "LEGACY_HEADERS_LEGACY_POSITIONAL_DATA",
    }


def test_dd105_migration_writes_only_header_and_is_idempotent():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const legacyHeaders = ['ID','上傳時間','用戶描述','品名','分類','年代/斷代','商品描述',
  '參考商品','參考成交價','參考網頁','雲端圖檔','標籤','審核狀態'];
const currentHeaders = ['UUID','入庫時間','用戶描述','品名','分類','年代','故事',
  '拍賣參考品','參考價格','Drive URL','標籤','狀態','展示建議'];
let activeHeaders = legacyHeaders.slice();
let headerWrites = [];
let dataWrites = 0;
let flushes = 0;
let lockWaits = 0;
let lockReleases = 0;
function row(j, k, l, m) {
  return ['id','time','caption','item','category','era','story','ref','price',j,k,l,m];
}
function formulas(j) {
  return ['','','','','','','','','',j,'','',''];
}
const displayRows = [
  row('查看圖片', '青銅，鼎', '完成', '適合獨立櫃位展示'),
  row('查看圖片', '陶瓷，瓶', '已退件', '建議柔和側光展示')
];
const formulaRows = [
  formulas('=HYPERLINK("https://drive.google.com/file/d/one/view","查看")'),
  formulas('=HYPERLINK("https://drive.google.com/file/d/two/view","查看")')
];
const headerRange = {
  getDisplayValues() { return [activeHeaders.slice()]; },
  setValues(values) { headerWrites.push(values[0].slice()); activeHeaders = values[0].slice(); }
};
const dataRange = {
  getDisplayValues() { return displayRows; },
  getFormulas() { return formulaRows; },
  setValues() { dataWrites += 1; }
};
const catalog = {
  getName() { return 'Collection list'; },
  getLastRow() { return displayRows.length + 1; },
  getRange(row) { return row === 1 ? headerRange : dataRange; }
};
const spreadsheet = {getSheets() { return [catalog]; }};
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {getProperty() { return 'x'; }}}},
  SpreadsheetApp: {openById() { return spreadsheet; }, flush() { flushes += 1; }},
  LockService: {getScriptLock() { return {
    waitLock(ms) { assert.strictEqual(ms, 30000); lockWaits += 1; },
    releaseLock() { lockReleases += 1; }
  }; }}
};
vm.createContext(context);
vm.runInContext(source, context);
const applied = context.applyDd105CatalogHeaderMigration();
assert.strictEqual(applied.status, 'APPLIED');
assert.strictEqual(applied.range, 'A1:M1');
assert.strictEqual(applied.headerRowsTouched, 1);
assert.strictEqual(applied.dataRowsTouched, 0);
assert.strictEqual(applied.evidence.currentPosition, 9);
assert.strictEqual(applied.evidence.legacyPosition, 0);
assert.strictEqual(activeHeaders.join('|'), currentHeaders.join('|'));
assert.strictEqual(headerWrites.length, 1);
assert.strictEqual(dataWrites, 0);
assert.strictEqual(flushes, 1);

const second = context.applyDd105CatalogHeaderMigration();
assert.strictEqual(second.status, 'ALREADY_APPLIED');
assert.strictEqual(second.headerRowsTouched, 0);
assert.strictEqual(headerWrites.length, 1);
assert.strictEqual(dataWrites, 0);
assert.strictEqual(lockWaits, 2);
assert.strictEqual(lockReleases, 2);
process.stdout.write(JSON.stringify({ok: true, first: applied.status, second: second.status}));
"""
    result = _run_node(harness, GAS_SOURCE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ok": True,
        "first": "APPLIED",
        "second": "ALREADY_APPLIED",
    }


def test_dd105_migration_rejects_drift_and_restores_failed_write():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const legacyHeaders = ['ID','上傳時間','用戶描述','品名','分類','年代/斷代','商品描述',
  '參考商品','參考成交價','參考網頁','雲端圖檔','標籤','審核狀態'];
let activeHeaders = legacyHeaders.slice();
let mode = 'drift';
let writes = [];
const displayRows = [
  ['id','time','caption','item','category','era','story','ref','price','查看圖片','tag','完成','display']
];
const formulaRows = [
  ['','','','','','','','','','=HYPERLINK("https://drive.google.com/file/d/one/view","查看")','','','']
];
const headerRange = {
  getDisplayValues() { return [activeHeaders.slice()]; },
  setValues(values) {
    writes.push(values[0].slice());
    if (mode === 'verify-fail' && writes.length === 1) {
      activeHeaders = ['BROKEN'];
    } else {
      activeHeaders = values[0].slice();
    }
  }
};
const dataRange = {
  getDisplayValues() { return mode === 'drift' ? [['id','','','','','','','','','','tag','NOT-A-STATUS','']] : displayRows; },
  getFormulas() { return mode === 'drift' ? [['','','','','','','','','','','','','']] : formulaRows; }
};
const catalog = {
  getName() { return 'Collection list'; },
  getLastRow() { return 2; },
  getRange(row) { return row === 1 ? headerRange : dataRange; }
};
const spreadsheet = {getSheets() { return [catalog]; }};
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {getProperty() { return 'x'; }}}},
  SpreadsheetApp: {openById() { return spreadsheet; }, flush() {}},
  LockService: {getScriptLock() { return {waitLock() {}, releaseLock() {}}; }}
};
vm.createContext(context);
vm.runInContext(source, context);
activeHeaders = ['UNEXPECTED'].concat(legacyHeaders.slice(1));
assert.throws(() => context.applyDd105CatalogHeaderMigration(), /既非 DD-105 精確舊契約/);
assert.strictEqual(writes.length, 0);
activeHeaders = legacyHeaders.slice();
assert.throws(() => context.applyDd105CatalogHeaderMigration(), /位置證據不再符合 DD-105/);
assert.strictEqual(writes.length, 0);
assert.strictEqual(activeHeaders.join('|'), legacyHeaders.join('|'));

mode = 'verify-fail';
assert.throws(() => context.applyDd105CatalogHeaderMigration(), /rollback=RESTORED_LEGACY_HEADERS/);
assert.strictEqual(writes.length, 2);
assert.strictEqual(writes[1].join('|'), legacyHeaders.join('|'));
assert.strictEqual(activeHeaders.join('|'), legacyHeaders.join('|'));
process.stdout.write(JSON.stringify({ok: true, writes: writes.length}));
"""
    result = _run_node(harness, GAS_SOURCE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "writes": 2}


def test_diagnostics_are_structurally_read_only():
    gas = GAS_SOURCE.read_text(encoding="utf-8")
    preflight = gas.split("function diagPredeployAudit()", 1)[1].split(
        "/** Controlled durable-bridge setup.", 1
    )[0]
    reconcile = gas.split("function diagMediaReconcilePlan()", 1)[1].split(
        "/** Read-only plan for durable local-bridge", 1
    )[0]
    bridge_reconcile = gas.split("function diagBridgeReconcilePlan()", 1)[1].split(
        "/**\n * CHANGE GAS-DURABLE-ASYNC", 1
    )[0]
    duplicate_diag = gas.split("function diagBridgeMessageDuplicates()", 1)[1].split(
        "/**\n * Craig-approved DD-108 repair", 1
    )[0]
    catalog_preview = gas.split("function diagCatalogContractPreview()", 1)[1].split(
        "/**\n * DD-105", 1
    )[0]
    postdeploy = gas.split("function diagPostdeployCanary()", 1)[1].split(
        "// ============================================================\n// 🧹 Trigger", 1
    )[0]
    assert "ScriptApp.getService()" in postdeploy
    assert "UrlFetchApp.fetch(serviceUrl" in postdeploy
    assert "discordReadOnlyCanary_" not in postdeploy
    assert "post.discord.bot" not in postdeploy
    assert 'gasEgressCalls: 0' in postdeploy
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
    for function_source in (
        catalog_preview,
        preflight,
        reconcile,
        bridge_reconcile,
        duplicate_diag,
        postdeploy,
    ):
        for forbidden in forbidden_mutations:
            assert forbidden not in function_source
