import { Alert, Button, Card, Descriptions, Spin, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  clearSession,
  fetchMe,
  getAccessToken,
  type MeResult,
} from "../auth";

export default function ProfilePage() {
  const [profile, setProfile] = useState<MeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!getAccessToken()) {
        setError("请先登录");
        setLoading(false);
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) setProfile(me);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <Spin tip="加载个人中心…" />;
  }

  if (error || !profile) {
    return (
      <Card title="个人中心">
        <Alert type="warning" showIcon message={error || "暂无数据"} />
        <Button type="link" style={{ paddingLeft: 0, marginTop: 8 }}>
          <Link to="/login">前往登录</Link>
        </Button>
      </Card>
    );
  }

  return (
    <Card
      title="个人中心"
      extra={
        <Button
          onClick={() => {
            clearSession();
            window.location.href = "/login";
          }}
        >
          退出登录
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        当前登录身份、所属部门与角色。
      </Typography.Paragraph>
      <Descriptions bordered column={1} size="middle">
        <Descriptions.Item label="用户名">{profile.username}</Descriptions.Item>
        <Descriptions.Item label="显示名">
          {profile.display_name}
        </Descriptions.Item>
        <Descriptions.Item label="部门">
          {profile.department.name}
        </Descriptions.Item>
        <Descriptions.Item label="角色">
          {profile.roles.map((r) => r.role_name).join("、") || "无"}
        </Descriptions.Item>
        <Descriptions.Item label="状态">{profile.status}</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
