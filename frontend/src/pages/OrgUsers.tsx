import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAccessToken, hasPermission } from "../auth";
import {
  createUser,
  fetchDepartments,
  fetchRoles,
  fetchUsers,
  flattenDepartments,
  updateUser,
  type OrgRole,
  type OrgUser,
} from "../orgApi";

type UserForm = {
  username: string;
  password?: string;
  display_name: string;
  department_id: string;
  role_ids: string[];
  status: string;
};

export default function OrgUsersPage() {
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [roles, setRoles] = useState<OrgRole[]>([]);
  const [deptOptions, setDeptOptions] = useState<{ id: string; name: string }[]>(
    [],
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<OrgUser | null>(null);
  const [form] = Form.useForm<UserForm>();

  const canCreate = hasPermission("user:create");
  const canUpdate = hasPermission("user:update");

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const [userList, roleList, departments] = await Promise.all([
        fetchUsers(),
        fetchRoles(),
        fetchDepartments(),
      ]);
      setUsers(userList);
      setRoles(roleList);
      setDeptOptions(flattenDepartments(departments));
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
    if (!hasPermission("user:view")) {
      setError("无查看用户权限");
      setLoading(false);
      return;
    }
    void reload();
  }, []);

  function openCreate() {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: "active", role_ids: [] });
    setOpen(true);
  }

  function openEdit(user: OrgUser) {
    setEditing(user);
    form.setFieldsValue({
      username: user.username,
      display_name: user.display_name,
      department_id: user.department.id,
      role_ids: user.roles.map((r) => r.id),
      status: user.status,
      password: undefined,
    });
    setOpen(true);
  }

  async function onSubmit(values: UserForm) {
    try {
      if (editing) {
        await updateUser(editing.id, {
          display_name: values.display_name,
          department_id: values.department_id,
          role_ids: values.role_ids,
          status: values.status,
          password: values.password || undefined,
        });
        message.success("用户已更新");
      } else {
        await createUser({
          username: values.username,
          password: values.password || "",
          display_name: values.display_name,
          department_id: values.department_id,
          role_ids: values.role_ids,
          status: values.status,
        });
        message.success("用户已创建");
      }
      setOpen(false);
      await reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function toggleStatus(user: OrgUser) {
    if (!canUpdate) return;
    const next = user.status === "active" ? "disabled" : "active";
    try {
      await updateUser(user.id, { status: next });
      message.success(next === "active" ? "已启用" : "已停用");
      await reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function resetPassword(user: OrgUser) {
    if (!canUpdate) return;
    Modal.confirm({
      title: "重置密码",
      content: `将 ${user.display_name} 的密码重置为 Reset@123`,
      okText: "确认",
      cancelText: "取消",
      onOk: async () => {
        await updateUser(user.id, { password: "Reset@123" });
        message.success("密码已重置");
      },
    });
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
    <>
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <Typography.Text type="secondary">
          维护账号、部门归属与角色关联。
        </Typography.Text>
        {canCreate ? (
          <Button type="primary" onClick={openCreate}>
            新增用户
          </Button>
        ) : null}
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={users}
        pagination={false}
        columns={[
          { title: "用户名", dataIndex: "username" },
          { title: "显示名", dataIndex: "display_name" },
          { title: "部门", dataIndex: ["department", "name"] },
          {
            title: "角色",
            render: (_, row) =>
              row.roles.map((r) => r.role_name).join("、") || "无",
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (status: string) =>
              status === "active" ? (
                <Tag color="success">启用</Tag>
              ) : (
                <Tag>停用</Tag>
              ),
          },
          {
            title: "操作",
            render: (_, row) =>
              canUpdate ? (
                <Space>
                  <Button type="link" onClick={() => openEdit(row)}>
                    编辑
                  </Button>
                  <Button type="link" onClick={() => resetPassword(row)}>
                    重置密码
                  </Button>
                  <Button type="link" onClick={() => void toggleStatus(row)}>
                    {row.status === "active" ? "停用" : "启用"}
                  </Button>
                </Space>
              ) : null,
          },
        ]}
      />
      <Modal
        title={editing ? "编辑用户" : "新增用户"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        destroyOnHidden
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item
            label={editing ? "新密码（留空不改）" : "密码"}
            name="password"
            rules={editing ? [] : [{ required: true, message: "请输入密码" }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            label="显示名"
            name="display_name"
            rules={[{ required: true, message: "请输入显示名" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="部门"
            name="department_id"
            rules={[{ required: true, message: "请选择部门" }]}
          >
            <Select
              options={deptOptions.map((d) => ({
                value: d.id,
                label: d.name,
              }))}
            />
          </Form.Item>
          <Form.Item label="角色" name="role_ids">
            <Select
              mode="multiple"
              options={roles.map((r) => ({
                value: r.id,
                label: r.role_name,
              }))}
            />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select
              options={[
                { value: "active", label: "启用" },
                { value: "disabled", label: "停用" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
