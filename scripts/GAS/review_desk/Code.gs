/**
 * 吉寶軒 Curator Review Desk — owner-only GAS Web App.
 *
 * This is intentionally a separate Apps Script project from the public
 * catalogue API. Deploy it with access restricted to the owner. The catalogue
 * sheet remains the source of truth; this app only changes existing cells and
 * writes its own review/audit tabs.
 */

const REVIEW_DESK = Object.freeze({
  CATALOG_SHEET_INDEX: 0,
  QUEUE_SHEET: "Review Queue",
  AUDIT_SHEET: "Review Audit",
  PROP_SHEET_ID: "AP_SHEET_ID",
  PROP_OWNER_EMAIL: "AP_REVIEW_OWNER_EMAIL",
});

const CATALOG_STATUS = Object.freeze({
  PUBLISHED: "完成",
  PENDING: "待人工覆核",
  ARCHIVED: "已下架",
  REJECTED: "已退件",
});

const ACTION_STATUS = Object.freeze({
  publish: CATALOG_STATUS.PUBLISHED,
  hold: CATALOG_STATUS.PENDING,
  archive: CATALOG_STATUS.ARCHIVED,
  reject: CATALOG_STATUS.REJECTED,
});

const VALID_ERAS = Object.freeze([
  "史前與高古",
  "唐宋元(含之前)",
  "明朝",
  "清朝",
  "民國",
  "近現代",
  "外國骨董",
  "時代不詳",
  "其他",
]);

const EDITABLE_FIELDS = Object.freeze({
  userCaption: { column: 3, label: "原始描述", maxLength: 1000 },
  itemName: { column: 4, label: "品名", maxLength: 120, required: true },
  category: { column: 5, label: "分類", maxLength: 80, required: true },
  era: { column: 6, label: "年代", maxLength: 40, required: true },
  story: { column: 7, label: "故事", maxLength: 3000 },
  refItem: { column: 8, label: "拍賣參考品", maxLength: 600 },
  refPrice: { column: 9, label: "參考價格", maxLength: 300 },
  imageUrl: { column: 10, label: "Drive 圖片 URL", maxLength: 500 },
  tags: { column: 11, label: "標籤", maxLength: 500 },
  displayRecommendation: { column: 13, label: "展示建議", maxLength: 1500 },
});

const QUEUE_HEADERS = Object.freeze([
  "groupId",
  "uuid",
  "sourceRowAtSeed",
  "recommendedRole",
  "reviewReason",
  "imageFingerprint",
  "reviewStatus",
  "reviewerNote",
  "updatedAt",
]);

const AUDIT_HEADERS = Object.freeze([
  "timestamp",
  "actor",
  "action",
  "groupId",
  "uuid",
  "catalogRow",
  "beforeStatus",
  "afterStatus",
  "changedFields",
  "note",
]);

const INITIAL_DUPLICATE_GROUPS = Object.freeze([
  {
    groupId: "D-01",
    reason: "同一帆船面照片；建議保留資料與標籤較完整者。",
    members: [
      ["e2f3e47c-69ba-4ba1-994d-0482d9f5748c", 137, "keeper"],
      ["472ef1d5-5fae-4e96-9100-767b0bd726b7", 178, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-02",
    reason: "同一孫像面照片；建議保留年代與品名較具體者。",
    members: [
      ["195fba32-ebc9-4bc8-8472-2675dd160d6a", 140, "keeper"],
      ["c88f2f51-bb7c-4c1d-962c-200869ca4a1a", 177, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-03",
    reason: "同一圓佩照片；建議保留展示資訊與參考脈絡較完整者。",
    members: [
      ["3dbae07d-be0f-4744-8c51-b4506556fba5", 147, "keeper"],
      ["1a0520c1-ae63-4875-b9c5-dffcbfafd72f", 173, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-04",
    reason: "同一玉牌照片；建議保留品名、故事與展示資訊較完整者。",
    members: [
      ["1d59c47d-9b97-4cda-90b3-409a6262d15f", 172, "keeper"],
      ["ee9b12fe-be99-4c17-9951-ea5b0124fa4c", 148, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-05",
    reason: "同一玉璜照片；建議保留紋飾描述與故事較完整者。",
    members: [
      ["bb99f7dd-1e49-4a48-8c14-1afe6559c323", 171, "keeper"],
      ["594b7d74-b08b-4de7-84c9-8275fec4eca7", 149, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-06",
    reason: "同一輪狀玉飾照片；建議保留參考與展示資訊較完整者。",
    members: [
      ["ce63dca2-12fd-455e-9425-13b9215641b7", 169, "keeper"],
      ["b5c31da7-76b6-4eac-a664-6eda6be2ec89", 152, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-07",
    reason: "同一帶板照片；建議保留資料與檢索標籤較完整者。",
    members: [
      ["0576cca8-d4d6-434b-9fd3-b49d31aa5c24", 168, "keeper"],
      ["9f8e274b-0099-4b66-bf77-1199f4f1d37c", 153, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-08",
    reason: "同一玉璧照片；建議保留器型名稱較具辨識性者。",
    members: [
      ["3e5f9fc7-d7dc-450c-8b8c-82b0467a241f", 158, "keeper"],
      ["1cd45a07-668d-442c-8b9b-f2f388538256", 157, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-09",
    reason: "同一銅爐照片，但明／清與器型互相衝突；不預選保留者。",
    members: [
      ["ec82088e-5211-4d9f-a9ab-e68f3c063a09", 105, "factual-conflict"],
      ["b0b719c7-2c25-49e5-81ba-ab39f77ebf99", 106, "factual-conflict"],
    ],
  },
  {
    groupId: "D-10",
    reason: "同一袁世凱銀幣照片；建議保留拍品參考與價格欄較完整者。",
    members: [
      ["44ba5688-d1fd-43f0-acff-ddf759d84c8d", 69, "keeper"],
      ["7b0f697b-d7e5-4a49-98ba-10b43ef3375f", 70, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-11",
    reason: "同一沖耳爐照片；建議保留故事與品名較完整者。",
    members: [
      ["9077bfba-1d25-48db-ba6e-31269019aaa3", 48, "keeper"],
      ["f71f37ea-adde-4055-96df-a4c5aa97afcf", 43, "duplicate-candidate"],
    ],
  },
  {
    groupId: "D-12",
    reason: "同一鳳鳥爐照片；建議保留器型、年代範圍與展示建議較完整者。",
    members: [
      ["b8810c2a-658b-48e2-acc9-2d04263105b8", 2, "keeper"],
      ["8a31bbaf-9eda-44b1-b61e-fa6f2cd9b193", 3, "duplicate-candidate"],
      ["3e648af5-8423-4561-8a68-b92cf2c39a88", 4, "duplicate-candidate"],
    ],
  },
]);

function doGet() {
  assertAuthorized_();
  return HtmlService.createHtmlOutputFromFile("Index")
    .setTitle("吉寶軒｜藏品審核台")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}

/** One-time setup from the Apps Script editor. Safe to rerun. */
function setupReviewDesk() {
  assertAuthorized_();
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const spreadsheet = getSpreadsheet_();
    const queueSheet = ensureSheet_(spreadsheet, REVIEW_DESK.QUEUE_SHEET, QUEUE_HEADERS);
    const auditSheet = ensureSheet_(spreadsheet, REVIEW_DESK.AUDIT_SHEET, AUDIT_HEADERS);
    seedQueue_(queueSheet);
    formatSupportSheet_(queueSheet, [120, 250, 120, 150, 420, 220, 130, 280, 170]);
    formatSupportSheet_(auditSheet, [170, 210, 120, 100, 250, 100, 120, 120, 220, 300]);
    return {
      ok: true,
      queueRows: Math.max(queueSheet.getLastRow() - 1, 0),
      message: "Review Desk 已建立；未更動收藏品欄位。",
    };
  } finally {
    lock.releaseLock();
  }
}

function getBootstrapData() {
  assertAuthorized_();
  const spreadsheet = getSpreadsheet_();
  const queueSheet = spreadsheet.getSheetByName(REVIEW_DESK.QUEUE_SHEET);
  if (!queueSheet) {
    throw new Error("尚未建立 Review Queue，請先在 Apps Script 執行 setupReviewDesk()。");
  }

  const catalogItems = loadCatalogItems_(spreadsheet);
  const itemByUuid = {};
  catalogItems.forEach((item) => { itemByUuid[item.uuid] = item; });

  const queueRows = readQueueRows_(queueSheet);
  const groupsById = {};
  queueRows.forEach((queueItem) => {
    if (!groupsById[queueItem.groupId]) {
      groupsById[queueItem.groupId] = {
        groupId: queueItem.groupId,
        reason: queueItem.reviewReason,
        items: [],
      };
    }
    const item = itemByUuid[queueItem.uuid];
    if (item) {
      groupsById[queueItem.groupId].items.push(Object.assign({}, item, {
        recommendedRole: queueItem.recommendedRole,
        reviewStatus: queueItem.reviewStatus,
        reviewerNote: queueItem.reviewerNote,
      }));
    }
  });

  const groups = Object.keys(groupsById)
    .sort()
    .map((groupId) => groupsById[groupId])
    .filter((group) => group.items.length > 0);

  return {
    reviewer: getReviewerEmail_(),
    generatedAt: new Date().toISOString(),
    groups,
    catalog: catalogItems,
    summary: buildSummary_(groups),
    statuses: CATALOG_STATUS,
    validEras: VALID_ERAS,
  };
}

/** Create a Craig-selected comparison group without changing publication state. */
function createManualReviewGroup(payload) {
  assertAuthorized_();
  const uuids = Array.from(new Set(
    ((payload && payload.uuids) || []).map((value) => String(value || "").trim()).filter(Boolean)
  ));
  if (uuids.length < 2 || uuids.length > 6) {
    throw new Error("人工比對群組必須選擇 2 至 6 件藏品。");
  }
  const reason = String((payload && payload.reason) || "Craig 人工選取的相似藏品，待並排覆核。")
    .trim()
    .slice(0, 500);

  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const spreadsheet = getSpreadsheet_();
    const catalogSheet = spreadsheet.getSheets()[REVIEW_DESK.CATALOG_SHEET_INDEX];
    const queueSheet = spreadsheet.getSheetByName(REVIEW_DESK.QUEUE_SHEET);
    const auditSheet = spreadsheet.getSheetByName(REVIEW_DESK.AUDIT_SHEET);
    if (!queueSheet || !auditSheet) throw new Error("Review Desk 尚未初始化。");

    const groupId = `M-${Utilities.formatDate(new Date(), "Asia/Taipei", "yyyyMMdd-HHmmss")}`;
    const now = new Date();
    const rows = uuids.map((uuid) => {
      const sourceRow = findCatalogRowByUuid_(catalogSheet, uuid);
      if (!sourceRow) throw new Error(`找不到藏品 UUID：${uuid}`);
      return [groupId, uuid, sourceRow, "manual-review", reason, "", "待審", "", now];
    });
    queueSheet.getRange(queueSheet.getLastRow() + 1, 1, rows.length, QUEUE_HEADERS.length)
      .setValues(rows);
    uuids.forEach((uuid) => auditSheet.appendRow([
      now,
      getReviewerEmail_(),
      "create-review-group",
      groupId,
      uuid,
      findCatalogRowByUuid_(catalogSheet, uuid),
      "",
      "",
      "[]",
      reason,
    ]));
    SpreadsheetApp.flush();
    return { ok: true, groupId, message: `已建立 ${groupId}，可前往重複覆核並排比較。` };
  } finally {
    lock.releaseLock();
  }
}

function saveReviewDecision(payload) {
  assertAuthorized_();
  const request = normalizeDecision_(payload);
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const spreadsheet = getSpreadsheet_();
    const catalogSheet = spreadsheet.getSheets()[REVIEW_DESK.CATALOG_SHEET_INDEX];
    const queueSheet = spreadsheet.getSheetByName(REVIEW_DESK.QUEUE_SHEET);
    const auditSheet = spreadsheet.getSheetByName(REVIEW_DESK.AUDIT_SHEET);
    if (!queueSheet || !auditSheet) {
      throw new Error("Review Desk 尚未初始化，請先執行 setupReviewDesk()。");
    }

    const row = findCatalogRowByUuid_(catalogSheet, request.uuid);
    if (!row) throw new Error("找不到對應 UUID；資料可能已被移動或刪除。");

    const before = readCatalogItemAtRow_(catalogSheet, row);
    const fields = sanitizeEditableFields_(request.fields || {});
    const afterCandidate = Object.assign({}, before, fields);
    if (request.action === "publish") validatePublishable_(afterCandidate);

    Object.keys(fields).forEach((fieldName) => {
      catalogSheet.getRange(row, EDITABLE_FIELDS[fieldName].column).setValue(fields[fieldName]);
    });

    const beforeStatus = before.status;
    const afterStatus = request.action === "edit"
      ? beforeStatus
      : ACTION_STATUS[request.action];
    if (request.action !== "edit") catalogSheet.getRange(row, 12).setValue(afterStatus);

    updateQueueDecision_(queueSheet, request, afterStatus);
    auditSheet.appendRow([
      new Date(),
      getReviewerEmail_(),
      request.action,
      request.groupId,
      request.uuid,
      row,
      beforeStatus,
      afterStatus,
      JSON.stringify(Object.keys(fields)),
      request.note,
    ]);

    SpreadsheetApp.flush();
    return {
      ok: true,
      item: readCatalogItemAtRow_(catalogSheet, row),
      message: decisionMessage_(request.action),
    };
  } finally {
    lock.releaseLock();
  }
}

function assertAuthorized_() {
  const properties = PropertiesService.getScriptProperties();
  const owner = String(properties.getProperty(REVIEW_DESK.PROP_OWNER_EMAIL) || "")
    .trim()
    .toLowerCase();
  if (!owner) {
    throw new Error("缺少 AP_REVIEW_OWNER_EMAIL Script Property；Review Desk 拒絕啟動。");
  }
  const reviewer = getReviewerEmail_().toLowerCase();
  if (!reviewer || reviewer !== owner) {
    throw new Error("此 Review Desk 僅限授權帳號使用。");
  }
}

function getReviewerEmail_() {
  return String(
    Session.getActiveUser().getEmail()
    || Session.getEffectiveUser().getEmail()
    || ""
  ).trim();
}

function getSpreadsheet_() {
  const sheetId = String(
    PropertiesService.getScriptProperties().getProperty(REVIEW_DESK.PROP_SHEET_ID) || ""
  ).trim();
  if (!sheetId) throw new Error("缺少 AP_SHEET_ID Script Property。");
  return SpreadsheetApp.openById(sheetId);
}

function ensureSheet_(spreadsheet, name, headers) {
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) sheet = spreadsheet.insertSheet(name);
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  } else {
    const current = sheet.getRange(1, 1, 1, headers.length).getDisplayValues()[0];
    if (current.join("|") !== headers.join("|")) {
      throw new Error(`${name} 欄位與 Review Desk 契約不一致；未自動覆寫。`);
    }
  }
  sheet.setFrozenRows(1);
  return sheet;
}

function formatSupportSheet_(sheet, widths) {
  sheet.getRange(1, 1, 1, widths.length)
    .setBackground("#2c2c2c")
    .setFontColor("#f7f4ed")
    .setFontWeight("bold");
  widths.forEach((width, index) => sheet.setColumnWidth(index + 1, width));
}

function seedQueue_(queueSheet) {
  const existingKeys = {};
  readQueueRows_(queueSheet).forEach((row) => {
    existingKeys[`${row.groupId}|${row.uuid}`] = true;
  });
  const rows = [];
  INITIAL_DUPLICATE_GROUPS.forEach((group) => {
    group.members.forEach((member) => {
      const key = `${group.groupId}|${member[0]}`;
      if (!existingKeys[key]) {
        rows.push([
          group.groupId,
          member[0],
          member[1],
          member[2],
          group.reason,
          "",
          "待審",
          "",
          new Date(),
        ]);
      }
    });
  });
  if (rows.length) {
    queueSheet.getRange(queueSheet.getLastRow() + 1, 1, rows.length, QUEUE_HEADERS.length)
      .setValues(rows);
  }
}

function loadCatalogItems_(spreadsheet) {
  const sheet = spreadsheet.getSheets()[REVIEW_DESK.CATALOG_SHEET_INDEX];
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  const values = sheet.getRange(2, 1, lastRow - 1, 13).getDisplayValues();
  const formulas = sheet.getRange(2, 1, lastRow - 1, 13).getFormulas();
  return values
    .map((row, index) => mapCatalogRow_(row, formulas[index], index + 2))
    .filter((item) => item.uuid && item.itemName && item.userCaption !== "系統日誌");
}

function readCatalogItemAtRow_(sheet, rowNumber) {
  const values = sheet.getRange(rowNumber, 1, 1, 13).getDisplayValues()[0];
  const formulas = sheet.getRange(rowNumber, 1, 1, 13).getFormulas()[0];
  return mapCatalogRow_(values, formulas, rowNumber);
}

function mapCatalogRow_(row, formulas, rowNumber) {
  const imageUrl = extractHyperlinkUrl_(formulas[9]) || row[9] || "";
  return {
    sourceRow: rowNumber,
    uuid: row[0] || "",
    uploadedAt: row[1] || "",
    userCaption: row[2] || "",
    itemName: row[3] || "",
    category: row[4] || "",
    era: row[5] || "",
    story: row[6] || "",
    refItem: row[7] || "",
    refPrice: row[8] || "",
    imageUrl,
    thumbnailUrl: toDriveThumbnailUrl_(imageUrl, 1200),
    tags: row[10] || "",
    status: row[11] || "",
    displayRecommendation: row[12] || "",
  };
}

function extractHyperlinkUrl_(formula) {
  const match = String(formula || "").match(/=HYPERLINK\("([^"]+)"/i);
  return match ? match[1] : "";
}

function getDriveFileId_(value) {
  const text = String(value || "");
  const pathMatch = text.match(/\/file\/d\/([A-Za-z0-9_-]+)/);
  if (pathMatch) return pathMatch[1];
  const queryMatch = text.match(/[?&]id=([A-Za-z0-9_-]+)/);
  return queryMatch ? queryMatch[1] : "";
}

function toDriveThumbnailUrl_(value, size) {
  const id = getDriveFileId_(value);
  return id ? `https://drive.google.com/thumbnail?id=${id}&sz=w${size || 1000}` : "";
}

function readQueueRows_(queueSheet) {
  const lastRow = queueSheet.getLastRow();
  if (lastRow < 2) return [];
  return queueSheet.getRange(2, 1, lastRow - 1, QUEUE_HEADERS.length)
    .getDisplayValues()
    .map((row, index) => ({
      row: index + 2,
      groupId: row[0],
      uuid: row[1],
      sourceRowAtSeed: row[2],
      recommendedRole: row[3],
      reviewReason: row[4],
      imageFingerprint: row[5],
      reviewStatus: row[6],
      reviewerNote: row[7],
      updatedAt: row[8],
    }))
    .filter((row) => row.groupId && row.uuid);
}

function findCatalogRowByUuid_(sheet, uuid) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return 0;
  const uuids = sheet.getRange(2, 1, lastRow - 1, 1).getDisplayValues();
  const offset = uuids.findIndex((row) => row[0] === uuid);
  return offset < 0 ? 0 : offset + 2;
}

function normalizeDecision_(payload) {
  if (!payload || typeof payload !== "object") throw new Error("缺少審核資料。");
  const action = String(payload.action || "").trim();
  if (action !== "edit" && !Object.prototype.hasOwnProperty.call(ACTION_STATUS, action)) {
    throw new Error("不支援的審核操作。");
  }
  const uuid = String(payload.uuid || "").trim();
  if (!uuid) throw new Error("缺少藏品 UUID。");
  return {
    action,
    uuid,
    groupId: String(payload.groupId || "").trim(),
    fields: payload.fields || {},
    note: String(payload.note || "").trim().slice(0, 1000),
  };
}

function sanitizeEditableFields_(fields) {
  if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
    throw new Error("編輯欄位格式錯誤。");
  }
  const clean = {};
  Object.keys(fields).forEach((fieldName) => {
    const rule = EDITABLE_FIELDS[fieldName];
    if (!rule) throw new Error(`欄位 ${fieldName} 不允許由 Review Desk 編輯。`);
    const value = String(fields[fieldName] == null ? "" : fields[fieldName]).trim();
    if (rule.required && !value) throw new Error(`${rule.label}不可留白。`);
    if (value.length > rule.maxLength) throw new Error(`${rule.label}超過字數上限。`);
    if (/^[=+\-@]/.test(value)) throw new Error(`${rule.label}不可使用試算表公式開頭。`);
    if (fieldName === "era" && value && VALID_ERAS.indexOf(value) < 0) {
      throw new Error("年代必須使用既有九項枚舉。");
    }
    if (fieldName === "imageUrl" && value && !/^https:\/\//i.test(value)) {
      throw new Error("Drive 圖片 URL 必須使用 https:// 網址。");
    }
    clean[fieldName] = value;
  });
  return clean;
}

function validatePublishable_(item) {
  ["itemName", "category", "era"].forEach((fieldName) => {
    if (!String(item[fieldName] || "").trim()) {
      throw new Error(`上架前必須完成${EDITABLE_FIELDS[fieldName].label}。`);
    }
  });
  if (VALID_ERAS.indexOf(item.era) < 0) {
    throw new Error("上架前請把年代改為既有九項枚舉之一。影像判讀不能直接作為真偽或斷代結論。");
  }
}

function updateQueueDecision_(queueSheet, request, status) {
  readQueueRows_(queueSheet).forEach((queueRow) => {
    if (queueRow.uuid === request.uuid
      && (!request.groupId || queueRow.groupId === request.groupId)) {
      queueSheet.getRange(queueRow.row, 7, 1, 3).setValues([[
        request.action === "edit" ? queueRow.reviewStatus : status,
        request.note || queueRow.reviewerNote,
        new Date(),
      ]]);
    }
  });
}

function buildSummary_(groups) {
  const summary = {
    groups: groups.length,
    items: 0,
    awaitingReview: 0,
    published: 0,
    archived: 0,
    rejected: 0,
  };
  groups.forEach((group) => group.items.forEach((item) => {
    summary.items += 1;
    if (!item.reviewStatus || item.reviewStatus === "待審") summary.awaitingReview += 1;
    if (item.status === CATALOG_STATUS.PUBLISHED) summary.published += 1;
    else if (item.status === CATALOG_STATUS.ARCHIVED) summary.archived += 1;
    else if (item.status === CATALOG_STATUS.REJECTED) summary.rejected += 1;
  }));
  return summary;
}

function decisionMessage_(action) {
  return {
    publish: "已上架；公開 API 將於下次載入讀取此筆資料。",
    hold: "已保留為待人工覆核，公開頁不顯示。",
    archive: "已下架封存，可日後恢復。",
    reject: "已標記退件，資料仍保留供稽核。",
    edit: "欄位已更新並留下變更紀錄。",
  }[action];
}
