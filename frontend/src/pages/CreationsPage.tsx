import React from 'react';
import { Navigate } from 'react-router-dom';

/** Legacy route — контент рендерится в UnifiedChatPage с тем же layout, что и чат. */
export default function CreationsPage() {
  return <Navigate to="/creations" replace />;
}
