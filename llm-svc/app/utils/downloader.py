"""
Утилита для загрузки моделей из различных источников:
- Локальная файловая система
- S3/S3-совместимые хранилища
- Google Cloud Storage
- HTTP/HTTPS
"""
import os
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def is_cloud_path(path: str) -> bool:
    """Проверка, является ли путь облачным"""
    return path.startswith(('s3://', 'gs://', 'https://', 'http://'))


def is_local_path(path: str) -> bool:
    """Проверка, является ли путь локальным файлом"""
    return os.path.exists(path) or not is_cloud_path(path)


def download_from_http(url: str, destination: str) -> bool:
    """Загрузка файла по HTTP/HTTPS"""
    try:
        logger.info(f"Загрузка модели с {url}...")
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (1024 * 1024) == 0:
                        progress = (downloaded / total_size) * 100
                        logger.info(f"Загружено {downloaded / 1024 / 1024:.1f} MB ({progress:.1f}%)")
        logger.info(f"Модель успешно загружена в {destination}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при загрузке с {url}: {str(e)}")
        return False


def download_from_s3(s3_url: str, destination: str) -> bool:
    """Загрузка файла из S3 или S3-совместимого хранилища"""
    try:
        import boto3
    except ImportError:
        logger.error("boto3 не установлен. Установите: pip install boto3")
        return False
    try:
        parsed = urlparse(s3_url)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        logger.info(f"Загрузка модели из S3: {bucket}/{key}")
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        s3_client.download_file(bucket, key, destination)
        logger.info(f"Модель успешно загружена из S3 в {destination}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при загрузке из S3: {str(e)}")
        return False


def download_from_gcs(gcs_url: str, destination: str) -> bool:
    """Загрузка файла из Google Cloud Storage"""
    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage не установлен. Установите: pip install google-cloud-storage")
        return False
    try:
        parsed = urlparse(gcs_url)
        bucket_name = parsed.netloc
        blob_path = parsed.path.lstrip('/')
        logger.info(f"Загрузка модели из GCS: {bucket_name}/{blob_path}")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(destination)
        logger.info(f"Модель успешно загружена из GCS в {destination}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при загрузке из GCS: {str(e)}")
        return False


def download_model(source: str, destination: str) -> bool:
    """
    Загрузка модели из различных источников.
    source: s3://, gs://, https://, http:// или локальный путь.
    """
    logger.info(f"Загрузка модели из {source}")
    if os.path.exists(destination):
        logger.info(f"Локальная модель уже существует: {destination}")
        return True
    if source.startswith('s3://'):
        return download_from_s3(source, destination)
    elif source.startswith('gs://'):
        return download_from_gcs(source, destination)
    elif source.startswith(('http://', 'https://')):
        return download_from_http(source, destination)
    else:
        if os.path.exists(source):
            import shutil
            logger.info(f"Копирование локальной модели {source} в {destination}")
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return True
        logger.error(f"Локальный файл не найден: {source}")
        return False


def ensure_model_exists(source: str, destination: str) -> bool:
    """Проверка существования модели и загрузка при необходимости."""
    if os.path.exists(destination):
        logger.info(f"Модель уже существует: {destination}")
        return True
    if is_cloud_path(source):
        logger.info(f"Загрузка модели из облака: {source}")
        return download_model(source, destination)
    if os.path.exists(source):
        return download_model(source, destination)
    logger.error(f"Модель не найдена ни в облаке, ни локально: {source}")
    return False
