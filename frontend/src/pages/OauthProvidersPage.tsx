import {
  Badge,
  Button,
  Code,
  Group,
  Modal,
  PasswordInput,
  Stack,
  Switch,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, qs } from "../api/client";
import type { OauthProvider, Paginated } from "../api/types";
import { DataTable, formatDate } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

interface FormState {
  id?: string;
  name: string;
  client_id: string;
  client_secret: string;
  auth_url: string;
  token_url: string;
  jwks_url: string;
  userinfo_url: string;
  enabled: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  client_id: "",
  client_secret: "",
  auth_url: "",
  token_url: "",
  jwks_url: "",
  userinfo_url: "",
  enabled: true,
};

export function OauthProvidersPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showArchived, setShowArchived] = useState(false);
  const [form, setForm] = useState<FormState | null>(null);

  const query = useQuery({
    queryKey: ["oauth-providers", page, showArchived],
    queryFn: () =>
      api<Paginated<OauthProvider>>(
        `/admin/oauth-providers${qs({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, archived: showArchived })}`,
      ),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["oauth-providers"] });

  const save = useMutation({
    mutationFn: async (state: FormState) => {
      const { id, client_secret, jwks_url, userinfo_url, ...rest } = state;
      const payload = {
        ...rest,
        jwks_url: jwks_url || null,
        userinfo_url: userinfo_url || null,
        // при редактировании пустой секрет = «не менять»
        ...(client_secret ? { client_secret } : {}),
      };
      if (id) {
        return api(`/admin/oauth-providers/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      }
      if (!client_secret) {
        throw new Error("Client secret is required");
      }
      return api("/admin/oauth-providers", { method: "POST", body: JSON.stringify(payload) });
    },
    onSuccess: () => {
      setForm(null);
      invalidate();
      notifications.show({ message: "Saved", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const archive = useMutation({
    mutationFn: (id: string) => api(`/admin/oauth-providers/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      notifications.show({ message: "Archived", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const columns: Column<OauthProvider>[] = [
    { key: "name", title: "Provider", render: (row) => <Code>{row.name}</Code> },
    { key: "client_id", title: "Client ID", render: (row) => row.client_id },
    {
      key: "secret",
      title: "Secret",
      render: (row) =>
        row.client_secret_set ? (
          <Badge color="green" variant="light">
            set
          </Badge>
        ) : (
          <Badge color="red" variant="light">
            missing
          </Badge>
        ),
    },
    {
      key: "enabled",
      title: "Enabled",
      render: (row) => (
        <Badge color={row.enabled ? "green" : "gray"} variant="light">
          {row.enabled ? "yes" : "no"}
        </Badge>
      ),
    },
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
                    name: row.name,
                    client_id: row.client_id,
                    client_secret: "",
                    auth_url: row.auth_url,
                    token_url: row.token_url,
                    jwks_url: row.jwks_url ?? "",
                    userinfo_url: row.userinfo_url ?? "",
                    enabled: row.enabled,
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

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>OAuth Providers</Title>
        <Group>
          <Switch
            label="Show archived"
            checked={showArchived}
            onChange={(e) => {
              setShowArchived(e.currentTarget.checked);
              setPage(1);
            }}
          />
          <Button onClick={() => setForm({ ...EMPTY_FORM })}>New provider</Button>
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
        title={form?.id ? `Edit ${form.name}` : "New OAuth provider"}
      >
        {form && (
          <Stack>
            <TextInput
              label="Name"
              description="e.g. google, github, apple"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
              required
            />
            <TextInput
              label="Client ID"
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.currentTarget.value })}
              required
            />
            <PasswordInput
              label="Client secret"
              description={form.id ? "Leave empty to keep the current secret" : undefined}
              value={form.client_secret}
              onChange={(e) => setForm({ ...form, client_secret: e.currentTarget.value })}
            />
            <TextInput
              label="Auth URL"
              value={form.auth_url}
              onChange={(e) => setForm({ ...form, auth_url: e.currentTarget.value })}
              required
            />
            <TextInput
              label="Token URL"
              value={form.token_url}
              onChange={(e) => setForm({ ...form, token_url: e.currentTarget.value })}
              required
            />
            <TextInput
              label="JWKS URL"
              value={form.jwks_url}
              onChange={(e) => setForm({ ...form, jwks_url: e.currentTarget.value })}
            />
            <TextInput
              label="Userinfo URL"
              value={form.userinfo_url}
              onChange={(e) => setForm({ ...form, userinfo_url: e.currentTarget.value })}
            />
            <Switch
              label="Enabled"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.currentTarget.checked })}
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
