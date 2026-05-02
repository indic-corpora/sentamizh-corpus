/**
 * Sentamizh Corpus — Annotation Backend (Google Apps Script) — Phase 1
 *
 * Paste into a new Apps Script project bound to a Google Sheet, then deploy
 * as a Web App with "Anyone" access. The deployment URL goes into
 * annotator/index.html → CONFIG.APPS_SCRIPT_URL.
 *
 * Endpoints (all under one Web App URL):
 *
 *   POST  body:{action:"transcribe-token"}      → mint a Soniox temp API key
 *   POST  body:{action:"lookup", text:string}    → Tamil dictionary lookup (Agarathi)
 *   POST  body:{action:"log", ...telemetry}      → append a telemetry row
 *   POST  body:{verse_id, source_text, ...}      → upsert a verse annotation
 *   GET   ?text=<corpus_id>                      → list saved annotations for a corpus
 *
 * Design notes:
 *   - All Tamil-text payloads use POST (URL length truncation prevented).
 *   - Audio never touches Apps Script. The browser streams directly to
 *     Soniox via WebSocket using a short-lived temporary API key.
 *   - The dictionary lookup proxies Agarathi's REST API; sandhi splitting
 *     is deferred to Phase 1.5 (we look up the user's selection as-is).
 *   - Telemetry rows go to a dedicated `_telemetry` tab, async-safe.
 *
 * Setup:
 *   In Project Settings → Script Properties, set:
 *     SONIOX_API_KEY    = sk_live_xxxx (from soniox.com dashboard)
 *     AGARATHI_API_KEY  = your X-Agarathi-Api-Secret value
 *
 *   These never reach the browser.
 */

const ANNOTATION_COLUMNS = [
  'verse_id', 'source_text', 'verse_number', 'classical_tamil',
  'modern_tamil', 'english',
  'thinai', 'turai', 'akam_or_puram',
  'karu', 'uri', 'ullurai',
  'speaker_role', 'metre', 'pann', 'dhvani_layer',
  'rasa_primary', 'rasa_secondary', 'themes',
  'philosophical_concept', 'cultural_context',
  'storytelling_seed_narrative', 'storytelling_seed_emotional',
  'nayika_bheda', 'visual_imagery', 'emotional_valence',
  'annotator', 'annotation_confidence',
  '_updated_at',
];

const TELEMETRY_COLUMNS = [
  'timestamp', 'session_id', 'endpoint', 'provider', 'status',
  'latency_ms', 'input_chars', 'output_chars',
  'audio_seconds', 'cost_estimate_usd',
  'verse_id', 'extra_json',
];


// ─── Routing ───────────────────────────────────────────────────────────────

function doGet(e) {
  try {
    const textId = (e.parameter.text || '').toLowerCase();
    if (!textId) return jsonResponse({ error: 'missing text param' });
    const sheet = sheetForText(textId);
    if (!sheet) return jsonResponse({});
    return jsonResponse(readAnnotationSheet(sheet));
  } catch (err) {
    return jsonResponse({ error: String(err) });
  }
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    const action = body.action || null;

    if (action === 'transcribe-token') {
      return jsonResponse(handleTranscribeToken(body));
    }
    if (action === 'lookup') {
      return jsonResponse(handleLookup(body));
    }
    if (action === 'log') {
      return jsonResponse(handleLog(body));
    }
    // Default: annotation upsert
    if (!body.verse_id || !body.source_text) {
      return jsonResponse({ error: 'verse_id and source_text are required' });
    }
    return jsonResponse(handleAnnotation(body));
  } catch (err) {
    return jsonResponse({ error: String(err) });
  }
}


// ─── Soniox temporary STT key ──────────────────────────────────────────────

function handleTranscribeToken(body) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('SONIOX_API_KEY');
  if (!apiKey) {
    return { error: 'SONIOX_API_KEY not configured', provider: 'soniox' };
  }

  const expires = Math.min(Math.max(parseInt(body.expires_in_seconds || '600'), 60), 3600);
  const sessionId = String(body.session_id || '').slice(0, 256);

  const start = Date.now();
  const res = UrlFetchApp.fetch('https://api.soniox.com/v1/auth/temporary-api-key', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + apiKey },
    payload: JSON.stringify({
      usage_type: 'transcribe_websocket',
      expires_in_seconds: expires,
      client_reference_id: sessionId || undefined,
    }),
    muteHttpExceptions: true,
  });
  const latency = Date.now() - start;

  if (res.getResponseCode() >= 300) {
    return {
      error: 'soniox auth failed: ' + res.getResponseCode(),
      provider: 'soniox',
      latency_ms: latency,
    };
  }
  const data = JSON.parse(res.getContentText());
  return {
    api_key: data.api_key,
    expires_at: data.expires_at,
    provider: 'soniox',
    latency_ms: latency,
  };
}


// ─── Tamil dictionary lookup (Agarathi → UMTL + others) ───────────────────

function handleLookup(body) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('AGARATHI_API_KEY');
  if (!apiKey) {
    return { error: 'AGARATHI_API_KEY not configured', provider: 'agarathi' };
  }
  const text = String(body.text || '').trim();
  if (!text) return { error: 'text is required', provider: 'agarathi' };

  const start = Date.now();
  const res = UrlFetchApp.fetch('https://api.agarathi.com/dictionary/search', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Agarathi-Api-Secret': apiKey },
    payload: JSON.stringify({ word: text }),
    muteHttpExceptions: true,
  });
  const latency = Date.now() - start;

  if (res.getResponseCode() >= 300) {
    return {
      error: 'agarathi failed: ' + res.getResponseCode() + ' ' + res.getContentText().slice(0, 200),
      provider: 'agarathi',
      latency_ms: latency,
    };
  }

  let data;
  try { data = JSON.parse(res.getContentText()); }
  catch (err) {
    return { error: 'agarathi returned non-JSON', provider: 'agarathi', latency_ms: latency };
  }

  // Normalize Agarathi's response into a consistent shape: an array of
  // {form, lemma, definitions[], source} objects. Agarathi structures
  // entries by source dictionary; we flatten and surface UMTL first.
  // Each Agarathi entry is shaped {dictionary, word, description}; the
  // definition text lives in `description` (a single string). A few
  // dictionaries instead expose meanings/meaning/definitions arrays, so
  // we fall back to those for forward compatibility.
  const entries = [];
  const contents = (data && data.contents) || [];
  contents.forEach((entry) => {
    if (!entry) return;
    const source = entry.dictionary || entry.source || 'unknown';
    const definitions = [];
    if (typeof entry.description === 'string' && entry.description.trim()) {
      definitions.push(entry.description.trim());
    }
    const meanings = entry.meanings || entry.meaning || entry.definitions || [];
    if (Array.isArray(meanings)) {
      meanings.forEach((m) => {
        if (typeof m === 'string' && m.trim()) definitions.push(m.trim());
        else if (m && (m.text || m.meaning)) definitions.push(m.text || m.meaning);
      });
    } else if (typeof meanings === 'string' && meanings.trim()) {
      definitions.push(meanings.trim());
    }
    entries.push({
      form: entry.word || text,
      lemma: entry.lemma || entry.headword || entry.word || text,
      definitions: definitions,
      source: source,
    });
  });
  // Stable order: UMTL first, then others.
  entries.sort((a, b) => {
    const score = (s) => /madras|umtl/i.test(String(s)) ? 0 : 1;
    return score(a.source) - score(b.source);
  });

  return {
    text: text,
    entries: entries,
    provider: 'agarathi',
    latency_ms: latency,
  };
}


// ─── Telemetry log (best-effort, fire-and-forget) ─────────────────────────

function handleLog(body) {
  try {
    const sheet = ensureTelemetrySheet();
    const row = TELEMETRY_COLUMNS.map((col) => {
      if (col === 'timestamp') return new Date().toISOString();
      if (col === 'extra_json') {
        const used = new Set(TELEMETRY_COLUMNS);
        const extra = {};
        Object.keys(body).forEach((k) => { if (!used.has(k)) extra[k] = body[k]; });
        return Object.keys(extra).length ? JSON.stringify(extra) : '';
      }
      const v = body[col];
      if (v === null || v === undefined) return '';
      if (Array.isArray(v) || (typeof v === 'object' && v !== null)) return JSON.stringify(v);
      return v;
    });
    sheet.appendRow(row);
    return { ok: true };
  } catch (err) {
    // Telemetry failures must never affect the user.
    return { ok: false, reason: String(err) };
  }
}

function ensureTelemetrySheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('_telemetry');
  if (!sheet) {
    sheet = ss.insertSheet('_telemetry');
    sheet.getRange(1, 1, 1, TELEMETRY_COLUMNS.length).setValues([TELEMETRY_COLUMNS]);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, TELEMETRY_COLUMNS.length).setFontWeight('bold');
  }
  return sheet;
}


// ─── Annotation upsert & read ─────────────────────────────────────────────

function handleAnnotation(body) {
  const textId = String(body.source_text)
    .toLowerCase().replace(/\s+/g, '_').replace(/[^a-z_]/g, '');
  const sheet = ensureAnnotationSheet(textId);
  upsertAnnotationRow(sheet, body);
  return { ok: true };
}

function ensureAnnotationSheet(textId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(textId);
  if (!sheet) {
    sheet = ss.insertSheet(textId);
    sheet.getRange(1, 1, 1, ANNOTATION_COLUMNS.length).setValues([ANNOTATION_COLUMNS]);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, ANNOTATION_COLUMNS.length).setFontWeight('bold');
  } else {
    const range = sheet.getRange(1, 1, 1, sheet.getLastColumn() || 1);
    const existing = range.getValues()[0];
    if (existing.join(',') !== ANNOTATION_COLUMNS.join(',')) {
      sheet.getRange(1, 1, 1, ANNOTATION_COLUMNS.length).setValues([ANNOTATION_COLUMNS]);
    }
  }
  return sheet;
}

function sheetForText(textId) {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(textId);
}

function readAnnotationSheet(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return {};
  const values = sheet.getRange(2, 1, lastRow - 1, ANNOTATION_COLUMNS.length).getValues();
  const out = {};
  values.forEach((row) => {
    const obj = {};
    let verseId = '';
    ANNOTATION_COLUMNS.forEach((col, idx) => {
      let v = row[idx];
      if (v === '' || v === null || v === undefined) {
        obj[col] = null;
      } else if (col === 'emotional_valence' && typeof v === 'string' && v.startsWith('{')) {
        try { obj[col] = JSON.parse(v); } catch { obj[col] = v; }
      } else if (
        ['rasa_secondary', 'themes', 'karu', 'visual_imagery'].includes(col)
        && typeof v === 'string' && v.startsWith('[')
      ) {
        try { obj[col] = JSON.parse(v); } catch { obj[col] = v; }
      } else {
        obj[col] = v;
      }
      if (col === 'verse_id') verseId = v;
    });
    if (verseId) out[verseId] = obj;
  });
  return out;
}

function upsertAnnotationRow(sheet, annotation) {
  const verseId = annotation.verse_id;
  const lastRow = sheet.getLastRow();
  let targetRow = -1;
  if (lastRow >= 2) {
    const ids = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < ids.length; i++) {
      if (ids[i][0] === verseId) { targetRow = i + 2; break; }
    }
  }
  const row = ANNOTATION_COLUMNS.map((col) => {
    let v = annotation[col];
    if (v === null || v === undefined) return '';
    if (Array.isArray(v) || (typeof v === 'object' && v !== null)) return JSON.stringify(v);
    return v;
  });
  if (targetRow > 0) {
    sheet.getRange(targetRow, 1, 1, ANNOTATION_COLUMNS.length).setValues([row]);
  } else {
    sheet.appendRow(row);
  }
}


// ─── Helpers ──────────────────────────────────────────────────────────────

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
