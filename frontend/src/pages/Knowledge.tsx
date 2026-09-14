import { Alert, Button, Form, Input, Modal, Progress, Select, Space, Table, Upload, message } from "antd";
import type { UploadFile } from "antd/es/upload/interface";
import { useCallback, useEffect, useMemo, useState, type Key } from "react";
import { Link, Navigate } from "react-router-dom";
import { authFetch, getAccessToken, hasPermission } from "../auth";

type ImportTask = {
  task_id: string;
  unit_id: string;
  filename: string;
};

type TaskStatus = {
  task_id: string;
  unit_id: string;
  status: string;
  progress: number;
  done_list: string[];
  running_list: string[];
  filename: string;
  error: string;
};

type KnowledgeUnit = {
  id: string;
  unit_code: string;
  title: string;
  category: string;
  file_type: string;
  permission_summary: string;
  creator_name: string;
  created_at: string;
  updated_at: string;
  status: string;
};

const statusLabel: Record<string, string> = {
  processing: "解析中",
  published: "已发布",
  failed: "失败",
  draft: "草稿",
  disabled: "已停用",
  pending: "排队中",
  completed: "已完成",
};

async function apiJson(path: string, init: RequestInit = {}) {
  const response = await authFetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "请求失败");
  }
  return response.json();
}

async function apiUpload(path: string, form: FormData) {
  const token = getAccessToken();
  if (!token) {
    throw new Error("未登录");
  }
  const response = await fetch(path, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "请求失败");
  }
  return response.json();
}

export default function KnowledgePage() {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [category, setCategory] = useState("");
  const [importing, setImporting] = useState(false);
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [units, setUnits] = useState<KnowledgeUnit[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [filterCategory, setFilterCategory] = useState<string | undefined>();
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  const canView = hasPermission("knowledge:view") || hasPermission("menu:knowledge");
  const canCreate = hasPermission("knowledge:create");
  const canUpdate = hasPermission("knowledge:update");
  const canDelete = hasPermission("knowledge:delete");
  const canPerm = hasPermission("knowledge:permission");
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [permTarget, setPermTarget] = useState<KnowledgeUnit | null>(null);
  const [permOpen, setPermOpen] = useState(false);
  const [permGlobal, setPermGlobal] = useState(false);
  const [permSummaryDraft, setPermSummaryDraft] = useState("");

  const loadUnits = useCallback(async () => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (filterCategory) params.set("category", filterCategory);
    if (filterStatus) params.set("status", filterStatus);
    const data = await apiJson(`/api/knowledge/units?${params.toString()}`);
    setUnits(data.items || []);
    setTotal(data.total || 0);
  }, [q, filterCategory, filterStatus]);

  useEffect(() => {
    if (!getAccessToken() || !canView) return;
    loadUnits().catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [loadUnits, canView]);

  useEffect(() => {
    if (!tasks.some((t) => t.status === "processing" || t.status === "pending")) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await Promise.all(
          tasks.map(async (task) => {
            if (task.status === "completed" || task.status === "failed") {
              return task;
            }
            return (await apiJson(
              `/api/knowledge/import/tasks/${task.task_id}`,
            )) as TaskStatus;
          }),
        );
        setTasks(next);
        if (next.every((t) => t.status === "completed" || t.status === "failed")) {
          await loadUnits();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "进度查询失败");
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [tasks, loadUnits]);

  const columns = useMemo(
    () => [
      { title: "编号", dataIndex: "unit_code", key: "unit_code" },
      { title: "标题", dataIndex: "title", key: "title" },
      { title: "分类", dataIndex: "category", key: "category" },
      { title: "格式", dataIndex: "file_type", key: "file_type" },
      { title: "权限摘要", dataIndex: "permission_summary", key: "permission_summary" },
      { title: "创建人", dataIndex: "creator_name", key: "creator_name" },
      { title: "更新时间", dataIndex: "updated_at", key: "updated_at" },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (value: string) => statusLabel[value] || value,
      },
      {
        title: "操作",
        key: "actions",
        render: (_: unknown, row: KnowledgeUnit) => (
          <Space>
            {canUpdate || canView ? <Link to={`/knowledge/${row.id}`}>编辑</Link> : null}
            {canPerm ? (
              <Button
                type="link"
                style={{ padding: 0 }}
                onClick={() => {
                  setPermTarget(row);
                  setPermGlobal(false);
                  setPermSummaryDraft(row.permission_summary || "");
                  setPermOpen(true);
                }}
              >
                权限
              </Button>
            ) : null}
          </Space>
        ),
      },
    ],
    [canUpdate, canView, canPerm],
  );

  async function onBatchDelete() {
    if (!selectedRowKeys.length) {
      message.warning("请先选择要删除的知识单元");
      return;
    }
    Modal.confirm({
      title: `确认删除 ${selectedRowKeys.length} 个知识单元？`,
      okType: "danger",
      onOk: async () => {
        await apiJson("/api/knowledge/units", {
          method: "DELETE",
          body: JSON.stringify({ ids: selectedRowKeys }),
        });
        message.success("已批量删除");
        setSelectedRowKeys([]);
        await loadUnits();
      },
    });
  }

  async function saveQuickPermission() {
    if (!permTarget) return;
    const permissions = permGlobal
      ? [{ type: "global", id: "*", name: "全局" }]
      : [];
    const updated = await apiJson(`/api/knowledge/units/${permTarget.id}/permissions`, {
      method: "POST",
      body: JSON.stringify({ permissions }),
    });
    message.success(`权限已更新：${updated.permission_summary}`);
    setPermOpen(false);
    setPermTarget(null);
    await loadUnits();
  }

  if (!getAccessToken()) {
    return <Navigate to="/login" replace />;
  }
  if (!canView) {
    return <Navigate to="/" replace />;
  }

  async function onImport() {
    setError(null);
    if (!fileList.length) {
      message.warning("请先选择文件");
      return;
    }
    setImporting(true);
    try {
      const form = new FormData();
      for (const file of fileList) {
        if (file.originFileObj) {
          form.append("files", file.originFileObj, file.name);
        }
      }
      const query = category ? `?category=${encodeURIComponent(category)}` : "";
      const data = await apiUpload(`/api/knowledge/import${query}`, form);
      const started: ImportTask[] = data.tasks || [];
      setTasks(
        started.map((task) => ({
          ...task,
          status: "pending",
          progress: 0,
          done_list: [],
          running_list: ["排队中"],
          error: "",
        })),
      );
      setFileList([]);
      message.success(data.message || "导入已提交");
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入失败");
    } finally {
      setImporting(false);
    }
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      {canCreate ? (
        <div>
          <h2 style={{ marginTop: 0 }}>知识导入中心</h2>
          {error ? (
            <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />
          ) : null}
          <Form layout="inline" style={{ marginBottom: 12 }}>
            <Form.Item label="分类">
              <Input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="可选分类"
                style={{ width: 180 }}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" loading={importing} onClick={onImport}>
                开始导入
              </Button>
            </Form.Item>
          </Form>
          <Upload.Dragger
            multiple
            directory
            accept=".pdf,.md,.markdown,.txt,.doc,.docx"
            fileList={fileList}
            beforeUpload={() => false}
            onChange={({ fileList: next }) => setFileList(next)}
          >
            <p>点击或拖拽上传 PDF / Word / Markdown / TXT，支持多文件与文件夹选择</p>
          </Upload.Dragger>
          {tasks.length ? (
            <Space direction="vertical" style={{ width: "100%", marginTop: 16 }}>
              {tasks.map((task) => (
                <div key={task.task_id}>
                  <div>
                    {task.filename} · {statusLabel[task.status] || task.status}
                  </div>
                  <Progress
                    percent={task.progress}
                    status={task.status === "failed" ? "exception" : undefined}
                  />
                  {task.error ? <Alert type="error" message={task.error} /> : null}
                </div>
              ))}
            </Space>
          ) : null}
        </div>
      ) : null}

      <div>
        <h2>知识单元列表</h2>
        <Space wrap style={{ marginBottom: 12 }}>
          {canDelete ? (
            <Button danger disabled={!selectedRowKeys.length} onClick={() => void onBatchDelete()}>
              批量删除
            </Button>
          ) : null}
          <Input.Search
            placeholder="搜索标题/编号/文件名"
            allowClear
            onSearch={(value) => setQ(value)}
            style={{ width: 260 }}
          />
          <Select
            allowClear
            placeholder="分类"
            style={{ width: 160 }}
            value={filterCategory}
            onChange={setFilterCategory}
            options={[
              { value: "产品手册", label: "产品手册" },
              { value: "运维", label: "运维" },
            ]}
          />
          <Select
            allowClear
            placeholder="状态"
            style={{ width: 140 }}
            value={filterStatus}
            onChange={setFilterStatus}
            options={[
              { value: "processing", label: "解析中" },
              { value: "published", label: "已发布" },
              { value: "failed", label: "失败" },
            ]}
          />
          <Button onClick={() => loadUnits().catch((err) => setError(err.message))}>
            刷新
          </Button>
        </Space>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={units}
          pagination={{ total, pageSize: 20 }}
          rowSelection={
            canDelete
              ? {
                  selectedRowKeys,
                  onChange: (keys) => setSelectedRowKeys(keys),
                }
              : undefined
          }
        />
      </div>

      <Modal
        title={permTarget ? `配置权限 · ${permTarget.title}` : "配置权限"}
        open={permOpen}
        onCancel={() => setPermOpen(false)}
        onOk={() => void saveQuickPermission()}
      >
        <Space direction="vertical">
          <div>当前摘要：{permSummaryDraft || "无数据权限"}</div>
          <label>
            <input
              type="checkbox"
              checked={permGlobal}
              onChange={(e) => setPermGlobal(e.target.checked)}
            />{" "}
            设为全局可见（完整混合权限请在编辑页配置）
          </label>
          <Link to={permTarget ? `/knowledge/${permTarget.id}` : "/knowledge"}>
            打开编辑页权限弹窗
          </Link>
        </Space>
      </Modal>
    </Space>
  );
}
