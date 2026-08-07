import requests
import os

# Target: models/medium
model_dir = os.path.join("models", "medium")
os.makedirs(model_dir, exist_ok=True)

files = [
    ("config.json", 260),
    ("model.bin", 1528036406),  # ~1.5GB
    ("tokenizer.json", 2203239),
    ("vocabulary.txt", 459861)
]

base_url = "https://hf-mirror.com/Systran/faster-whisper-medium/resolve/main"

for file, expected_size in files:
    url = f"{base_url}/{file}"
    dest_path = os.path.join(model_dir, file)
    
    if os.path.exists(dest_path) and os.path.getsize(dest_path) == expected_size:
        print(f"Skipping {file} (already complete)")
        continue
    
    print(f"Downloading {file} ({expected_size/1024/1024:.1f} MB)...")
    try:
        response = requests.get(url, timeout=600, stream=True)
        response.raise_for_status()
        
        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                f.write(chunk)
                downloaded += len(chunk)
                print(f"\r  Progress: {downloaded/1024/1024:.1f} MB", end="", flush=True)
        print(f"\n  ✓ {file} complete")
    except Exception as e:
        print(f"\n  Error: {e}")

print(f"\nModel saved to {os.path.abspath(model_dir)}")
