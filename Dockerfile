# Imagem oficial leve do Python
FROM python:3.11-slim

# Evita a gravação de arquivos .pyc e força os logs direto no terminal da AWS
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Atualiza dependências do SO, instala o Microsoft Edge e o Xvfb (Monitor Virtual)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    apt-transport-https \
    unzip \
    xvfb \
    && wget -q -O - https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update \
    && apt-get install -y microsoft-edge-stable \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho no container
WORKDIR /app

# Copia e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para dentro do container
COPY . .

# Comando de arranque (o Orquestrador)
CMD ["python", "main.py"]