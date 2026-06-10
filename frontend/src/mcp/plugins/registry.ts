import React from 'react';
import AtlassianServerDetails from './AtlassianServerDetails';
import { AtlassianServerSettings } from './AtlassianServerSettings';
import type { ServerPluginProps } from '../types';

const MCP_SERVER_PLUGINS: Record<string, React.ComponentType<ServerPluginProps>> = {
  atlassian: AtlassianServerDetails,
};

const MCP_SERVER_SETTINGS_PLUGINS: Record<string, React.ComponentType<ServerPluginProps>> = {
  atlassian: AtlassianServerSettings,
};

export function getMcpServerPlugin(serverId: string): React.ComponentType<ServerPluginProps> | null {
  return MCP_SERVER_PLUGINS[serverId] || null;
}

export function getMcpServerSettingsPlugin(serverId: string): React.ComponentType<ServerPluginProps> | null {
  return MCP_SERVER_SETTINGS_PLUGINS[serverId] || null;
}

export { MCP_SERVER_PLUGINS };
