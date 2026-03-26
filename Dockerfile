# 使用 Python 3.10 轻量镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（uWSGI、MySQL客户端等）
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 收集静态文件（会在容器启动时执行）
RUN python manage.py collectstatic --noinput

# 暴露 uWSGI 端口
EXPOSE 8000

# 启动 uWSGI
CMD ["uwsgi", "--ini", "uwsgi.ini"]