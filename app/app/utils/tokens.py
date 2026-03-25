import secrets


def generate_share_token() -> str:
    return secrets.token_urlsafe(16)
