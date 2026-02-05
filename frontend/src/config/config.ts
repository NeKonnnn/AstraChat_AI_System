// Конфигурация для astrachat Frontend
// Загружает и парсит YAML конфиг из public/config/config.yml
import yaml from 'js-yaml';

let _config: any = null;
let _loadPromise: Promise<any> | null = null;

// Загрузка конфигурации из YAML файла
const loadConfig = async (): Promise<any> => {
  if (_config) return _config;
  if (_loadPromise) return _loadPromise;

  _loadPromise = (async () => {
    try {
      // Загружаем config.yml из public/config
      const response = await fetch('/config/config.yml');
      if (!response.ok) {
        throw new Error(`Не удалось загрузить config.yml: ${response.statusText}. Проверьте наличие файла public/config/config.yml`);
      }
      
      const yamlText = await response.text();
      _config = yaml.load(yamlText) || {};
      
      if (!_config.urls) {
        throw new Error('В config.yml отсутствует секция urls. Проверьте формат файла.');
      }
      
      return _config;
    } catch (error) {
      console.error('КРИТИЧЕСКАЯ ОШИБКА загрузки конфигурации:', error);
      throw error; // Выбрасываем ошибку вместо fallback значения
    } finally {
      _loadPromise = null;
    }
  })();

  return _loadPromise;
};

// Получение URL из конфигурации (синхронно, использует кэш)
// ВСЕ значения должны быть ТОЛЬКО в config.yml!
export const getUrl = (key: string): string => {
  if (!_config) {
    throw new Error(
      `Конфигурация не загружена! Убедитесь, что initConfig() вызван перед использованием getUrl('${key}'). ` +
      `Проверьте наличие файла public/config/config.yml`
    );
  }
  
  const url = _config.urls?.[key];
  if (!url) {
    throw new Error(
      `Ключ '${key}' не найден в config.yml! Проверьте наличие этого ключа в секции urls файла public/config/config.yml`
    );
  }
  
  return url;
};

// Инициализация конфигурации (загружает конфиг заранее при старте приложения)
// ОБЯЗАТЕЛЬНО вызвать при старте приложения!
export const initConfig = async () => {
  await loadConfig();
};
