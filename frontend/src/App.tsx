import { Layout, Menu, Typography } from "antd";
import { useMemo, type ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { getAccessToken, getPermissions, hasPermission } from "./auth";
import LoginPage from "./pages/Login";
import KnowledgePage from "./pages/Knowledge";
import KnowledgeEditPage from "./pages/KnowledgeEdit";
import OrgPage from "./pages/Org";
import ProfilePage from "./pages/Profile";
import AiChatPage from "./pages/AiChat";
import DashboardPage from "./pages/Dashboard";

const { Header, Content } = Layout;

type MenuDef = {
  key: string;
  label: string;
  permission?: string;
  always?: boolean;
};

const MENU_DEFS: MenuDef[] = [
  { key: "/", label: "首页", always: true },
  { key: "/login", label: "登录", always: true },
  { key: "/profile", label: "个人中心", always: true },
  { key: "/org", label: "组织", permission: "menu:org" },
  { key: "/knowledge", label: "知识库", permission: "menu:knowledge" },
  { key: "/ai", label: "AI 对话", permission: "menu:ai" },
  { key: "/dashboard", label: "看板", permission: "menu:dashboard" },
  { key: "/settlement", label: "沉淀", permission: "menu:settlement" },
];

function Page({ title }: { title: string }) {
  return (
    <Typography.Title level={3} style={{ margin: 0 }}>
      {title}
    </Typography.Title>
  );
}

function RequirePerm({
  code,
  children,
}: {
  code: string;
  children: ReactNode;
}) {
  if (!getAccessToken() || !hasPermission(code)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const location = useLocation();
  const permissions = getPermissions();
  const loggedIn = !!getAccessToken();

  const menuItems = useMemo(() => {
    return MENU_DEFS.filter((item) => {
      if (item.key === "/login") return !loggedIn;
      if (item.key === "/profile") return loggedIn;
      if (item.always) return true;
      if (!item.permission) return true;
      return permissions.includes(item.permission);
    }).map((item) => ({
      key: item.key,
      label: <Link to={item.key}>{item.label}</Link>,
    }));
  }, [permissions, loggedIn]);

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
          <Route
            path="/org"
            element={
              <RequirePerm code="menu:org">
                <OrgPage />
              </RequirePerm>
            }
          />
          <Route
            path="/knowledge"
            element={
              <RequirePerm code="menu:knowledge">
                <KnowledgePage />
              </RequirePerm>
            }
          />
          <Route
            path="/knowledge/:id"
            element={
              <RequirePerm code="menu:knowledge">
                <KnowledgeEditPage />
              </RequirePerm>
            }
          />
          <Route
            path="/ai"
            element={
              <RequirePerm code="menu:ai">
                <AiChatPage />
              </RequirePerm>
            }
          />
          <Route
            path="/dashboard"
            element={
              <RequirePerm code="menu:dashboard">
                <DashboardPage />
              </RequirePerm>
            }
          />
          <Route
            path="/settlement"
            element={
              <RequirePerm code="menu:settlement">
                <Page title="知识沉淀" />
              </RequirePerm>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}
