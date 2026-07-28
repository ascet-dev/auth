import {
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  NumberInput,
  PasswordInput,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { AuthMethodConfig } from "../api/types";

const METHOD_INFO: Record<string, { title: string; description: string }> = {
  PASSWORD: { title: "Password", description: "Логин и пароль (Argon2id, lockout после 5 неудачных попыток)" },
  OTP: { title: "OTP", description: "Одноразовые коды по SMS/email — пока не реализовано" },
  TMA: { title: "Telegram Mini App", description: "Вход по initData, подписанному ботом" },
  OAUTH: { title: "OAuth 2.0", description: "Внешние провайдеры (Google, GitHub, …)" },
};

function MethodCard({ method }: { method: AuthMethodConfig }) {
  const queryClient = useQueryClient();
  const [botToken, setBotToken] = useState("");
  const [maxAge, setMaxAge] = useState<number | null>(method.auth_date_max_age);

  const update = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api(`/admin/auth-methods/${method.method}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth-methods"] });
      setBotToken("");
      notifications.show({ message: "Saved", color: "green" });
    },
    onError: (e: Error) => notifications.show({ message: e.message, color: "red" }),
  });

  const info = METHOD_INFO[method.method];
  const notImplemented = method.method === "OTP";

  return (
    <Card withBorder>
      <Group justify="space-between" align="flex-start">
        <div>
          <Group gap="sm">
            <Title order={5}>{info.title}</Title>
            {notImplemented && (
              <Badge color="gray" variant="light">
                not implemented
              </Badge>
            )}
          </Group>
          <Text size="sm" c="dimmed">
            {info.description}
          </Text>
        </div>
        <Switch
          size="md"
          checked={method.enabled}
          disabled={notImplemented}
          onLabel="ON"
          offLabel="OFF"
          onChange={(e) => update.mutate({ enabled: e.currentTarget.checked })}
        />
      </Group>

      {method.method === "PASSWORD" && (
        <Switch
          mt="md"
          label="Allow self-registration"
          description="Выключите, чтобы закрыть открытую регистрацию (существующие пользователи продолжат логиниться)"
          checked={method.allow_registration ?? true}
          onChange={(e) => update.mutate({ allow_registration: e.currentTarget.checked })}
        />
      )}

      {method.method === "TMA" && (
        <Stack mt="md" gap="xs">
          <Group gap="xs">
            <Text size="sm">Bot token:</Text>
            {method.bot_token_set ? (
              <Badge color="green" variant="light">
                set (db)
              </Badge>
            ) : method.env_bot_token_set ? (
              <Badge color="yellow" variant="light">
                from env
              </Badge>
            ) : (
              <Badge color="red" variant="light">
                missing
              </Badge>
            )}
          </Group>
          <Group align="flex-end">
            <PasswordInput
              label="New bot token"
              description="Write-only; пустое сохранение очищает токен в БД (fallback на env)"
              value={botToken}
              onChange={(e) => setBotToken(e.currentTarget.value)}
              w={320}
            />
            <NumberInput
              label="initData max age, sec"
              value={maxAge ?? undefined}
              onChange={(value) => setMaxAge(Number(value) || null)}
              min={10}
              w={180}
            />
            <Button
              loading={update.isPending}
              onClick={() =>
                update.mutate({
                  bot_token: botToken,
                  ...(maxAge ? { auth_date_max_age: maxAge } : {}),
                })
              }
            >
              Save
            </Button>
          </Group>
        </Stack>
      )}

      {method.method === "OAUTH" && (
        <Text size="sm" mt="md">
          Провайдеры и их секреты настраиваются на странице{" "}
          <Anchor component={Link} to="/oauth-providers" size="sm">
            OAuth Providers
          </Anchor>
          . Этот тумблер выключает метод целиком.
        </Text>
      )}
    </Card>
  );
}

export function AuthMethodsPage() {
  const query = useQuery({
    queryKey: ["auth-methods"],
    queryFn: () => api<AuthMethodConfig[]>("/admin/auth-methods"),
  });

  if (query.isLoading || !query.data) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  return (
    <Stack>
      <div>
        <Title order={3}>Auth Methods</Title>
        <Text size="sm" c="dimmed">
          Глобальные выключатели и параметры. Каждому приложению можно сузить набор методов в его настройках
          (Client Apps → Allowed auth methods).
        </Text>
      </div>
      {query.data.map((method) => (
        <MethodCard key={method.method} method={method} />
      ))}
    </Stack>
  );
}
