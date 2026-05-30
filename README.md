# MovieRec-NNCF

## 项目概述
MovieRec-NNCF 是一个基于神经矩阵分解（NeuMF）的模型实现。该系统支持冷启动与个性化推荐两种模式，采用业务调度模块与深度学习推理模块分离的架构设计。系统设置了基于时间戳的冷启动降级逻辑，并具备数据监控功能，以保证推荐服务的稳定性。

## 系统架构与实现

### 1. 业务调度层 (Spring Boot)
- **非阻塞 I/O**：采用 WebFlux 与 Reactor 框架实现异步调用，提高系统的并发处理能力。
- **服务路由与容错 (Resilience4j)**：根据用户交互数据量自动切换冷启动模式或个性化推荐模式。设置了 150ms 的超时中断，在推理服务响应超时时自动回退至热门榜单数据。
- **多级缓存**：通过 Redis 存储短效语义数据与热门榜单，减轻后台数据库查询压力。

### 2. 模型推理模块 (PyTorch + FastAPI)
- **神经网络结构**：集成 GMF（广义矩阵分解）与 MLP（多层感知机）双通道。通过独立的 Embedding 层映射用户与电影特征，并使用全连接层进行融合。
- **性能优化**：推理服务启动时加载模型权重并设置为评估模式（Eval）。所有推理请求在 `torch.no_grad()` 上下文中运行，以减少显存占用并提高响应速度。

### 3. 数据处理与反馈管线 (Kafka + Python)
- **数据采集与反馈**：利用 Kafka 收集用户交互事件。在线部分用于更新 Redis 中的用户画像；离线部分将全量事件存入数据库，供后续模型训练使用。
- **数据工程**：使用 Pandas 处理 ML-32M 数据集。实现 1:4 的正负样本采样，并采用基于时间序列的 Leave-One-Out 方法划分数据集，防止数据泄露。
- **存储方案**：
  -  MySQL：存储电影元数据、用户基本信息及全量评分交互记录。
  -  Redis：存储热点数据及用户短期会话特征。

### 4. 前端交互 (Vue 3 + Tailwind CSS)
- **请求限流**：在前端设置防抖（Debounce）逻辑，限制用户高频操作对后端及消息队列产生的压力。
- **界面逻辑**：采用 Vue 3 组合式 API 开发。支持深色模式切换，并根据后端返回的推荐模式（冷启动/个性化）动态调整界面提示状态。

## 目录结构
```text
MovieRec-NNCF/
30: ├── data_pipeline/         # 数据采样、清洗与离线集切分脚本
31: ├── docs/                  # 系统设计文档与进度记录
32: ├── inference/             # 基于 FastAPI + PyTorch 的推理服务
33: ├── model/                 # 神经网络结构定义与增量训练脚本
34: ├── sql/                   # 数据库表结构 DDL 脚本
35: └── src/
36:     ├── main/java/         # 业务路由、Kafka 消费者及数据持久化代码
37:     └── frontend/          # Vue 3 前端代码
```

## 部署与启动指引

### 1. 环境要求与依赖安装

- **后端系统 (Java 17 / Maven 3.x)**
  - 核心依赖：`Spring WebFlux`, `R2DBC (MySQL Reactive)`, `Reactive Redis`, `Spring Kafka`, `Resilience4j`, `Lombok`, `jjwt`
  - 依赖安装：
    ```bash
    # 在项目根目录下执行以预下载并构建 Maven 依赖
    mvn clean install -Dmaven.test.skip=true
    ```

- **模型推理与数据管道 (Python 3.8+ / 推荐 CUDA 环境)**
  - 核心依赖：`FastAPI`, `Uvicorn`, `Pydantic`, `PyTorch`, `Pandas`, `NumPy`, `Scikit-Learn`, `Tqdm`
  - 依赖安装：
    ```bash
    # 安装 Python 深度学习和推理所需依赖
    pip install -r inference/requirements.txt
    ```

- **前端交互系统 (Node.js 18.x / npm 9.x+)**
  - 核心依赖：`Vue 3`, `Vite`, `Element Plus`, `Pinia`, `Vue Router`, `GSAP`, `Lucide Vue`, `Tailwind CSS v4`
  - 依赖安装：
    ```bash
    # 切换至前端目录并安装依赖
    cd src/frontend && npm install
    ```

### 2. 基础设施与推理模块启动

- **容器化基础设施**：使用 Docker Compose 可以一键构建并启动底层服务及**模型推理边车**。它会自动运行以下容器：
  - **Redis** (缓存服务)
  - **Zookeeper & Kafka** (事件消息总线)
  - **FastAPI 推理边车** (`inference-sidecar`，自动加载训练好的模型权重 `/app/model/model.pth` 并运行在 `8000` 端口)
- **启动命令**：
  ```bash
  docker-compose up -d
  ```
- **MySQL 数据库**：采用宿主机本地安装的实例，确保其正常运行，并执行 `sql/schema.sql` 完成表结构设计与分区表的初始化。

### 3. 数据准备与模型训练

- 将 MovieLens 32M 数据集的 `ratings.csv` 放入 `data` 目录。
- 运行数据清洗及采样脚本进行特征管道处理：
  ```bash
  python data_pipeline/data_processor.py
  ```
- 运行模型训练脚本，训练完成后将模型权重保存为 `model/model.pth`（该目录已通过 Volume 挂载同步到推理容器内）。

### 4. 服务运行与启动

- **业务调度/后端模块 (Spring Boot)**：
  - **项目目录**：项目根目录 `MovieRec-NNCF/` (因 `pom.xml` 位于根目录)。
  - **启动方式**：直接在 IDE 中打开项目根目录并运行 `com.movierec.nncf.MovieRecNncfApplication` 的 `main` 方法，或直接在根目录下通过命令行启动：
    ```bash
    mvn spring-boot:run
    ```
  - **提示**：若遇到端口占用，可在任务管理器中结束名为 `ApplicationWebServerDaemon` 的进程。

- **前端交互模块 (Vue 3)**：
  - **项目目录**：`src/frontend/`
  - **启动方式**：
    ```bash
    cd src/frontend
    npm run dev
    ```

- **[可选] 手动调试推理模块 (Python/FastAPI)**：
  - **说明**：正常情况下推理模块已在第二步通过 Docker 自动拉起。若需要对其代码进行本地开发或断点调试，可关闭容器并手动运行：
  - **项目目录**：`inference/`
  - **启动方式**：
    ```bash
    cd inference
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```

更多详细信息请参考 [Incremental_Training_Summary.md](./docs/MovieRec/Incremental_Training_Summary.md)。
