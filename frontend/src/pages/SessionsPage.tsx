import { Badge, Button, Code, Group, Select, Stack, TextInput, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, qs } from "../api/client";
import type { Paginated, SessionInfo } from "../api/types";
import { DataTable, formatDate, shortId } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

// Частичный UUID даёт 400 от API, поэтому фильтр применяем только когда он валиден
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function asUuidFilter(value: string): string | undefined {
  const trimmed = value.trim();
  return UUID_RE.test(trimmed) ? trimmed : undefined;
}


const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "green",
  REVOKED: "gray",
  EXPIRED: "yellow",
  COMPROMISED: "red",
};

export function SessionsPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string | null>("ACTIVE");
  const [identityId, setIdentityId] = useState(searchParams.get("identity_id") ?? "");

  const query = useQuery({
    queryKey: ["sessions", page, status, identityId],
    queryFn: () =>
      api<Paginated<SessionInfo>>(
        `/admin/sessions${qs({
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
          status: status ?? undefined,
          identity_id: asUuidFilter(identityId),
        })}`,
      ),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api(`/admin/sessions/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      notifications.show({ message: "Session revoked", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const columns: Column<SessionInfo>[] = [
    { key: "id", title: "ID", render: (row) => <Code>{shortId(row.id)}</Code> },
    { key: "identity", title: "Identity", render: (row) => <Code>{shortId(row.identity_id)}</Code> },
    {
      key: "status",
      title: "Status",
      render: (row) => (
        <Badge color={STATUS_COLORS[row.status ?? ""] ?? "gray"} variant="light">
          {row.status ?? "—"}
        </Badge>
      ),
    },
    { key: "ip", title: "IP", render: (row) => row.ip ?? "—" },
    { key: "created", title: "Created", render: (row) => formatDate(row.created) },
    { key: "expires", title: "Refresh expires", render: (row) => formatDate(row.refresh_expires_at) },
    {
      key: "actions",
      title: "",
      render: (row) =>
        row.status === "ACTIVE" ? (
          <Button size="compact-xs" color="red" variant="light" onClick={() => revoke.mutate(row.id)}>
            Revoke
          </Button>
        ) : null,
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Sessions</Title>
        <Group>
          <TextInput
            placeholder="Filter by identity UUID"
            description={identityId.trim() && !asUuidFilter(identityId) ? "Введите полный UUID" : undefined}
            value={identityId}
            onChange={(e) => {
              setIdentityId(e.currentTarget.value);
              setPage(1);
            }}
            size="sm"
            w={300}
          />
          <Select
            placeholder="Any status"
            data={["ACTIVE", "REVOKED", "EXPIRED", "COMPROMISED"]}
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
            clearable
            size="sm"
          />
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
    </Stack>
  );
}
