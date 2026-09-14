import { authFetch } from "./auth";

export type UserBrief = {
  id: string;
  username: string;
  display_name: string;
};

export type DepartmentNode = {
  id: string;
  name: string;
  parent_id: string | null;
  sort_order: number;
  leader: UserBrief | null;
  members: UserBrief[];
  children: DepartmentNode[];
};

export type OrgUser = {
  id: string;
  username: string;
  display_name: string;
  status: string;
  department: { id: string; name: string };
  roles: { id: string; role_name: string; role_code: string }[];
};

export type OrgRole = {
  id: string;
  role_name: string;
  role_code: string;
  description: string;
  permissions: string[];
};

export type PermissionNode = {
  code: string;
  name: string;
  children: PermissionNode[];
};

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "请求失败");
  }
  return (await response.json()) as T;
}

export async function fetchDepartments(): Promise<DepartmentNode[]> {
  return readJson(await authFetch("/api/org/departments"));
}

export async function fetchUsers(): Promise<OrgUser[]> {
  return readJson(await authFetch("/api/org/users"));
}

export async function createUser(payload: {
  username: string;
  password: string;
  display_name: string;
  department_id: string;
  role_ids: string[];
  status?: string;
}): Promise<OrgUser> {
  return readJson(
    await authFetch("/api/org/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export async function updateUser(
  userId: string,
  payload: {
    display_name?: string;
    department_id?: string;
    role_ids?: string[];
    status?: string;
    password?: string;
  },
): Promise<OrgUser> {
  return readJson(
    await authFetch(`/api/org/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export async function fetchRoles(): Promise<OrgRole[]> {
  return readJson(await authFetch("/api/org/roles"));
}

export async function fetchPermissionTree(): Promise<PermissionNode[]> {
  return readJson(await authFetch("/api/org/permissions/tree"));
}

export async function updateRolePermissions(
  roleId: string,
  permissions: string[],
): Promise<OrgRole> {
  return readJson(
    await authFetch(`/api/org/roles/${roleId}/permissions`, {
      method: "POST",
      body: JSON.stringify({ permissions }),
    }),
  );
}

export function flattenDepartments(
  nodes: DepartmentNode[],
): { id: string; name: string }[] {
  const rows: { id: string; name: string }[] = [];
  const walk = (list: DepartmentNode[], prefix = "") => {
    for (const node of list) {
      const label = prefix ? `${prefix} / ${node.name}` : node.name;
      rows.push({ id: node.id, name: label });
      if (node.children?.length) walk(node.children, label);
    }
  };
  walk(nodes);
  return rows;
}
