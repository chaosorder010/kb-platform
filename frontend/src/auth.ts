export type RoleInfo = {
  id: string;
  role_name: string;
  role_code: string;
};

export type DepartmentInfo = {
  id: string;
  name: string;
};

export type UserInfo = {
  id: string;
  username: string;
  display_name: string;
  status: string;
  department: DepartmentInfo;
  roles: RoleInfo[];
};

export type LoginResult = {
  access_token: string;
  user_info: UserInfo;
  permissions: string[];
};

export type MeResult = UserInfo & {
  permissions: string[];
};

const TOKEN_KEY = "access_token";
const USER_KEY = "user_info";
const PERMS_KEY = "permissions";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserInfo;
  } catch {
    return null;
  }
}

export function getPermissions(): string[] {
  const raw = localStorage.getItem(PERMS_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as string[]) : [];
  } catch {
    return [];
  }
}

export function hasPermission(code: string): boolean {
  return getPermissions().includes(code);
}

export function persistSession(result: LoginResult): void {
  localStorage.setItem(TOKEN_KEY, result.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(result.user_info));
  localStorage.setItem(PERMS_KEY, JSON.stringify(result.permissions));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(PERMS_KEY);
}

export async function login(
  username: string,
  password: string,
): Promise<LoginResult> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "登录失败");
  }
  return (await response.json()) as LoginResult;
}

export async function fetchMe(): Promise<MeResult> {
  const token = getAccessToken();
  if (!token) {
    throw new Error("未登录");
  }
  const response = await fetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "获取个人信息失败");
  }
  const me = (await response.json()) as MeResult;
  localStorage.setItem(USER_KEY, JSON.stringify(me));
  localStorage.setItem(PERMS_KEY, JSON.stringify(me.permissions));
  return me;
}

export async function authFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();
  if (!token) {
    throw new Error("未登录");
  }
  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(input, { ...init, headers });
}
