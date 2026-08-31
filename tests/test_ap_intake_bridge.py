"""No-network tests for the local Discord -> GAS intake bridge.

CHANGE GAS-LOCAL-BRIDGE: verify bounded image compression, secret/config gates,
multi-image payloads, and messageId replay behavior without Discord or Gemini calls.
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
