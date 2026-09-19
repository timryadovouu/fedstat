from fedstat.client import USER_AGENTS, FedstatClient, _build_headers


def test_default_user_agent_from_pool():
    c = FedstatClient()
    assert c.session.headers["User-Agent"] in USER_AGENTS


def test_browserlike_headers_present():
    h = _build_headers(USER_AGENTS[0])
    for key in ("Accept", "Accept-Language", "Sec-Fetch-Mode", "Cache-Control"):
        assert key in h


def test_reset_session_makes_new_session_and_keeps_headers():
    c = FedstatClient()
    old = c.session
    c.reset_session()
    assert c.session is not old               # новая сессия (чистые cookies)
    assert c.session.headers["User-Agent"] in USER_AGENTS


def test_explicit_user_agent_no_rotation():
    c = FedstatClient(user_agent="my-agent/1.0", rotate_user_agent=False)
    assert c.session.headers["User-Agent"] == "my-agent/1.0"
    c.reset_session()
    assert c.session.headers["User-Agent"] == "my-agent/1.0"  # не меняется
