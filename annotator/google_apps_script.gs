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
 *   POST  body:{action:"lookup", text:string}    → Tamil dictionary lookup
 *                                                  (Tamil Wiktionary, see ADR 0006)
 *   POST  body:{action:"log", ...telemetry}      → append a telemetry row
 *   POST  body:{verse_id, source_text, ...}      → upsert a verse annotation
 *   GET   ?text=<corpus_id>                      → list saved annotations for a corpus
 *
 * Design notes:
 *   - All Tamil-text payloads use POST (URL length truncation prevented).
 *   - Audio never touches Apps Script. The browser streams directly to
 *     Soniox via WebSocket using a short-lived temporary API key.
 *   - Dictionary lookup proxies the Tamil Wiktionary `extracts` API;
 *     no API key required. Phase 2 plan: add a self-hosted UMTL backend
 *     behind the same /lookup endpoint (ADR 0006).
 *   - Telemetry rows go to a dedicated `_telemetry` tab, async-safe.
 *
 * Setup:
 *   In Project Settings → Script Properties, set:
 *     SONIOX_API_KEY    = sk_live_xxxx (from soniox.com dashboard)
 *
 *   No dictionary key is required — Tamil Wiktionary is queried without
 *   authentication. The Soniox key never reaches the browser.
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


// ─── Tamil dictionary lookup (Tamil Wiktionary at runtime) ────────────────

/**
 * Looks up a Tamil word in Tamil Wiktionary (ta.wiktionary.org) via the
 * MediaWiki extracts API. Returns the same {form, lemma, definitions[],
 * source} shape the frontend already consumes, so the UI is unchanged.
 *
 * This is Phase 1's dictionary-lookup backend, decided in ADR 0006.
 * Phase 2 plans to add a self-hosted UMTL backend behind the same
 * /lookup endpoint, so swapping providers is a server-side change only.
 */
function handleLookup(body) {
  const text = String(body.text || '').trim();
  if (!text) return { error: 'text is required', provider: 'wiktionary' };

  const start = Date.now();
  const url = 'https://ta.wiktionary.org/w/api.php?' +
    'action=query' +
    '&prop=extracts' +
    '&explaintext=1' +
    '&titles=' + encodeURIComponent(text) +
    '&format=json' +
    '&redirects=1';

  const res = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      // Wikimedia requests a User-Agent that identifies the consumer so
      // they can contact us if our usage causes problems.
      'User-Agent': 'SentamizhCorpus/0.1 (+https://github.com/indic-corpora/sentamizh-corpus)',
    },
  });
  const latency = Date.now() - start;

  if (res.getResponseCode() >= 300) {
    return {
      error: 'wiktionary failed: ' + res.getResponseCode(),
      provider: 'wiktionary',
      latency_ms: latency,
    };
  }

  let data;
  try { data = JSON.parse(res.getContentText()); }
  catch (err) {
    return { error: 'wiktionary returned non-JSON', provider: 'wiktionary', latency_ms: latency };
  }

  // The extracts API shape is:
  //   { query: { pages: { "<pageid>": { title, extract } } } }
  // For missing words it's:
  //   { query: { pages: { "-1": { missing: "" } } } }
  const pages = (data && data.query && data.query.pages) || {};
  const pageKey = Object.keys(pages)[0];
  const page = pages[pageKey] || {};

  if (page.missing !== undefined || !page.extract) {
    // Word not found in Tamil Wiktionary. Frontend renders this as
    // "இந்த வார்த்தை அகராதியில் இல்லை" (not in dictionary).
    return {
      text: text,
      entries: [],
      provider: 'wiktionary',
      latency_ms: latency,
    };
  }

  const definitions = parseWiktionaryExtract(page.extract);
  if (!definitions.length) {
    return {
      text: text,
      entries: [],
      provider: 'wiktionary',
      latency_ms: latency,
    };
  }

  return {
    text: text,
    entries: [{
      form: text,
      lemma: text,
      definitions: definitions,
      source: 'Tamil Wiktionary',
    }],
    provider: 'wiktionary',
    latency_ms: latency,
  };
}

/**
 * Splits a Wiktionary "extract" plain-text response into a list of
 * candidate definition lines. Returns at most 5 lines, each between
 * 5 and 500 characters. Defensive against extracts that have section
 * headings, blank lines, or extremely long single paragraphs.
 */
function parseWiktionaryExtract(extract) {
  const text = String(extract || '').trim();
  if (!text) return [];

  // Split on newlines first; many extracts come as one definition per line
  // or grouped under section headings.
  const lines = text.split(/\n+/)
    .map(function (s) { return s.trim(); })
    .filter(function (s) { return s.length > 0; });

  var defs = [];
  for (var i = 0; i < lines.length && defs.length < 5; i++) {
    var line = lines[i];
    // Skip section markers and very short headings like "தமிழ்" or "Tamil"
    if (line.length < 5) continue;
    // Skip lines that look like pure heading markers
    if (/^[=#\-\s]+$/.test(line)) continue;
    // Skip overly long walls of text — probably etymology paragraphs
    if (line.length > 500) {
      defs.push(line.substring(0, 280).trim() + '…');
      continue;
    }
    defs.push(line);
  }

  // If splitting by line yielded nothing usable, fall back to first 280 chars
  if (defs.length === 0) {
    defs.push(text.substring(0, 280).trim());
  }
  return defs;
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


// ─── One-time authorization ───────────────────────────────────────────────

/**
 * Run this ONCE from the Apps Script editor (function dropdown → authorize →
 * Run) any time the manifest's scopes change. It touches each scoped API so
 * Apps Script prompts for OAuth consent on all of them at once.
 *
 * Why it exists: clasp push / clasp deploy do not trigger consent. The web
 * app runs as USER_DEPLOYING, and if USER_DEPLOYING has never authorized a
 * scope, calls into that scope at runtime fail with:
 *
 *   "You do not have permission to call UrlFetchApp.fetch.
 *    Required permissions: https://www.googleapis.com/auth/script.external_request"
 *
 * Running this function from the editor is the only way to grant consent.
 * No-op once consent is granted (calls are cheap, results are discarded).
 *
 * Add a touch for any new scope here when the manifest grows.
 */
function authorize() {
  // script.external_request — needed by handleLookup (Wiktionary) and
  // handleTranscribeToken (Soniox).
  UrlFetchApp.fetch('https://ta.wiktionary.org/w/api.php?action=query&format=json&meta=siteinfo', {
    muteHttpExceptions: true,
  });

  // spreadsheets.currentonly — needed by handleAnnotation, handleLog, doGet.
  SpreadsheetApp.getActiveSpreadsheet().getName();

  // script.scriptapp — needed if we ever call ScriptApp.getOAuthToken() or
  // similar. Currently unused, but the manifest declares it.
  ScriptApp.getScriptId();

  Logger.log('authorize(): all manifest scopes consented. Live deploys can now call UrlFetchApp + SpreadsheetApp.');
}
