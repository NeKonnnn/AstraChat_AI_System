import { useEffect } from 'react';
import { clearTabNotifications, initTabNotifications } from '../utils/tabNotifications';

/**
 * Сбрасывает счётчик на вкладке, когда пользователь возвращается на страницу.
 */
export default function TabNotificationWatcher() {
  useEffect(() => {
    initTabNotifications();

    const handleFocus = () => {
      if (!document.hidden) {
        clearTabNotifications();
      }
    };

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleFocus);
    };
  }, []);

  return null;
}
