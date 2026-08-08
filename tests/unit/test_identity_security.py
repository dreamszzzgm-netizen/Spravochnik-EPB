from app.modules.identity.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password = "A-strong-test-password-123!"
    hashed = hash_password(password)
    assert password not in hashed
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_short_password_is_rejected() -> None:
    try:
        hash_password("short")
    except ValueError as exc:
        assert "12" in str(exc)
    else:
        raise AssertionError("short password must be rejected")


def test_session_token_is_random_and_only_hash_is_stable() -> None:
    first = generate_session_token()
    second = generate_session_token()
    assert first != second
    assert len(hash_session_token(first)) == 64
    assert hash_session_token(first) == hash_session_token(first)
