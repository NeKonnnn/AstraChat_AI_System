import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { MENU_MIN_WIDTH_PX } from './constants/menuStyles';

// Ширина меню задаётся до первого рендера, чтобы глобальные стили в App.css точно её подхватили
document.documentElement.style.setProperty('--menu-min-width', `${MENU_MIN_WIDTH_PX}px`);

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
