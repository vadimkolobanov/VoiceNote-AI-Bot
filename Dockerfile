# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файл с зависимостями в рабочую директорию
COPY requirements.txt .

# Устанавливаем зависимости
# --no-cache-dir чтобы не хранить кеш pip и уменьшить размер образа
# --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host pypi.org могут быть нужны в некоторых сетях
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы проекта в рабочую директорию
# (main.py, inline_keyboards.py, utills.py, llm_processor.py, database_setup.py)
COPY . .

# Указываем команду для запуска приложения
# Предполагается, что переменные окружения (TG_BOT_TOKEN, DEEPSEEK_API_KEY, DB_USER и т.д.)
# будут переданы в контейнер при его запуске.
CMD ["python", "main.py"]
LABEL authors  = "Diana Globuz"
EXPOSE 8000