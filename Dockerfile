FROM python:3.9-slim

# 设置环境变量，禁用Python的输出缓冲
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制程序文件
COPY . .

# 运行程序
CMD ["python", "-u", "binanceListing.py"] 