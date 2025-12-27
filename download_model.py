import os
os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'
os.environ['CURL_CA_BUNDLE'] = ''

import warnings
warnings.filterwarnings("ignore")

from huggingface_hub import snapshot_download

print("Downloading model with SSL verification disabled...")
try:
    model_path = snapshot_download(repo_id="sentence-transformers/all-MiniLM-L6-v2", 
                                 allow_patterns=["*.json", "*.txt", "*.model", "*.bin", "*.safetensors", "*.onnx", "*.h5"],
                                 local_dir="./local_embeddings_model",
                                 local_dir_use_symlinks=False)
    print(f"Model downloaded to: {model_path}")
except Exception as e:
    print(f"Download failed: {e}")
