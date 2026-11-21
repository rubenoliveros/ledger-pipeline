from ledger.generate import generate_rows, write_extract


def test_same_seed_same_file(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_extract(a, 1_000, seed=1)
    write_extract(b, 1_000, seed=1)
    assert a.read_bytes() == b.read_bytes()


def test_row_count_and_defects(tmp_path):
    report = write_extract(tmp_path / "x.csv", 5_000, seed=3, defect_rate=0.01)
    assert report.rows == 5_000
    assert 0 < report.defect_total < 150


def test_clean_documents_balance():
    docs: dict[str, float] = {}
    for row, kind in generate_rows(2_000, seed=5, defect_rate=0.0):
        docs[row["document_no"]] = docs.get(row["document_no"], 0) + float(row["amount"])
    complete = list(docs.values())[:-1]  # the last document may be cut off by the row limit
    assert all(abs(total) < 0.005 for total in complete)
