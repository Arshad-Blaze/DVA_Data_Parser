import os


def detect_file_type(file_path):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return "excel", None
        with open(file_path, "r", encoding="cp1252", errors="ignore") as f:
            lines = [f.readline() for _ in range(5)]

        delimiters = [",", "|", "\t", ";"]
        scores = {d: sum(line.count(d) for line in lines) for d in delimiters}
        best = max(scores, key=scores.get)

        if scores[best] > 0:
            return "delimited", best
        return "fixed", None
    except Exception:
        return None, None


def is_multiline_record(file_path):
    try:
        with open(file_path, "r", encoding="cp1252", errors="ignore") as f:
            lines = [f.readline().strip() for _ in range(10)]

        lines = [l for l in lines if l]
        if not lines:
            return False

        alpha_prefixes = set()
        for line in lines:
            if len(line) >= 2 and line[0].isalpha() and line[1] in ",|\t;":
                alpha_prefixes.add(line[0])

        if len(alpha_prefixes) >= 2:
            return True

        backslash = sum(line.rstrip().endswith("\\") for line in lines)
        return backslash >= 5
    except Exception:
        return False


def detect_record_types(file_path, delimiter=None, sample_lines=50):
    try:
        with open(file_path, "r", encoding="cp1252", errors="ignore") as f:
            lines = [f.readline().strip() for _ in range(sample_lines)]

        prefixes = set()
        for line in lines:
            if not line:
                continue
            first = line[0]
            if first.isalpha() and len(line) >= 2:
                sep = line[1]
                if sep in ",|\t;" if delimiter is None else sep == delimiter:
                    prefixes.add(first)

        return sorted(prefixes)
    except Exception:
        return []


def has_header(file_path, delimiter=","):
    try:
        with open(file_path, "r", encoding="cp1252", errors="ignore") as f:
            first_line = f.readline().strip()

        if not first_line:
            return False

        values = first_line.split(delimiter)
        alpha_count = sum(any(c.isalpha() for c in v) for v in values)
        return alpha_count >= len(values) / 2
    except Exception:
        return False
