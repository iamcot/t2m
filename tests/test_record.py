import json
from pathlib import Path

from t2m.record import concat_list, login_script


def test_concat_list_holds_each_frame_until_the_next():
    frames = [(10.0, Path("/f/0.jpg")), (11.0, Path("/f/1.jpg")), (12.5, Path("/f/2.jpg")), (20.0, Path("/f/3.jpg"))]
    lines = concat_list(frames, 10.5, 13.0).splitlines()
    assert lines == ["file '/f/0.jpg'", "duration 0.500", "file '/f/1.jpg'", "duration 1.500",
                     "file '/f/2.jpg'", "duration 0.500", "file '/f/2.jpg'"]
    assert concat_list(frames, 1.0, 2.0) == ""


def test_login_script_stores_the_user_as_the_site_does():
    script = login_script({"jwtToken": "a'b", "name": "Demo"})
    stored = script.split("setItem('anylearn_user', ")[1].rsplit("); }", 1)[0]
    assert json.loads(json.loads(stored)) == {"jwtToken": "a'b", "name": "Demo"}
