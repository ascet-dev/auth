import { AppShell, Badge, Button, Group, NavLink, Text, Title } from "@mantine/core";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const NAV_ITEMS = [
  { to: "/auth-methods", label: "Auth Methods" },
  { to: "/client-apps", label: "Client Apps" },
  { to: "/oauth-providers", label: "OAuth Providers" },
  { to: "/identities", label: "Identities" },
  { to: "/sessions", label: "Sessions" },
  { to: "/logins", label: "Login Audit" },
  { to: "/grants", label: "Admin Grants", ownerOnly: true },
];

export function Layout() {
  const { me, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const items = NAV_ITEMS.filter((item) => !item.ownerOnly || me?.role === "OWNER");

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 220, breakpoint: "sm" }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={4}>Auth Admin</Title>
          <Group gap="sm">
            <Badge variant="light" color={me?.role === "OWNER" ? "grape" : "blue"}>
              {me?.role}
            </Badge>
            <Text size="sm" c="dimmed">
              {me?.identity_id.slice(0, 8)}…
            </Text>
            <Button
              size="xs"
              variant="default"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
            >
              Logout
            </Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {items.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            active={location.pathname.startsWith(item.to)}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
