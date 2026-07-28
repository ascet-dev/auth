import {
  Badge,
  Button,
  Code,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  Stack,
  Switch,
  TagsInput,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, qs } from "../api/client";
import type { ClientApp, Connector, Paginated } from "../api/types";
import { DataTable, formatDate, shortId } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

interface FormState {
  id?: string;
  key: string;
  name: string;
  allowed_redirect_uris: string[];
  allowed_scopes: string[];
  connector_ids: string[];
  access_token_ttl_sec: number;
  refresh_token_ttl_sec: number;
}

const EMPTY_FORM: FormState = {
  key: "",
  name: "",
  allowed_redirect_uris: [],
  allowed_scopes: [],
  connector_ids: [],
  access_token_ttl_sec: 900,
  refresh_token_ttl_sec: 2592000,
};

export function ClientAppsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showArchived, setShowArchived] = useState(false);
  const [form, setForm] = useState<FormState | null>(null);

  const query = useQuery({
    queryKey: ["client-apps", page, showArchived],
    queryFn: () =>
      api<Paginated<ClientApp>>(
        `/admin/client-apps${qs({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, archived: showArchived })}`,
      ),
  });

  const connectorsQuery = useQuery({
    queryKey: ["connectors", "all"],
    queryFn: () => api<Paginated<Connector>>(`/admin/connectors${qs({ limit: 200 })}`),
  });

  const connectorOptions = (connectorsQuery.data?.items ?? []).map((c) => ({
    value: c.id,
    label: `${c.key} (${c.type})`,
  }));

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["client-apps"] });

  const openEdit = async (row: ClientApp) => {
    const mapped = await api<Connector[]>(`/admin/client-apps/${row.id}/connectors`);
    setForm({
      id: row.id,
      key: row.key,
      name: row.name,
      allowed_redirect_uris: row.allowed_redirect_uris ?? [],
      allowed_scopes: row.allowed_scopes ?? [],
      connector_ids: mapped.map((c) => c.id),
      access_token_ttl_sec: row.access_token_ttl_sec,
      refresh_token_ttl_sec: row.refresh_token_ttl_sec,
    });
  };

  const save = useMutation({
    mutationFn: async (state: FormState) => {
      const { id, key, connector_ids, ...rest } = state;
      const saved = id
        ? await api<ClientApp>(`/admin/client-apps/${id}`, { method: "PATCH", body: JSON.stringify(rest) })
        : await api<ClientApp>("/admin/client-apps", { method: "POST", body: JSON.stringify({ key, ...rest }) });
      // Приложение уже создано: переводим форму в режим правки, чтобы повторный
      // Save после ошибки маппинга не пытался создать его снова ("key exists")
      if (!id) setForm({ ...state, id: saved.id });
      await api(`/admin/client-apps/${saved.id}/connectors`, {
        method: "PUT",
        body: JSON.stringify({ connector_ids }),
      });
      return saved;
    },
    onSuccess: () => {
      setForm(null);
      invalidate();
      notifications.show({ message: "Saved", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const archive = useMutation({
    mutationFn: (id: string) => api(`/admin/client-apps/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      notifications.show({ message: "Archived", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const columns: Column<ClientApp>[] = [
    { key: "key", title: "Key", render: (row) => <Code>{row.key}</Code> },
    { key: "name", title: "Name", render: (row) => row.name },
    { key: "id", title: "ID", render: (row) => <Code>{shortId(row.id)}</Code> },
    { key: "access", title: "Access TTL", render: (row) => `${row.access_token_ttl_sec}s` },
    { key: "refresh", title: "Refresh TTL", render: (row) => `${row.refresh_token_ttl_sec}s` },
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
              <Button size="compact-xs" variant="default" onClick={() => void openEdit(row)}>
                Edit
              </Button>
              <Button
                size="compact-xs"
                color="red"
                variant="light"
                disabled={row.key === "auth-admin"}
                onClick={() => archive.mutate(row.id)}
              >
                Archive
              </Button>
            </>
          )}
        </Group>
      ),
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Client Apps</Title>
        <Group>
          <Switch
            label="Show archived"
            checked={showArchived}
            onChange={(e) => {
              setShowArchived(e.currentTarget.checked);
              setPage(1);
            }}
          />
          <Button onClick={() => setForm({ ...EMPTY_FORM })}>New client app</Button>
        </Group>
      </Group>

      <DataTable
        data={query.data}
        isLoading={query.isLoading}
        columns={columns}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
      />

      <Modal
        opened={form !== null}
        onClose={() => setForm(null)}
        title={form?.id ? `Edit ${form.key}` : "New client app"}
      >
        {form && (
          <Stack>
            <TextInput
              label="Key"
              description="Logical audience id, immutable after creation"
              value={form.key}
              disabled={!!form.id}
              onChange={(e) => setForm({ ...form, key: e.currentTarget.value })}
              required
            />
            <TextInput
              label="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
              required
            />
            <TagsInput
              label="Allowed redirect URIs"
              value={form.allowed_redirect_uris}
              onChange={(value) => setForm({ ...form, allowed_redirect_uris: value })}
            />
            <TagsInput
              label="Allowed scopes"
              value={form.allowed_scopes}
              onChange={(value) => setForm({ ...form, allowed_scopes: value })}
            />
            <MultiSelect
              label="Connectors"
              description="Способы входа приложения. Пусто = все включённые коннекторы"
              data={connectorOptions}
              value={form.connector_ids}
              onChange={(value) => setForm({ ...form, connector_ids: value })}
              searchable
            />
            <NumberInput
              label="Access token TTL, sec"
              value={form.access_token_ttl_sec}
              onChange={(value) => setForm({ ...form, access_token_ttl_sec: Number(value) || 0 })}
              min={1}
            />
            <NumberInput
              label="Refresh token TTL, sec"
              value={form.refresh_token_ttl_sec}
              onChange={(value) => setForm({ ...form, refresh_token_ttl_sec: Number(value) || 0 })}
              min={1}
            />
            <Button loading={save.isPending} onClick={() => save.mutate(form)}>
              Save
            </Button>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
