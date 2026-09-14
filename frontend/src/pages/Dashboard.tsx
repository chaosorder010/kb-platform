import {
  Card,
  Col,
  Progress,
  Radio,
  Row,
  Space,
  Statistic,
  Table,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { authFetch, getAccessToken, hasPermission } from "../auth";

type Metrics = {
  visit_count: number;
  uv: number;
  knowledge_unit_count: number;
  total_tokens: number;
  avg_response_time_ms: number;
};

type QuestionRank = { question: string; count: number };
type UnitRank = { unit_id: string; title: string; count: number };
type TrendPoint = {
  bucket: string;
  visit_count: number;
  total_tokens: number;
  avg_response_time_ms: number;
};
type DistBucket = { bucket: string; count: number };

async function apiJson<T>(path: string): Promise<T> {
  const response = await authFetch(path);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail || "加载看板失败",
    );
  }
  return response.json() as Promise<T>;
}

function BarList({
  items,
}: {
  items: { label: string; value: number }[];
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <Space direction="vertical" style={{ width: "100%" }} size={8}>
      {items.map((item) => (
        <div key={item.label}>
          <Typography.Text>
            {item.label}（{item.value}）
          </Typography.Text>
          <Progress
            percent={Math.round((item.value / max) * 100)}
            showInfo={false}
            size="small"
          />
        </div>
      ))}
    </Space>
  );
}

export default function DashboardPage() {
  const loggedIn = !!getAccessToken();
  const canAccess =
    hasPermission("menu:dashboard") || hasPermission("dashboard:view");
  const [granularity, setGranularity] = useState<"day" | "week">("day");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [questions, setQuestions] = useState<QuestionRank[]>([]);
  const [units, setUnits] = useState<UnitRank[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [dist, setDist] = useState<DistBucket[]>([]);

  useEffect(() => {
    if (!loggedIn || !canAccess) return;
    let cancelled = false;
    (async () => {
      try {
        const [m, q, u, stats] = await Promise.all([
          apiJson<Metrics>("/api/dashboard/metrics"),
          apiJson<{ items: QuestionRank[] }>(
            "/api/dashboard/rankings/questions?limit=10",
          ),
          apiJson<{ items: UnitRank[] }>(
            "/api/dashboard/rankings/units?limit=10",
          ),
          apiJson<{
            trend: TrendPoint[];
            response_time_distribution: DistBucket[];
          }>(`/api/dashboard/stats/tokens?granularity=${granularity}`),
        ]);
        if (cancelled) return;
        setMetrics(m);
        setQuestions(q.items || []);
        setUnits(u.items || []);
        setTrend(stats.trend || []);
        setDist(stats.response_time_distribution || []);
      } catch (err) {
        if (!cancelled) {
          message.error(err instanceof Error ? err.message : "加载看板失败");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loggedIn, canAccess, granularity]);

  const visitBars = useMemo(
    () =>
      trend.map((item) => ({
        label: item.bucket,
        value: item.visit_count,
      })),
    [trend],
  );
  const tokenBars = useMemo(
    () =>
      trend.map((item) => ({
        label: item.bucket,
        value: item.total_tokens,
      })),
    [trend],
  );
  const latencyBars = useMemo(
    () =>
      trend.map((item) => ({
        label: item.bucket,
        value: item.avg_response_time_ms,
      })),
    [trend],
  );
  const distBars = useMemo(
    () => dist.map((item) => ({ label: item.bucket, value: item.count })),
    [dist],
  );

  if (!loggedIn) return <Navigate to="/login" replace />;
  if (!canAccess) return <Navigate to="/" replace />;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        业务看板
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
        指标来自问答访问日志聚合，可与日志逐条核对。
      </Typography.Paragraph>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="访问次数" value={metrics?.visit_count ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="独立用户 UV" value={metrics?.uv ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="知识单元数"
              value={metrics?.knowledge_unit_count ?? 0}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Statistic title="Token 总量" value={metrics?.total_tokens ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Statistic
              title="平均响应时间 (ms)"
              value={metrics?.avg_response_time_ms ?? 0}
              precision={2}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="常见问题 TOP">
            <Table
              size="small"
              pagination={false}
              rowKey={(r) => r.question}
              dataSource={questions}
              columns={[
                { title: "问题", dataIndex: "question" },
                { title: "次数", dataIndex: "count", width: 80 },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="知识单元热度 TOP">
            <Table
              size="small"
              pagination={false}
              rowKey={(r) => r.unit_id}
              dataSource={units}
              columns={[
                { title: "知识单元", dataIndex: "title" },
                { title: "次数", dataIndex: "count", width: 80 },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="趋势与分布"
        extra={
          <Radio.Group
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
            optionType="button"
            options={[
              { label: "按日", value: "day" },
              { label: "按周", value: "week" },
            ]}
          />
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Typography.Title level={5}>访问趋势</Typography.Title>
            <BarList items={visitBars} />
          </Col>
          <Col xs={24} md={12}>
            <Typography.Title level={5}>Token 走势</Typography.Title>
            <BarList items={tokenBars} />
          </Col>
          <Col xs={24} md={12}>
            <Typography.Title level={5}>平均耗时走势</Typography.Title>
            <BarList items={latencyBars} />
          </Col>
          <Col xs={24} md={12}>
            <Typography.Title level={5}>响应时间分布</Typography.Title>
            <BarList items={distBars} />
          </Col>
        </Row>
      </Card>
    </Space>
  );
}
