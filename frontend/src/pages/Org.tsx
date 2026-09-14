import { Card, Tabs } from "antd";
import { Navigate } from "react-router-dom";
import { getAccessToken, hasPermission } from "../auth";
import OrgDepartmentsPage from "./OrgDepartments";
import OrgRolesPage from "./OrgRoles";
import OrgUsersPage from "./OrgUsers";

export default function OrgPage() {
  if (!getAccessToken()) {
    return <Navigate to="/login" replace />;
  }
  if (!hasPermission("menu:org")) {
    return <Navigate to="/" replace />;
  }

  const items = [];
  if (hasPermission("user:view")) {
    items.push({ key: "users", label: "用户", children: <OrgUsersPage /> });
  }
  if (hasPermission("role:manage") || hasPermission("menu:org")) {
    items.push({ key: "roles", label: "角色", children: <OrgRolesPage /> });
  }
  if (
    hasPermission("dept:manage") ||
    hasPermission("menu:org") ||
    hasPermission("user:view")
  ) {
    items.push({
      key: "departments",
      label: "部门",
      children: <OrgDepartmentsPage />,
    });
  }

  return (
    <Card title="组织管理">
      <Tabs items={items} />
    </Card>
  );
}
