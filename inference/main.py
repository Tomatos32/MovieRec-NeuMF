import torch
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
import os
import sys

# 本地环境变量与路径兼容
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from model.neumf import NeuMF
except ImportError:
    pass  # 实际集成部署时处理包路径问题

app = FastAPI(
    title="MovieRec NeuMF Sidecar Inference",
    description="基于 PyTorch 神经矩阵分解模型的极低延迟推理边车",
    version="1.0.0"
)

class PredictRequest(BaseModel):
    user_id: int
    candidate_movie_ids: List[int]
    top_k: int = 10

# 全局变量挂载模型实例与设备状态
model = None
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

@app.on_event("startup")
async def startup_event():
    global model
    print("[Sidecar] Loading NeuMF model weights into eval mode...")
    
    model_path = os.getenv("MODEL_PATH", "../model/model.pth")
    num_users = int(os.getenv("NUM_USERS", 200948))
    num_movies = int(os.getenv("NUM_MOVIES", 84432))
    
    if os.path.exists(model_path):
        # 动态自适应探测：读取权重中的真正 Embedding 大小
        state_dict = torch.load(model_path, map_location=device)
        
        # 探测 GMF 或 MLP 中的用户/电影 embedding 维度
        if 'embedding_user_mlp.weight' in state_dict:
            real_num_users = state_dict['embedding_user_mlp.weight'].shape[0]
            real_num_movies = state_dict['embedding_movie_mlp.weight'].shape[0]
            print(f"[Sidecar] Detected dimensions from weights: {real_num_users} users, {real_num_movies} movies.")
            num_users = real_num_users
            num_movies = real_num_movies
            
        model = NeuMF(num_users=num_users, num_movies=num_movies)
        model.load_state_dict(state_dict)
        print(f"[Sidecar] Model loaded successfully from {model_path}.")
    else:
        print("[Sidecar] Warning: model.pth not found. Using randomly initialized weights for debugging.")
        model = NeuMF(num_users=num_users, num_movies=num_movies)
        
    model.to(device)
    model.eval()

@app.post("/api/predict")
async def predict(request: PredictRequest) -> Dict:
    global model
    
    user_id = request.user_id
    candidate_ids = request.candidate_movie_ids
    
    if not candidate_ids:
        return {"data": []}
        
    # ==========================================
    # 核心安全审计：索引越界保护 (防范 CUDA Error)
    # ==========================================
    num_users_limit = model.embedding_user_mlp.num_embeddings
    num_items_limit = model.embedding_movie_mlp.num_embeddings
    
    # 1. 检查用户 ID 权限范围
    if not (0 <= user_id < num_users_limit):
        print(f"[Sidecar] Warning: UserID {user_id} is out of model bounds {num_users_limit}. Skipping.")
        return {"data": [], "error": "User ID out of bounds"}
        
    # 2. 过滤电影 ID 权限范围
    valid_movie_ids = [mid for mid in candidate_ids if 0 <= mid < num_items_limit]
    
    if not valid_movie_ids:
        print(f"[Sidecar] Warning: All candidate movie IDs out of bounds. Possible ID mapping mismatch.")
        return {"data": []}

    # 构建 batch tensor
    try:
        users_tensor = torch.full((len(valid_movie_ids),), user_id, dtype=torch.long).to(device)
        movies_tensor = torch.tensor(valid_movie_ids, dtype=torch.long).to(device)
        
        # 极速非梯度推理
        with torch.no_grad():
            scores = model(users_tensor, movies_tensor)
            
        scores_list = scores.cpu().numpy().tolist()
        
        # 将结果与有效 ID 重新配对
        results = [{"movie_id": mid, "score": score} for mid, score in zip(valid_movie_ids, scores_list)]
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return {"data": results[:request.top_k]}
        
    except Exception as e:
        print(f"[Sidecar] Inference Exception: {e}")
        return {"data": [], "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    # 建议部署在与主业务相同的 Pod 或同一物理机内部 (127.0.0.1) 消除网络传输损耗
    uvicorn.run("main:app", host="127.0.0.1", port=8000, workers=1)
