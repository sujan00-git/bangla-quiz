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
      min-height: 100vh;
      padding: 24px 16px;
    }

    /* ── Shared card shell ── */
    .card {
      max-width: 780px;
      margin: 0 auto;
      background: #fff;
      border-radius: 20px;
      box-shadow: 0 24px 64px rgba(0,0,0,.35);
      overflow: hidden;
    }
    header {
      background: linear-gradient(135deg, #1a237e, #3949ab);
      color: #fff;
      padding: 24px 30px 18px;
      text-align: center;
    }
    header h1 { font-size: 1.7rem; }
    header p  { margin-top: 6px; font-size: .9rem; opacity: .85; }

    /* ── Quiz-selection screen ── */
    #screen-home  { display: block; }
    #screen-quiz  { display: none;  }

    .quiz-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 16px;
      padding: 24px;
    }
    .quiz-card {
      background: linear-gradient(135deg, #e8eaf6, #c5cae9);
      border: 2px solid #9fa8da;
      border-radius: 14px;
      padding: 22px 16px;
      text-align: center;
      cursor: pointer;
      transition: transform .15s, box-shadow .15s;
      user-select: none;
    }
    .quiz-card:hover  { transform: translateY(-3px);
                        box-shadow: 0 8px 24px rgba(0,0,0,.18); }
    .quiz-card:active { transform: scale(.96); }
    .quiz-card .icon  { font-size: 2.2rem; margin-bottom: 8px; }
    .quiz-card .label { font-size: 1rem; font-weight: 700;
                        color: #1a237e; line-height: 1.3; }
    .quiz-card .count { font-size: .8rem; color: #555; margin-top: 4px; }

    /* ── Quiz screen ── */
    .quiz-header-row {
      display: flex; align-items: center; gap: 12px; padding: 14px 20px 0;
    }
    #back-btn {
      background: #e8eaf6; border: none; border-radius: 8px;
      padding: 7px 14px; font-size: .9rem; font-weight: 700;
      color: #1a237e; cursor: pointer;
    }
    #back-btn:hover { background: #c5cae9; }
    #quiz-title { font-size: 1.1rem; font-weight: 700; color: #1a237e; }

    .table-wrap { padding: 12px 18px 8px; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    thead tr { background: #283593; color: #fff; }
    thead th { padding: 9px 13px; text-align: left;
               font-size: .85rem; white-space: nowrap; }
    tbody tr:nth-child(odd)  { background: #fff; }
    tbody tr:nth-child(even) { background: #f3f4fb; }
    tbody tr { transition: background .25s; }
    td { padding: 9px 13px; vertical-align: middle; }
    td.sl      { text-align: center; font-weight: 700; color: #555;
                 width: 46px; font-size: .95rem; }
    td.english { font-size: 1rem; font-weight: 500; }
    td.bangla  { font-size: 1.1rem; font-weight: 700;
                 color: #1a237e; letter-spacing: .4px; }
    td.answer  { width: 88px; }
    td.answer input {
      width: 66px; padding: 6px 8px; border: 2px solid #bbb;
      border-radius: 8px; font-size: 1rem; text-align: center;
      -moz-appearance: textfield; transition: border-color .2s;
    }
    td.answer input::-webkit-outer-spin-button,
    td.answer input::-webkit-inner-spin-button { -webkit-appearance: none; }
    td.answer input:focus { outline: none; border-color: #3949ab; }
    td.verdict { font-size: .9rem; font-weight: 700; white-space: nowrap; }

    tr.correct td            { background: #e8f5e9 !important; }
    tr.correct td.answer input{ background: #c8e6c9; border-color: #43a047; }
    tr.correct td.verdict    { color: #2e7d32; }
    tr.wrong td              { background: #ffebee !important; }
    tr.wrong td.answer input { background: #ffcdd2; border-color: #e53935; }
    tr.wrong td.verdict      { color: #b71c1c; }
    tr.blank td              { background: #fff8e1 !important; }
    tr.blank td.answer input { background: #fff9c4; border-color: #ffc107; }
    tr.blank td.verdict      { color: #e65100; }

    .footer {
      background: #f0f2ff; border-top: 1px solid #e0e0e0;
      padding: 13px 20px;
      display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    }
    button.action {
      padding: 9px 20px; border: none; border-radius: 10px;
      font-size: .95rem; font-weight: 700; cursor: pointer;
      transition: filter .15s, transform .1s;
    }
    button.action:hover  { filter: brightness(1.1); }
    button.action:active { transform: scale(.96); }
    #grade-btn { background: #2e7d32; color: #fff; }
    #new-btn   { background: #1565c0; color: #fff; }
    #score { margin-left: auto; font-size: 1.05rem; font-weight: 800; }
    #score.perfect { color: #2e7d32; }
    #score.great   { color: #1565c0; }
    #score.ok      { color: #e65100; }
    #score.low     { color: #b71c1c; }

    /* ── Celebration ── */
    #overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,.45); z-index: 99;
      align-items: center; justify-content: center;
    }
    #overlay.show { display: flex; }
    .celebrate-box {
      background: #fff; border-radius: 20px;
      padding: 40px 50px; text-align: center;
      box-shadow: 0 16px 48px rgba(0,0,0,.4);
      animation: pop .3s ease;
    }
    @keyframes pop { from { transform: scale(.7); opacity: 0; }
                     to   { transform: scale(1);  opacity: 1; } }
    .celebrate-box .star { font-size: 3.2rem; }
    .celebrate-box h2 { font-size: 1.7rem; color: #2e7d32; margin: 10px 0 6px; }
    .celebrate-box p  { color: #555; margin-bottom: 18px; }
    .celebrate-box button { background: #2e7d32; color: #fff;
      padding: 10px 28px; font-size: 1rem; border: none;
      border-radius: 10px; cursor: pointer; font-weight: 700; }

    @media (max-width: 520px) {
      header h1 { font-size: 1.3rem; }
      td { padding: 7px 8px; font-size: .85rem; }
      td.bangla { font-size: .95rem; }
      td.answer input { width: 52px; }
      .quiz-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
    }
  </style>
</head>
<body>

<!-- ── Home screen ── -->
<div id="screen-home" class="card">
  <header>
    <h1>Bangla Quiz</h1>
    <p>Choose a quiz to start</p>
  </header>
  <div class="quiz-grid" id="quiz-grid"></div>
</div>

<!-- ── Quiz screen ── -->
<div id="screen-quiz" class="card">
  <header>
    <h1>Bangla Quiz</h1>
    <p>Type the Serial # whose English word matches the Bangla word shown</p>
  </header>
  <div class="quiz-header-row">
    <button id="back-btn" onclick="goHome()">&#8592; Back</button>
    <span id="quiz-title"></span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th><th>English Word</th>
          <th>Bangla Word</th><th>Your Answer</th><th></th>
        </tr>
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

<!-- ── Celebration overlay ── -->
<div id="overlay">
  <div class="celebrate-box">
    <div class="star">&#11088;</div>
    <h2>Perfect Score!</h2>
    <p id="celebrate-msg">You got everything right!</p>
    <button onclick="closeOverlay(); newQuiz()">Play Again</button>
  </div>
</div>

<script>
// ── Quiz data (generated from ODS files) ────────────────────────────────
const QUIZZES = __QUIZZES_JSON__;

// ── State ────────────────────────────────────────────────────────────────
let currentQuiz = null;
let answerKey   = [];

// ── Home screen ──────────────────────────────────────────────────────────
const ICONS = ["🎨","📚","🌿","⭐","🏠","🐾","🎵","🌈","🍎","🔢","🌍","🦋","🎯"];

function buildHome() {
  const grid = document.getElementById('quiz-grid');
  grid.innerHTML = '';
  QUIZZES.forEach((q, i) => {
    const card = document.createElement('div');
    card.className = 'quiz-card';
    card.innerHTML = `
      <div class="icon">${ICONS[i % ICONS.length]}</div>
      <div class="label">${q.title}</div>
      <div class="count">${q.words.length} words</div>`;
    card.onclick = () => startQuiz(q);
    grid.appendChild(card);
  });
}

function goHome() {
  document.getElementById('screen-quiz').style.display = 'none';
  document.getElementById('screen-home').style.display = 'block';
  closeOverlay();
}

// ── Quiz logic ───────────────────────────────────────────────────────────
function startQuiz(quiz) {
  currentQuiz = quiz;
  document.getElementById('screen-home').style.display = 'none';
  document.getElementById('screen-quiz').style.display = 'block';
  document.getElementById('quiz-title').textContent = quiz.title;
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
  let result, tries = 0;
  do {
    result = shuffle(arr);
    tries++;
  } while (tries < 50 && result.some((w, i) => w.serial === arr[i].serial));
  return result;
}

function newQuiz() {
  closeOverlay();
  const words    = currentQuiz.words;
  const shuffled = derange(words);
  answerKey      = shuffled.map(w => w.serial);   // hidden

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
        <input type="number" id="ans-${i}" min="1" max="${words.length}"
          placeholder="#"
          onkeydown="if(event.key==='Enter'||event.key==='Tab'){
            event.preventDefault(); focusNext(${i}); }">
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

function grade() {
  const total = currentQuiz.words.length;
  let correct = 0;

  currentQuiz.words.forEach((_, i) => {
    const input   = document.getElementById(`ans-${i}`);
    const verdict = document.getElementById(`v-${i}`);
    const row     = document.getElementById(`row-${i}`);
    const val     = input.value.trim();
    const student = parseInt(val);
    const right   = answerKey[i];

    row.className = '';
    if (!val) {
      row.classList.add('blank');
      verdict.textContent = `→ ${right}`;
    } else if (student === right) {
      correct++;
      row.classList.add('correct');
      verdict.textContent = '✓';
    } else {
      row.classList.add('wrong');
      verdict.textContent = `✗ → ${right}`;
    }
  });

  const pct = Math.round(correct / total * 100);
  const el  = document.getElementById('score');

  if (pct === 100) {
    el.textContent = `Perfect! ${correct}/${total} ★`;
    el.className   = 'perfect';
    document.getElementById('celebrate-msg').textContent =
      `You got all ${total} correct — amazing!`;
    setTimeout(() => document.getElementById('overlay').classList.add('show'), 400);
  } else if (pct >= 80) {
    el.textContent = `Great!  ${correct}/${total} (${pct}%)`;
    el.className   = 'great';
  } else if (pct >= 60) {
    el.textContent = `Good!  ${correct}/${total} (${pct}%)`;
    el.className   = 'ok';
  } else {
    el.textContent = `${correct}/${total} (${pct}%) — Keep trying!`;
    el.className   = 'low';
  }
}

function closeOverlay() {
  document.getElementById('overlay').classList.remove('show');
}

// ── Boot ─────────────────────────────────────────────────────────────────
buildHome();
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
