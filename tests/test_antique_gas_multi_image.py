"""No-network contract tests for AP GAS multi-image intake and media publication.

CHANGE GAS-MULTI-IMAGE: verify the frozen Catalog remains intact while AP_MEDIA,
Gemini inline/Files routing, and the guest images[] compatibility layer stay wired.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GAS_SOURCE = REPO / "scripts" / "GAS" / "AntiqueAnalysis_AI.md"
REVIEW_CODE = REPO / "scripts" / "GAS" / "review_desk" / "Code.gs"
REVIEW_UI = REPO / "scripts" / "GAS" / "review_desk" / "Index.html"
PUBLISH_UI = REPO / "Publish" / "index.html"


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", script, str(GAS_SOURCE)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_multi_image_contract_is_wired_end_to_end():
    gas = GAS_SOURCE.read_text(encoding="utf-8")
    review_code = REVIEW_CODE.read_text(encoding="utf-8")
    review_ui = REVIEW_UI.read_text(encoding="utf-8")
    publish_ui = PUBLISH_UI.read_text(encoding="utf-8")

    assert "const MAX_IMAGES_PER_ARTIFACT = 8" in gas
    assert "const INLINE_BINARY_BUDGET_BYTES = 12 * 1024 * 1024" in gas
    assert 'const MEDIA_SHEET_NAME = "AP_MEDIA"' in gas
    assert "loadApprovedMediaByArtifact_" in gas
    assert "images:                images" in gas
    assert "saveMediaArrangement" in review_code
    assert "syncArtifactMediaStatus_" in review_code
    assert 'MEDIA_SHEET: "AP_MEDIA"' in review_code
    assert 'id="media-editor-list"' in review_ui
    assert "normalizedArtifactImages" in publish_ui
    assert 'id="modalMediaRail"' in publish_ui
    assert "CHANGE R10-MEDIA" in publish_ui


def test_inline_and_files_api_routing_without_network():
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
let uploadCounter = 0;
const fetchCalls = [];
const context = {
  console: {log() {}, warn() {}, error() {}},
  PropertiesService: {getScriptProperties() { return {getProperty(key) {
    if (key === 'GEMINI_API_KEY') return 'test-key';
    if (key === 'DISCORD_BOT_TOKEN') return 'test-token';
    return '';
  }}}},
  Utilities: {
    base64Encode(bytes) { return Buffer.from(bytes).toString('base64'); },
    sleep() {}
  },
  UrlFetchApp: {fetch(url, options) {
    fetchCalls.push({url, options});
    if (url.includes('/upload/v1beta/files')) {
      uploadCounter += 1;
      return {
        getResponseCode() { return 200; },
        getAllHeaders() { return {'x-goog-upload-url': 'mock://upload/' + uploadCounter}; },
        getContentText() { return ''; }
      };
    }
    if (url.startsWith('mock://upload/')) {
      const id = url.split('/').pop();
      return {
        getResponseCode() { return 200; },
        getContentText() { return JSON.stringify({file: {name: 'files/' + id, uri: 'mock://file/' + id}}); }
      };
    }
    throw new Error('unexpected URL ' + url);
  }}
};
vm.createContext(context);
vm.runInContext(source, context);

function blob(size, name) {
  const bytes = Buffer.alloc(size, 7);
  return {
    getBytes() { return bytes; },
    getContentType() { return 'image/jpeg'; },
    getName() { return name; }
  };
}

const inline = context.prepareGeminiImageParts_([blob(12, 'front.jpg'), blob(14, 'base.jpg')]);
assert.strictEqual(inline.inputMode, 'inline');
assert.strictEqual(inline.imageCount, 2);
assert.strictEqual(inline.parts.length, 4);
assert.strictEqual(inline.parts[1].media_resolution.level, 'MEDIA_RESOLUTION_HIGH');
assert.ok(inline.parts[1].inline_data.data);

const files = context.prepareGeminiImageParts_([blob(7 * 1024 * 1024, 'front.jpg'), blob(6 * 1024 * 1024, 'detail.jpg')]);
assert.strictEqual(files.inputMode, 'files_api');
assert.strictEqual(files.uploadedFiles.length, 2);
assert.strictEqual(files.parts.length, 4);
assert.strictEqual(files.parts[1].file_data.file_uri, 'mock://file/1');
assert.strictEqual(files.parts[3].file_data.file_uri, 'mock://file/2');
assert.strictEqual(files.parts[3].media_resolution.level, 'MEDIA_RESOLUTION_HIGH');
process.stdout.write(JSON.stringify({ok: true, calls: fetchCalls.length}));
"""
    result = _run_node(harness)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "calls": 4}


def test_multi_image_grouping_fails_closed_when_objects_do_not_match():
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
const result = context.normalizeAnalysisResult_({
  isValid: true,
  rejectionReason: '',
  objectGrouping: 'multiple_objects',
  views: [
    {imageIndex: 1, role: 'front', observation: '器身正面'},
    {imageIndex: 2, role: 'base', observation: '另一器底'}
  ],
  missingViews: [], itemName: '待研究器物', category: '陶瓷', era: '時代不詳',
  features: '', story: '', refItem: '', refPrice: '', displayRecommendation: '',
  highlightQuote: '', currentSellingPoint: '', tags: ''
}, '', 2);
assert.strictEqual(result.isValid, false);
assert.strictEqual(result.objectGrouping, 'multiple_objects');
assert.match(result.rejectionReason, /不同物件/);
assert.strictEqual(result.views.length, 2);
process.stdout.write(JSON.stringify({ok: true}));
"""
    result = _run_node(harness)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}
