import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm

class NeuMF(nn.Module):
    """
    神经矩阵分解 (Neural Matrix Factorization, NeuMF) 模型实现
    内核融合了广义矩阵分解 (GMF) 与多层感知机 (MLP) 双独立通道。
    本次更新：在 MLP 层允许拼接电影的特征元数据 (如流派 Genres)。
    """
    def __init__(self, num_users: int, num_movies: int, latent_dim: int = 64, num_genres: int = 18):
        super(NeuMF, self).__init__()
        
        self.num_genres = num_genres
        
        # ==========================================
        # 1. 广义矩阵分解 (GMF) 路径的独立 Embedding
        # ==========================================
        self.embedding_user_mf = nn.Embedding(num_embeddings=num_users, embedding_dim=latent_dim)
        self.embedding_movie_mf = nn.Embedding(num_embeddings=num_movies, embedding_dim=latent_dim)
        
        # ==========================================
        # 2. 多层感知机 (MLP) 路径的独立 Embedding
        # ==========================================
        self.embedding_user_mlp = nn.Embedding(num_embeddings=num_users, embedding_dim=latent_dim)
        self.embedding_movie_mlp = nn.Embedding(num_embeddings=num_movies, embedding_dim=latent_dim)
        
        # MLP 塔式网络: 接收拼接后的双重 Embedding 输入 + 电影元数据 (如流派 Multi-Hot)
        mlp_input_dim = latent_dim * 2 + self.num_genres
        self.mlp_layers = nn.Sequential(
            nn.Linear(mlp_input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU()
        )
        
        # ==========================================
        # 3. 神经融合层 (NeuMF Layer)
        # ==========================================
        self.fusion_layer = nn.Linear(latent_dim + 16, 1)
        self.sigmoid = nn.Sigmoid()
        
        self._init_weights()

    def _init_weights(self):
        """Embedding 权重截断正态或正态分布初始化"""
        nn.init.normal_(self.embedding_user_mf.weight, std=0.01)
        nn.init.normal_(self.embedding_movie_mf.weight, std=0.01)
        nn.init.normal_(self.embedding_user_mlp.weight, std=0.01)
        nn.init.normal_(self.embedding_movie_mlp.weight, std=0.01)

    def forward(self, user_indices: torch.Tensor, movie_indices: torch.Tensor, movie_genres: torch.Tensor = None) -> torch.Tensor:
        """
        前向传播计算逻辑
        :param user_indices: Batch 维度的用户索引 Tensor
        :param movie_indices: Batch 维度的电影索引 Tensor
        :param movie_genres: Batch 维度的流派 Multi-Hot 特征 Tensor (shape: batch_size, num_genres)
        :return: 区间 (0,1) 的点击/交互概率 Tensor
        """
        # --- GMF Path ---
        user_embedding_mf = self.embedding_user_mf(user_indices)
        movie_embedding_mf = self.embedding_movie_mf(movie_indices)
        mf_vector = torch.mul(user_embedding_mf, movie_embedding_mf) 
        
        # --- MLP Path ---
        user_embedding_mlp = self.embedding_user_mlp(user_indices)
        movie_embedding_mlp = self.embedding_movie_mlp(movie_indices)
        
        # 将用户、电影的 Embedding 以及电影流派元数据拼接 (Concatenation)
        if self.num_genres > 0 and movie_genres is not None:
            mlp_vector = torch.cat([user_embedding_mlp, movie_embedding_mlp, movie_genres.float()], dim=-1)
        elif self.num_genres > 0 and movie_genres is None:
            # 兼容模式：如果没有输入元数据则默认填充零（或者抛出异常）
            dummy_genres = torch.zeros(user_indices.size(0), self.num_genres, device=user_indices.device)
            mlp_vector = torch.cat([user_embedding_mlp, movie_embedding_mlp, dummy_genres], dim=-1)
        else:
            mlp_vector = torch.cat([user_embedding_mlp, movie_embedding_mlp], dim=-1)
            
        # 依次穿过深度塔式网络
        mlp_vector = self.mlp_layers(mlp_vector)
        
        # --- Fusion Path ---
        fusion_vector = torch.cat([mf_vector, mlp_vector], dim=-1)
        prediction = self.fusion_layer(fusion_vector)
        
        return prediction.squeeze(-1)

def get_optimizer(model: NeuMF, lr: float = 1e-3, weight_decay: float = 1e-4) -> optim.Optimizer:
    """
    创建带有特定部分 L2 正则化的 Adam 优化器。
    工程约束: 仅在 MLP 的 Embedding 和权重上应用轻量级的 L2 正则化。
    """
    mlp_params = []
    mf_params = []
    
    # 按照命名空间拆分参数组
    for name, param in model.named_parameters():
        if 'mlp' in name:
            mlp_params.append(param)
        else:
            mf_params.append(param)
            
    optimizer = optim.Adam([
        {'params': mf_params, 'weight_decay': 0.0},
        {'params': mlp_params, 'weight_decay': weight_decay}
    ], lr=lr)
    
    return optimizer


def train_one_epoch(model: nn.Module, data_loader: DataLoader, 
                    optimizer: optim.Optimizer, criterion: nn.Module, 
                    device: torch.device, global_genres_matrix: torch.Tensor = None) -> float:
    """
    控制完成模型单次 Epoch 的标准训练循环 (已引入 AMP 混合精度加速)
    :return: 批次的均摊损失 Avg Loss
    """
    model.train()
    total_loss = 0.0
    
    # 1. 初始化梯度缩放器 (AMP)
    scaler = torch.amp.GradScaler('cuda', enabled=(device.type == 'cuda'))
    
    progress = tqdm(enumerate(data_loader), total=len(data_loader), 
                    desc="  Training", unit="batch", ncols=100)
    
    if global_genres_matrix is not None:
        global_genres_matrix = global_genres_matrix.to(device)

    for batch_idx, (users, movies, labels) in progress:
        users = users.to(device, non_blocking=True)
        movies = movies.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        
        # 2. 以前向传播开启混合精度上下文
        with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
            if global_genres_matrix is not None:
                batch_genres = global_genres_matrix[movies]
                predictions = model(users, movies, batch_genres)
            else:
                predictions = model(users, movies)
            
            loss = criterion(predictions, labels)
        
        # 3. 优化解算 (使用 Scaler 支持半精度梯度)
        optimizer.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        
        total_loss += loss.item()
        
        # 实时更新进度条的 loss 显示
        if batch_idx % 50 == 0:
            progress.set_postfix(loss=f"{loss.item():.4f}")
            
    return total_loss / len(data_loader)

class NeuMFNoConcat(nn.Module):
    """
    对比模型：无向量拼接的 NeuMF
    内核去除了多层感知机 (MLP) 路径中的拼接操作 (Concatenation)，
    改为使用逐元素相乘后进入 MLP 层，用于对比验证拼接操作对非线性交叉特征的影响。
    """
    def __init__(self, num_users: int, num_movies: int, latent_dim: int = 64):
        super(NeuMFNoConcat, self).__init__()
        
        self.embedding_user_mf = nn.Embedding(num_embeddings=num_users, embedding_dim=latent_dim)
        self.embedding_movie_mf = nn.Embedding(num_embeddings=num_movies, embedding_dim=latent_dim)
        
        self.embedding_user_mlp = nn.Embedding(num_embeddings=num_users, embedding_dim=latent_dim)
        self.embedding_movie_mlp = nn.Embedding(num_embeddings=num_movies, embedding_dim=latent_dim)
        
        # 移除拼接，因此输入维度从 (latent_dim * 2) 变为 latent_dim
        self.mlp_layers = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU()
        )
        
        self.fusion_layer = nn.Linear(latent_dim + 16, 1)
        self.sigmoid = nn.Sigmoid()
        
        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.embedding_user_mf.weight, std=0.01)
        nn.init.normal_(self.embedding_movie_mf.weight, std=0.01)
        nn.init.normal_(self.embedding_user_mlp.weight, std=0.01)
        nn.init.normal_(self.embedding_movie_mlp.weight, std=0.01)

    def forward(self, user_indices: torch.Tensor, movie_indices: torch.Tensor) -> torch.Tensor:
        # --- GMF Path ---
        user_embedding_mf = self.embedding_user_mf(user_indices)
        movie_embedding_mf = self.embedding_movie_mf(movie_indices)
        mf_vector = torch.mul(user_embedding_mf, movie_embedding_mf) 
        
        # --- MLP Path ---
        user_embedding_mlp = self.embedding_user_mlp(user_indices)
        movie_embedding_mlp = self.embedding_movie_mlp(movie_indices)
        # 改动核心：使用逐元素相乘代替 tensor.cat 拼接
        mlp_vector = torch.mul(user_embedding_mlp, movie_embedding_mlp)
        mlp_vector = self.mlp_layers(mlp_vector)
        
        # --- Fusion Path ---
        fusion_vector = torch.cat([mf_vector, mlp_vector], dim=-1)
        prediction = self.fusion_layer(fusion_vector)
        return prediction.squeeze(-1)

if __name__ == '__main__':
    # 简单实例化调试
    dummy_model = NeuMF(num_users=1000, num_movies=1000)
    dummy_model_noconcat = NeuMFNoConcat(num_users=1000, num_movies=1000)
    print("PyTorch NeuMF Init Success.")
