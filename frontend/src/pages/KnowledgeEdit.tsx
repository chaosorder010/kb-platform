import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd/es/upload/interface";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { authFetch, getAccessToken, hasPermission } from "../auth";
import {
  fetchDepartments,
  fetchRoles,
  fetchUsers,
  type DepartmentNode,
  type OrgRole,
  type OrgUser,
} from "../orgApi";

type Attachment = {
  id: string;
  filename: string;
  object_key: string;
  size: number;
};

type KnowledgeUnit = {
  id: string;
  unit_code: string;
  title: string;
  content: string;
  tags: string[];
  status: string;
  category: string;
  permission_summary: string;
  data_permissions: DataPermission[];
  attachments: Attachment[];
};

type DataPermission = {
  type: "global" | "department" | "role" | "user";
  id: string;
  name?: string;
};

type UnitVersion = {
  id: string;
  version: number;
  title: string;
  content: string;
  tags: string[];
  status: string;
  editor_id: string;
  editor_name: string;
  created_at: string;
};

const statusOptions = [
  { value: "draft", label: "草稿" },
  { value: "published", label: "已发布" },
  { value: "disabled", label: "已停用" },
];

async function apiJson(path: string, init: RequestInit = {}) {
  const response = await authFetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "请求失败");
  }
  return response.json();
}

function flattenDepartments(nodes: DepartmentNode[]): { id: string; name: string }[] {
  const out: { id: string; name: string }[] = [];
  const walk = (list: DepartmentNode[]) => {
    for (const node of list) {
      out.push({ id: node.id, name: node.name });
      if (node.children?.length) walk(node.children);
    }
  };
  walk(nodes);
  return out;
}

export default function KnowledgeEditPage() {
  const { id } = useParams<{ id: string }>();
  const [unit, setUnit] = useState<KnowledgeUnit | null>(null);
  const [versions, setVersions] = useState<UnitVersion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [status, setStatus] = useState("draft");
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [permOpen, setPermOpen] = useState(false);
  const [departments, setDepartments] = useState<{ id: string; name: string }[]>([]);
  const [roles, setRoles] = useState<OrgRole[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [permGlobal, setPermGlobal] = useState(false);
  const [permDeptIds, setPermDeptIds] = useState<string[]>([]);
  const [permRoleIds, setPermRoleIds] = useState<string[]>([]);
  const [permUserIds, setPermUserIds] = useState<string[]>([]);
  const [permSaving, setPermSaving] = useState(false);

  const canView = hasPermission("knowledge:view") || hasPermission("menu:knowledge");
  const canUpdate = hasPermission("knowledge:update");
  const canPerm = hasPermission("knowledge:permission");

  const load = useCallback(async () => {
    if (!id) return;
    const [detail, versionBody] = await Promise.all([
      apiJson(`/api/knowledge/units/${id}`),
      apiJson(`/api/knowledge/units/${id}/versions`),
    ]);
    setUnit(detail);
    setTitle(detail.title || "");
    setContent(detail.content || "");
    setTags(detail.tags || []);
    setStatus(detail.status || "draft");
    setVersions(versionBody.items || []);
  }, [id]);

  useEffect(() => {
    if (!getAccessToken() || !canView || !id) return;
    load().catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [load, canView, id]);

  const versionColumns = useMemo(
    () => [
      { title: "版本", dataIndex: "version", key: "version", width: 80 },
      { title: "标题", dataIndex: "title", key: "title" },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (value: string) =>
          statusOptions.find((o) => o.value === value)?.label || value,
      },
      {
        title: "编辑人",
        key: "editor",
        render: (_: unknown, row: UnitVersion) => row.editor_name || row.editor_id,
      },
      { title: "时间", dataIndex: "created_at", key: "created_at" },
    ],
    [],
  );

  if (!getAccessToken()) {
    return <Navigate to="/login" replace />;
  }
  if (!canView) {
    return <Navigate to="/" replace />;
  }

  async function onSave() {
    if (!id) return;
    setSaving(true);
    setError(null);
    try {
      await apiJson(`/api/knowledge/units/${id}`, {
        method: "PUT",
        body: JSON.stringify({ title, content, tags, status }),
      });
      if (fileList.length) {
        for (const file of fileList) {
          if (!file.originFileObj) continue;
          const form = new FormData();
          form.append("file", file.originFileObj, file.name);
          const token = getAccessToken();
          const response = await fetch(`/api/knowledge/units/${id}/attachments`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: form,
          });
          if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.detail || "附件上传失败");
          }
        }
        setFileList([]);
      }
      message.success("已保存并生成版本快照");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function openPermissions() {
    if (!unit) return;
    setError(null);
    try {
      const [deps, roleList, userList] = await Promise.all([
        fetchDepartments(),
        fetchRoles(),
        fetchUsers(),
      ]);
      setDepartments(flattenDepartments(deps));
      setRoles(roleList);
      setUsers(userList);
      const perms = unit.data_permissions || [];
      setPermGlobal(perms.some((p) => p.type === "global"));
      setPermDeptIds(perms.filter((p) => p.type === "department").map((p) => p.id));
      setPermRoleIds(perms.filter((p) => p.type === "role").map((p) => p.id));
      setPermUserIds(perms.filter((p) => p.type === "user").map((p) => p.id));
      setPermOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载权限选项失败");
    }
  }

  async function savePermissions() {
    if (!id) return;
    setPermSaving(true);
    try {
      const permissions: DataPermission[] = [];
      if (permGlobal) {
        permissions.push({ type: "global", id: "*", name: "全局" });
      }
      for (const deptId of permDeptIds) {
        const dept = departments.find((d) => d.id === deptId);
        permissions.push({
          type: "department",
          id: deptId,
          name: dept?.name || deptId,
        });
      }
      for (const roleId of permRoleIds) {
        const role = roles.find((r) => r.id === roleId);
        permissions.push({
          type: "role",
          id: roleId,
          name: role?.role_name || roleId,
        });
      }
      for (const userId of permUserIds) {
        const user = users.find((u) => u.id === userId);
        permissions.push({
          type: "user",
          id: userId,
          name: user?.display_name || userId,
        });
      }
      const updated = await apiJson(`/api/knowledge/units/${id}/permissions`, {
        method: "POST",
        body: JSON.stringify({ permissions }),
      });
      setUnit(updated);
      message.success("数据权限已生效");
      setPermOpen(false);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存权限失败");
    } finally {
      setPermSaving(false);
    }
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Space>
        <Link to="/knowledge">返回列表</Link>
        <span>
          编辑知识单元 {unit?.unit_code ? `· ${unit.unit_code}` : ""}
        </span>
      </Space>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <Form layout="vertical" style={{ maxWidth: 880 }}>
        <Form.Item label="标题">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={!canUpdate}
          />
        </Form.Item>
        <Form.Item label="标签">
          <Select
            mode="tags"
            value={tags}
            onChange={setTags}
            tokenSeparators={[","]}
            disabled={!canUpdate}
            placeholder="输入后回车添加标签"
          />
        </Form.Item>
        <Form.Item label="状态">
          <Select
            value={status}
            onChange={setStatus}
            options={statusOptions}
            disabled={!canUpdate}
            style={{ width: 200 }}
          />
        </Form.Item>
        <Form.Item label="正文">
          <Input.TextArea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={12}
            disabled={!canUpdate}
          />
        </Form.Item>
        <Form.Item label="附件">
          <Upload
            multiple
            fileList={fileList}
            beforeUpload={() => false}
            onChange={({ fileList: next }) => setFileList(next)}
            disabled={!canUpdate}
          >
            <Button disabled={!canUpdate}>选择附件</Button>
          </Upload>
          {unit?.attachments?.length ? (
            <Space wrap style={{ marginTop: 8 }}>
              {unit.attachments.map((att) => (
                <Tag key={att.id}>
                  {att.filename} ({att.size}B)
                </Tag>
              ))}
            </Space>
          ) : null}
        </Form.Item>
        <Form.Item label="数据权限摘要">
          <Space>
            <span>{unit?.permission_summary || "无数据权限"}</span>
            {canPerm ? (
              <Button onClick={() => void openPermissions()}>配置权限</Button>
            ) : null}
          </Space>
        </Form.Item>
        <Space>
          {canUpdate ? (
            <Button type="primary" loading={saving} onClick={() => void onSave()}>
              保存
            </Button>
          ) : null}
        </Space>
      </Form>

      <div>
        <h3>版本历史</h3>
        <Table
          rowKey="id"
          columns={versionColumns}
          dataSource={versions}
          pagination={{ pageSize: 10 }}
          expandable={{
            expandedRowRender: (row: UnitVersion) => (
              <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{row.content}</pre>
            ),
          }}
        />
      </div>

      <Modal
        title="数据权限"
        open={permOpen}
        onCancel={() => setPermOpen(false)}
        onOk={() => void savePermissions()}
        confirmLoading={permSaving}
        width={640}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Checkbox checked={permGlobal} onChange={(e) => setPermGlobal(e.target.checked)}>
            全局可见
          </Checkbox>
          <div>
            <div style={{ marginBottom: 8 }}>部门（OR）</div>
            <Select
              mode="multiple"
              style={{ width: "100%" }}
              value={permDeptIds}
              onChange={setPermDeptIds}
              options={departments.map((d) => ({ value: d.id, label: d.name }))}
              placeholder="选择部门"
            />
          </div>
          <div>
            <div style={{ marginBottom: 8 }}>角色（OR）</div>
            <Select
              mode="multiple"
              style={{ width: "100%" }}
              value={permRoleIds}
              onChange={setPermRoleIds}
              options={roles.map((r) => ({ value: r.id, label: r.role_name }))}
              placeholder="选择角色"
            />
          </div>
          <div>
            <div style={{ marginBottom: 8 }}>用户（OR）</div>
            <Select
              mode="multiple"
              style={{ width: "100%" }}
              value={permUserIds}
              onChange={setPermUserIds}
              options={users.map((u) => ({
                value: u.id,
                label: `${u.display_name} (${u.username})`,
              }))}
              placeholder="选择用户"
            />
          </div>
          <Alert
            type="info"
            showIcon
            message="多选混合权限按 OR 生效；未配置时任意提问者均不可访问。"
          />
        </Space>
      </Modal>
    </Space>
  );
}
