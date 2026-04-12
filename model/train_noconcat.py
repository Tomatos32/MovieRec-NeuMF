import os
import sys
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline.data_processor import MovieLensProcessor, MovieLensDataset
from model.neumf import NeuMFNoConcat, get_optimizer, train_one_epoch

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Standard Model] Using device: {device}")

    data_path = '../data/ratings.csv'
    if not os.path.exists(data_path):
        print(f"Error: Data file {data_path} not found.")
        return

    print("\n>>> 1. Processing data using MovieLensProcessor...")
    processor = MovieLensProcessor(data_path)
    train_df, valid_df, test_df = processor.process()

    if train_df is None:
        return

    num_users = len(processor.user_mapping)
    num_movies = len(processor.movie_mapping)
    
    print("\n>>> 2. Building PyTorch Dataset...")
    train_dataset = MovieLensDataset(
        train_df,
        processor.user_interacted_movies,
        processor.all_movies_list,
        num_negatives=4,
        is_training=True
    )

    use_cuda = device.type == "cuda"
    batch_size = 4096
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=use_cuda,
    )

    latent_dim = 64
    print(f"\n>>> 3. Initializing Standard NeuMFNoConcat Model (Latent Dim = {latent_dim})...")
    model = NeuMFNoConcat(num_users=num_users, num_movies=num_movies, latent_dim=latent_dim)
    model.to(device)

    print("\n>>> 4. Configuring Optimizer...")
    # 同样借用 get_optimizer (NeuMFNoConcat 里的名字也是 mlp 和 mf 命名的)
    optimizer = get_optimizer(model, lr=1e-3, weight_decay=1e-4)
    criterion = nn.BCELoss()

    epochs = 1
    print(f"\n>>> 5. Starting Training (No Concat Model) for {epochs} Epochs...")

    os.makedirs('../model', exist_ok=True)

    for epoch in range(1, epochs + 1):
        print(f"\n--- Epoch {epoch}/{epochs} ---")
        epoch_start = time.time()
        # 注意: 这里的 train_one_epoch 不传入 genres_matrix，这是对照组
        avg_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        epoch_time = time.time() - epoch_start
        print(f"    - Epoch {epoch} completed | Avg Loss: {avg_loss:.4f} | Time: {epoch_time:.1f}s")

    save_path = '../model/model_noconcat.pth'
    torch.save(model.state_dict(), save_path)
    print(f"\n>>> 6. Model saved to {os.path.abspath(save_path)}")

if __name__ == '__main__':
    main()
