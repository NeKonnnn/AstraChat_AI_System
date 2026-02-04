import logging
from fastapi import HTTPException, status, Depends, Header
from app.core.config import get_settings
from dmkfr_vault_interface.interface import VaultInterface
from typing import Dict
logger = logging.getLogger(__name__)
_settings = get_settings()
def _handle_critical_failure(message: str, exc: Exception) -> None:
    """
    Обработка критических исключений
    :param message: сообщение ошибки
    :param exc: возникшее исключение
    """
    # Логирование критического исключения
    logger.critical(f"{message}: {exc}", exc_info=True)
    # Поднятие HTTP ошибки
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"External Security Service Unavailable: {message.split(':')[0]}"
    )
def _get_vault_interface() -> VaultInterface:
    """
    Получение инстанса интерфейса для работы с Vault
    :return: Инстанс Vault интерфейса
    """
    vault_config = _settings.vault
    # Не предоставлен ID или название роли для подключения к Vault
    if not (vault_config.role_id and vault_config.approle_name):
        _handle_critical_failure(
            "Configuration Error: Vault connection parameters are missing",
            ValueError("Missing role_id or approle_name")
        )
    # Попытка получения инстанса интерфейса
    try:
        return VaultInterface(
            role_id=vault_config.role_id,
            approle_name=vault_config.approle_name,
            verify=vault_config.verify
        )
    # Ошибка при подключении к Vault
    except Exception as e:
        _handle_critical_failure(
            "Vault Initialization Failed: Could not create VaultInterface.",
            e
        )
def _get_valid_api_keys_map() -> Dict[str, str]:
    """
    Получение валидных API ключей из Vault
    :return: словарь с валидными API ключами
    """
    vault_config = _settings.vault
    # Не предоставлен путь к API кдючам в хранилище секретов
    if not vault_config.path:
        _handle_critical_failure(
            "Configuration Error: Vault secret path field is missing iin config.",
            ValueError("Missing Vault path")
        )
    # Попытка получение API ключей
    try:
        vault_interface = _get_vault_interface()
        api_key_map = vault_interface.get_secret(
            tuz_username=vault_config.tuz_username,
            tuz_password=vault_config.tuz_password,
            path=vault_config.path
        )
        # Секрет с API ключами не является словарем - будет падать ошибка 401 с любым предоставленным API ключом
        if not isinstance(api_key_map, dict):
            logger.warning(f"Vault secret at path {vault_config.path} does not contain expected api keys dictionary.")
            return {}
        return api_key_map
    # Ошибка получения валидных API ключей
    except Exception as e:
        _handle_critical_failure(
            "Vault Access Failed: Could not fetch API keys from Hashicorp Vault.",
            e
        )
async def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """
    Проверка валидности переданного API ключа
    :param x_api_key: переданных API ключ
    :return: True - в случае валидности ключа, False - в случае ошибки
    """
    # Случай с отключенной проверкой ключей
    if not _settings.security.enabled:
        return True
    # Обработка отсутствия API ключа
    header_name = _settings.security.api_key_header
    if not x_api_key:
        logger.warning(f"Request missing required API key header ({header_name}).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API key ({header_name}) must be provided.",
            headers={"WWW-Authenticate": header_name}
        )
    # Получение словаря валидных API ключей из Vault
    valid_keys_map = _get_valid_api_keys_map()
    # Проверка API ключа
    if x_api_key in valid_keys_map.values():
        logger.info("API key successfully validated.")
        return True
    # Неверный API ключ
    logger.warning("Client provided invalid API key.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
        headers={"WWW-Authenticate": header_name}
    )
async def require_api_key(api_key_verified: bool = Depends(verify_api_key)) -> bool:
    """Зависимость для роутов."""
    return api_key_verified

