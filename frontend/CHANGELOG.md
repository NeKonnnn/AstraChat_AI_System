# CHANGELOG

## [0.1.1.2] - 2026-02-11

### Added

- Реализован функционал "Проектов" для организации чатов. Пользователи могут создавать проекты с настройками памяти, инструкциями и файлами. Добавлены компоненты NewProjectModal, функции управления проектами в AppContext (createProject, updateProject, deleteProject, getProjects, moveChatToProject, togglePinInProject) и интеграция в Sidebar.

- Разработан функционал выбора настроек для RAG (Retrieval-Augmented Generation). Пользователи могут выбирать стратегию поиска по документам: автоматический выбор, reranking, иерархический поиск, гибридный поиск или стандартный поиск. Настройки сохраняются автоматически через API.

- Вынесен подраздел "Интерфейс" из раздела "Общие" в самостоятельный раздел настроек. Теперь настройки интерфейса (автогенерация заголовков, отображение сообщений, уведомления, режим широкоформатного экрана и другие) доступны в отдельной секции настроек.

### Changed

- Применены абстрактные классы конфигурации подключений ко всем необходимым файлам проекта. Абстрактные интерфейсы APIConnectionConfig и WebSocketConnectionConfig, а также их реализации APIConnectionConfigImpl и WebSocketConnectionConfigImpl теперь используются в следующих файлах:
  - frontend/src/config/api.ts
  - frontend/src/contexts/AuthContext.tsx
  - frontend/src/contexts/SocketContext.tsx
  - frontend/src/pages/ProfilePage.tsx
  - frontend/src/components/settings/ProfileSettings.tsx
  - frontend/src/pages/SettingsPage.tsx
  - frontend/src/pages/HistoryPage.tsx
  - frontend/src/pages/VoicePage.tsx
  - frontend/src/components/settings/ModelsSettings.tsx
  - frontend/src/components/TranscriptionModal.tsx
  - frontend/src/components/AgentArchitectureSettings.tsx
  - frontend/src/pages/DocumentsPage.tsx
  - frontend/src/components/settings/AgentsSettings.tsx
  - frontend/src/components/ManageSharesDialog.tsx
  - frontend/src/components/settings/RAGSettings.tsx
  - frontend/src/components/settings/TranscriptionSettings.tsx
  - frontend/src/pages/PromptGalleryPage.tsx
  - frontend/src/components/ModelSelector.tsx
  - frontend/src/pages/UnifiedChatPage.tsx
  - frontend/src/components/settings/GeneralSettings.tsx

## [0.1.1.1] - 2026-02-03

### Added

- Разработаны абстрактные классы для конфигурации подключений: интерфейсы APIConnectionConfig и WebSocketConnectionConfig, а также их реализации APIConnectionConfigImpl и WebSocketConnectionConfigImpl. Классы находятся в папке frontend/src/settings в файлах connections.ts (интерфейсы и реализации), config.ts (основной класс Settings) и index.ts (экспорты). Классы обеспечивают централизованное управление настройками API и WebSocket подключений.

- Создан YAML файл конфигурации (frontend/public/config/config.yml) для настройки URL и других параметров приложения. Файл содержит настройки URL для frontend, backend и LLM сервисов, включая поддержку различных портов и Docker окружений. Все URL вынесены в переменные для удобного управления конфигурацией.

