from t2m import checks
from t2m.schema import ItemRef


def messages(problems):
    return [p.message for p in problems]


def test_example_script_passes(script):
    assert checks.check_script(script) == []


def test_word_count_out_of_range(script):
    script.scenes[1].narration += " thêm" * 40
    problems = checks.check_script(script)
    assert any("chữ, cần 105 đến 128" in m for m in messages(problems))
    assert checks.has_errors(problems)


def test_brand_spellings():
    found = messages(checks.check_text("x", "Nhận 50 AnyPoints, đổi leo xu, ghé Anylearn nhé"))
    assert any('"anyPoint"' in m for m in found)
    assert any('"Leo Xu"' in m for m in found)
    assert any('"anyLEARN"' in m for m in found)
    assert checks.check_text("x", "Nhận 50 anyPoint và 10 Leo Xu trên anyLEARN") == []


def test_links_are_not_brand_errors():
    assert checks.check_text("x", "Vào anylearn.vn/search hoặc https://anylearn.vn/fun nhé") == []


def test_points_written_as_diem():
    assert checks.check_text("x", "Mỗi khóa được 120 điểm")
    assert checks.check_text("x", "6 điểm mới của phiên bản này") == []


def test_refund_only_when_class_does_not_open():
    assert checks.check_text("x", "Đăng ký mà lớp không mở thì được hoàn tiền.") == []
    bad = checks.check_text("x", "Không hài lòng được hoàn tiền 100%.")
    assert any("hoàn tiền" in m for m in messages(bad))
    assert any("100%" in m for m in messages(bad))


def test_cheaper_only_as_promised():
    assert checks.check_text("x", "Giá bằng hoặc rẻ hơn tại trường.") == []
    assert checks.has_errors(checks.check_text("x", "Rẻ hơn ở trường nhiều."))


def test_missing_shot_and_bad_link(script):
    script.scenes[1].visual.shot = "khong-co"
    script.cta.link = "https://example.com"
    found = messages(checks.check_script(script))
    assert any("shot 'khong-co'" in m for m in found)
    assert any("bắt đầu bằng /" in m for m in found)


def test_items_against_api(script):
    script.items = [ItemRef(id=1, title="Bơi 1", price=100000), ItemRef(id=2, title="Vẽ", price=None),
                    ItemRef(id=3, title="Ẩn")]
    live = {1: {"title": "Bơi 1", "price": 120000.0}, 2: {"title": "Vẽ màu", "price": 1}}
    found = messages(checks.check_items(script, live.get))
    assert len(found) == 3
    assert "120,000đ" in found[0]
    assert "Vẽ màu" in found[1]
    assert "không đọc được" in found[2]
