import {
  Button,
  Input,
  Space,
  Switch,
  Table,
  Tabs,
  Typography,
  message,
} from "antd";
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { authFetch, getAccessToken, hasPermission } from "../auth";

type FaqItem = {
  id: string;
  question: string;
  answer: string;
  hit_count: number;
  related_unit_id?: string;
  related_unit_ids?: string[];
  status: string;
  cache_enabled?: boolean;
  sample_questions?: string[];
};

type GapItem = {
  id: string;
  question_pattern: string;
  sample_questions?: string[];
  ask_count: number;
  last_asked_at?: string;
  status: string;
  resolved_unit_id?: string;
};

async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "请求失败");
  }
  return response.json() as Promise<T>;
}

export default function SettlementPage() {
  const loggedIn = !!getAccessToken();
  const canManage = hasPermission("settlement:manage");
  const [recommendations, setRecommendations] = useState<FaqItem[]>([]);
  const [published, setPublished] = useState<FaqItem[]>([]);
  const [gaps, setGaps] = useState<GapItem[]>([]);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const refreshQuery = refresh ? "refresh=true" : "refresh=false";
      const [rec, pub, gapResp] = await Promise.all([
        apiJson<{ items: FaqItem[] }>(
          `/api/settlement/faqs/recommendations?${refreshQuery}`,
        ),
        apiJson<{ items: FaqItem[] }>("/api/settlement/faqs?status=published"),
        apiJson<{ items: GapItem[] }>(
          `/api/settlement/knowledge-gaps?${refreshQuery}`,
        ),
      ]);
      setRecommendations(rec.items || []);
      setPublished(pub.items || []);
      setGaps(gapResp.items || []);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loggedIn && canManage) void reload(false);
  }, [loggedIn, canManage, reload]);

  if (!loggedIn) return <Navigate to="/login" replace />;
  if (!canManage) return <Navigate to="/" replace />;

  async function onReview(id: string, action: "approve" | "reject") {
    try {
      await apiJson(`/api/settlement/faqs/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          edited_answer: editing[id] || "",
        }),
      });
      message.success(action === "approve" ? "已发布" : "已驳回");
      await reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "审核失败");
    }
  }

  async function onToggleCache(id: string, enabled: boolean) {
    try {
      await apiJson(`/api/settlement/faqs/${id}/cache`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cache_enabled: enabled }),
      });
      message.success(enabled ? "缓存已开启" : "缓存已关闭");
      await reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "更新缓存失败");
    }
  }

  async function onCreateUnit(id: string) {
    try {
      const result = await apiJson<{
        unit: { id: string; title: string };
      }>(`/api/settlement/knowledge-gaps/${id}/create-unit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      message.success(`已创建知识单元 ${result.unit.title || result.unit.id}`);
      await reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "建档失败");
    }
  }

  async function onGapStatus(id: string, statusValue: string) {
    try {
      await apiJson(`/api/settlement/knowledge-gaps/${id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: statusValue }),
      });
      message.success("状态已更新");
      await reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "更新失败");
    }
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        知识沉淀
      </Typography.Title>
      <Button onClick={() => void reload(true)} loading={loading}>
        刷新挖掘
      </Button>
      <Tabs
        items={[
          {
            key: "rec",
            label: "FAQ 推荐审核",
            children: (
              <Table
                rowKey="id"
                loading={loading}
                dataSource={recommendations}
                pagination={false}
                columns={[
                  { title: "问题", dataIndex: "question" },
                  { title: "频次", dataIndex: "hit_count", width: 80 },
                  {
                    title: "关联单元",
                    render: (_, row) =>
                      row.related_unit_id ||
                      (row.related_unit_ids || []).join(", ") ||
                      "-",
                  },
                  {
                    title: "建议答案",
                    render: (_, row) => (
                      <Input.TextArea
                        rows={2}
                        value={editing[row.id] ?? row.answer}
                        onChange={(e) =>
                          setEditing((prev) => ({
                            ...prev,
                            [row.id]: e.target.value,
                          }))
                        }
                      />
                    ),
                  },
                  {
                    title: "操作",
                    width: 180,
                    render: (_, row) => (
                      <Space>
                        <Button
                          type="primary"
                          onClick={() => void onReview(row.id, "approve")}
                        >
                          通过
                        </Button>
                        <Button
                          danger
                          onClick={() => void onReview(row.id, "reject")}
                        >
                          驳回
                        </Button>
                      </Space>
                    ),
                  },
                ]}
              />
            ),
          },
          {
            key: "gaps",
            label: "知识缺口",
            children: (
              <Table
                rowKey="id"
                loading={loading}
                dataSource={gaps}
                pagination={false}
                columns={[
                  { title: "模式", dataIndex: "question_pattern" },
                  {
                    title: "样例",
                    render: (_, row) =>
                      (row.sample_questions || []).slice(0, 3).join("；") ||
                      "-",
                  },
                  { title: "频次", dataIndex: "ask_count", width: 80 },
                  {
                    title: "最近提问",
                    dataIndex: "last_asked_at",
                    width: 200,
                  },
                  { title: "状态", dataIndex: "status", width: 110 },
                  {
                    title: "关联单元",
                    dataIndex: "resolved_unit_id",
                    width: 140,
                    render: (v) => v || "-",
                  },
                  {
                    title: "操作",
                    width: 320,
                    render: (_, row) => (
                      <Space wrap>
                        <Button
                          type="primary"
                          disabled={row.status === "resolved"}
                          onClick={() => void onCreateUnit(row.id)}
                        >
                          一键建档
                        </Button>
                        <Button
                          onClick={() => void onGapStatus(row.id, "resolved")}
                          disabled={row.status === "resolved"}
                        >
                          已解决
                        </Button>
                        <Button
                          onClick={() => void onGapStatus(row.id, "ignored")}
                        >
                          忽略
                        </Button>
                        <Button
                          onClick={() =>
                            void onGapStatus(row.id, "unresolved")
                          }
                        >
                          重开
                        </Button>
                      </Space>
                    ),
                  },
                ]}
              />
            ),
          },
          {
            key: "pub",
            label: "已发布 FAQ 库",
            children: (
              <Table
                rowKey="id"
                loading={loading}
                dataSource={published}
                pagination={false}
                columns={[
                  { title: "问题", dataIndex: "question" },
                  { title: "标准答案", dataIndex: "answer" },
                  { title: "命中次数", dataIndex: "hit_count", width: 100 },
                  {
                    title: "缓存",
                    width: 100,
                    render: (_, row) => (
                      <Switch
                        checked={!!row.cache_enabled}
                        onChange={(checked) =>
                          void onToggleCache(row.id, checked)
                        }
                      />
                    ),
                  },
                ]}
              />
            ),
          },
        ]}
      />
    </Space>
  );
}