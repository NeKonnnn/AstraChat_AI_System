import os

def split_py_file_to_txt(input_file, lines_per_file=500):
    """
    Открывает .py файл и разделяет его содержимое на .txt файлы по указанному количеству строк
    """
    
    if not os.path.exists(input_file):
        print(f"Ошибка: Файл '{input_file}' не найден!")
        return
    
    try:
        # Открываем и читаем исходный файл
        with open(input_file, 'r', encoding='utf-8') as file:
            all_lines = file.readlines()
        
        total_lines = len(all_lines)
        print(f"Всего строк в файле: {total_lines}")
        
        # Создаем директорию для выходных файлов
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = f"{base_name}_split"
        os.makedirs(output_dir, exist_ok=True)
        
        # Разделяем на части
        file_number = 1
        for i in range(0, total_lines, lines_per_file):
            chunk = all_lines[i:i + lines_per_file]
            
            # Формируем имя выходного файла
            output_file = os.path.join(
                output_dir, 
                f"{base_name}_part{file_number:03d}.txt"
            )
            
            # Записываем в файл
            with open(output_file, 'w', encoding='utf-8') as out_file:
                out_file.writelines(chunk)
            
            print(f"Создан файл: {output_file} (строк: {len(chunk)})")
            file_number += 1
        
        print(f"\nГотово! Создано {file_number - 1} файлов в папке '{output_dir}'")
        
    except Exception as e:
        print(f"Произошла ошибка: {e}")

# Пример использования
if __name__ == "__main__":
    # Укажите путь к вашему .py файлу
    file_to_split = "main.py"  # ИЗМЕНИТЕ ЭТОТ ПУТЬ
    
    split_py_file_to_txt(file_to_split, 500)