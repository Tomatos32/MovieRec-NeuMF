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

1. **环境要求**
   - JDK 17 / Maven
   - Python 3.8+ (CUDA 12.x)
   - Node.js 18.x

2. **基础设施启动**
   - 确保 MySQL, Redis, Kafka 服务正常运行。
   - 执行 `sql/schema.sql` 完成表结构初始化。

3. **数据准备与初始训练**
   - 将 MovieLens 32M 数据集的 `ratings.csv` 放入指定目录。
   - 运行 `data_pipeline/data_processor.py` 进行数据预处理。
   - 运行模型训练脚本，训练完成后将权重保存为 `model/model.pth`。

4. **服务启动**
   - 使用 Docker Compose 一键启动基础设施：
     ```bash
     docker-compose up -d
     ```
   - 启动 Spring Boot 后端主程序。
   - 启动前端开发服务器：
     ```bash
     cd src/frontend && npm install && npm run dev
     ```

更多详细信息请参考 [Incremental_Training_Summary.md](./docs/MovieRec/Incremental_Training_Summary.md)。
