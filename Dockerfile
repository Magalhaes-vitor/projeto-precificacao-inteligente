# Imagem oficial leve do Python
FROM python:3.11-slim

# Força os logs a aparecerem em tempo real no CloudWatch da AWS
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala apenas o Google Chrome (Sem o xvfb!)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    apt-transport-https \
    unzip \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando de arranque limpo e direto
CMD ["python", "scrapers/main.py"]