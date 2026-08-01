from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LOGIN_ASSET_ROOT = REPOSITORY_ROOT / "assets" / "login"
FRONTEND_PATH = REPOSITORY_ROOT / "aicc-frontend-demo.html"


def test_login_page_uses_curated_axure_assets() -> None:
    html = FRONTEND_PATH.read_text(encoding="utf-8")

    assert "/assets/login/login-background.png" in (
        LOGIN_ASSET_ROOT / "login.css"
    ).read_text(encoding="utf-8")
    assert "/assets/login/login-illustration.png" in html
    assert (LOGIN_ASSET_ROOT / "login-background.png").is_file()
    assert (LOGIN_ASSET_ROOT / "login-illustration.png").is_file()
    assert "resources/scripts/axure" not in html


def test_login_form_has_required_states_without_default_credentials() -> None:
    html = FRONTEND_PATH.read_text(encoding="utf-8")
    controller = (LOGIN_ASSET_ROOT / "login-page.js").read_text(encoding="utf-8")

    assert 'id="loginAccount"' in html
    assert 'id="loginPassword"' in html
    assert 'id="toggleLoginPassword"' in html
    assert 'id="rememberAccount"' in html
    assert 'value="ops_admin"' not in html
    assert 'value="demo123456"' not in html
    assert "请输入账号" in controller
    assert "请输入密码" in controller
    assert "正在登录" in controller


def test_remember_account_never_persists_plaintext_password() -> None:
    controller = (LOGIN_ASSET_ROOT / "login-page.js").read_text(encoding="utf-8")

    storage_writes = [
        line.strip()
        for line in controller.splitlines()
        if "localStorage.setItem" in line
    ]
    assert storage_writes == [
        "global.localStorage.setItem(REMEMBERED_ACCOUNT_KEY, account);"
    ]
