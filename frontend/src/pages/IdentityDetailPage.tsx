import {
  Anchor,
  Badge,
  Card,
  Center,
  Code,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { IdentityDetail } from "../api/types";
import { formatDate } from "../components/DataTable";

export function IdentityDetailPage() {
  const { id } = useParams<{ id: string }>();

  const query = useQuery({
    queryKey: ["identity", id],
    queryFn: () => api<IdentityDetail>(`/admin/identities/${id}`),
    enabled: !!id,
  });

  if (query.isLoading || !query.data) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  const { identity, credentials, external_links, grant } = query.data;

  return (
    <Stack>
      <Group>
        <Title order={3}>Identity</Title>
        <Code>{identity.id}</Code>
        <Badge variant="light" color={identity.status === "ACTIVE" ? "green" : "orange"}>
          {identity.status}
        </Badge>
        {grant && (
          <Badge variant="light" color={grant.role === "OWNER" ? "grape" : "blue"}>
            {grant.role}
          </Badge>
        )}
      </Group>

      <Card withBorder>
        <Group gap="xl">
          <Text size="sm">Tenant: {identity.tenant_id ?? "—"}</Text>
          <Text size="sm">Created: {formatDate(identity.created)}</Text>
          <Text size="sm">
            Sessions:{" "}
            <Anchor component={Link} to={`/sessions?identity_id=${identity.id}`} size="sm">
              view
            </Anchor>
          </Text>
          <Text size="sm">
            Login audit:{" "}
            <Anchor component={Link} to={`/logins?identity_id=${identity.id}`} size="sm">
              view
            </Anchor>
          </Text>
        </Group>
      </Card>

      <Title order={5}>Credentials</Title>
      <Table withTableBorder striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Type</Table.Th>
            <Table.Th>Identifier</Table.Th>
            <Table.Th>Provider</Table.Th>
            <Table.Th>External subject</Table.Th>
            <Table.Th>Last used</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {credentials.length === 0 && (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Text c="dimmed" ta="center">
                  No credentials
                </Text>
              </Table.Td>
            </Table.Tr>
          )}
          {credentials.map((credential) => (
            <Table.Tr key={credential.id}>
              <Table.Td>
                <Badge variant="light">{credential.type}</Badge>
              </Table.Td>
              <Table.Td>{credential.identifier ?? "—"}</Table.Td>
              <Table.Td>{credential.provider ?? "—"}</Table.Td>
              <Table.Td>{credential.external_subject_id ?? "—"}</Table.Td>
              <Table.Td>{formatDate(credential.last_used)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      {external_links.length > 0 && (
        <>
          <Title order={5}>External links</Title>
          <Table withTableBorder striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>System</Table.Th>
                <Table.Th>External user ID</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {external_links.map((link) => (
                <Table.Tr key={link.id}>
                  <Table.Td>{link.external_system}</Table.Td>
                  <Table.Td>
                    <Code>{link.external_user_id}</Code>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  );
}
