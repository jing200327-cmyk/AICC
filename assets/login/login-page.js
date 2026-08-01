(function setupLoginPage(global, document) {
  "use strict";

  const REMEMBERED_ACCOUNT_KEY = "aicc.remembered-account";

  function byId(id) {
    return document.getElementById(id);
  }

  function setFieldError(field, errorElement, input, message) {
    field.classList.toggle("has-error", Boolean(message));
    errorElement.textContent = message;
    input.setAttribute("aria-invalid", message ? "true" : "false");
  }

  function init() {
    const loginPage = byId("loginPage");
    const app = byId("app");
    const form = byId("loginForm");
    if (!loginPage || !app || !form || !global.AiccAuthService) {
      return;
    }

    const accountInput = byId("loginAccount");
    const passwordInput = byId("loginPassword");
    const accountField = byId("accountField");
    const passwordField = byId("passwordField");
    const accountError = byId("accountError");
    const passwordError = byId("passwordError");
    const formError = byId("loginFormError");
    const rememberAccount = byId("rememberAccount");
    const togglePassword = byId("toggleLoginPassword");
    const submitButton = byId("loginSubmit");
    const submitText = byId("loginSubmitText");
    let isSubmitting = false;

    try {
      const rememberedAccount = global.localStorage.getItem(REMEMBERED_ACCOUNT_KEY) || "";
      accountInput.value = rememberedAccount;
      rememberAccount.checked = Boolean(rememberedAccount);
      (rememberedAccount ? passwordInput : accountInput).focus();
    } catch (_error) {
      accountInput.focus();
    }

    function clearFormError() {
      formError.textContent = "";
    }

    function validate() {
      const account = accountInput.value.trim();
      const password = passwordInput.value;
      setFieldError(accountField, accountError, accountInput, account ? "" : "请输入账号");
      setFieldError(passwordField, passwordError, passwordInput, password ? "" : "请输入密码");
      return { account, password, valid: Boolean(account && password) };
    }

    function setLoading(loading) {
      isSubmitting = loading;
      submitButton.disabled = loading;
      submitButton.classList.toggle("is-loading", loading);
      submitButton.setAttribute("aria-busy", loading ? "true" : "false");
      submitText.textContent = loading ? "正在登录" : "登 录";
    }

    function persistRememberedAccount(account) {
      try {
        if (rememberAccount.checked) {
          global.localStorage.setItem(REMEMBERED_ACCOUNT_KEY, account);
        } else {
          global.localStorage.removeItem(REMEMBERED_ACCOUNT_KEY);
        }
      } catch (_error) {
        // Storage can be unavailable in privacy modes; login should still work.
      }
    }

    function enterWorkbench(result) {
      persistRememberedAccount(accountInput.value.trim());
      loginPage.hidden = true;
      loginPage.style.display = "none";
      app.classList.add("is-auth");
      app.style.display = "flex";
      global.dispatchEvent(new CustomEvent("aicc:login", { detail: { mode: result.mode } }));
    }

    accountInput.addEventListener("input", () => {
      setFieldError(accountField, accountError, accountInput, "");
      clearFormError();
    });

    passwordInput.addEventListener("input", () => {
      setFieldError(passwordField, passwordError, passwordInput, "");
      clearFormError();
    });

    togglePassword.addEventListener("click", () => {
      const showPassword = passwordInput.type === "password";
      passwordInput.type = showPassword ? "text" : "password";
      togglePassword.textContent = showPassword ? "隐藏" : "显示";
      togglePassword.setAttribute("aria-label", showPassword ? "隐藏密码" : "显示密码");
      togglePassword.setAttribute("aria-pressed", showPassword ? "true" : "false");
      passwordInput.focus();
    });

    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (isSubmitting) {
        return;
      }

      clearFormError();
      const credentials = validate();
      if (!credentials.valid) {
        (credentials.account ? passwordInput : accountInput).focus();
        return;
      }

      setLoading(true);
      try {
        const result = await global.AiccAuthService.login(credentials);
        enterWorkbench(result);
      } catch (error) {
        const knownMessage = {
          LOGIN_FAILED: "账号或密码错误，请重新输入",
          NETWORK_ERROR: "网络连接异常，请稍后重试",
          SERVICE_ERROR: "系统暂时无法访问，请稍后重试",
        };
        formError.textContent = error?.code === "LOGIN_FAILED" && error.message
          ? error.message
          : knownMessage[error?.code] || knownMessage.SERVICE_ERROR;
        passwordInput.focus();
        passwordInput.select();
      } finally {
        setLoading(false);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})(window, document);
