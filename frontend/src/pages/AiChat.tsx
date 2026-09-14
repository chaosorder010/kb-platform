import { Alert, Button, Card, Input, List, Space, Typography, message } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import { authFetch, getAccessToken, getStoredUser, hasPermission } from "../auth";

type ChatRole = "user" | "assistant";

type PermissionCard = {
  unit_id: string;
  title: string;
  message: string;
};

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  permissionCards?: PermissionCard[];
  references?: { unit_id: string; title: string }[];
};

type HistoryItem = {
  _id?: string;
  id?: string;
  role: string;
  text: string;
};

function newId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function ensureSessionId(): string {
  const user = getStoredUser();
  const userPart = user?.id || "anonymous";
  const key = `ai_chat_session_id:${userPart}`;
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(key, created);
  return created;
}

async function readSseStream(
  response: Response,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("浏览器不支持流式响应");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      if (!part.trim()) continue;
      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of part.split("\n")) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }
      try {
        const payload = JSON.parse(dataLines.join("\n") || "{}") as Record<
          string,
          unknown
        >;
        onEvent(eventName, payload);
      } catch {
        // ignore malformed chunk
      }
    }
  }
}

export default function AiChatPage() {
  const loggedIn = !!getAccessToken();
  const canAccess = hasPermission("menu:ai") || hasPermission("ai:access");
  const userId = getStoredUser()?.id || "";
  const sessionId = useMemo(() => ensureSessionId(), [userId]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!loggedIn || !canAccess) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await authFetch(
          `/api/ai/chat/history/${encodeURIComponent(sessionId)}`,
        );
        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new Error(
            (errBody as { detail?: string }).detail || "历史会话加载失败",
          );
        }
        const body = (await response.json()) as { items: HistoryItem[] };
        if (cancelled) return;
        const loaded: ChatMessage[] = (body.items || [])
          .filter((item) => item.role === "user" || item.role === "assistant")
          .map((item) => ({
            id: item._id || item.id || newId(),
            role: item.role as ChatRole,
            text: item.text || "",
          }));
        if (loaded.length) {
          setMessages(loaded);
        }
      } catch (err) {
        message.warning(
          err instanceof Error ? err.message : "历史会话加载失败",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loggedIn, canAccess, sessionId]);

  if (!loggedIn) {
    return <Navigate to="/login" replace />;
  }
  if (!canAccess) {
    return <Navigate to="/" replace />;
  }

  async function onSend() {
    const q = question.trim();
    if (!q || sending) return;
    setSending(true);
    setQuestion("");
    const userMsg: ChatMessage = { id: newId(), role: "user", text: q };
    const assistantId = newId();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", text: "" },
    ]);

    try {
      const response = await authFetch("/api/ai/chat/stream", {
        method: "POST",
        body: JSON.stringify({ question: q, session_id: sessionId }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "提问失败");
      }

      let assembled = "";
      let cards: PermissionCard[] = [];
      let references: { unit_id: string; title: string }[] = [];

      await readSseStream(response, (event, data) => {
        if (event === "delta") {
          const piece =
            (data.content as string | undefined) ||
            (data.delta as string | undefined) ||
            "";
          if (piece) {
            assembled += piece;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, text: assembled } : m,
              ),
            );
          }
        }
        if (event === "permission_missing") {
          cards = (data.cards as PermissionCard[]) || [];
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, permissionCards: cards } : m,
            ),
          );
        }
        if (event === "final") {
          if (typeof data.answer === "string" && data.answer) {
            assembled = data.answer;
          }
          if (Array.isArray(data.unauthorized_units)) {
            cards = data.unauthorized_units as PermissionCard[];
          }
          if (Array.isArray(data.references)) {
            references = data.references as {
              unit_id: string;
              title: string;
            }[];
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    text: assembled,
                    permissionCards: cards,
                    references,
                  }
                : m,
            ),
          );
        }
      });
    } catch (err) {
      message.error(err instanceof Error ? err.message : "提问失败");
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, text: m.text || "回答失败，请稍后重试。" }
            : m,
        ),
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        AI 对话台
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
        登录后即可提问；回答仅基于你有权限的知识，无权限内容会单独提示。
      </Typography.Paragraph>

      <Card
        styles={{ body: { maxHeight: 480, overflowY: "auto" } }}
        title="会话"
      >
        <List
          dataSource={messages}
          locale={{ emptyText: "暂无消息，先提一个问题吧" }}
          renderItem={(item) => (
            <List.Item style={{ display: "block" }}>
              <Typography.Text strong>
                {item.role === "user" ? "我" : "助手"}
              </Typography.Text>
              <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>
                {item.text || (item.role === "assistant" ? "…" : "")}
              </Typography.Paragraph>
              {item.permissionCards?.length ? (
                <Space direction="vertical" style={{ width: "100%" }}>
                  {item.permissionCards.map((card) => (
                    <Alert
                      key={card.unit_id}
                      type="warning"
                      showIcon
                      message="权限缺失"
                      description={
                        card.message ||
                        `无权限访问知识单元「${card.title || card.unit_id}」`
                      }
                    />
                  ))}
                </Space>
              ) : null}
              {item.references?.length ? (
                <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                  引用：
                  {item.references
                    .map((r) => r.title || r.unit_id)
                    .filter(Boolean)
                    .join("、")}
                </Typography.Paragraph>
              ) : null}
            </List.Item>
          )}
        />
        <div ref={bottomRef} />
      </Card>

      <Space.Compact style={{ width: "100%" }}>
        <Input.TextArea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="输入问题，例如：怎么检修？"
          autoSize={{ minRows: 2, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              void onSend();
            }
          }}
        />
        <Button type="primary" loading={sending} onClick={() => void onSend()}>
          发送
        </Button>
      </Space.Compact>
    </Space>
  );
}
