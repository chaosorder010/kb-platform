import { Alert, Button, Card, Form, Input, Select, Space, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getAccessToken, hasPermission } from "../auth";
import {
  fetchDepartments,
  fetchUsers,
  updateDepartment,
  type DepartmentNode,
  type OrgUser,
} from "../orgApi";

function flatten(nodes: DepartmentNode[], acc: DepartmentNode[] = []): DepartmentNode[] {
  for (const node of nodes) {
    acc.push(node);
    if (node.children?.length) flatten(node.children, acc);
  }
  return acc;
}

function toTreeData(nodes: DepartmentNode[]): DataNode[] {
  return nodes.map((node) => {
    const leader = node.leader
      ? `负责人：${node.leader.display_name}`
      : "负责人：未设置";
    const members =
      node.members.length > 0
        ? `成员：${node.members.map((m) => m.display_name).join("、")}`
        : "成员：无";
    return {
      key: node.id,
      title: (
        <span>
          <strong>{node.name}</strong>
          <Typography.Text type="secondary" style={{ marginLeft: 12 }}>
            {leader}；{members}
          </Typography.Text>
        </span>
      ),
      children: node.children?.length ? toTreeData(node.children) : undefined,
    };
  });
}

export default function OrgDepartmentsPage() {
  const [tree, setTree] = useState<DepartmentNode[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canManage = hasPermission("dept:manage");

  async function reload() {
    const [deps, userList] = await Promise.all([
      fetchDepartments(),
      canManage ? fetchUsers() : Promise.resolve([]),
    ]);
    setTree(deps);
    setUsers(userList);
    const flat = flatten(deps);
    if (!selectedId && flat[0]) setSelectedId(flat[0].id);
  }

  useEffect(() => {
    if (!getAccessToken()) {
      setError("请先登录");
      setLoading(false);
      return;
    }
    if (
      !hasPermission("menu:org") &&
      !hasPermission("dept:manage") &&
      !hasPermission("user:view")
    ) {
      setError("无部门查看权限");
      setLoading(false);
      return;
    }
    void (async () => {
      try {
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selected = useMemo(
    () => flatten(tree).find((d) => d.id === selectedId) || null,
    [tree, selectedId],
  );

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
    <Space align="start" size={24} style={{ width: "100%" }}>
      <Card title="部门树" loading={loading} style={{ minWidth: 420 }}>
        <Tree
          defaultExpandAll
          treeData={toTreeData(tree)}
          selectedKeys={selectedId ? [selectedId] : []}
          onSelect={(keys) => {
            if (keys[0]) setSelectedId(String(keys[0]));
          }}
        />
      </Card>
      {canManage ? (
        <Card title="维护负责人与成员" loading={loading} style={{ minWidth: 360 }}>
          {selected ? (
            <Form
              key={selected.id}
              layout="vertical"
              initialValues={{
                leader_id: selected.leader?.id,
                member_ids: selected.members.map((m) => m.id),
              }}
              onFinish={(values) => {
                void (async () => {
                  setSaving(true);
                  try {
                    await updateDepartment(selected.id, {
                      leader_id: values.leader_id || "",
                      member_ids: values.member_ids || [],
                    });
                    await reload();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "保存失败");
                  } finally {
                    setSaving(false);
                  }
                })();
              }}
            >
              <Form.Item label="部门">
                <Input value={selected.name} disabled />
              </Form.Item>
              <Form.Item label="负责人" name="leader_id">
                <Select
                  allowClear
                  options={users.map((u) => ({
                    value: u.id,
                    label: `${u.display_name} (${u.username})`,
                  }))}
                />
              </Form.Item>
              <Form.Item label="成员" name="member_ids">
                <Select
                  mode="multiple"
                  options={users.map((u) => ({
                    value: u.id,
                    label: `${u.display_name} (${u.username})`,
                  }))}
                />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存
              </Button>
            </Form>
          ) : (
            <Typography.Text type="secondary">请选择部门</Typography.Text>
          )}
        </Card>
      ) : null}
    </Space>
  );
}
