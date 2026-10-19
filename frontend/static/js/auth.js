/**
 * Auth module — manages JWT token and user session in localStorage.
 */
const Auth = (() => {
  const TOKEN_KEY = "sf_token";
  const USER_KEY  = "sf_user";

  return {
    setSession(token, user) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    },
    getToken() {
      return localStorage.getItem(TOKEN_KEY);
    },
    getUser() {
      try {
        return JSON.parse(localStorage.getItem(USER_KEY));
      } catch { return null; }
    },
    isLoggedIn() {
      return !!localStorage.getItem(TOKEN_KEY);
    },
    logout() {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      window.location.href = "/login";
    },
    requireLogin() {
      if (!this.isLoggedIn()) window.location.href = "/login";
    },
    requireAdmin() {
      if (!this.isLoggedIn()) { window.location.href = "/login"; return; }
      const user = this.getUser();
      if (!user || user.role !== "ADMIN") window.location.href = "/dashboard";
    }
  };
})();
