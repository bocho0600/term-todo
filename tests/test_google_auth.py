import json

from term_todo import google_auth as ga


def write_token(path, scopes):
    path.write_text(json.dumps({"token": "x", "scopes": scopes}))


def test_not_signed_in_without_token(tmp_path, monkeypatch):
    monkeypatch.setattr(ga, "TOKEN_PATH", tmp_path / "token.json")
    assert ga.granted_scopes() == set()
    assert not ga.cloud_enabled()
    assert not ga.has_scopes(ga.CALENDAR_SCOPES)


def test_calendar_only_login_does_not_enable_cloud(tmp_path, monkeypatch):
    tok = tmp_path / "token.json"
    monkeypatch.setattr(ga, "TOKEN_PATH", tok)
    write_token(tok, [ga.CALENDAR_SCOPE])
    assert ga.has_scopes(ga.CALENDAR_SCOPES)
    assert not ga.cloud_enabled()


def test_full_login_enables_cloud_and_logout_clears_it(tmp_path, monkeypatch):
    tok = tmp_path / "token.json"
    monkeypatch.setattr(ga, "TOKEN_PATH", tok)
    write_token(tok, ga.ALL_SCOPES)
    assert ga.cloud_enabled()
    assert ga.logout() is True
    assert not ga.cloud_enabled()
    assert ga.logout() is False


def test_corrupt_token_is_treated_as_signed_out(tmp_path, monkeypatch):
    tok = tmp_path / "token.json"
    tok.write_text("not json")
    monkeypatch.setattr(ga, "TOKEN_PATH", tok)
    assert not ga.cloud_enabled()


def test_non_interactive_without_login_raises(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(ga, "TOKEN_PATH", tmp_path / "token.json")
    with pytest.raises(ga.NotSignedIn):
        ga.get_credentials(ga.ALL_SCOPES, interactive=False)
