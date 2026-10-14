"""认证与授权：错误口令/伪造令牌 401、/auth/me 200、控制台 403、注册与重复注册。"""
from __future__ import annotations


def test_wrong_password_returns_401(app_client) -> None:
    resp = app_client.post(
        "/api/auth/login",
        json={"student_no": "20240004", "password": "wrong-pass"},
    )
    assert resp.status_code == 401
    assert resp.json()["data"] is None


def test_unknown_student_no_returns_401(app_client) -> None:
    resp = app_client.post(
        "/api/auth/login",
        json={"student_no": "not-exist", "password": "123456"},
    )
    assert resp.status_code == 401


def test_forged_token_returns_401(app_client) -> None:
    resp = app_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer forged.token.value"},
    )
    assert resp.status_code == 401


def test_missing_token_returns_401(app_client) -> None:
    resp = app_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_auth_me_returns_current_user(app_client, login_factory) -> None:
    headers = login_factory("20240004")
    resp = app_client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["student_no"] == "20240004"
    assert data["nickname"] == "赵一鸣"


def test_normal_user_forbidden_from_console(app_client, login_factory) -> None:
    headers = login_factory("20240004")
    resp = app_client.get("/api/console/agents", headers=headers)
    assert resp.status_code == 403


def test_admin_can_access_console(app_client, login_factory) -> None:
    headers = login_factory("2400320321")
    resp = app_client.get("/api/console/agents", headers=headers)
    assert resp.status_code == 200
    names = {a["name"] for a in resp.json()["data"]}
    assert {"user_agent", "commodity", "moderation", "search", "negotiation",
            "order", "credit", "arbitrator", "coordinator"} <= names


def test_register_new_student_tag_new(app_client) -> None:
    resp = app_client.post(
        "/api/auth/register",
        json={"student_no": "20249999", "password": "123456", "nickname": "测试新人"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["user"]["risk_tag"] == "new"
    assert data["token"]
    # 注册后可直接登录
    login = app_client.post(
        "/api/auth/login",
        json={"student_no": "20249999", "password": "123456"},
    )
    assert login.status_code == 200


def test_duplicate_register_returns_400(app_client) -> None:
    body = {"student_no": "20248888", "password": "123456", "nickname": "只注册一次"}
    first = app_client.post("/api/auth/register", json=body)
    assert first.status_code == 200
    second = app_client.post("/api/auth/register", json=body)
    assert second.status_code == 400
    assert "已注册" in second.json()["message"]


def test_register_short_password_rejected(app_client) -> None:
    resp = app_client.post(
        "/api/auth/register",
        json={"student_no": "20247777", "password": "123", "nickname": "短口令"},
    )
    assert resp.status_code == 422
