import { Badge, Button, Code, Group, Modal, Select, Stack, Switch, TextInput, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, qs } from "../api/client";
import type { Grant, Paginated } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { DataTable, formatDate, shortId } from "../components/DataTable";
import type { Column } from "../components/DataTable";

const PAGE_SIZE = 50;

export function GrantsPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showArchived, setShowArchived] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [identityId, setIdentityId] = useState("");
  const [role, setRole] = useState<string>("ADMIN");

  const isOwner = me?.role === "OWNER";

  const query = useQuery({
    queryKey: ["grants", page, showArchived],
    queryFn: () =>
      api<Paginated<Grant>>(
        `/admin/grants${qs({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, archived: showArchived })}`,
      ),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["grants"] });

  const create = useMutation({
    mutationFn: () =>
      api("/admin/grants", {
        method: "POST",
        body: JSON.stringify({ identity_id: identityId.trim(), role }),
      }),
    onSuccess: () => {
      setModalOpen(false);
      setIdentityId("");
      invalidate();
      notifications.show({ message: "Grant created", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api(`/admin/grants/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      notifications.show({ message: "Grant revoked", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const columns: Column<Grant>[] = [
    {
      key: "identity",
      title: "Identity",
      render: (row) => (
        <Link to={`/identities/${row.identity_id}`}>
          <Code>{shortId(row.identity_id)}</Code>
        </Link>
      ),
    },
    {
      key: "role",
      title: "Role",
      render: (row) => (
        <Badge variant="light" color={row.role === "OWNER" ? "grape" : "blue"}>
          {row.role}
        </Badge>
      ),
    },
    {
      key: "granted_by",
      title: "Granted by",
      render: (row) => (row.granted_by ? <Code>{shortId(row.granted_by)}</Code> : <Badge variant="light">bootstrap</Badge>),
    },
    { key: "created", title: "Granted at", render: (row) => formatDate(row.created) },
    {
      key: "actions",
      title: "",
      render: (row) =>
        row.archived ? (
          <Badge color="gray" variant="light">
            revoked
          </Badge>
        ) : isOwner ? (
          <Button size="compact-xs" color="red" variant="light" onClick={() => revoke.mutate(row.id)}>
            Revoke
          </Button>
        ) : null,
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Admin Grants</Title>
        <Group>
          <Switch
            label="Show revoked"
            checked={showArchived}
            onChange={(e) => {
              setShowArchived(e.currentTarget.checked);
              setPage(1);
            }}
          />
          {isOwner && <Button onClick={() => setModalOpen(true)}>Grant role</Button>}
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

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Grant admin role">
        <Stack>
          <TextInput
            label="Identity UUID"
            description="The identity must be ACTIVE and have no active grant"
            value={identityId}
            onChange={(e) => setIdentityId(e.currentTarget.value)}
            required
          />
          <Select label="Role" data={["ADMIN", "OWNER"]} value={role} onChange={(value) => setRole(value ?? "ADMIN")} />
          <Button loading={create.isPending} onClick={() => create.mutate()} disabled={!identityId.trim()}>
            Grant
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
