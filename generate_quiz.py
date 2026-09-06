#!/usr/bin/env python3
"""
generate_quiz.py
Reads every sheet from sian_questions.ods (quiz) and
sian_questions-answer-key.ods (correct mappings), then writes index.html.

Run this whenever you update the ODS files:
    python generate_quiz.py
Then upload the new index.html to GitHub.
"""

import json
import sys
from pathlib import Path

QUIZ_FILE = Path(__file__).parent / "sian_questions.ods"
KEY_FILE  = Path(__file__).parent / "sian_questions-answer-key.ods"
OUT_FILE  = Path(__file__).parent / "index.html"


# ── ODS helpers ────────────────────────────────────────────────────────────

def load_sheet_rows(filepath, sheet_name):
    """Return list of (serial_str, english, bangla) from one sheet."""
    import pandas as pd
    df = pd.read_excel(str(filepath), engine="odf",
                       sheet_name=sheet_name, header=None)
    rows = []
    for _, row in df.iterrows():
        a = str(row.iloc[0]).strip() if len(row) > 0 else ""
        b = str(row.iloc[1]).strip() if len(row) > 1 else ""
        c = str(row.iloc[2]).strip() if len(row) > 2 else ""
        if a.isdigit() and b and c \
                and b.lower() != "nan" and c.lower() != "nan":
            rows.append((a, b, c))
    return rows


def sheet_title(filepath, sheet_name):
    """Return the display title from row 0 col 0 (falls back to sheet name)."""
    import pandas as pd
    df = pd.read_excel(str(filepath), engine="odf",
                       sheet_name=sheet_name, header=None)
    val = str(df.iloc[0, 0]).strip()
    return val if val and val.lower() != "nan" else sheet_name


def build_quizzes():
    import pandas as pd

    quiz_xl = pd.ExcelFile(str(QUIZ_FILE), engine="odf")
    key_xl  = pd.ExcelFile(str(KEY_FILE),  engine="odf")

    # Case-insensitive lookup for key sheets
    key_map = {s.lower(): s for s in key_xl.sheet_names}

    quizzes = []
    for sheet in quiz_xl.sheet_names:
        matched_key = key_map.get(sheet.lower(), None)

        try:
            quiz_rows = load_sheet_rows(QUIZ_FILE, sheet)
            key_rows  = load_sheet_rows(KEY_FILE, matched_key or sheet) \
                        if matched_key else quiz_rows
        except Exception as exc:
            print(f"  Skipping sheet '{sheet}': {exc}")
            continue

        if not quiz_rows:
            continue

        title = sheet_title(QUIZ_FILE, sheet)

        # Build correct English→Bangla lookup from answer key
        key_by_eng = {eng.lower(): (ser, ban) for ser, eng, ban in key_rows}

        words = []
        for serial, english, fallback_bangla in quiz_rows:
            if english.lower() in key_by_eng:
                _, bangla = key_by_eng[english.lower()]
            else:
                bangla = fallback_bangla
            words.append({"serial": int(serial),
                          "english": english,
                          "bangla": bangla})

        quizzes.append({"id": sheet.replace(" ", "_"),
                        "title": title,
                        "sheet": sheet,
                        "words": words})
        print(f"  Loaded: {title!r}  ({len(words)} words)")

    return quizzes


# ── HTML template ──────────────────────────────────────────────────────────
# (All screens: name entry, home, quiz, scores/leaderboard)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bangla Quiz</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Segoe UI', Arial, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh; padding: 24px 16px;
    }

    /* ── Card shell (shared) ── */
    .card {
      max-width: 800px; margin: 0 auto; background: #fff;
      border-radius: 20px; box-shadow: 0 24px 64px rgba(0,0,0,.35);
      overflow: hidden; display: none;
    }
    .card.active { display: block; }
    header {
      background: linear-gradient(135deg, #1a237e, #3949ab);
      color: #fff; padding: 20px 28px 16px;
    }
    header h1 { font-size: 1.6rem; }
    header p  { margin-top: 4px; font-size: .88rem; opacity: .85; }

    /* ── Name screen ── */
    .name-body {
      padding: 48px 32px; text-align: center;
    }
    .name-body .wave { font-size: 3.5rem; margin-bottom: 12px; }
    .name-body h2    { font-size: 1.5rem; color: #1a237e; margin-bottom: 6px; }
    .name-body p     { color: #666; margin-bottom: 24px; }
    .name-body input {
      width: 280px; max-width: 100%; padding: 12px 16px;
      border: 2px solid #c5cae9; border-radius: 12px;
      font-size: 1.1rem; text-align: center; outline: none;
      transition: border-color .2s;
    }
    .name-body input:focus { border-color: #3949ab; }
    .name-body .start-btn {
      display: block; margin: 16px auto 0; padding: 12px 36px;
      background: #1a237e; color: #fff; border: none;
      border-radius: 12px; font-size: 1rem; font-weight: 700;
      cursor: pointer; transition: filter .15s;
    }
    .name-body .start-btn:hover { filter: brightness(1.15); }

    /* ── Home screen ── */
    .home-header-inner {
      display: flex; justify-content: space-between;
      align-items: flex-start; gap: 12px;
    }
    .home-nav { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .home-nav button {
      padding: 6px 13px; border: none; border-radius: 8px;
      font-size: .82rem; font-weight: 700; cursor: pointer;
      transition: filter .15s; white-space: nowrap;
    }
    .home-nav button:hover { filter: brightness(1.12); }
    .btn-scores   { background: #fff; color: #1a237e; }
    .btn-top10    { background: #FFD700; color: #5d4000; }
    .btn-player   { background: rgba(255,255,255,.25); color: #fff; }

    .quiz-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
      gap: 14px; padding: 22px;
    }
    .quiz-card {
      background: linear-gradient(135deg, #e8eaf6, #c5cae9);
      border: 2px solid #9fa8da; border-radius: 14px;
      padding: 20px 14px; text-align: center; cursor: pointer;
      transition: transform .15s, box-shadow .15s; user-select: none;
    }
    .quiz-card:hover  { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.18); }
    .quiz-card:active { transform: scale(.96); }
    .quiz-card .icon  { font-size: 2rem; margin-bottom: 8px; }
    .quiz-card .label { font-size: .95rem; font-weight: 700; color: #1a237e; line-height: 1.3; }
    .quiz-card .count { font-size: .78rem; color: #555; margin-top: 4px; }
    .quiz-card .best  { font-size: .78rem; margin-top: 4px; font-weight: 700; }

    /* ── Quiz screen ── */
    .quiz-header-row {
      display: flex; align-items: center; gap: 10px; padding: 12px 18px 0;
    }
    .back-btn {
      background: #e8eaf6; border: none; border-radius: 8px;
      padding: 7px 13px; font-size: .88rem; font-weight: 700;
      color: #1a237e; cursor: pointer; white-space: nowrap;
    }
    .back-btn:hover { background: #c5cae9; }
    #quiz-title { font-size: 1rem; font-weight: 700; color: #1a237e; }

    .table-wrap { padding: 10px 16px 6px; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    thead tr { background: #283593; color: #fff; }
    thead th { padding: 9px 12px; text-align: left; font-size: .83rem; white-space: nowrap; }
    tbody tr:nth-child(odd)  { background: #fff; }
    tbody tr:nth-child(even) { background: #f3f4fb; }
    tbody tr { transition: background .25s; }
    td { padding: 9px 12px; vertical-align: middle; }
    td.sl      { text-align: center; font-weight: 700; color: #555; width: 44px; }
    td.english { font-size: .97rem; font-weight: 500; }
    td.bangla  { font-size: 1.05rem; font-weight: 700; color: #1a237e; letter-spacing: .4px; }
    td.answer  { width: 86px; }
    td.answer input {
      width: 64px; padding: 6px 8px; border: 2px solid #bbb;
      border-radius: 8px; font-size: 1rem; text-align: center;
      -moz-appearance: textfield; transition: border-color .2s;
    }
    td.answer input::-webkit-outer-spin-button,
    td.answer input::-webkit-inner-spin-button { -webkit-appearance: none; }
    td.answer input:focus { outline: none; border-color: #3949ab; }
    td.verdict { font-size: .88rem; font-weight: 700; white-space: nowrap; }

    tr.correct td             { background: #e8f5e9 !important; }
    tr.correct td.answer input { background: #c8e6c9; border-color: #43a047; }
    tr.correct td.verdict     { color: #2e7d32; }
    tr.wrong td               { background: #ffebee !important; }
    tr.wrong td.answer input  { background: #ffcdd2; border-color: #e53935; }
    tr.wrong td.verdict       { color: #b71c1c; }
    tr.blank td               { background: #fff8e1 !important; }
    tr.blank td.answer input  { background: #fff9c4; border-color: #ffc107; }
    tr.blank td.verdict       { color: #e65100; }

    .footer {
      background: #f0f2ff; border-top: 1px solid #e0e0e0;
      padding: 12px 18px; display: flex; align-items: center;
      gap: 10px; flex-wrap: wrap;
    }
    button.action {
      padding: 9px 18px; border: none; border-radius: 10px;
      font-size: .92rem; font-weight: 700; cursor: pointer;
      transition: filter .15s, transform .1s;
    }
    button.action:hover  { filter: brightness(1.1); }
    button.action:active { transform: scale(.96); }
    #grade-btn { background: #2e7d32; color: #fff; }
    #new-btn   { background: #1565c0; color: #fff; }
    #score { margin-left: auto; font-size: 1rem; font-weight: 800; }
    #score.gold   { color: #b8860b; }
    #score.silver { color: #607d8b; }
    #score.bronze { color: #8d4e00; }
    #score.low    { color: #b71c1c; }

    /* ── Scores screen ── */
    .scores-top {
      display: flex; align-items: center; gap: 10px; padding: 12px 18px 0;
    }
    .tabs {
      display: flex; gap: 0; border-bottom: 2px solid #e0e0e0; padding: 0 18px;
    }
    .tab {
      padding: 10px 20px; border: none; background: none;
      font-size: .92rem; font-weight: 700; color: #888; cursor: pointer;
      border-bottom: 3px solid transparent; margin-bottom: -2px;
      transition: color .15s, border-color .15s;
    }
    .tab.active { color: #1a237e; border-bottom-color: #1a237e; }

    .scores-body { padding: 14px 18px; min-height: 200px; }

    .scores-table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    .scores-table th {
      background: #283593; color: #fff;
      padding: 8px 10px; text-align: left; white-space: nowrap;
    }
    .scores-table td { padding: 8px 10px; border-bottom: 1px solid #eee; }
    .scores-table tr:hover td { background: #f3f4fb; }
    .medal-cell { font-size: 1.1rem; text-align: center; }
    .rank-cell  { font-weight: 700; color: #1a237e; text-align: center; }
    .pct-cell   { font-weight: 700; }
    .empty-msg  { text-align: center; color: #999; padding: 40px 0; font-size: .95rem; }

    .scores-footer {
      display: flex; gap: 10px; padding: 12px 18px;
      border-top: 1px solid #eee; flex-wrap: wrap;
    }
    .btn-clear { background: #ffebee; color: #c62828; border: none;
      border-radius: 8px; padding: 8px 14px; font-size: .85rem;
      font-weight: 700; cursor: pointer; margin-left: auto; }
    .btn-clear:hover { background: #ffcdd2; }

    /* ── Confetti canvas ── */
    #confetti-canvas {
      position: fixed; inset: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 200;
    }

    /* ── Result overlay ── */
    #overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,.5); z-index: 150;
      align-items: center; justify-content: center;
    }
    #overlay.show { display: flex; }
    .result-box {
      background: #fff; border-radius: 24px;
      padding: 34px 46px; text-align: center;
      box-shadow: 0 20px 60px rgba(0,0,0,.45);
      animation: pop .35s cubic-bezier(.34,1.56,.64,1);
      max-width: 340px; width: 90%;
    }
    @keyframes pop {
      from { transform: scale(.5); opacity: 0; }
      to   { transform: scale(1);  opacity: 1; }
    }
    .result-box .medal { font-size: 4.8rem; line-height: 1; margin-bottom: 10px; }
    .result-box h2     { font-size: 1.55rem; margin-bottom: 8px; }
    .result-box p      { color: #555; font-size: .97rem; margin-bottom: 6px; }
    .result-box .sub   { font-size: .83rem; color: #888; margin-bottom: 20px; }
    .result-box.gold   { border-top: 8px solid #FFD700; }
    .result-box.silver { border-top: 8px solid #C0C0C0; }
    .result-box.bronze { border-top: 8px solid #CD7F32; }
    .result-box.sad    { border-top: 8px solid #90a4ae; }
    .result-box h2.gold   { color: #b8860b; }
    .result-box h2.silver { color: #546e7a; }
    .result-box h2.bronze { color: #6d4c41; }
    .result-box h2.sad    { color: #546e7a; }
    .result-btns { display: flex; gap: 10px; justify-content: center; }
    .btn-again {
      padding: 10px 22px; border: none; border-radius: 12px;
      font-size: .95rem; font-weight: 700; cursor: pointer; color: #fff;
      transition: filter .15s;
    }
    .btn-again:hover { filter: brightness(1.1); }
    .btn-again.gold   { background: #f9a825; }
    .btn-again.silver { background: #607d8b; }
    .btn-again.bronze { background: #8d4e00; }
    .btn-again.sad    { background: #1565c0; }
    .btn-home-after {
      padding: 10px 22px; border: 2px solid #ccc; border-radius: 12px;
      font-size: .95rem; font-weight: 700; cursor: pointer;
      background: #fff; color: #444; transition: border-color .15s;
    }
    .btn-home-after:hover { border-color: #999; }

    @media (max-width: 520px) {
      header h1 { font-size: 1.25rem; }
      td { padding: 7px 7px; font-size: .82rem; }
      td.bangla { font-size: .9rem; }
      td.answer input { width: 50px; }
      .quiz-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
      .result-box { padding: 26px 22px; }
      .scores-table { font-size: .8rem; }
    }
  </style>
</head>
<body>

<canvas id="confetti-canvas"></canvas>

<!-- ══ NAME SCREEN ════════════════════════════════════════════════════════ -->
<div id="screen-name" class="card">
  <header><h1>Bangla Quiz</h1><p>Learn Bangla words the fun way!</p></header>
  <div class="name-body">
    <div class="wave">👋</div>
    <h2>Welcome!</h2>
    <p>What is your name?</p>
    <input type="text" id="name-input" placeholder="Type your name…" maxlength="30"
      onkeydown="if(event.key==='Enter') saveName()">
    <button class="start-btn" onclick="saveName()">Start Quiz →</button>
  </div>
</div>

<!-- ══ HOME SCREEN ════════════════════════════════════════════════════════ -->
<div id="screen-home" class="card">
  <header>
    <div class="home-header-inner">
      <div>
        <h1>Bangla Quiz</h1>
        <p id="home-greeting">Choose a quiz to start</p>
      </div>
      <div class="home-nav">
        <button class="btn-scores" onclick="showScores('my')">📊 My Scores</button>
        <button class="btn-top10"  onclick="showScores('top')">🏆 Top 10</button>
        <button class="btn-player" onclick="changePlayer()">👤 Change Player</button>
      </div>
    </div>
  </header>
  <div class="quiz-grid" id="quiz-grid"></div>
</div>

<!-- ══ QUIZ SCREEN ════════════════════════════════════════════════════════ -->
<div id="screen-quiz" class="card">
  <header><h1>Bangla Quiz</h1><p>Type the Serial # whose English word matches the Bangla word shown</p></header>
  <div class="quiz-header-row">
    <button class="back-btn" onclick="goHome()">&#8592; Back</button>
    <span id="quiz-title"></span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>#</th><th>English Word</th><th>Bangla Word</th><th>Answer with SL#</th><th></th></tr>
      </thead>
      <tbody id="quiz-body"></tbody>
    </table>
  </div>
  <div class="footer">
    <button class="action" id="grade-btn" onclick="grade()">Grade My Answers</button>
    <button class="action" id="new-btn"   onclick="newQuiz()">New Quiz</button>
    <span id="score"></span>
  </div>
</div>

<!-- ══ SCORES SCREEN ══════════════════════════════════════════════════════ -->
<div id="screen-scores" class="card">
  <header><h1>Score History</h1><p id="scores-subtitle"></p></header>
  <div class="scores-top">
    <button class="back-btn" onclick="goHome()">&#8592; Back</button>
  </div>
  <div class="tabs">
    <button class="tab active" id="tab-my-btn"  onclick="switchTab('my')">📋 My Scores</button>
    <button class="tab"        id="tab-top-btn" onclick="switchTab('top')">🏆 Top 10</button>
  </div>
  <div class="scores-body" id="scores-body"></div>
  <div class="scores-footer">
    <button class="btn-clear" onclick="clearMyScores()">🗑 Clear My Scores</button>
  </div>
</div>

<!-- ══ RESULT OVERLAY ════════════════════════════════════════════════════ -->
<div id="overlay" onclick="closeOverlay()">
  <div class="result-box" id="result-box" onclick="event.stopPropagation()">
    <div class="medal" id="r-medal"></div>
    <h2 id="r-heading"></h2>
    <p  id="r-msg"></p>
    <p  class="sub" id="r-sub"></p>
    <div class="result-btns">
      <button class="btn-again"    id="r-btn"      onclick="closeOverlay(); newQuiz()">Try Again</button>
      <button class="btn-home-after"               onclick="closeOverlay(); goHome()">Home</button>
    </div>
  </div>
</div>

<script>
// ── Quiz data ─────────────────────────────────────────────────────────────
const QUIZZES = __QUIZZES_JSON__;

// ── State ─────────────────────────────────────────────────────────────────
let currentQuiz  = null;
let answerKey    = [];
let confettiId   = null;
let currentTab   = 'my';

// ── localStorage helpers ──────────────────────────────────────────────────
const LS_NAME   = 'bq_name';
const LS_SCORES = 'bq_scores';

function getPlayerName() { return localStorage.getItem(LS_NAME) || ''; }
function setPlayerName(n) { localStorage.setItem(LS_NAME, n.trim()); }

function loadScores() {
  try { return JSON.parse(localStorage.getItem(LS_SCORES)) || []; }
  catch { return []; }
}

function saveScore(entry) {
  const scores = loadScores();
  scores.push(entry);
  localStorage.setItem(LS_SCORES, JSON.stringify(scores));
}

function medalEmoji(tier) {
  return { gold:'🏆', silver:'🥈', bronze:'🥉', sad:'😢' }[tier] || '';
}

// ── Screen routing ────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// ── Name screen ───────────────────────────────────────────────────────────
function saveName() {
  const val = document.getElementById('name-input').value.trim();
  if (!val) { document.getElementById('name-input').focus(); return; }
  setPlayerName(val);
  showHome();
}

function changePlayer() {
  document.getElementById('name-input').value = getPlayerName();
  showScreen('screen-name');
}

// ── Home screen ───────────────────────────────────────────────────────────
const ICONS = ["🎨","📚","🌿","⭐","🏠","🐾","🎵","🌈","🍎","🔢","🌍","🦋","🎯"];

function showHome() {
  const name = getPlayerName();
  document.getElementById('home-greeting').textContent =
    `Hi ${name}! Choose a quiz to start`;
  buildHome();
  showScreen('screen-home');
  stopConfetti();
  closeOverlay();
}

function goHome() { showHome(); }

function buildHome() {
  const scores = loadScores();
  const name   = getPlayerName();
  const grid   = document.getElementById('quiz-grid');
  grid.innerHTML = '';

  QUIZZES.forEach((q, i) => {
    // Best score for this player + this quiz
    const mine = scores.filter(s => s.name === name && s.quiz === q.title);
    const best = mine.length ? Math.max(...mine.map(s => s.pct)) : null;
    const bestLabel = best !== null
      ? `<span class="best" style="color:${best===100?'#b8860b':best>=90?'#546e7a':best>=80?'#6d4c41':'#999'}">Best: ${best}% ${medalEmoji(best===100?'gold':best>=90?'silver':best>=80?'bronze':'sad')}</span>`
      : `<span class="best" style="color:#bbb">Not attempted</span>`;

    const card = document.createElement('div');
    card.className = 'quiz-card';
    card.innerHTML = `
      <div class="icon">${ICONS[i % ICONS.length]}</div>
      <div class="label">${q.title}</div>
      <div class="count">${q.words.length} words</div>
      ${bestLabel}`;
    card.onclick = () => startQuiz(q);
    grid.appendChild(card);
  });
}

// ── Quiz logic ────────────────────────────────────────────────────────────
function startQuiz(quiz) {
  currentQuiz = quiz;
  document.getElementById('quiz-title').textContent = quiz.title;
  showScreen('screen-quiz');
  newQuiz();
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function derange(arr) {
  let r, t = 0;
  do { r = shuffle(arr); t++; }
  while (t < 50 && r.some((w, i) => w.serial === arr[i].serial));
  return r;
}

function newQuiz() {
  closeOverlay();
  stopConfetti();
  const words    = currentQuiz.words;
  const shuffled = derange(words);
  answerKey      = shuffled.map(w => w.serial);

  const tbody = document.getElementById('quiz-body');
  tbody.innerHTML = '';
  document.getElementById('score').textContent = '';
  document.getElementById('score').className   = '';

  words.forEach((word, i) => {
    const tr = document.createElement('tr');
    tr.id = `row-${i}`;
    tr.innerHTML = `
      <td class="sl">${word.serial}</td>
      <td class="english">${word.english}</td>
      <td class="bangla">${shuffled[i].bangla}</td>
      <td class="answer">
        <input type="number" id="ans-${i}" min="1" max="${words.length}" placeholder="#"
          onkeydown="if(event.key==='Enter'||event.key==='Tab'){event.preventDefault();focusNext(${i});}">
      </td>
      <td class="verdict" id="v-${i}"></td>`;
    tbody.appendChild(tr);
  });
  document.getElementById('ans-0').focus();
}

function focusNext(i) {
  const next = document.getElementById(`ans-${i + 1}`);
  if (next) next.focus(); else grade();
}

// ── Grading ───────────────────────────────────────────────────────────────
function grade() {
  const total = currentQuiz.words.length;
  let correct = 0;

  currentQuiz.words.forEach((_, i) => {
    const input   = document.getElementById(`ans-${i}`);
    const verdict = document.getElementById(`v-${i}`);
    const row     = document.getElementById(`row-${i}`);
    const val     = input.value.trim();
    const right   = answerKey[i];
    row.className = '';
    if (!val) {
      row.classList.add('blank');
      verdict.textContent = `→ ${right}`;
    } else if (parseInt(val) === right) {
      correct++;
      row.classList.add('correct');
      verdict.textContent = '✓';
    } else {
      row.classList.add('wrong');
      verdict.textContent = `✗ → ${right}`;
    }
  });

  const pct  = Math.round(correct / total * 100);
  const tier = pct === 100 ? 'gold' : pct >= 90 ? 'silver' : pct >= 80 ? 'bronze' : 'sad';

  // Persist score
  const now = new Date();
  saveScore({
    name:    getPlayerName(),
    quiz:    currentQuiz.title,
    correct, total, pct, tier,
    date:    now.toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'}),
    ts:      now.getTime(),
  });

  showResult(correct, total, pct, tier);
}

// ── Result overlay ────────────────────────────────────────────────────────
const MEDALS = {
  gold:   { emoji:'🏆', heading:'GOLD!',  h2:'gold',   confetti:160, scoreLabel:'🏆 Gold!' },
  silver: { emoji:'🥈', heading:'SILVER!', h2:'silver', confetti:90,  scoreLabel:'🥈 Silver!' },
  bronze: { emoji:'🥉', heading:'BRONZE!', h2:'bronze', confetti:45,  scoreLabel:'🥉 Bronze!' },
  sad:    { emoji:'😢', heading:'Better Luck Next Time!', h2:'sad', confetti:0, scoreLabel:'😢' },
};
const CONFETTI_PALETTES = {
  gold:   ['#FFD700','#FFA500','#FF6347','#FF69B4','#00CED1','#9370DB','#32CD32','#fff'],
  silver: ['#C0C0C0','#A8A8A8','#D3D3D3','#87CEEB','#B0C4DE','#E0E0E0','#fff'],
  bronze: ['#CD7F32','#B8860B','#DAA520','#D2691E','#FFA07A','#F4A460'],
};

function showResult(correct, total, pct, tier) {
  const m  = MEDALS[tier];
  const el = document.getElementById('score');
  el.className   = tier === 'sad' ? 'low' : tier;
  el.textContent = tier === 'sad'
    ? `😢  ${correct}/${total} (${pct}%)`
    : `${m.scoreLabel}  ${correct}/${total} (${pct}%)`;

  const box = document.getElementById('result-box');
  box.className = `result-box ${tier}`;
  document.getElementById('r-medal').textContent   = m.emoji;
  document.getElementById('r-heading').textContent = m.heading;
  document.getElementById('r-heading').className   = m.h2;
  document.getElementById('r-btn').className       = `btn-again ${tier}`;

  const msgs = {
    gold:   [`Perfect! All ${total} correct!`,     'Outstanding — you know them all!'],
    silver: [`${correct} out of ${total} (${pct}%)`, 'Excellent! Almost perfect!'],
    bronze: [`${correct} out of ${total} (${pct}%)`, 'Good effort! Keep practising!'],
    sad:    [`${correct} out of ${total} (${pct}%)`, 'Review the answers and try again — you can do it!'],
  };
  document.getElementById('r-msg').textContent = msgs[tier][0];
  document.getElementById('r-sub').textContent = msgs[tier][1];

  setTimeout(() => document.getElementById('overlay').classList.add('show'), 300);
  if (m.confetti > 0) setTimeout(() => launchConfetti(tier, m.confetti), 350);
  if (tier !== 'sad')  setTimeout(() => playSound(tier), 400);
}

function closeOverlay() {
  document.getElementById('overlay').classList.remove('show');
  stopConfetti();
}

// ── Scores screen ─────────────────────────────────────────────────────────
function showScores(tab) {
  const name = getPlayerName();
  document.getElementById('scores-subtitle').textContent =
    `Player: ${name}`;
  showScreen('screen-scores');
  switchTab(tab || 'my');
}

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-my-btn').classList.toggle('active', tab === 'my');
  document.getElementById('tab-top-btn').classList.toggle('active', tab === 'top');
  tab === 'my' ? renderMyScores() : renderTop10();
}

function renderMyScores() {
  const name   = getPlayerName();
  const scores = loadScores()
    .filter(s => s.name === name)
    .sort((a, b) => b.ts - a.ts);   // newest first

  const body = document.getElementById('scores-body');
  if (!scores.length) {
    body.innerHTML = '<p class="empty-msg">No scores yet — take a quiz to get started!</p>';
    return;
  }

  body.innerHTML = `
    <table class="scores-table">
      <thead><tr>
        <th>Date</th><th>Quiz</th><th>Score</th><th>%</th><th>Medal</th>
      </tr></thead>
      <tbody>
        ${scores.map(s => `
          <tr>
            <td>${s.date}</td>
            <td>${s.quiz}</td>
            <td>${s.correct}/${s.total}</td>
            <td class="pct-cell">${s.pct}%</td>
            <td class="medal-cell">${medalEmoji(s.tier)}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function renderTop10() {
  const scores = loadScores()
    .sort((a, b) => b.pct - a.pct || b.ts - a.ts)
    .slice(0, 10);

  const body = document.getElementById('scores-body');
  if (!scores.length) {
    body.innerHTML = '<p class="empty-msg">No scores recorded yet!</p>';
    return;
  }

  body.innerHTML = `
    <table class="scores-table">
      <thead><tr>
        <th>#</th><th>Name</th><th>Quiz</th><th>Score</th><th>%</th><th>Date</th><th>Medal</th>
      </tr></thead>
      <tbody>
        ${scores.map((s, i) => `
          <tr>
            <td class="rank-cell">${i + 1}</td>
            <td><strong>${s.name}</strong></td>
            <td>${s.quiz}</td>
            <td>${s.correct}/${s.total}</td>
            <td class="pct-cell">${s.pct}%</td>
            <td>${s.date}</td>
            <td class="medal-cell">${medalEmoji(s.tier)}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function clearMyScores() {
  const name = getPlayerName();
  if (!confirm(`Delete all scores for "${name}"? This cannot be undone.`)) return;
  const kept = loadScores().filter(s => s.name !== name);
  localStorage.setItem(LS_SCORES, JSON.stringify(kept));
  switchTab(currentTab);
}

// ── Confetti ──────────────────────────────────────────────────────────────
function launchConfetti(tier, count) {
  stopConfetti();
  const canvas = document.getElementById('confetti-canvas');
  const ctx    = canvas.getContext('2d');
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
  const colors = CONFETTI_PALETTES[tier] || CONFETTI_PALETTES.gold;
  const pieces = Array.from({length: count}, () => ({
    x: Math.random() * canvas.width, y: -Math.random() * 120,
    w: Math.random() * 13 + 6, h: Math.random() * 8 + 4,
    color: colors[Math.floor(Math.random() * colors.length)],
    rot: Math.random() * 360, rotV: (Math.random() - 0.5) * 9,
    vx: (Math.random() - 0.5) * 4, vy: Math.random() * 4 + 2, alpha: 1,
  }));
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = false;
    for (const p of pieces) {
      if (p.y < canvas.height + 30 && p.alpha > 0.02) {
        alive = true;
        ctx.save(); ctx.globalAlpha = p.alpha;
        ctx.translate(p.x + p.w / 2, p.y + p.h / 2);
        ctx.rotate(p.rot * Math.PI / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
        p.x += p.vx; p.y += p.vy; p.rot += p.rotV;
        if (p.y > canvas.height * 0.65) p.alpha -= 0.018;
      }
    }
    if (alive) confettiId = requestAnimationFrame(draw);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  draw();
}

function stopConfetti() {
  if (confettiId) { cancelAnimationFrame(confettiId); confettiId = null; }
  const c = document.getElementById('confetti-canvas');
  c.getContext('2d').clearRect(0, 0, c.width, c.height);
}

// ── Sound ─────────────────────────────────────────────────────────────────
function playSound(tier) {
  try {
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    function note(freq, start, dur, vol = 0.35, type = 'triangle') {
      const osc = ac.createOscillator(), gain = ac.createGain();
      osc.connect(gain); gain.connect(ac.destination);
      osc.type = type; osc.frequency.value = freq;
      const t = ac.currentTime + start;
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(vol, t + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
      osc.start(t); osc.stop(t + dur + 0.05);
    }
    if      (tier === 'gold')   [[523,.00],[659,.14],[784,.28],[1047,.42],[1319,.60],[1047,.80],[1319,.95]].forEach(([f,s]) => note(f,s,.45,.4));
    else if (tier === 'silver') [[523,.00],[659,.18],[784,.36]].forEach(([f,s]) => note(f,s,.55,.35,'sine'));
    else if (tier === 'bronze') [[440,.00],[523,.22]].forEach(([f,s]) => note(f,s,.6,.3,'sine'));
  } catch(e) {}
}

// ── Boot ──────────────────────────────────────────────────────────────────
if (getPlayerName()) { showHome(); }
else                  { showScreen('screen-name'); }
</script>
</body>
</html>
"""


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas not installed. Run:  pip install pandas odfpy")
        sys.exit(1)

    for f in (QUIZ_FILE, KEY_FILE):
        if not f.exists():
            print(f"ERROR: File not found: {f}")
            sys.exit(1)

    print("Reading sheets...")
    quizzes = build_quizzes()

    if not quizzes:
        print("ERROR: No quiz data found.")
        sys.exit(1)

    html = HTML.replace("__QUIZZES_JSON__", json.dumps(quizzes, ensure_ascii=False))
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"\nDone! {len(quizzes)} quiz(zes) written to:\n  {OUT_FILE}")
    print("\nUpload index.html to GitHub to update the live site.")


if __name__ == "__main__":
    main()
