import {
  Alert,
  Button,
  Card,
  Space,
  Tree,
  Typography,
  message,
} from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getAccessToken, hasPermission } from "../auth";
import {
  fetchPermissionTree,
  fetchRoles,
  updateRolePermissions,
  type OrgRole,
  type PermissionNode,
} from "../orgApi";

function toTreeData(nodes: PermissionNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.code,
    title: `${node.name}（${node.code}）`,
    children: node.children?.length ? toTreeData(node.children) : undefined,
  }));
}

function collectCodes(nodes: PermissionNode[]): string[] {
  const codes: string[] = [];
  const walk = (list: PermissionNode[]) => {
    for (const node of list) {
      codes.push(node.code);
      if (node.children?.length) walk(node.children);
    }
  };
  walk(nodes);
  return codes;
}

export default function OrgRolesPage() {
  const [roles, setRoles] = useState<OrgRole[]>([]);
  const [tree, setTree] = useState<PermissionNode[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [checked, setChecked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const canManage = hasPermission("role:manage");

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const [roleList, permissionTree] = await Promise.all([
        fetchRoles(),
        fetchPermissionTree(),
      ]);
      setRoles(roleList);
      setTree(permissionTree);
      const current =
        roleList.find((r) => r.id === selectedRoleId) || roleList[0] || null;
      if (current) {
        setSelectedRoleId(current.id);
        setChecked(current.permissions);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!getAccessToken()) {
      setError("请先登录");
      setLoading(false);
      return;
    }
    if (!hasPermission("role:manage") && !hasPermission("menu:org")) {
      setError("无角色管理权限");
      setLoading(false);
      return;
    }
    void reload();
  }, []);

  const treeData = useMemo(() => toTreeData(tree), [tree]);
  const selectedRole = roles.find((r) => r.id === selectedRoleId) || null;

  async function save() {
    if (!selectedRole || !canManage) return;
    try {
      const updated = await updateRolePermissions(selectedRole.id, checked);
      setRoles((prev) =>
        prev.map((role) => (role.id === updated.id ? updated : role)),
      );
      message.success("权限已保存");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  if (error) {
    return (
      <Alert
        type="warning"
        showIcon
        message={error}
        action={
          <Button type="link">
            <Link to="/login">前往登录</Link>
          </Button>
        }
      />
    );
  }

  return (
    <Space align="start" size={16} style={{ width: "100%" }} wrap>
      <Card title="角色" loading={loading} style={{ width: 280 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          {roles.map((role) => (
            <Button
              key={role.id}
              type={role.id === selectedRoleId ? "primary" : "default"}
              block
              onClick={() => {
                setSelectedRoleId(role.id);
                setChecked(role.permissions);
              }}
            >
              {role.role_name}
            </Button>
          ))}
        </Space>
      </Card>
      <Card
        title={selectedRole ? `${selectedRole.role_name} · 操作权限树` : "权限树"}
        loading={loading}
        style={{ flex: 1, minWidth: 360 }}
        extra={
          canManage ? (
            <Button type="primary" onClick={() => void save()}>
              保存权限
            </Button>
          ) : null
        }
      >
        <Typography.Paragraph type="secondary">
          勾选菜单与按钮级权限，保存后影响该角色用户可见范围。
        </Typography.Paragraph>
        <Tree
          checkable
          defaultExpandAll
          treeData={treeData}
          checkedKeys={checked}
          onCheck={(keys) => {
            const next = Array.isArray(keys) ? keys : keys.checked;
            setChecked(next.map(String).filter((code) => collectCodes(tree).includes(code)));
          }}
        />
      </Card>
    </Space>
  );
}
