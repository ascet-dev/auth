#Админы
- [x] админская аутентификация + bootstrap owner-а — план: [admin_auth_plan.md](admin_auth_plan.md)
- [x] admin CRUD API: client apps, oauth providers, identities (read), sessions, login audit, grants

#UI
- [x] админский логин
- [x] админка (SPA): client apps, oauth providers, identities, sessions, login audit, grants

#Инициализация (визард для разворачивания приложения)
- [x] цель - скопировать с github проект, запустить одну команду и подождать пока поднимется сервис. Предоставить UI для настройки
      → `make init`: полный docker-стек (postgres → миграции → сид → bootstrap-owner → backend + SPA),
      админка на http://localhost:8003/admin/ui/ (admin/admin в LOCAL)
- [ ] отдельный setup-визард в UI (смена пароля овнера при первом входе, настройка провайдеров пошагово)
