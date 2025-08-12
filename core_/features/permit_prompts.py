class PermitPrompts:
    MODEL        = "gpt-4.1-mini-2025-04-14"
    TEMPERATURE  = 0
    MAX_TOKENS   = 50  # ok for short numeric/string outputs

    ADA = """
This value comes from the PDF filename (stem). Ignore this field and do not search the text.
Return the single letter "a".
"""

    KAEK = """
Find the ΚΑΕΚ code in the document. Typical shapes:
- "NNNNNNNNNNNN" (12–13 digits)
- "NNNNNNNNNNNN/N/N" (digits with slashes)
- Sometimes with dots or spaces.

Rules:
- Look for labels like "ΚΑΕΚ", "Κωδικός Αριθμός Εθνικού Κτηματολογίου".
- If multiple candidates, pick the one nearest to headings like "Στοιχεία έργου" / "Στοιχεία κυρίου του έργου".
- Return ONLY the code (digits plus optional "/" or "."). No extra words.
- If not found, return exactly "a".
"""

    # ----------------------------- Στοιχεία Διαγράμματος Κάλυψης (ΣΥΝΟΛΟ) --
    # For all 7 rows below: read the table titled "Στοιχεία Διαγράμματος Κάλυψης".
    # Columns we care about: ΥΦΙΣΤΑΜΕΝΑ | ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ | ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ | ΣΥΝΟΛΟ
    # Return ONLY the number from the ΣΥΝΟΛΟ column.
    # Numbers are in European format (e.g., "29.543,26"). Remove thousand dots and use dot as decimal.
    # Strip any units/symbols (m², m3, %, κ.λπ.). If missing/unreadable, return 0.

    BUILDING_COVER = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Εμβ. κάλυψης κτιρίου".
Return ONLY the numeric value from the ΣΥΝΟΛΟ column, normalized (e.g., "29.543,26" → 29543.26).
If not found, return 0.
"""

    BUILDING_FLOOR = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Εμβ. δόμησης κτιρίου".
Return ONLY the numeric value from the ΣΥΝΟΛΟ column, normalized.
If not found, return 0.
"""

    UNCOVERED_PLOT = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Εμβ. ακάλυπτου χώρου οικοπέδου".
Return ONLY the numeric value from the ΣΥΝΟΛΟ column, normalized.
If not found, return 0.
"""

    VOLUME = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Όγκος κτιρίου (άνω εδάφους)".
Return ONLY the numeric value from the ΣΥΝΟΛΟ column, normalized.
If not found, return 0.
"""

    HEIGHT = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Μέγιστο ύψος κτιρίου".
Return ONLY the numeric value from the ΣΥΝΟΛΟ column, normalized.
If not found, return 0.
"""

    FLOORS = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Αριθμός Ορόφων".
Return ONLY the integer from the ΣΥΝΟΛΟ column (e.g., "5" → 5). If decimal, round/truncate to integer.
If not found, return 0.
"""

    PARKING = """
Locate the table "Στοιχεία Διαγράμματος Κάλυψης".
Find the row labeled exactly "Αριθμός Θέσεων Στάθμευσης".
Return ONLY the integer from the ΣΥΝΟΛΟ column. If decimal, round/truncate to integer.
If not found, return 0.
"""

    # -------------------------------------------- Owners: names / role / right
    # We return aligned, slash-separated lists; downstream code splits and zips.

    OWNER = """
Find the table titled (or near the heading) "Στοιχεία κυρίου του έργου".
Columns of interest:
- "Επώνυμο/ία" (surname) and "Όνομα" (given name).
Notes:
- The table can be broken across lines/pages; a company name may appear on the next lines.
- Do NOT include role, share, or right in this field—ONLY the name.
- Company/legal forms must be preserved as written (e.g., "ALUMINCO A.E." keep the dots if present).

Return the owners as a single string of full names, in table row order:
"SURNAME GIVEN / SURNAME GIVEN / …"
If not found, return "a".
"""

    CAPACITY = """
From the same "Στοιχεία κυρίου του έργου" table, extract "Ιδιότητα" for each owner row.
Return them in row order, joined by " / ":
"Ιδιοκτήτης / Εξουσιοδοτημένο πρόσωπο / Νόμιμος Εκπρόσωπος / …"
If not found, return "a".
"""

    TITLE = """
From the same "Στοιχεία κυρίου του έργου" table, extract "Τύπος δικαιώματος" for each owner row.
Return them in row order, joined by " / ":
"Πλήρης κυριότητα / Ψιλή κυριότητα / …"
If not found, return "a".
"""

    # Optional but recommended if you add a Feature for shares:
    SHARE = """
From the same "Στοιχεία κυρίου του έργου" table, extract "Ποσοστό" for each owner row.
- Normalize European numbers: "12,5%" → 12.5 (strip "%").
- Empty or placeholder values ("-", "…", ".") → 0.
Return the list in row order, joined by " / ":
"50 / 50"   or   "100"
If not found, return "0".
"""
