FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY inference/requirements.txt .
RUN export HTTP_PROXY="http://host.docker.internal:7897" && \
    export HTTPS_PROXY="http://host.docker.internal:7897" && \
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements.txt

# 复制推理代码和模型定义
COPY inference/main.py ./inference/
COPY model/neumf.py ./model/

# 添加空 __init__.py 使 model 成为可导入包
RUN touch model/__init__.py

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "inference.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
