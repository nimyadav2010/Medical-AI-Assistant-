import os
import requests
from pathlib import Path

# Configuration
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
LOCAL_DIR = "./local_embeddings_model"
FILES_TO_DOWNLOAD = [
    "config.json",
    "data_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "special_tokens_map.json",
    "modules.json",
    "sentence_bert_config.json",
    "1_Pooling/config.json"
]

BASE_URL = f"https://huggingface.co/{MODEL_ID}/resolve/main"

def download_file(filename):
    url = f"{BASE_URL}/{filename}"
    local_path = Path(LOCAL_DIR) / filename
    
    print(f"Downloading {filename}...")
    
    try:
        # verify=False disables SSL checking
        response = requests.get(url, verify=False, timeout=30)
        response.raise_for_status()
        
        # Ensure directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(local_path, "wb") as f:
            f.write(response.content)
        print(f"✓ Saved to {local_path}")
        return True
    except Exception as e:
        print(f"✗ Failed to download {filename}: {e}")
        return False

def main():
    print(f"Starting manual download of {MODEL_ID} to {LOCAL_DIR}")
    print("SSL Verification is DISABLED.")
    
    # Create directory
    Path(LOCAL_DIR).mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    for file in FILES_TO_DOWNLOAD:
        if download_file(file):
            success_count += 1
            
    print(f"\nDownload complete. {success_count}/{len(FILES_TO_DOWNLOAD)} files downloaded.")
    
    if success_count == len(FILES_TO_DOWNLOAD):
        print("You can now use this local path for embeddings.")
    else:
        print("Some files failed to download. The model may not work.")

if __name__ == "__main__":
    # Suppress InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
