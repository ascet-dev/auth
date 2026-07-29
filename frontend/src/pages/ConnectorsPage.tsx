import {
  Badge,
  Button,
  Code,
  Group,
  Modal,
  NumberInput,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, qs } from "../api/client";
import type { Connector, ConnectorType, Paginated } from "../api/types";
import { DataTable, formatDate } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

const TYPE_COLORS: Record<ConnectorType, string> = {
  PASSWORD: "blue",
  TMA: "cyan",
  OAUTH: "orange",
  OTP: "gray",
};

interface FormState {
  id?: string;
  key: string;
  type: ConnectorType;
  name: string;
  enabled: boolean;
  settings: Record<string, string | number | boolean>;
}

const EMPTY_FORM: FormState = { key: "", type: "TMA", name: "", enabled: true, settings: {} };

function secretBadge(connector: Connector): React.ReactNode {
  const secretFlag = connector.type === "TMA" ? "bot_token_set" : connector.type === "OAUTH" ? "client_secret_set" : null;
  if (!secretFlag) return null;
  return connector.settings[secretFlag] ? (
    <Badge color="green" variant="light">
      secret set
    </Badge>
  ) : (
    <Badge color="red" variant="light">
      no secret
    </Badge>
  );
}

export function ConnectorsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showArchived, setShowArchived] = useState(false);
  const [form, setForm] = useState<FormState | null>(null);

  const query = useQuery({
    queryKey: ["connectors", page, showArchived],
    queryFn: () =>
      api<Paginated<Connector>>(
        `/admin/connectors${qs({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, archived: showArchived })}`,
      ),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["connectors"] });

  const save = useMutation({
    mutationFn: async (state: FormState) => {
      // секреты: пустое значение при редактировании = не менять
      const settings = Object.fromEntries(
        Object.entries(state.settings).filter(([key, value]) => {
          if (state.id && (key === "bot_token" || key === "client_secret") && value === "") return false;
          return value !== "" && value !== undefined;
        }),
      );
      if (state.id) {
        return api(`/admin/connectors/${state.id}`, {
          method: "PATCH",
          body: JSON.stringify({ name: state.name, enabled: state.enabled, settings }),
        });
      }
      return api("/admin/connectors", {
        method: "POST",
        body: JSON.stringify({ key: state.key, type: state.type, name: state.name, enabled: state.enabled, settings }),
      });
    },
    onSuccess: () => {
      setForm(null);
      invalidate();
      notifications.show({ message: "Saved", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const archive = useMutation({
    mutationFn: (id: string) => api(`/admin/connectors/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      notifications.show({ message: "Archived", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const setSetting = (key: string, value: string | number | boolean) =>
    setForm((f) => (f ? { ...f, settings: { ...f.settings, [key]: value } } : f));

  const columns: Column<Connector>[] = [
    { key: "key", title: "Key", render: (row) => <Code>{row.key}</Code> },
    {
      key: "type",
      title: "Type",
      render: (row) => (
        <Badge color={TYPE_COLORS[row.type]} variant="light">
          {row.type}
        </Badge>
      ),
    },
    { key: "name", title: "Name", render: (row) => row.name },
    {
      key: "enabled",
      title: "Enabled",
      render: (row) => (
        <Badge color={row.enabled ? "green" : "gray"} variant="light">
          {row.enabled ? "yes" : "no"}
        </Badge>
      ),
    },
    { key: "secret", title: "Secret", render: (row) => secretBadge(row) },
    { key: "created", title: "Created", render: (row) => formatDate(row.created) },
    {
      key: "actions",
      title: "",
      render: (row) => (
        <Group gap="xs" justify="flex-end" wrap="nowrap">
          {row.archived ? (
            <Badge color="gray" variant="light">
              archived
            </Badge>
          ) : (
            <>
              <Button
                size="compact-xs"
                variant="default"
                onClick={() =>
                  setForm({
                    id: row.id,
                    key: row.key,
                    type: row.type,
                    name: row.name,
                    enabled: row.enabled,
                    settings: Object.fromEntries(
                      Object.entries(row.settings).filter(
                        ([k, v]) => !k.endsWith("_set") && (typeof v === "string" || typeof v === "number" || typeof v === "boolean"),
                      ),
                    ) as Record<string, string | number | boolean>,
                  })
                }
              >
                Edit
              </Button>
              <Button size="compact-xs" color="red" variant="light" onClick={() => archive.mutate(row.id)}>
                Archive
              </Button>
            </>
          )}
        </Group>
      ),
    },
  ];

  const f = form;

  return (
    <Stack>
      <Group justify="space-between">
        <div>
          <Title order={3}>Connectors</Title>
          <Text size="sm" c="dimmed">
            Экземпляры способов входа: несколько TMA-ботов, разные OAuth-приложения, парольные политики.
            Привязка к приложению — в Client Apps (пусто = все включённые).
          </Text>
        </div>
        <Group>
          <Switch
            label="Show archived"
            checked={showArchived}
            onChange={(e) => {
              setShowArchived(e.currentTarget.checked);
              setPage(1);
            }}
          />
          <Button onClick={() => setForm({ ...EMPTY_FORM })}>New connector</Button>
        </Group>
      </Group>

      <DataTable
        data={query.data}
        isLoading={query.isLoading}
        error={query.error as Error | null}
        columns={columns}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
      />

      <Modal opened={f !== null} onClose={() => setForm(null)} title={f?.id ? `Edit ${f.key}` : "New connector"}>
        {f && (
          <Stack>
            <Select
              label="Type"
              data={["TMA", "OAUTH", "PASSWORD", "OTP"]}
              value={f.type}
              disabled={!!f.id}
              onChange={(value) => value && setForm({ ...f, type: value as ConnectorType, settings: {} })}
            />
            <TextInput
              label="Key"
              description="Слаг: tma-shop-bot, google-web… Для OAUTH это параметр `provider` в /auth/oauth/*"
              value={f.key}
              disabled={!!f.id}
              onChange={(e) => setForm({ ...f, key: e.currentTarget.value })}
              required
            />
            <TextInput
              label="Name"
              value={f.name}
              onChange={(e) => setForm({ ...f, name: e.currentTarget.value })}
              required
            />
            <Switch label="Enabled" checked={f.enabled} onChange={(e) => setForm({ ...f, enabled: e.currentTarget.checked })} />

            {f.type === "TMA" && (
              <>
                <PasswordInput
                  label="Bot token"
                  description={f.id ? "Пусто = не менять" : undefined}
                  value={String(f.settings.bot_token ?? "")}
                  onChange={(e) => setSetting("bot_token", e.currentTarget.value)}
                />
                <NumberInput
                  label="initData max age, sec"
                  value={(f.settings.auth_date_max_age as number) ?? undefined}
                  onChange={(value) => setSetting("auth_date_max_age", Number(value) || 300)}
                  min={10}
                />
              </>
            )}

            {f.type === "OAUTH" && (
              <>
                <TextInput
                  label="Client ID"
                  value={String(f.settings.client_id ?? "")}
                  onChange={(e) => setSetting("client_id", e.currentTarget.value)}
                  required
                />
                <PasswordInput
                  label="Client secret"
                  description={f.id ? "Пусто = не менять" : undefined}
                  value={String(f.settings.client_secret ?? "")}
                  onChange={(e) => setSetting("client_secret", e.currentTarget.value)}
                />
                <TextInput
                  label="Auth URL"
                  value={String(f.settings.auth_url ?? "")}
                  onChange={(e) => setSetting("auth_url", e.currentTarget.value)}
                  required
                />
                <TextInput
                  label="Token URL"
                  value={String(f.settings.token_url ?? "")}
                  onChange={(e) => setSetting("token_url", e.currentTarget.value)}
                  required
                />
                <TextInput
                  label="JWKS URL"
                  value={String(f.settings.jwks_url ?? "")}
                  onChange={(e) => setSetting("jwks_url", e.currentTarget.value)}
                />
                <TextInput
                  label="Userinfo URL"
                  value={String(f.settings.userinfo_url ?? "")}
                  onChange={(e) => setSetting("userinfo_url", e.currentTarget.value)}
                />
              </>
            )}

            {f.type === "PASSWORD" && (
              <>
                <NumberInput
                  label="Max failed attempts"
                  value={(f.settings.max_failed_attempts as number) ?? 5}
                  onChange={(value) => setSetting("max_failed_attempts", Number(value) || 5)}
                  min={1}
                />
                <NumberInput
                  label="Lockout, minutes"
                  value={(f.settings.lockout_minutes as number) ?? 30}
                  onChange={(value) => setSetting("lockout_minutes", Number(value) || 30)}
                  min={1}
                />
                <Switch
                  label="Allow self-registration"
                  checked={(f.settings.allow_registration as boolean) ?? true}
                  onChange={(e) => setSetting("allow_registration", e.currentTarget.checked)}
                />
              </>
            )}

            {f.type === "OTP" && (
              <Text size="sm" c="dimmed">
                OTP пока не реализован — коннектор можно завести заранее.
              </Text>
            )}

            <Button loading={save.isPending} onClick={() => save.mutate(f)}>
              Save
            </Button>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
