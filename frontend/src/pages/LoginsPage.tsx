import { Badge, Code, Group, Select, Stack, TextInput, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, qs } from "../api/client";
import type { LoginRecord, Paginated } from "../api/types";
import { DataTable, formatDate, shortId } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

// Частичный UUID даёт 400 от API, поэтому фильтр применяем только когда он валиден
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function asUuidFilter(value: string): string | undefined {
  const trimmed = value.trim();
  return UUID_RE.test(trimmed) ? trimmed : undefined;
}


export function LoginsPage() {
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [method, setMethod] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [identityId, setIdentityId] = useState(searchParams.get("identity_id") ?? "");

  const query = useQuery({
    queryKey: ["logins", page, method, success, identityId],
    queryFn: () =>
      api<Paginated<LoginRecord>>(
        `/admin/logins${qs({
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
          method: method ?? undefined,
          success: success === null ? undefined : success === "success",
          identity_id: asUuidFilter(identityId),
        })}`,
      ),
  });

  const columns: Column<LoginRecord>[] = [
    { key: "created", title: "Time", render: (row) => formatDate(row.created) },
    { key: "method", title: "Method", render: (row) => <Badge variant="light">{row.method}</Badge> },
    { key: "identifier", title: "Identifier", render: (row) => row.identifier ?? "—" },
    { key: "identity", title: "Identity", render: (row) => <Code>{shortId(row.identity_id)}</Code> },
    {
      key: "success",
      title: "Result",
      render: (row) => (
        <Badge color={row.success ? "green" : "red"} variant="light">
          {row.success ? "success" : "failure"}
        </Badge>
      ),
    },
    { key: "ip", title: "IP", render: (row) => row.ip_address || "—" },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Login Audit</Title>
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
            placeholder="Any method"
            data={["password", "admin_password", "oauth", "tma", "otp"]}
            value={method}
            onChange={(value) => {
              setMethod(value);
              setPage(1);
            }}
            clearable
            size="sm"
          />
          <Select
            placeholder="Any result"
            data={[
              { value: "success", label: "Success" },
              { value: "failure", label: "Failure" },
            ]}
            value={success}
            onChange={(value) => {
              setSuccess(value);
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
