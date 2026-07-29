import { Alert, Center, Group, Loader, Pagination, Table, Text } from "@mantine/core";
import type { ReactNode } from "react";

import type { Paginated } from "../api/types";

export interface Column<T> {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  data: Paginated<T> | undefined;
  isLoading: boolean;
  error?: Error | null;
  columns: Column<T>[];
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onRowClick?: (row: T) => void;
}

export function DataTable<T extends { id: string }>(props: DataTableProps<T>) {
  const { data, isLoading, error, columns, page, pageSize, onPageChange, onRowClick } = props;

  // Ошибку показываем явно: иначе неудачный запрос неотличим от загрузки
  // и таблица навсегда остаётся спиннером
  if (error) {
    return (
      <Alert color="red" title="Не удалось загрузить данные">
        {error.message}
      </Alert>
    );
  }

  if (isLoading || !data) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.pagination.total / pageSize));

  return (
    <>
      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            {columns.map((col) => (
              <Table.Th key={col.key}>{col.title}</Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.items.length === 0 && (
            <Table.Tr>
              <Table.Td colSpan={columns.length}>
                <Text c="dimmed" ta="center" py="md">
                  Nothing here yet
                </Text>
              </Table.Td>
            </Table.Tr>
          )}
          {data.items.map((row) => (
            <Table.Tr
              key={row.id}
              style={onRowClick ? { cursor: "pointer" } : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <Table.Td key={col.key}>{col.render(row)}</Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Group justify="space-between" mt="sm">
        <Text size="sm" c="dimmed">
          Total: {data.pagination.total}
        </Text>
        {totalPages > 1 && <Pagination value={page} onChange={onPageChange} total={totalPages} size="sm" />}
      </Group>
    </>
  );
}

export function shortId(id: string | null | undefined): string {
  return id ? `${id.slice(0, 8)}…` : "—";
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`);
  return date.toLocaleString();
}
