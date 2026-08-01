(function createAuthService(global) {
  "use strict";

  const DEFAULT_CONFIG = Object.freeze({
    endpoint: "",
    method: "POST",
    accountField: "username",
    passwordField: "password",
    credentials: "same-origin",
    tokenStorageKey: "aicc.access-token",
  });

  class AuthError extends Error {
    constructor(code, message, status) {
      super(message);
      this.name = "AuthError";
      this.code = code;
      this.status = status || 0;
    }
  }

  function getConfig() {
    return { ...DEFAULT_CONFIG, ...(global.AICC_AUTH_CONFIG || {}) };
  }

  function safeBackendMessage(payload) {
    const message = payload?.message || payload?.detail?.message;
    if (typeof message !== "string" || !message.trim() || message.length > 80) {
      return "";
    }
    if (/traceback|exception|stack|sql|token|password|<html/i.test(message)) {
      return "";
    }
    return message.trim();
  }

  async function readPayload(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      return {};
    }
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  async function login(credentials) {
    const config = getConfig();

    // The current workbench has no user-auth API. Keep its existing local entry
    // behavior isolated here until an endpoint is supplied via AICC_AUTH_CONFIG.
    if (!config.endpoint) {
      await new Promise(resolve => global.setTimeout(resolve, 320));
      return {
        mode: "static",
        user: { account: credentials.account },
        token: "",
      };
    }

    let response;
    try {
      response = await global.fetch(config.endpoint, {
        method: config.method,
        credentials: config.credentials,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          [config.accountField]: credentials.account,
          [config.passwordField]: credentials.password,
        }),
      });
    } catch (_error) {
      throw new AuthError("NETWORK_ERROR", "网络连接异常，请稍后重试");
    }

    const payload = await readPayload(response);
    if (!response.ok) {
      if (response.status >= 500) {
        throw new AuthError("SERVICE_ERROR", "系统暂时无法访问，请稍后重试", response.status);
      }
      throw new AuthError(
        "LOGIN_FAILED",
        safeBackendMessage(payload) || "账号或密码错误，请重新输入",
        response.status,
      );
    }

    if (payload?.success === false) {
      throw new AuthError(
        "LOGIN_FAILED",
        safeBackendMessage(payload) || "账号或密码错误，请重新输入",
        response.status,
      );
    }

    const result = payload?.data || payload || {};
    const token = result.access_token || result.token || "";
    if (token) {
      try {
        global.sessionStorage.setItem(config.tokenStorageKey, token);
      } catch (_error) {
        // Cookie-based auth and the current page can still work without storage.
      }
    }
    return {
      mode: "remote",
      token,
      user: result.user || result.userInfo || { account: credentials.account },
    };
  }

  global.AiccAuthService = Object.freeze({
    AuthError,
    getConfig,
    login,
  });
})(window);
