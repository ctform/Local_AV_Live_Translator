import os
import subprocess
import shutil
import sys

def build_executable():
    print("🚀 开始构建 Live Subtitle Translator...")
    
    # 1. 检查 PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. 定义打包参数
    # --onedir:以此生成目录结构 (推荐，启动快，方便改配置)
    # --windowed: 运行时不显示黑框控制台
    # --name: 程序名称
    # --add-data: 添加非代码资源 (ui, core 等)
    # --collect-all: 强制收集 faster_whisper 和 ctranslate2 的所有隐式依赖
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "LiveSubtitleTranslator",
        "--clean",
        # 包含源代码目录 (PyInstaller 有时分析不全)
        "--add-data", "core;core",
        "--add-data", "ui;ui",
        # 强制收集关键库的依赖
        "--collect-all", "faster_whisper",
        "--collect-all", "ctranslate2",
        "--collect-all", "pyaudiowpatch",
        "main.py"
    ]
    
    print(f"📦 执行打包命令: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    print("\n✅ 代码打包完成！")
    
    # 3. 后处理：处理 models 文件夹
    # 我们不把模型打进 exe，而是确保 dist 目录里有一个空的 models 文件夹结构
    dist_dir = os.path.join("dist", "LiveSubtitleTranslator")
    models_dir = os.path.join(dist_dir, "models")
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        print("📂 创建 models 目录 (不包含模型文件，减小体积)")
    
    # 可选：复制当前的 medium 模型过去？
    # 通常发布版不带模型，让用户自己下载，或者提供单独的下载包。
    # 这里我们只复制目录结构。
    
    print("\n🎉 构建成功！")
    print(f"程序位置: {os.path.abspath(dist_dir)}")
    print("注意：发布时，请确保目标机器已安装 Ollama，并将您的 'models' 文件夹内容复制到程序目录中，或者让程序首次运行自动下载。")

if __name__ == "__main__":
    build_executable()
