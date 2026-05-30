FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py estimate_generator.py drive_uploader.py calendar_generator.py context.md .
CMD ["python", "bot.py"]
