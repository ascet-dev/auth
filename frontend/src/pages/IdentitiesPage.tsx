import { Badge, Code, Group, Select, Stack, Switch, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, qs } from "../api/client";
import type { Identity, Paginated } from "../api/types";
import { DataTable, formatDate } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "green",
  BLOCKED: "orange",
  DELETED: "red",
};

export function IdentitiesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  const query = useQuery({
    queryKey: ["identities", page, status, showArchived],
    queryFn: () =>
      api<Paginated<Identity>>(
        `/admin/identities${qs({
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
          status: status ?? undefined,
          archived: showArchived,
        })}`,
      ),
  });

  const columns: Column<Identity>[] = [
    { key: "id", title: "ID", render: (row) => <Code>{row.id}</Code> },
    {
      key: "status",
      title: "Status",
      render: (row) => (
        <Badge color={STATUS_COLORS[row.status ?? ""] ?? "gray"} variant="light">
          {row.status ?? "—"}
        </Badge>
      ),
    },
    { key: "tenant", title: "Tenant", render: (row) => row.tenant_id ?? "—" },
    { key: "created", title: "Created", render: (row) => formatDate(row.created) },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Identities</Title>
        <Group>
          <Select
            placeholder="Any status"
            data={["ACTIVE", "BLOCKED", "DELETED"]}
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
            clearable
            size="sm"
          />
          <Switch
            label="Show archived"
            checked={showArchived}
            onChange={(e) => {
              setShowArchived(e.currentTarget.checked);
              setPage(1);
            }}
          />
        </Group>
      </Group>

      <DataTable
        data={query.data}
        isLoading={query.isLoading}
        columns={columns}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/identities/${row.id}`)}
      />
    </Stack>
  );
}
