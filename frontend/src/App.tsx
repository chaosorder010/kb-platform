import { Layout, Menu, Typography } from "antd";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import LoginPage from "./pages/Login";
import ProfilePage from "./pages/Profile";

const { Header, Content } = Layout;

const menuItems = [
  { key: "/", label: <Link to="/">首页</Link> },
  { key: "/login", label: <Link to="/login">登录</Link> },
  { key: "/profile", label: <Link to="/profile">个人中心</Link> },
  { key: "/org", label: <Link to="/org">组织</Link> },
  { key: "/knowledge", label: <Link to="/knowledge">知识库</Link> },
  { key: "/ai", label: <Link to="/ai">AI 对话</Link> },
  { key: "/dashboard", label: <Link to="/dashboard">看板</Link> },
  { key: "/settlement", label: <Link to="/settlement">沉淀</Link> },
];

function Page({ title }: { title: string }) {
  return (
    <Typography.Title level={3} style={{ margin: 0 }}>
      {title}
    </Typography.Title>
  );
}

export default function App() {
  const location = useLocation();
  const selected =
    menuItems.find((item) =>
      item.key === "/"
        ? location.pathname === "/"
        : location.pathname.startsWith(item.key),
    )?.key ?? "/";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <Typography.Text style={{ color: "#fff", whiteSpace: "nowrap" }}>
          知识库管理平台
        </Typography.Text>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selected]}
          items={menuItems}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<Page title="首页" />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/org" element={<Page title="组织管理" />} />
          <Route path="/knowledge" element={<Page title="知识单元" />} />
          <Route path="/ai" element={<Page title="AI 对话台" />} />
          <Route path="/dashboard" element={<Page title="业务看板" />} />
          <Route path="/settlement" element={<Page title="知识沉淀" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}
