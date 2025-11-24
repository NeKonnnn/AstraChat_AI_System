import os
import tempfile
from io import BytesIO
import docx
import PyPDF2
import openpyxl
import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document

class DocumentProcessor:
    def __init__(self):
        print("Инициализируем DocumentProcessor...")
        # Инициализация векторного хранилища с пустым набором
        self.documents = []
        self.doc_names = []
        self.embeddings = None
        self.vectorstore = None
        # Хранилище информации об уверенности для каждого документа
        # {filename: {"confidence": float, "text_length": int, "file_type": str, "words": [{"word": str, "confidence": float}]}}
        self.confidence_data = {}
        # Хранилище путей к изображениям для мультимодальной модели
        # {filename: {"path": file_path, "minio_object": object_name, "minio_bucket": bucket_name}}
        # или {filename: file_path} для обратной совместимости
        self.image_paths = {}

        print("DocumentProcessor инициализирован")
        self.init_embeddings()
        
    def init_embeddings(self):
        """Инициализация модели для эмбеддингов"""
        print("Инициализируем модель эмбеддингов...")
        try:
            # Путь к локальной модели
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "models",
                "paraphrase-multilingual-MiniLM-L12-v2"
            )
            
            # Проверяем, существует ли локальная модель
            if os.path.exists(model_path):
                print(f"Используем локальную модель: {model_path}")
                model_name = model_path
            else:
                # Fallback на Hugging Face Hub
                print("Локальная модель не найдена, загружаем из Hugging Face Hub...")
                model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            
            # ВАЖНО: Используем CPU, так как CUDA может не поддерживать новые GPU
            self.embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={'device': 'cpu'}  # Принудительно используем CPU
            )
            print("Модель эмбеддингов успешно загружена (CPU)")
        except Exception as e:
            print(f"Ошибка при загрузке модели эмбеддингов: {str(e)}")
            import traceback
            traceback.print_exc()
            self.embeddings = None
    
    def process_document(self, file_data: bytes, filename: str, file_extension: str, minio_object_name=None, minio_bucket=None):
        """
        Обработка документа в зависимости от его типа
        
        Args:
            file_data: Данные файла в виде bytes
            filename: Имя файла (для идентификации)
            file_extension: Расширение файла (например, '.pdf', '.docx')
            minio_object_name: Имя объекта в MinIO (если файл хранится в MinIO)
            minio_bucket: Имя bucket в MinIO (если файл хранится в MinIO)
        """
        file_extension = file_extension.lower()
        document_text = ""
        confidence_info = None
        
        try:
            print(f"Обрабатываем документ: {filename} (тип: {file_extension}, размер: {len(file_data)} байт)")
            
            if file_extension == '.docx':
                result = self.extract_text_from_docx_bytes(file_data)
                if isinstance(result, dict):
                    document_text = result.get("text", "")
                    confidence_info = result.get("confidence_info", {"confidence": 100.0, "text_length": len(document_text), "file_type": "docx", "words": []})
                else:
                    document_text = result
                    confidence_info = self._create_confidence_info_for_text(document_text, 100.0, "docx")
            elif file_extension == '.pdf':
                result = self.extract_text_from_pdf_bytes(file_data)
                if isinstance(result, dict):
                    document_text = result.get("text", "")
                    confidence_info = result.get("confidence_info", {"confidence": 100.0, "text_length": len(document_text), "file_type": "pdf", "words": []})
                else:
                    document_text = result
                    confidence_info = self._create_confidence_info_for_text(document_text, 100.0, "pdf")
            elif file_extension in ['.xlsx', '.xls']:
                result = self.extract_text_from_excel_bytes(file_data)
                if isinstance(result, dict):
                    document_text = result.get("text", "")
                    confidence_info = result.get("confidence_info", {"confidence": 100.0, "text_length": len(document_text), "file_type": "excel", "words": []})
                else:
                    document_text = result
                    confidence_info = self._create_confidence_info_for_text(document_text, 100.0, "excel")
            elif file_extension == '.txt':
                result = self.extract_text_from_txt_bytes(file_data)
                if isinstance(result, dict):
                    document_text = result.get("text", "")
                    confidence_info = result.get("confidence_info", {"confidence": 100.0, "text_length": len(document_text), "file_type": "txt", "words": []})
                else:
                    document_text = result
                    confidence_info = self._create_confidence_info_for_text(document_text, 100.0, "txt")
            elif file_extension in ['.jpg', '.jpeg', '.png', '.webp']:
                result = self.extract_text_from_image_bytes(file_data)
                if isinstance(result, dict):
                    document_text = result.get("text", "")
                    confidence_info = result.get("confidence_info", {"confidence": 0.0, "text_length": len(document_text), "file_type": "image", "words": []})
                    # Если OCR не удался (пустой текст и есть ошибка), логируем, но продолжаем обработку
                    if not document_text and confidence_info.get("error"):
                        error_msg = confidence_info.get("error", "Неизвестная ошибка")
                        print(f"ВНИМАНИЕ: OCR не удался для {filename}: {error_msg}")
                        print(f"Изображение будет сохранено, но текст не будет извлечен")
                        # Продолжаем обработку - документ будет добавлен с пустым текстом
                        # Изображение все равно будет доступно для мультимодальной модели
                else:
                    document_text = result
                    confidence_info = self._create_confidence_info_for_text(document_text, 50.0, "image")
            else:
                return False, f"Неподдерживаемый формат файла: {file_extension}"
            
            print(f"Извлечено текста: {len(document_text)} символов")
            
            # Сохраняем информацию об уверенности
            if confidence_info:
                self.confidence_data[filename] = confidence_info
                print(f"Сохранена информация об уверенности для {filename}: {confidence_info['confidence']:.2f}%")
            
            # Сохраняем информацию об изображении в MinIO, если это изображение
            if file_extension in ['.jpg', '.jpeg', '.png', '.webp']:
                # Сохраняем информацию о MinIO объекте
                if minio_object_name and minio_bucket:
                    self.image_paths[filename] = {
                        "minio_object": minio_object_name,
                        "minio_bucket": minio_bucket,
                        "file_data": file_data  # Сохраняем данные в памяти для быстрого доступа
                    }
                    print(f"Сохранена информация об изображении в MinIO для {filename}: {minio_bucket}/{minio_object_name}")
                else:
                    # Fallback: сохраняем данные в памяти
                    self.image_paths[filename] = {
                        "file_data": file_data
                    }
                    print(f"Сохранены данные изображения в памяти для {filename}")
            
            # Добавляем документ в коллекцию
            # Если текст пустой (например, OCR не сработал), все равно добавляем документ
            # чтобы изображение было доступно для мультимодальной модели
            if document_text or file_extension in ['.jpg', '.jpeg', '.png', '.webp']:
                # Для изображений добавляем даже с пустым текстом
                self.add_document_to_collection(document_text, filename)
                print(f"Документ добавлен в коллекцию. Всего документов: {len(self.doc_names)}")
            else:
                print(f"Пропускаем добавление документа {filename} - текст пустой и это не изображение")
            
            return True, f"Документ {filename} успешно обработан"
            
        except Exception as e:
            print(f"Ошибка при обработке документа: {str(e)}")
            return False, f"Ошибка при обработке документа: {str(e)}"
    
    def _create_confidence_info_for_text(self, text, confidence_per_word, file_type):
        """Создание структуры информации об уверенности для текста"""
        import re
        # Улучшенное разбиение на слова: разделяем слова и знаки препинания
        # Находим слова (буквы, цифры, дефисы внутри слов) и знаки препинания отдельно
        # Паттерн: \w+ для слов (включая буквы, цифры, подчеркивания), или [^\w\s] для знаков препинания
        # Но лучше использовать более простой подход: разбиваем по пробелам и сохраняем структуру
        
        # Разбиваем текст на токены, сохраняя структуру
        # Используем регулярное выражение, которое находит слова и знаки препинания отдельно
        tokens = re.findall(r'\w+|[^\w\s]+', text)
        
        # Фильтруем пустые токены и формируем список слов
        words_with_confidence = []
        for token in tokens:
            token = token.strip()
            if token:  # Пропускаем пустые токены
                words_with_confidence.append({"word": token, "confidence": float(confidence_per_word)})
        
        avg_confidence = confidence_per_word
        
        return {
            "confidence": avg_confidence,
            "text_length": len(text),
            "file_type": file_type,
            "words": words_with_confidence
        }
    
    def extract_text_from_docx_bytes(self, file_data: bytes):
        """Извлечение текста из DOCX файла из bytes"""
        print(f"Извлекаем текст из DOCX файла (размер: {len(file_data)} байт)")
        doc = docx.Document(BytesIO(file_data))
        full_text = []
        
        for para in doc.paragraphs:
            full_text.append(para.text)
        
        # Извлекаем текст из таблиц
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text.append(cell.text)
        
        result = "\n".join(full_text)
        print(f"Извлечено {len(result)} символов из DOCX")
        return result
    
    def extract_text_from_pdf_bytes(self, file_data: bytes):
        """Извлечение текста из PDF файла из bytes с информацией об уверенности"""
        print(f"Извлекаем текст из PDF файла (размер: {len(file_data)} байт)")
        text = ""
        confidence_scores = []
        total_chars = 0
        
        # Используем PDFPlumber для более точного извлечения текста
        try:
            with pdfplumber.open(BytesIO(file_data)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    text += page_text
                    total_chars += len(page_text)
                    
                    # Для PDF оцениваем уверенность на основе возможности извлечения текста
                    # Если текст извлекается успешно, считаем уверенность высокой
                    if page_text.strip():
                        # PDFPlumber обычно имеет высокую уверенность, если текст извлекается
                        confidence_scores.append(95.0)  # Высокая уверенность для успешного извлечения
                    else:
                        confidence_scores.append(50.0)  # Средняя уверенность, если текст не найден
                        
            print(f"PDFPlumber успешно извлек {len(text)} символов")
        except Exception as e:
            print(f"Ошибка при извлечении текста с помощью pdfplumber: {str(e)}")
            
            # Резервный метод с PyPDF2
            try:
                reader = PyPDF2.PdfReader(BytesIO(file_data))
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    text += page_text
                    total_chars += len(page_text)
                    if page_text.strip():
                        confidence_scores.append(85.0)  # Немного ниже уверенность для PyPDF2
                    else:
                        confidence_scores.append(40.0)
                print(f"PyPDF2 успешно извлек {len(text)} символов")
            except Exception as e2:
                print(f"Ошибка при извлечении текста с помощью PyPDF2: {str(e2)}")
                raise
        
        # Если текст не извлечен (сканированный PDF), пробуем OCR через Surya
        if not text or len(text.strip()) == 0:
            print("PDF не содержит текста, возможно это сканированный документ. Пробуем OCR через Surya...")
            try:
                # Пробуем использовать pdf2image для конвертации PDF в изображения
                try:
                    from pdf2image import convert_from_bytes
                    from backend.llm_client import recognize_text_from_image_llm_svc
                    from PIL import Image
                    import io
                    
                    # Конвертируем PDF в изображения из bytes
                    images = convert_from_bytes(file_data, dpi=300)
                    print(f"PDF конвертирован в {len(images)} изображений для OCR")
                    
                    # Применяем OCR к каждому изображению через Surya
                    ocr_text = ""
                    ocr_confidence_scores = []
                    for i, image in enumerate(images):
                        print(f"Обрабатываем страницу {i+1}/{len(images)} с помощью Surya OCR...")
                        
                        # Конвертируем PIL Image в bytes
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        page_image_data = img_bytes.getvalue()
                        
                        # Вызываем OCR через llm-svc API
                        result = recognize_text_from_image_llm_svc(
                            image_file=page_image_data,
                            filename=f"page_{i+1}.png",
                            languages="ru,en"
                        )
                        
                        if result.get("success", False):
                            page_text = result.get("text", "")
                            page_confidence = result.get("confidence", 50.0)
                            ocr_text += f"\n--- Страница {i+1} ---\n{page_text}\n"
                            ocr_confidence_scores.append(page_confidence)
                        else:
                            print(f"Ошибка OCR для страницы {i+1}: {result.get('error', 'Unknown error')}")
                            ocr_confidence_scores.append(50.0)
                    
                    if ocr_text.strip():
                        text = ocr_text
                        confidence_scores = ocr_confidence_scores
                        print(f"Surya OCR успешно извлек {len(text)} символов из {len(images)} страниц")
                    else:
                        print("Surya OCR не смог извлечь текст из PDF")
                except ImportError:
                    print("Библиотека pdf2image не установлена. Для обработки сканированных PDF установите: pip install pdf2image")
                    print("Также требуется установить poppler: https://github.com/oschwartz10612/poppler-windows/releases")
                except Exception as ocr_error:
                    print(f"Ошибка при OCR обработке PDF через Surya: {ocr_error}")
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f"Не удалось применить OCR к PDF: {e}")
        
        # Вычисляем среднюю уверенность
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Создаем слова с уверенностью (для PDF используем среднюю уверенность или 100%)
        confidence_per_word = 100.0 if avg_confidence > 90.0 else avg_confidence
        confidence_info = self._create_confidence_info_for_text(text, confidence_per_word, "pdf")
        confidence_info["pages_processed"] = len(confidence_scores)
        
        return {
            "text": text,
            "confidence_info": confidence_info
        }
    
    def extract_text_from_excel(self, file_path):
        """Извлечение текста из Excel файла"""
        print(f"Извлекаем текст из Excel файла: {file_path}")
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        text_content = []
        
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            text_content.append(f"Лист: {sheet_name}")
            
            for row in sheet.iter_rows():
                row_values = []
                for cell in row:
                    if cell.value is not None:
                        row_values.append(str(cell.value))
                if row_values:
                    text_content.append("\t".join(row_values))
        
        result = "\n".join(text_content)
        print(f"Извлечено {len(result)} символов из Excel")
        return result
    
    def extract_text_from_txt_bytes(self, file_data: bytes):
        """Извлечение текста из TXT файла из bytes"""
        print(f"Извлекаем текст из TXT файла (размер: {len(file_data)} байт)")
        try:
            # Пробуем декодировать как UTF-8
            result = file_data.decode('utf-8')
            print(f"UTF-8 успешно извлек {len(result)} символов")
            return result
        except UnicodeDecodeError:
            # Если не удалось декодировать как UTF-8, пробуем другие кодировки
            encodings = ['cp1251', 'latin-1', 'koi8-r']
            for encoding in encodings:
                try:
                    result = file_data.decode(encoding)
                    print(f"{encoding} успешно извлек {len(result)} символов")
                    return result
                except UnicodeDecodeError:
                    continue
            
            # Если все кодировки не подошли, возвращаем строковое представление
            result = str(file_data)
            print(f"Бинарный режим извлек {len(result)} символов")
            return result

    def extract_text_from_image_bytes(self, file_data: bytes):
        """Извлечение текста из изображения из bytes с помощью Surya OCR через llm-svc API с информацией об уверенности"""
        print(f"Извлекаем текст из изображения с помощью Surya OCR (размер: {len(file_data)} байт)")
        print(f"DEBUG: Начинаем вызов OCR через llm-svc API...")
        try:
            # Импортируем функцию для работы с OCR через llm-svc
            from backend.llm_client import recognize_text_from_image_llm_svc
            from PIL import Image
            
            # Определяем имя файла на основе формата изображения
            img = Image.open(BytesIO(file_data))
            filename = "image.jpg"
            if img.format:
                filename = f"image.{img.format.lower()}"
            
            print(f"DEBUG: Изображение открыто, формат: {img.format}, размер: {img.size}")
            
            # Вызываем OCR через llm-svc API
            print("Отправляем запрос на распознавание текста через llm-svc...")
            print(f"DEBUG: Вызываем recognize_text_from_image_llm_svc с filename={filename}, languages=ru,en")
            try:
                result = recognize_text_from_image_llm_svc(
                    image_file=file_data,
                    filename=filename,
                    languages="ru,en"
                )
                print(f"DEBUG: OCR вернул результат: success={result.get('success', False)}")
            except Exception as ocr_exception:
                print(f"DEBUG: Исключение при вызове OCR: {ocr_exception}")
                import traceback
                traceback.print_exc()
                raise
            
            # Проверяем результат
            if not result.get("success", False):
                error_msg = result.get("error", "Неизвестная ошибка")
                print(f"Surya OCR вернул ошибку: {error_msg}")
                print(f"ВНИМАНИЕ: OCR не удался, текст не будет извлечен из изображения")
                # Не сохраняем сообщение об ошибке как текст документа
                # Вместо этого возвращаем пустой текст
                return {
                    "text": "",  # Пустой текст вместо сообщения об ошибке
                    "confidence_info": {
                        "confidence": 0.0,
                        "text_length": 0,
                        "file_type": "image",
                        "ocr_available": False,
                        "error": error_msg,
                        "words": []
                    }
                }
            
            # Извлекаем данные из результата
            text = result.get("text", "")
            words_with_confidence = result.get("words", [])
            avg_confidence = result.get("confidence", 0.0)
            word_count = result.get("words_count", 0)
            
            # Если текст не извлечен, возвращаем пустой текст
            if not text.strip():
                print(f"Surya OCR не смог извлечь текст из изображения (текст пустой)")
                # Не сохраняем сообщение об отсутствии текста как текст документа
                return {
                    "text": "",  # Пустой текст
                    "confidence_info": {
                        "confidence": 0.0,
                        "text_length": 0,
                        "file_type": "image",
                        "ocr_available": False,
                        "words": []
                    }
                }
            
            print(f"Surya OCR успешно извлек {len(text)} символов, {word_count} слов, средняя уверенность: {avg_confidence:.2f}%")
            
            return {
                "text": text,
                "confidence_info": {
                    "confidence": avg_confidence,
                    "text_length": len(text),
                    "file_type": "image",
                    "ocr_available": True,
                    "words": words_with_confidence
                }
            }
        except ImportError:
            # Если функция не доступна, возвращаем информацию о файле
            result_text = f"[Изображение. Для распознавания текста требуется доступ к llm-svc API.]"
            print(f"Функция распознавания через llm-svc не доступна, возвращаем описание: {len(result_text)} символов")
            return {
                "text": result_text,
                "confidence_info": {
                    "confidence": 0.0,
                    "text_length": len(result_text),
                    "file_type": "image",
                    "ocr_available": False,
                    "words": []
                }
            }
        except Exception as e:
            error_msg = str(e)
            print(f"Ошибка при обработке изображения через Surya OCR: {error_msg}")
            import traceback
            traceback.print_exc()
            
            # Не сохраняем сообщение об ошибке как текст документа
            # Вместо этого возвращаем пустой текст, но сохраняем информацию об ошибке
            result_text = ""  # Пустой текст вместо сообщения об ошибке
            print(f"ВНИМАНИЕ: OCR не удался, текст не будет извлечен из изображения")
            return {
                "text": result_text,
                "confidence_info": {
                    "confidence": 0.0,
                    "text_length": 0,
                    "file_type": "image",
                    "ocr_available": False,
                    "error": error_msg,
                    "words": []
                }
            }
    
    def add_document_to_collection(self, text, doc_name):
        """Добавление документа в коллекцию и обновление векторного хранилища"""
        print(f"Добавляем документ '{doc_name}' в коллекцию...")
        print(f"Длина текста: {len(text)} символов")
        
        # Разбиваем текст на части (уменьшили размер для экономии токенов)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # Уменьшили с 1000 до 500
            chunk_overlap=100,  # Уменьшили с 200 до 100
            length_function=len,
        )
        
        chunks = text_splitter.split_text(text)
        print(f"Создано чанков: {len(chunks)}")
        
        # Если нет чанков (пустой текст), создаем хотя бы один минимальный чанк
        if len(chunks) == 0:
            print(f"ВНИМАНИЕ: Нет чанков для документа '{doc_name}', создаем минимальный чанк")
            chunks = [text] if text else [f"[Документ: {doc_name}]"]
        
        # Создаем документы для langchain
        langchain_docs = []
        for i, chunk in enumerate(chunks):
            langchain_docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": doc_name, "chunk": i}
                )
            )
        
        # Добавляем в общий список документов
        self.documents.extend(langchain_docs)
        if doc_name not in self.doc_names:
            self.doc_names.append(doc_name)
        
        print(f"Документ добавлен. Всего документов: {len(self.documents)}, имен: {len(self.doc_names)}")
        
        # Обновляем векторное хранилище
        self.update_vectorstore()
    
    def update_vectorstore(self):
        """Обновление или создание векторного хранилища"""
        print(f"\n{'='*60}")
        print(f"ОБНОВЛЕНИЕ ВЕКТОРНОГО ХРАНИЛИЩА")
        print(f"{'='*60}")
        print(f"Документов для индексации: {len(self.documents)}")
        print(f"Модель эмбеддингов инициализирована: {self.embeddings is not None}")
        print(f"Текущий vectorstore существует: {self.vectorstore is not None}")
        
        if not self.documents:
            print("ОШИБКА: Нет документов для индексации")
            return
        
        if not self.embeddings:
            print("Модель эмбеддингов не инициализирована, пытаемся инициализировать...")
            self.init_embeddings()
            if not self.embeddings:
                print("ОШИБКА: Не удалось инициализировать модель эмбеддингов")
                return
            else:
                print("Модель эмбеддингов успешно инициализирована")
        
        try:
            # Создаем новое векторное хранилище
            print("\nСоздаем векторное хранилище FAISS...")
            print(f"Количество документов: {len(self.documents)}")
            print(f"Первый документ (preview): {self.documents[0].page_content[:100]}..." if self.documents else "   Нет документов")
            
            self.vectorstore = FAISS.from_documents(self.documents, self.embeddings)
            
            print(f"\nУСПЕХ: Векторное хранилище обновлено!")
            print(f"Добавлено чанков: {len(self.documents)}")
            print(f"Vectorstore доступен: {self.vectorstore is not None}")
            print(f"Тип vectorstore: {type(self.vectorstore)}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"\nОШИБКА при обновлении векторного хранилища:")
            print(f"{str(e)}")
            print(f"{'='*60}\n")
            import traceback
            traceback.print_exc()
    
    def query_documents(self, query, k=2):
        """Поиск релевантных документов по запросу"""
        print(f"Ищем релевантные документы для запроса: '{query}'")
        print(f"Векторное хранилище: {self.vectorstore is not None}")
        
        if not self.vectorstore:
            print("Векторное хранилище не инициализировано или пусто")
            return "Векторное хранилище не инициализировано или пусто"
        
        try:
            print(f"Выполняем поиск с k={k}...")
            docs = self.vectorstore.similarity_search(query, k=k)
            print(f"Найдено документов: {len(docs)}")
            
            results = []
            for doc in docs:
                result = {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "Неизвестный источник"),
                    "chunk": doc.metadata.get("chunk", 0)
                }
                results.append(result)
                print(f"Документ: {result['source']}, чанк: {result['chunk']}, длина: {len(result['content'])}")
            
            return results
        except Exception as e:
            print(f"Ошибка при поиске по документам: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Ошибка при поиске по документам: {str(e)}"
    
    def get_document_list(self):
        """Получение списка загруженных документов"""
        print(f"get_document_list вызван. Документы: {self.doc_names}")
        return self.doc_names
    
    def get_image_paths(self):
        """
        Получение списка путей к изображениям для мультимодальной модели
        Возвращает список путей к локальным файлам (временные файлы, скачанные из MinIO при необходимости)
        """
        image_paths_list = []
        print(f"DEBUG get_image_paths: image_paths = {self.image_paths}")
        
        for filename, path_info in self.image_paths.items():
            print(f"DEBUG get_image_paths: обрабатываем {filename}, path_info = {path_info}")
            
            if isinstance(path_info, dict):
                # Если есть file_data, создаем временный файл
                if "file_data" in path_info:
                    try:
                        import tempfile
                        # Создаем временный файл
                        suffix = os.path.splitext(filename)[1] or ".jpg"
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        temp_file.write(path_info["file_data"])
                        temp_file.close()
                        temp_path = temp_file.name
                        print(f"DEBUG get_image_paths: создан временный файл для {filename}: {temp_path}")
                        image_paths_list.append(temp_path)
                    except Exception as e:
                        print(f"ERROR get_image_paths: не удалось создать временный файл для {filename}: {e}")
                        image_paths_list.append(None)
                # Если есть путь, используем его
                elif "path" in path_info:
                    image_paths_list.append(path_info.get("path"))
                else:
                    print(f"WARNING get_image_paths: нет file_data или path для {filename}")
                    image_paths_list.append(None)
            else:
                # Обратная совместимость: просто путь
                image_paths_list.append(path_info)
        
        print(f"get_image_paths вызван. Изображения: {image_paths_list}")
        return image_paths_list
    
    def get_image_minio_info(self, filename):
        """
        Получение информации о MinIO объекте для изображения
        
        Returns:
            dict: {"minio_object": str, "minio_bucket": str} или None
        """
        if filename in self.image_paths:
            path_info = self.image_paths[filename]
            if isinstance(path_info, dict):
                return {
                    "minio_object": path_info.get("minio_object"),
                    "minio_bucket": path_info.get("minio_bucket")
                }
        return None
    
    def clear_documents(self):
        """Очистка коллекции документов"""
        print("Очищаем коллекцию документов...")
        self.documents = []
        self.doc_names = []
        self.vectorstore = None
        self.confidence_data = {}
        self.image_paths = {}
        print("Коллекция документов очищена")
        return "Коллекция документов очищена"
    
    def get_confidence_report_data(self):
        """Получение данных для отчета об уверенности с процентами над словами"""
        if not self.confidence_data:
            return {
                "total_documents": 0,
                "documents": [],
                "average_confidence": 0.0,
                "formatted_texts": []
            }
        
        documents = []
        formatted_texts = []
        total_confidence = 0.0
        total_weighted_confidence = 0.0
        total_words = 0
        
        for filename, info in self.confidence_data.items():
            words = info.get("words", [])
            
            # Форматируем текст с процентами над словами
            formatted_lines = []
            current_line = []
            
            for word_info in words:
                word = word_info.get("word", "")
                conf = word_info.get("confidence", 0.0)
                
                # Пропускаем пустые слова
                if not word:
                    continue
                
                # Форматируем каждое слово с процентом над ним
                formatted_word = f"{conf:.0f}%\n{word}"
                current_line.append(formatted_word)
                
                # Добавляем перенос строки после каждого слова для читаемости
                if len(current_line) >= 10:  # Примерно 10 слов на строку
                    formatted_lines.append("  ".join(current_line))
                    current_line = []
            
            # Добавляем оставшиеся слова
            if current_line:
                formatted_lines.append("  ".join(current_line))
            
            formatted_text = "\n".join(formatted_lines)
            
            # Вычисляем среднюю уверенность для документа
            doc_avg_confidence = info.get("confidence", 0.0)
            if words:
                doc_avg_confidence = sum(w.get("confidence", 0.0) for w in words) / len(words)
            
            documents.append({
                "filename": filename,
                "confidence": doc_avg_confidence,
                "text_length": info.get("text_length", 0),
                "file_type": info.get("file_type", "unknown"),
                "words_count": len(words)
            })
            
            formatted_texts.append({
                "filename": filename,
                "formatted_text": formatted_text,
                "words": words
            })
            
            total_confidence += doc_avg_confidence
            if words:
                total_weighted_confidence += sum(w.get("confidence", 0.0) for w in words)
                total_words += len(words)
        
        # Вычисляем общую среднюю уверенность
        avg_confidence = total_confidence / len(documents) if documents else 0.0
        
        # Вычисляем итоговую уверенность по всем словам
        overall_confidence = total_weighted_confidence / total_words if total_words > 0 else avg_confidence
        
        return {
            "total_documents": len(documents),
            "documents": documents,
            "average_confidence": avg_confidence,
            "overall_confidence": overall_confidence,
            "total_words": total_words,
            "formatted_texts": formatted_texts
        }
    
    def process_query(self, query, agent_function):
        """Обработка запроса с контекстом документов для LLM"""
        print(f"Обрабатываем запрос: {query}")
        print(f"Векторное хранилище: {self.vectorstore is not None}")
        print(f"Количество документов: {len(self.documents)}")
        print(f"Имена документов: {self.doc_names}")
        
        if not self.vectorstore:
            return "Нет загруженных документов. Пожалуйста, загрузите документы перед выполнением запроса."
        
        try:
            # Получаем релевантные документы
            docs = self.query_documents(query)
            print(f"Найдено релевантных фрагментов: {len(docs) if isinstance(docs, list) else 'ошибка'}")
            
            if isinstance(docs, str):  # Если возникла ошибка
                print(f"Ошибка при поиске документов: {docs}")
                return docs
            
            # Формируем контекст из найденных документов
            context = "Контекст из документов:\n\n"
            for i, doc in enumerate(docs):
                context += f"Фрагмент {i+1} (из документа '{doc['source']}'):\n{doc['content']}\n\n"
            
            print(f"Контекст сформирован, длина: {len(context)} символов")
            
            # Подготавливаем запрос для LLM с инструкциями и контекстом
            prompt = f"""На основе предоставленного контекста ответь на вопрос пользователя. 
Если информации в контексте недостаточно, укажи это.
Отвечай только на основе информации из контекста. Не придумывай информацию.

{context}

Вопрос пользователя: {query}

Ответ:"""
            
            print("Отправляем запрос к LLM...")
            # Отправляем запрос к LLM
            response = agent_function(prompt)
            print(f"Получен ответ от LLM, длина: {len(response)} символов")
            return response
            
        except Exception as e:
            print(f"Ошибка при обработке запроса: {str(e)}")
            return f"Ошибка при обработке запроса: {str(e)}"
    
    def remove_document(self, filename):
        """Удалить конкретный документ по имени файла"""
        print(f"Удаляем документ: {filename}")
        print(f"До удаления - self.doc_names: {self.doc_names}")
        print(f"До удаления - self.documents: {len(self.documents)}")
        print(f"До удаления - self.vectorstore доступен: {self.vectorstore is not None}")
        
        try:
            # Находим индекс документа
            if filename not in self.doc_names:
                print(f"Документ {filename} не найден")
                return False
            
            # Удаляем документ из списка имен
            index = self.doc_names.index(filename)
            self.doc_names.pop(index)
            print(f"Документ {filename} удален из списка имен")
            
            # Удаляем информацию об уверенности
            if filename in self.confidence_data:
                del self.confidence_data[filename]
                print(f"Информация об уверенности для {filename} удалена")
            
            # Удаляем путь к изображению, если это изображение
            if filename in self.image_paths:
                del self.image_paths[filename]
                print(f"Путь к изображению для {filename} удален")
            
            # Удаляем ВСЕ чанки этого документа из списка документов
            # Ищем все документы с этим именем и удаляем их
            documents_to_remove = []
            for i, doc in enumerate(self.documents):
                if doc.metadata.get("source") == filename:
                    documents_to_remove.append(i)
            
            # Удаляем чанки в обратном порядке, чтобы индексы не сдвигались
            for i in reversed(documents_to_remove):
                self.documents.pop(i)
            
            print(f"Удалено чанков документа {filename}: {len(documents_to_remove)}")
            print(f"После удаления - self.doc_names: {self.doc_names}")
            print(f"После удаления - self.documents: {len(self.documents)}")
            
            # Пересоздаем vectorstore с оставшимися документами
            if self.documents:
                print("Пересоздаем vectorstore с оставшимися документами")
                self.update_vectorstore()
                print(f"После обновления vectorstore - self.vectorstore доступен: {self.vectorstore is not None}")
            else:
                print("Нет документов, очищаем vectorstore")
                self.vectorstore = None
                print(f"После очистки - self.vectorstore доступен: {self.vectorstore is not None}")
            
            print(f"Документ {filename} успешно удален. Осталось документов: {len(self.doc_names)}")
            return True
            
        except Exception as e:
            print(f"Ошибка при удалении документа {filename}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False 
    
    def get_document_context(self, query, k=2):
        """Получение контекста документов для запроса"""
        print(f"Получаем контекст документов для запроса: '{query}'")
        print(f"Векторное хранилище: {self.vectorstore is not None}")
        
        if not self.vectorstore:
            print("Векторное хранилище не инициализировано")
            return None
        
        try:
            # Получаем релевантные документы
            docs = self.query_documents(query, k=k)
            print(f"Найдено релевантных фрагментов: {len(docs) if isinstance(docs, list) else 'ошибка'}")
            
            if isinstance(docs, str):  # Если возникла ошибка
                print(f"Ошибка при поиске документов: {docs}")
                return None
            
            # Формируем контекст из найденных документов
            context = ""
            for i, doc in enumerate(docs):
                context += f"Фрагмент {i+1} (из документа '{doc['source']}'):\n{doc['content']}\n\n"
            
            print(f"Контекст сформирован, длина: {len(context)} символов")
            
            return context
            
        except Exception as e:
            print(f"Ошибка при получении контекста документов: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
