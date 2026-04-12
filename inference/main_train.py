import os
import sys
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline.data_processor import MovieLensProcessor, MovieLensDataset
from model.neumf import NeuMF, get_optimizer, train_one_epoch


def main():
    # ===== 0. 检测计算设备 =====
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[GPU] 检测到加速器: {gpu_name} ({gpu_mem:.1f} GB VRAM)")
    else:
        print("[CPU] 未检测到 CUDA GPU，将使用 CPU 训练（速度较慢）")

    # ===== 1. 检查数据路径 =====
    data_path = '../data/ratings.csv'
    if not os.path.exists(data_path):
        print(f"Error: 找不到数据文件 {data_path}")
        print("请检查 ML-32M 数据集是否已正确解压到 data 目录。")
        return

    # ===== 2. 运行数据处理管道 =====
    print("\n>>> 1. 启动数据预处理管道 (ML-32M)...")
    processor = MovieLensProcessor(data_path)
    train_df, valid_df, test_df = processor.process()

    if train_df is None:
        return

    num_users = len(processor.user_mapping)
    num_movies = len(processor.movie_mapping)
    print(f"    - 总用户数: {num_users}, 总电影数: {num_movies}")

    # ===== 2.1 构建元数据 (Genres) =====
    genres_matrix, num_genres = processor.build_genres_matrix()

    # ===== 3. 构建 PyTorch Dataset 与 DataLoader =====
    print("\n>>> 2. 构建 Dataset 与动态负采样 DataLoader...")
    train_dataset = MovieLensDataset(
        train_df,
        processor.user_interacted_movies,
        processor.all_movies_list,
        num_negatives=4,
        is_training=True
    )

    use_cuda = device.type == "cuda"
    batch_size = 16384  # 核心优化：充分利用 GPU 吞吐量
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=4,  # 已静态化 Tensor，开启多线程毫无压力
        pin_memory=use_cuda,
    )

    # ===== 4. 初始化模型 =====
    latent_dim = 64
    print(f"\n>>> 3. 初始化 NeuMF 模型 (Latent Dim = {latent_dim}, Num Genres = {num_genres})...")
    print(f"    - 使用计算设备: {device}")

    model = NeuMF(num_users=num_users, num_movies=num_movies, latent_dim=latent_dim, num_genres=num_genres)
    model.to(device)

    # 估算模型参数量
    total_params = sum(p.numel() for p in model.parameters())
    print(f"    - 模型总参数量: {total_params:,}")

    # ===== 5. 配置优化器与损失函数 =====
    print("\n>>> 4. 配置优化器 (带选择性 L2 正则化) & BCELoss...")
    optimizer = get_optimizer(model, lr=1e-3, weight_decay=1e-4)
    criterion = nn.BCELoss()

    # ===== 6. 开始正式训练 =====
    epochs = 3  
    print(f"\n>>> 5. 开始正式训练 (Total Epochs: {epochs})...")

    # 确保保存模型的目录存在
    os.makedirs('../model', exist_ok=True)

    for epoch in range(1, epochs + 1):
        print(f"\n--- Epoch {epoch}/{epochs} ---")
        epoch_start = time.time()

        avg_loss = train_one_epoch(model, train_loader, optimizer, criterion, device, global_genres_matrix=genres_matrix)

        epoch_time = time.time() - epoch_start
        print(f"    - Epoch {epoch} 完毕 | 平均损失: {avg_loss:.4f} | 耗时: {epoch_time:.1f}s")

        # 每个 epoch 后清理 GPU 缓存
        if use_cuda:
            torch.cuda.empty_cache()

    # ===== 7. 保存权重 =====
    save_path = '../model/model.pth'
    torch.save(model.state_dict(), save_path)
    print(f"\n>>> 6. 训练完成！模型已持久化保存至: {save_path}")

    print("\n请记下以下环境参数，用于后续推理边车的环境变量配置：")
    print("=========================================")
    print(f"export NUM_USERS={num_users}")
    print(f"export NUM_MOVIES={num_movies}")
    print(f'export MODEL_PATH="{save_path}"')
    print("=========================================")


if __name__ == '__main__':
    main()
