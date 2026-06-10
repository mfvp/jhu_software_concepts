"""
query_data.py - Analysis / summary queries for the Grad Cafe data.
Module 4 / JHU Software Concepts in Python

In module 3 every question was a separate SQL string. That worked but it was
basically impossible to unit test without a full database loaded with the right
data. For module 4 I changed the approach: the Database layer hands us all the
rows as plain dicts, and these functions compute the answers in plain Python.
That way the analysis logic can be tested with a tiny list of fake rows.

Every percentage is formatted to exactly two decimal places (e.g. "39.28%")
because the assignment require it.
"""

from db import Database


# the universities we care about for the "top schools PhD CS" question (Q8/Q9)
TOP_SCHOOLS = [
    "georgetown",
    "massachusetts institute of technology",
    "mit",
    "stanford",
    "carnegie mellon",
]


def percentage(part, whole):
    """Return part/whole as a percentage rounded to 2 decimals (0.0 if whole is 0)."""
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 2)


def format_percent(value):
    """Format a number as a percent string with exactly two decimals, e.g. 39.28%."""
    return "{:.2f}%".format(value)


def format_number(value):
    """Format an average/number to two decimals, or 'N/A' when we have no data."""
    if value is None:
        return "N/A"
    return "{:.2f}".format(value)


def _avg(values):
    """Average a list of numbers, skipping Nones. Returns None when nothing is left."""
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _contains(text, needle):
    """Case-insensitive 'is needle in text', safe when text is None."""
    if not text:
        return False
    return needle.lower() in text.lower()


def count_fall_2026(rows):
    """Q1: how many entries are for the Fall 2026 term."""
    return sum(1 for r in rows if r.get("term") == "Fall 2026")


def percent_international(rows):
    """Q2: percent of International applicants out of American+International."""
    intl = sum(1 for r in rows if r.get("us_or_international") == "International")
    considered = sum(
        1 for r in rows
        if r.get("us_or_international") in ("International", "American")
    )
    return percentage(intl, considered)


def average_scores(rows):
    """Q3: average GPA / GRE / GRE V / GRE AW across everyone who reported them."""
    return {
        "gpa": _avg([r.get("gpa") for r in rows]),
        "gre": _avg([r.get("gre") for r in rows]),
        "gre_v": _avg([r.get("gre_v") for r in rows]),
        "gre_aw": _avg([r.get("gre_aw") for r in rows]),
    }


def average_gpa_american_fall(rows):
    """Q4: average GPA of American applicants for Fall 2026."""
    gpas = [
        r.get("gpa") for r in rows
        if r.get("us_or_international") == "American"
        and r.get("term") == "Fall 2026"
    ]
    return _avg(gpas)


def percent_acceptances_fall(rows):
    """Q5: percent of Fall 2026 entries that were Acceptances."""
    fall = [r for r in rows if r.get("term") == "Fall 2026"]
    accepted = sum(1 for r in fall if r.get("status") == "Accepted")
    return percentage(accepted, len(fall))


def average_gpa_accept_fall(rows):
    """Q6: average GPA of Fall 2026 acceptances."""
    gpas = [
        r.get("gpa") for r in rows
        if r.get("term") == "Fall 2026" and r.get("status") == "Accepted"
    ]
    return _avg(gpas)


def count_jhu_masters_cs(rows):
    """Q7: JHU Masters in Computer Science entries (using the raw program field)."""
    total = 0
    for r in rows:
        program = r.get("program")
        if (_contains(program, "johns hopkins") or _contains(program, "jhu")) \
                and _contains(program, "computer science") \
                and r.get("degree") == "Masters":
            total += 1
    return total


def _top_school_phd_cs(rows, university_field, program_field):
    """Shared helper for Q8/Q9 - counts 2026 PhD CS acceptances at the top schools."""
    total = 0
    for r in rows:
        if not _contains(r.get("term"), "2026"):
            continue
        if r.get("status") != "Accepted" or r.get("degree") != "PhD":
            continue
        if not _contains(r.get(program_field), "computer science"):
            continue
        if any(_contains(r.get(university_field), school) for school in TOP_SCHOOLS):
            total += 1
    return total


def count_top_school_phd_raw(rows):
    """Q8: top-school PhD CS acceptances using the raw scraped program field."""
    # the raw "program" column holds the "Program, University" string from grad cafe
    return _top_school_phd_cs(rows, "program", "program")


def count_top_school_phd_llm(rows):
    """Q9: same as Q8 but using the cleaner LLM generated fields."""
    return _top_school_phd_cs(rows, "llm_generated_university", "llm_generated_program")


def top_universities(rows, limit=10):
    """Q10: the most applied-to universities (by llm_generated_university)."""
    counts = {}
    for r in rows:
        uni = r.get("llm_generated_university")
        if uni:
            counts[uni] = counts.get(uni, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return ordered[:limit]


def lowest_acceptance_rates(rows, limit=10, min_entries=15):
    """Q11: universities with the lowest acceptance rate (needs >= min_entries)."""
    totals = {}
    accepted = {}
    for r in rows:
        uni = r.get("llm_generated_university")
        if not uni:
            continue
        totals[uni] = totals.get(uni, 0) + 1
        if r.get("status") == "Accepted":
            accepted[uni] = accepted.get(uni, 0) + 1

    results = []
    for uni, total in totals.items():
        if total >= min_entries:
            rate = percentage(accepted.get(uni, 0), total)
            results.append((uni, rate, total))

    # sort by acceptance rate ascending so the hardest schools come first
    results.sort(key=lambda item: item[1])
    return results[:limit]


def build_analysis(rows):
    """
    Turn the raw rows into the list of question/answer items the template renders.
    Each item is a dict with a 'question' and an already-formatted 'answer' string.
    Percentages are pre-formatted to two decimals here.
    """
    scores = average_scores(rows)

    items = [
        {
            "question": "How many entries are for Fall 2026?",
            "answer": "Applicant count: {}".format(count_fall_2026(rows)),
        },
        {
            "question": "What percent of entries are from International students?",
            "answer": "Percent International: {}".format(
                format_percent(percent_international(rows))
            ),
        },
        {
            "question": "Average GPA, GRE, GRE V, GRE AW of applicants who provided them?",
            "answer": "Average GPA: {}, GRE: {}, GRE V: {}, GRE AW: {}".format(
                format_number(scores["gpa"]),
                format_number(scores["gre"]),
                format_number(scores["gre_v"]),
                format_number(scores["gre_aw"]),
            ),
        },
        {
            "question": "Average GPA of American students in Fall 2026?",
            "answer": "Average GPA American: {}".format(
                format_number(average_gpa_american_fall(rows))
            ),
        },
        {
            "question": "What percent of Fall 2026 entries are Acceptances?",
            "answer": "Acceptance percent: {}".format(
                format_percent(percent_acceptances_fall(rows))
            ),
        },
        {
            "question": "Average GPA of Fall 2026 Acceptances?",
            "answer": "Average GPA Acceptance: {}".format(
                format_number(average_gpa_accept_fall(rows))
            ),
        },
        {
            "question": "How many JHU Masters in Computer Science entries are there?",
            "answer": "JHU Masters CS count: {}".format(count_jhu_masters_cs(rows)),
        },
        {
            "question": "2026 PhD CS acceptances at top schools (raw fields)?",
            "answer": "Count (raw fields): {}".format(count_top_school_phd_raw(rows)),
        },
        {
            "question": "Does Q8 change when using the LLM generated fields?",
            "answer": "Count (LLM fields): {}".format(count_top_school_phd_llm(rows)),
        },
    ]
    return items


def get_analysis(database):
    """
    Top level entry point used by the Flask app: read every row from the database
    and return a dict the template can render. 'items' is the labeled Q&A list,
    'top_universities' and 'lowest_acceptance' back the two ranked lists.
    """
    rows = database.fetch_all()
    return {
        "total": len(rows),
        "items": build_analysis(rows),
        "top_universities": top_universities(rows),
        "lowest_acceptance": lowest_acceptance_rates(rows),
    }


def query_applicants(database):
    """
    Simple query helper: return the applicant rows as dicts. Each dict has the
    Module-3 required keys, which is what the analysis template relies on.
    """
    return database.fetch_all()


def main():  # pragma: no cover - convenience CLI, not used by the tests
    """Print the analysis to the console (handy when running locally)."""
    database = Database(__import__("db").connect())
    analysis = get_analysis(database)
    print("Total entries:", analysis["total"])
    for item in analysis["items"]:
        print("-", item["question"])
        print("  Answer:", item["answer"])
    database.close()


if __name__ == "__main__":  # pragma: no cover
    main()
