import { Alert, Button, Card, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAccessToken, hasPermission } from "../auth";
import { fetchDepartments, type DepartmentNode } from "../orgApi";

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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
        setTree(await fetchDepartments());
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

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
    <Card title="部门树" loading={loading}>
      <Typography.Paragraph type="secondary">
        展示部门层级、负责人与成员关联。
      </Typography.Paragraph>
      <Tree defaultExpandAll treeData={toTreeData(tree)} />
    </Card>
  );
}
