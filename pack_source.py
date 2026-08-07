import zipfile
import os

def create_source_zip():
    # Defne blacklist
    ignore_dirs = {
        'models', 'dist', 'build', '__pycache__', '.git', '.vscode', '.agent', 
        'env', 'venv', '.idea', 'LiveSubtitle_SourceCode.zip'
    }
    ignore_extensions = {'.pyc', '.pyd', '.spec', '.log'}
    
    zip_filename = "LiveSubtitle_SourceCode.zip"
    print(f"📦 Creating source code archive: {zip_filename} ...")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through directory
        for root, dirs, files in os.walk("."):
            # Filtering directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check extension
                _, ext = os.path.splitext(file)
                if ext in ignore_extensions:
                    continue
                
                # Check specific files
                if file == zip_filename:
                    continue
                
                # Add to zip
                print(f"  + Adding: {file_path}")
                zipf.write(file_path, arcname=os.path.relpath(file_path, "."))
                
    print(f"\n✅ Archive created successfully at:\n{os.path.abspath(zip_filename)}")
    print("Now you can upload this ZIP file to GitHub (via 'Upload files' button) or email it.")

if __name__ == "__main__":
    create_source_zip()
