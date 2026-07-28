import { Alert, Button, Card, Center, PasswordInput, Stack, TextInput, Title } from "@mantine/core";
import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (me) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(loginValue, password);
      const from = (location.state as { from?: string } | null)?.from ?? "/";
      navigate(from, { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Center h="100vh">
      <Card withBorder shadow="sm" w={360} p="lg">
        <form onSubmit={onSubmit}>
          <Stack>
            <Title order={3} ta="center">
              Auth Admin
            </Title>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput
              label="Login"
              value={loginValue}
              onChange={(e) => setLoginValue(e.currentTarget.value)}
              required
              autoFocus
            />
            <PasswordInput
              label="Password"
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              required
            />
            <Button type="submit" loading={submitting} fullWidth>
              Sign in
            </Button>
          </Stack>
        </form>
      </Card>
    </Center>
  );
}
