import os
import sys
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline.data_processor import MovieLensProcessor, MovieLensDataset
# 引入我们刚才添加的消融模型
from model.neumf import NeuMFNoConcat, get_optimizer, train_one_epoch

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Ablation Study] 开始训练对比模型 (NeuMF - No Concat) on {device}")

    data_path = '../data/ratings.csv'
    if not os.path.exists(data_path):
        print(f"Error: 找不到数据文件 {data_path}")
        return

    # 1. 数据处理 (与主模型保持完全一致，保证控制变量)
    print("\n>>> 1. 启动数据预处理...")
    processor = MovieLensProcessor(data_path)
    train_df, valid_df, test_df = processor.process()
    if train_df is None: return

    num_users = len(processor.user_mapping)
    num_movies = len(processor.movie_mapping)

    print("\n>>> 2. 构建 DataLoader...")
    train_dataset = MovieLensDataset(
        train_df, processor.user_interacted_movies, processor.all_movies_list,
        num_negatives=4, is_training=True
    )
    
    batch_size = 4096
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=0, pin_memory=(device.type == "cuda"),
    )

    # 2. 初始化【无拼接】的消融模型
    latent_dim = 64
    print(f"\n>>> 3. 初始化 NeuMFNoConcat 模型...")
    model = NeuMFNoConcat(num_users=num_users, num_movies=num_movies, latent_dim=latent_dim)
    model.to(device)

    # 3. 配置优化器与损失函数
    optimizer = get_optimizer(model, lr=1e-3, weight_decay=1e-4)
    criterion = nn.BCELoss()

    # 4. 训练过程
    epochs = 3
    print(f"\n>>> 4. 开始训练 (Total Epochs: {epochs})...")
    os.makedirs('../model', exist_ok=True)

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()
        avg_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        epoch_time = time.time() - epoch_start
        print(f"    - Epoch {epoch} 完毕 | 平均损失: {avg_loss:.4f} | 耗时: {epoch_time:.1f}s")
        if device.type == "cuda": torch.cuda.empty_cache()

    # 5. 安全保存：绝对隔离的名字
    save_path = '../model/model_noconcat.pth'
    torch.save(model.state_dict(), save_path)
    print(f"\n>>> 5. 训练完成！消融模型已安全保存至: {save_path}")
    print("此模型独立于主系统，仅供 evaluate_model.py 进行对比测试。")

if __name__ == '__main__':
    main()