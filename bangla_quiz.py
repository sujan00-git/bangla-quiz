#!/usr/bin/env python3
"""Bangla Vocabulary Quiz — shuffles Bangla words each run and auto-grades."""

import sys
import random
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

QUIZ_FILE = Path(__file__).parent / "sian_questions.ods"
KEY_FILE  = Path(__file__).parent / "sian_questions-answer-key.ods"

# Fonts — Nirmala UI renders Bangla script on Windows; fallback to Arial
BANGLA_FONT = ("Nirmala UI", 13)
UI_FONT     = ("Segoe UI", 11)
UI_BOLD     = ("Segoe UI", 11, "bold")
TITLE_FONT  = ("Segoe UI", 17, "bold")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(filepath: Path):
    """Return list of (serial_str, english, bangla) from the ODS file.

    Skips any row where column A is not a plain integer (title / header rows).
    """
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            "pandas is not installed.\n"
            "Run:  pip install pandas odfpy"
        )

    try:
        df = pd.read_excel(str(filepath), engine="odf", header=None)
    except Exception as exc:
        raise RuntimeError(f"Could not open file:\n{filepath}\n\n{exc}")

    rows = []
    for _, row in df.iterrows():
        a = str(row.iloc[0]).strip() if len(row) > 0 else ""
        b = str(row.iloc[1]).strip() if len(row) > 1 else ""
        c = str(row.iloc[2]).strip() if len(row) > 2 else ""

        if a.isdigit() and b and c and b.lower() != "nan" and c.lower() != "nan":
            rows.append((a, b, c))   # (serial, english, bangla)

    if not rows:
        raise RuntimeError(
            "No data rows found in the file.\n"
            "Ensure column A has serial numbers and columns B/C have words."
        )
    return rows


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class BanglaQuiz(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bangla Vocabulary Quiz")
        self.geometry("880x660")
        self.minsize(700, 500)
        self.configure(bg="#f0f4fb")

        self._data: list[tuple[str, str, str]] = []
        self._answer_key: list[str] = []       # hidden; answer_key[i] = correct serial for row i
        self._shuffled_bangla: list[str] = []
        self._entry_vars: list[tk.StringVar] = []
        self._entry_widgets: list[tk.Entry] = []
        self._row_frames: list[tk.Frame] = []
        self._result_labels: list[tk.Label] = []

        self._build_header()
        self._build_table_area()
        self._build_footer()
        self._new_quiz()

    # ------------------------------------------------------------------ UI
    def _build_header(self):
        hdr = tk.Frame(self, bg="#1a237e", pady=14)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(hdr, font=TITLE_FONT, fg="white", bg="#1a237e")
        title_lbl.pack()
        self._title_lbl = title_lbl

        tk.Label(
            hdr,
            text="For each row: look at the Bangla word → type the Serial # whose English word it means",
            font=("Segoe UI", 10), fg="#c5cae9", bg="#1a237e",
        ).pack(pady=(3, 0))

    def _build_table_area(self):
        outer = tk.Frame(self, bg="#f0f4fb")
        outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 4))

        self._canvas = tk.Canvas(outer, bg="#f0f4fb", highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._table = tk.Frame(self._canvas, bg="#f0f4fb")
        self._win_id = self._canvas.create_window((0, 0), window=self._table, anchor="nw")

        self._table.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width),
        )
        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

    def _build_footer(self):
        foot = tk.Frame(self, bg="#e8eaf6", pady=10)
        foot.pack(fill=tk.X, padx=0)

        btn_area = tk.Frame(foot, bg="#e8eaf6")
        btn_area.pack(padx=16, fill=tk.X)

        tk.Button(
            btn_area, text="  Grade My Answers  ",
            font=UI_BOLD, bg="#2e7d32", fg="white",
            relief=tk.FLAT, pady=7, cursor="hand2",
            command=self._grade,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_area, text="  New Quiz (Reshuffle)  ",
            font=UI_FONT, bg="#1565c0", fg="white",
            relief=tk.FLAT, pady=7, cursor="hand2",
            command=self._new_quiz,
        ).pack(side=tk.LEFT)

        self._score_var = tk.StringVar()
        tk.Label(
            btn_area, textvariable=self._score_var,
            font=("Segoe UI", 13, "bold"), bg="#e8eaf6",
        ).pack(side=tk.RIGHT)

    # ------------------------------------------------------------ Quiz logic
    def _new_quiz(self):
        # Load English word list from quiz file (display order)
        try:
            self._data = load_data(QUIZ_FILE)
        except RuntimeError as exc:
            messagebox.showerror("Error loading quiz file", str(exc))
            return

        # Load correct English→Bangla mappings from the answer key (hidden from student)
        try:
            key_rows = load_data(KEY_FILE)
        except RuntimeError as exc:
            messagebox.showerror("Error loading answer key", str(exc))
            return

        self._title_lbl.config(
            text=f"Bangla Vocabulary Quiz  ({len(self._data)} words)"
        )

        # Build lookup: english word → (serial, bangla) from the answer key
        key_by_english = {eng.lower(): (serial, bangla) for serial, eng, bangla in key_rows}

        # Resolve each quiz row to its correct serial and Bangla using the answer key
        # (handles any ordering difference between the two files)
        correct_bangla_pool = []
        serial_of_bangla: dict[str, str] = {}
        resolved_data = []
        for serial, english, _quiz_bangla in self._data:
            if english.lower() in key_by_english:
                key_serial, key_bangla = key_by_english[english.lower()]
                correct_bangla_pool.append(key_bangla)
                serial_of_bangla[key_bangla] = key_serial
                resolved_data.append((serial, english, key_bangla))
            else:
                # Fallback: use quiz file data if not found in key
                correct_bangla_pool.append(_quiz_bangla)
                serial_of_bangla[_quiz_bangla] = serial
                resolved_data.append((serial, english, _quiz_bangla))
        self._data = resolved_data

        # Shuffle Bangla words — ensure no word lands on its own original row
        shuffled = correct_bangla_pool[:]
        for _ in range(30):
            random.shuffle(shuffled)
            if all(shuffled[i] != correct_bangla_pool[i] for i in range(len(shuffled))):
                break

        self._shuffled_bangla = shuffled
        self._answer_key = [serial_of_bangla[b] for b in shuffled]  # hidden

        self._score_var.set("")
        self._render_table()

    def _render_table(self):
        for w in self._table.winfo_children():
            w.destroy()

        self._entry_vars = []
        self._entry_widgets = []
        self._row_frames = []
        self._result_labels = []

        # Header row
        hdr = tk.Frame(self._table, bg="#283593")
        hdr.pack(fill=tk.X, pady=(0, 1))
        for col, (text, wid) in enumerate([
            ("#", 4), ("English Word", 20), ("Bangla Word", 18), ("Your Answer", 12), ("", 8)
        ]):
            tk.Label(
                hdr, text=text, font=UI_BOLD, fg="white", bg="#283593",
                width=wid, anchor="w", padx=8, pady=6,
            ).grid(row=0, column=col, sticky="w")

        # Data rows
        for i, ((serial, english, _orig), bangla) in enumerate(
            zip(self._data, self._shuffled_bangla)
        ):
            bg = "#ffffff" if i % 2 == 0 else "#e8eaf6"

            row_f = tk.Frame(self._table, bg=bg, pady=1)
            row_f.pack(fill=tk.X)
            self._row_frames.append(row_f)

            tk.Label(row_f, text=serial, font=UI_FONT, bg=bg, width=4,
                     anchor="center", padx=8).grid(row=0, column=0, sticky="w")
            tk.Label(row_f, text=english, font=UI_FONT, bg=bg, width=20,
                     anchor="w", padx=8).grid(row=0, column=1, sticky="w")
            tk.Label(row_f, text=bangla, font=BANGLA_FONT, bg=bg, width=18,
                     anchor="w", padx=8).grid(row=0, column=2, sticky="w")

            var = tk.StringVar()
            entry = tk.Entry(
                row_f, textvariable=var, font=UI_FONT,
                width=8, relief=tk.SOLID, bd=1, bg="white",
                justify="center",
            )
            entry.grid(row=0, column=3, padx=8, pady=5, sticky="w")

            result = tk.Label(row_f, text="", font=UI_BOLD, bg=bg, width=8, anchor="w")
            result.grid(row=0, column=4, padx=4, sticky="w")

            self._entry_vars.append(var)
            self._entry_widgets.append(entry)
            self._result_labels.append(result)

        self._canvas.yview_moveto(0)
        # Focus first entry
        if self._entry_widgets:
            self._entry_widgets[0].focus_set()

    # ---------------------------------------------------------------- Grading
    def _grade(self):
        if not self._data:
            return

        unanswered = sum(1 for v in self._entry_vars if not v.get().strip())
        if unanswered:
            if not messagebox.askyesno(
                "Incomplete",
                f"{unanswered} question(s) left blank.\nGrade anyway?",
            ):
                return

        correct = 0
        total = len(self._data)

        for i, (var, entry, result_lbl, row_f) in enumerate(
            zip(self._entry_vars, self._entry_widgets, self._result_labels, self._row_frames)
        ):
            student = var.get().strip()
            correct_serial = self._answer_key[i]   # hidden answer

            if student == correct_serial:
                correct += 1
                row_bg, entry_bg = "#e8f5e9", "#a5d6a7"
                result_lbl.config(text="✓", fg="#1b5e20")
            elif not student:
                row_bg, entry_bg = "#fff8e1", "#ffe082"
                result_lbl.config(text=f"→ {correct_serial}", fg="#e65100")
            else:
                row_bg, entry_bg = "#ffebee", "#ef9a9a"
                result_lbl.config(text=f"✗ → {correct_serial}", fg="#b71c1c")

            row_f.config(bg=row_bg)
            entry.config(bg=entry_bg)
            result_lbl.config(bg=row_bg)
            for child in row_f.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=row_bg)

        pct = correct / total * 100

        if pct == 100:
            score_text, color = f"Perfect! {correct}/{total} (100%) ★", "#2e7d32"
        elif pct >= 80:
            score_text, color = f"Great!  {correct}/{total} ({pct:.0f}%)", "#1565c0"
        elif pct >= 60:
            score_text, color = f"Good!   {correct}/{total} ({pct:.0f}%)", "#e65100"
        else:
            score_text, color = f"{correct}/{total} ({pct:.0f}%) — Keep trying!", "#b71c1c"

        self._score_var.set(score_text)

        lines = [f"Score: {correct} out of {total}  ({pct:.0f}%)"]
        if pct == 100:
            lines.append("\nExcellent! You know all the words!")
        elif pct >= 60:
            lines.append("\nGood job! Review the red rows and try again.")
        else:
            lines.append("\nKeep practising! Check the correct answers shown in each row.")

        messagebox.showinfo("Quiz Results", "\n".join(lines))


# ---------------------------------------------------------------------------
def main():
    missing = [f for f in (QUIZ_FILE, KEY_FILE) if not f.exists()]
    if missing:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "File Not Found",
            "Cannot find:\n" + "\n".join(str(p) for p in missing) +
            "\n\nPlace both ODS files in the same folder as this script.",
        )
        root.destroy()
        sys.exit(1)

    app = BanglaQuiz()
    app.mainloop()


if __name__ == "__main__":
    main()
