"""No-network tests for the local Discord -> GAS intake bridge.

CHANGE GAS-LOCAL-BRIDGE: verify bounded image compression, secret/config gates,
multi-image payloads, and messageId replay behavior without Discord or Gemini calls.
CHANGE GAS-DURABLE-ASYNC: verify v4 submit/status protocol and duplicate grouping.
"""

from __future__ import annotations

import ast
import io
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image


REPO = Path(__file__).resolve().parents[1]
BRIDGE = REPO / "scripts" / "ap_intake_bridge.py"
BOT = REPO / "ap_discord_bot.py"
GAS = REPO / "scripts" / "GAS" / "AntiqueAnalysis_AI.md"


def _bridge_module():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("ap_intake_bridge_under_test", BRIDGE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _jpeg(width: int = 4200, height: int = 3000) -> bytes:
    image = Image.effect_noise((width, height), 70).convert("RGB")
    output = io.BytesIO()
    image.save(output, "JPEG", quality=96)
    return output.getvalue()


def test_python_sources_parse_and_bot_has_no_hardcoded_bridge_secret_or_ssl_false():
    ast.parse(BRIDGE.read_text(encoding="utf-8"))
    ast.parse(BOT.read_text(encoding="utf-8"))
    source = BOT.read_text(encoding="utf-8")
    assert 'env("AP_GAS_DOPOST_URL")' in source
    assert 'env("AP_INGEST_SECRET")' in source
    assert "build_ingest_payload" in source
    assert "message.attachments" in source
    assert '"action": "status"' in source
    assert "12 * 60" in source
    assert "AP-local-bridge-v4.0" in source
    assert "ssl=False" not in source
    assert "script.google.com/macros/s/" not in source


def test_compression_normalizes_to_bounded_jpeg_and_strips_metadata():
    bridge = _bridge_module()
    source = _jpeg()
    prepared = bridge.compress_image_bytes(
        source,
        attachment_id="attachment-1",
        filename="手機 原圖.heic.jpg",
        index=1,
        target_bytes=900_000,
    )
    assert prepared.mime_type == "image/jpeg"
    assert len(prepared.data) <= 900_000
    assert max(prepared.width, prepared.height) <= bridge.DEFAULT_MAX_DIMENSION
    assert prepared.filename.endswith(".jpg")
    with Image.open(io.BytesIO(prepared.data)) as decoded:
        assert decoded.format == "JPEG"
        assert not decoded.getexif()


def test_payload_accepts_one_to_eight_images_and_enforces_total_budget():
    bridge = _bridge_module()
    prepared = bridge.PreparedImage(
        attachment_id="a",
        filename="front.jpg",
        mime_type="image/jpeg",
        data=b"jpeg-bytes",
        original_bytes=20,
        width=100,
        height=100,
        quality=82,
    )
    payload, request_bytes = bridge.build_ingest_payload(
        [prepared] * 8,
        ingest_secret="s" * 32,
        caption="同一件藏品",
        message_id="1495279823009087551",
        channel_id="1495279823009087552",
        user_id="566565645483769863",
        user_name="Craig",
    )
    assert len(payload["images"]) == 8
    assert payload["messageId"] == "1495279823009087551"
    assert payload["bridgeVersion"] == "AP-local-bridge-v4.0"
    assert payload["action"] == "submit"
    assert request_bytes < bridge.MAX_GAS_JSON_BYTES
    with pytest.raises(bridge.BridgeInputError, match="1–8"):
        bridge.build_ingest_payload(
            [prepared] * 9,
            ingest_secret="s" * 32,
            caption="",
            message_id="1495279823009087551",
            channel_id="c",
            user_id="u",
            user_name="Craig",
        )


def test_config_requires_raw_token_formal_exec_url_and_long_shared_secret():
    bridge = _bridge_module()
    valid_url = "https://script.google.com/macros/s/DEPLOYMENT_ID/exec"
    bridge.validate_bridge_config("raw-token", valid_url, "s" * 32)
    with pytest.raises(RuntimeError, match="Bot 前綴"):
        bridge.validate_bridge_config("Bot token", valid_url, "s" * 32)
    with pytest.raises(RuntimeError, match="/exec"):
        bridge.validate_bridge_config("raw-token", valid_url.replace("/exec", "/dev"), "s" * 32)
    with pytest.raises(RuntimeError, match="24"):
        bridge.validate_bridge_config("raw-token", valid_url, "short")


def test_gas_replays_existing_message_id_without_gemini_or_writes():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const secret = 'ingest-super-secret-32-chars';
const messageId = '1495279823009087551';
const mediaRows = [
  ['artifact-1','m1','file-1','https://drive.google.com/file/d/file-1/view','front',1,true,'pending','a1',messageId,'image/jpeg',1000,'2026'],
  ['artifact-1','m2','file-2','https://drive.google.com/file/d/file-2/view','base',2,false,'pending','a2',messageId,'image/jpeg',1000,'2026']
];
const catalogRows = [
  ['artifact-1','2026','caption','青花瓶','陶瓷','清朝','story','ref','price','link','tag','待人工覆核','display']
];
function sheet(rows) {
  return {
    getLastRow() { return rows.length + 1; },
    getRange() { return {getValues() { return rows; }, getDisplayValues() { return rows; }}; }
  };
}
const catalog = sheet(catalogRows);
const media = sheet(mediaRows);
const spreadsheet = {getSheets() { return [catalog]; }, getSheetByName() { return media; }};
const values = {};
const props = {
  getProperty(key) {
    if (key === 'AP_INGEST_SECRET') return secret;
    if (key === 'GEMINI_API_KEY') return 'gemini-key';
    return values[key] || '';
  },
  setProperty(key, value) { values[key] = String(value); },
  deleteProperty(key) { delete values[key]; }
};
let lockReleased = 0;
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return props; }},
  CacheService: {getScriptCache() { return {get() { return null; }, put() {}, remove() {}}; }},
  LockService: {getScriptLock() { return {waitLock() {}, releaseLock() { lockReleased += 1; }}; }},
  SpreadsheetApp: {openById() { return spreadsheet; }},
  ContentService: {
    MimeType: {JSON: 'json'},
    createTextOutput(text) { return {text, setMimeType() { return this; }}; }
  }
};
vm.createContext(context);
vm.runInContext(source, context);
const response = context.doPost({postData: {contents: JSON.stringify({
  bridgeVersion: 'AP-local-bridge-v4.0',
  action: 'submit',
  ingestSecret: secret,
  messageId,
  images: [{imageBase64: 'should-not-be-decoded'}]
})}});
const result = JSON.parse(response.text);
assert.strictEqual(result.success, true);
assert.strictEqual(result.duplicate, true);
assert.strictEqual(result.artifactUuid, 'artifact-1');
assert.strictEqual(result.imageCount, 2);
assert.strictEqual(lockReleased, 1);
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        ["node", "-e", harness, str(GAS)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["duplicate"] is True


def test_gas_durable_queue_claim_is_single_consumer_and_status_is_read_only():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const values = {
  bridge_state_1495279823009087551: JSON.stringify({
    messageId: '1495279823009087551', jobId: '1495279823009087551',
    state: 'QUEUED', phase: 'STAGED', queuedAt: '2026-09-01T00:00:00.000Z'
  })
};
const props = {
  getProperty(key) { return values[key] || ''; },
  getProperties() { return Object.assign({}, values); },
  setProperty(key, value) { values[key] = String(value); },
  deleteProperty(key) { delete values[key]; }
};
let releases = 0;
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return props; }},
  LockService: {getScriptLock() { return {waitLock() {}, releaseLock() { releases += 1; }}; }}
};
vm.createContext(context);
vm.runInContext(source, context);
const first = context.claimNextBridgeJob_();
const second = context.claimNextBridgeJob_();
const status = context.statusBridgeJob_('1495279823009087551');
assert.strictEqual(first.state, 'RUNNING');
assert.strictEqual(second, null);
assert.strictEqual(status.accepted, true);
assert.strictEqual(status.state, 'RUNNING');
assert.strictEqual(releases, 2);
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = subprocess.run(
        ["node", "-e", harness, str(GAS)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


def test_gas_duplicate_detector_reports_only_repeated_message_groups():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {getProperty() { return ''; }}; }}
};
vm.createContext(context);
vm.runInContext(source, context);
const catalog = [
  ['keeper','','','','','','','','','','','待人工覆核',''],
  ['duplicate','','','','','','','','','','','待人工覆核',''],
  ['single','','','','','','','','','','','完成','']
];
function media(uuid, mediaId, attachment, messageId, status) {
  return [uuid, mediaId, '', '', 'front', 1, true, status, attachment, messageId, 'image/jpeg', 10, ''];
}
const groups = context.analyzeBridgeMessageDuplicates_(catalog, [
  media('keeper', 'm1', 'a1', '1543912512204967967', 'pending'),
  media('duplicate', 'm2', 'a1', '1543912512204967967', 'pending'),
  media('single', 'm3', 'a2', '1999999999999999999', 'approved')
]);
assert.strictEqual(groups.length, 1);
assert.strictEqual(groups[0].messageId, '1543912512204967967');
assert.strictEqual(groups[0].artifactCount, 2);
assert.ok(!JSON.stringify(groups).includes('Drive URL'));
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = subprocess.run(
        ["node", "-e", harness, str(GAS)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


def test_known_duplicate_quarantine_changes_only_duplicate_statuses():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const messageId = '1543912512204967967';
const keeper = '9a3705a2-fa29-420b-8047-6b56c524a0a5';
const duplicate = '06b0648a-3e4a-4ffe-a330-4e0523b53bba';
const catalogRows = [
  [keeper,'','','','','','','','','','','待人工覆核',''],
  [duplicate,'','','','','','','','','','','待人工覆核','']
];
const mediaRows = [
  [keeper,'k1','','','front',1,true,'pending','a1',messageId,'image/jpeg',10,''],
  [keeper,'k2','','','back',2,false,'pending','a2',messageId,'image/jpeg',10,''],
  [duplicate,'d1','','','front',1,true,'pending','a1',messageId,'image/jpeg',10,''],
  [duplicate,'d2','','','back',2,false,'pending','a2',messageId,'image/jpeg',10,'']
];
function sheet(rows, isCatalog) {
  return {
    getLastRow() { return rows.length + 1; },
    getRange(row, column, rowCount) {
      if (rowCount) {
        return {
          getValues() { return rows; },
          getDisplayValues() { return rows; }
        };
      }
      const dataIndex = row - 2;
      const valueIndex = column - 1;
      return {
        getDisplayValue() { return rows[dataIndex][valueIndex]; },
        setValue(value) { rows[dataIndex][valueIndex] = value; return this; }
      };
    }
  };
}
const catalog = sheet(catalogRows, true);
const media = sheet(mediaRows, false);
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {getProperty() { return ''; }}; }},
  SpreadsheetApp: {
    openById() { return {getSheets() { return [catalog]; }, getSheetByName() { return media; }}; },
    flush() {}
  },
  LockService: {getScriptLock() { return {waitLock() {}, releaseLock() {}}; }}
};
vm.createContext(context);
vm.runInContext(source, context);
const receipt = context.applyDd108KnownTestDuplicateQuarantine();
assert.strictEqual(receipt.status, 'APPLIED');
assert.strictEqual(receipt.catalogRowsTouched, 1);
assert.strictEqual(receipt.mediaRowsTouched, 2);
assert.strictEqual(receipt.filesDeleted, 0);
assert.strictEqual(catalogRows[0][11], '待人工覆核');
assert.strictEqual(catalogRows[1][11], '已退件');
assert.deepStrictEqual(mediaRows.slice(0, 2).map(row => row[7]), ['pending', 'pending']);
assert.deepStrictEqual(mediaRows.slice(2).map(row => row[7]), ['rejected', 'rejected']);
const replay = context.applyDd108KnownTestDuplicateQuarantine();
assert.strictEqual(replay.status, 'ALREADY_APPLIED');
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = subprocess.run(
        ["node", "-e", harness, str(GAS)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


# ----------------------------------------------------------------------------
# CHANGE DD109-MERGE: user-confirmed "merge into keeper" (Craig approved 2026-09-03)
# ----------------------------------------------------------------------------
def test_payload_carries_merge_into_only_when_confirmed_and_validates_shape():
    bridge = _bridge_module()
    prepared = [bridge.compress_image_bytes(_jpeg(1600, 1200), attachment_id="a1", filename="a.jpg", index=1)]
    common = dict(ingest_secret="ingest-super-secret-32-chars", caption="", message_id="1495279823009087551",
                  channel_id="1", user_id="2", user_name="craig")
    payload, _ = bridge.build_ingest_payload(prepared, **common)
    assert "mergeInto" not in payload
    payload, _ = bridge.build_ingest_payload(prepared, merge_into="9a3705a2-1111-4222-8333-444455556666", **common)
    assert payload["mergeInto"] == "9a3705a2-1111-4222-8333-444455556666"
    with pytest.raises(bridge.BridgeInputError):
        bridge.build_ingest_payload(prepared, merge_into="../etc", **common)


def test_bot_asks_before_merging_and_never_merges_by_time_alone():
    source = BOT.read_text(encoding="utf-8")
    assert "_ask_merge_confirmation" in source
    assert 'bot.wait_for("reaction_add"' in source
    assert "merge_into=merge_into" in source
    assert "NEW_ITEM_KEYWORDS" in source
    # time proximity alone must not submit a merge: the only path that sets merge_into is the reaction.
    assert source.count("merge_into = await _ask_merge_confirmation") == 1


def test_gas_merge_gate_rejects_missing_or_rejected_keeper_and_worker_skips_gemini():
    gas = GAS.read_text(encoding="utf-8")
    assert "processMergeBridgeJob_" in gas
    assert "MERGE_TARGET_INVALID" in gas
    # merge path is decided before any Gemini call
    assert gas.index("if (manifest.mergeInto)") < gas.index("const analysis = analyzeWithGemini(blobs")
    harness = r"""
const fs = require('fs'); const vm = require('vm'); const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const props = {getProperty(k){ return k === 'AP_INGEST_SECRET' ? 'ingest-super-secret-32-chars' : ''; }, setProperty(){}, deleteProperty(){}};
const context = {
  console: {log(){}, warn(){}, error(){}},
  PropertiesService: {getScriptProperties(){ return props; }},
  CacheService: {getScriptCache(){ return {get(){return null;}, put(){}, remove(){}}; }},
  LockService: {getScriptLock(){ return {waitLock(){}, releaseLock(){}}; }},
  SpreadsheetApp: {openById(){ throw new Error('not needed'); }},
  ContentService: {MimeType:{JSON:'json'}, createTextOutput(t){ return {text:t, setMimeType(){ return this; }}; }}
};
vm.createContext(context); vm.runInContext(source, context);
const KEEPER = 'd20f8cdf-0000-4000-8000-000000000183';
const GONE = '9a3705a2-0000-4000-8000-000000000181';
const rows = [
  [KEEPER,'2026','c','龍洋','雜項','清朝','s','','','link','t','待人工覆核','d'],
  [GONE,'2026','c','x','雜項','清朝','s','','','link','t','已退件','d']
];
assert.strictEqual(context.assertMergeTargetValid_(rows, KEEPER)[3], '龍洋');
for (const bad of ['aaaaaaaa-0000-4000-8000-000000000999', GONE, '../x', '']) {
  let code = '';
  try { context.assertMergeTargetValid_(rows, bad); } catch (e) { code = e.bridgeCode; }
  assert.strictEqual(code, 'MERGE_TARGET_INVALID', 'expected rejection for ' + JSON.stringify(bad));
}
process.stdout.write('ok');
"""
    result = subprocess.run(["node", "-e", harness, str(GAS)], cwd=REPO, check=False,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "ok"


def test_review_desk_merge_is_reversible_and_wired_in_ui():
    code = (REPO / "scripts" / "GAS" / "review_desk" / "Code.gs").read_text(encoding="utf-8")
    ui = (REPO / "scripts" / "GAS" / "review_desk" / "Index.html").read_text(encoding="utf-8")
    assert "function mergeArtifactInto(payload)" in code
    assert "deleteRow" not in code and "setTrashed" not in code
    assert '"merge-into"' in code and '"merge-receive"' in code
    assert 'id="merge-dialog"' in ui and "mergeArtifactInto" in ui and "data-merge-uuid" in ui
