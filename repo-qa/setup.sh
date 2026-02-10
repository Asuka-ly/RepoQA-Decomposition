#!/bin/bash
# RepoQA 环境配置脚本

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🔧 RepoQA Environment Setup"
echo "=========================================="
echo

# 1. 检测项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "📂 Project Root: $PROJECT_ROOT"
echo

# 2. 检查 Conda 环境
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "⚠️  Warning: Not in a Conda environment"
    echo "   Please run: conda activate swe-agent"
    echo
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ Conda environment: $CONDA_DEFAULT_ENV"
fi
echo

# 3. 安装 Python 依赖
echo "📦 Installing Python dependencies..."
cd "$PROJECT_ROOT/repo-qa"

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --break-system-packages
    echo "✓ Dependencies installed"
else
    echo "⚠️  requirements.txt not found, installing minimal dependencies..."
    pip install mini-swe-agent==1.17.5 \
                tree-sitter==0.25.2 \
                tree-sitter-python==0.25.0 \
                networkx==3.4.2 \
                litellm==1.81.5 \
                python-dotenv \
                pyyaml \
                --break-system-packages
fi
echo

# 4. 创建必要的目录
echo "📁 Creating directories..."
mkdir -p data/questions
mkdir -p data/trajectories
mkdir -p data/results
mkdir -p configs
mkdir -p tests
echo "✓ Directories created"
echo

# 5. 检查 .env 文件
echo "🔑 Checking .env configuration..."
cd "$PROJECT_ROOT"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "⚠️  .env not found, copying from .env.example..."
        cp .env.example .env
        echo
        echo "⚠️  IMPORTANT: Please edit .env and set your OPENAI_API_KEY"
        echo "   File location: /root/RepoQA-Project/.env"
        echo
    else
        echo "❌ Neither .env nor .env.example found!"
        echo "   Please create .env manually with:"
        echo "   OPENAI_API_KEY=your-key-here"
        echo
        exit 1
    fi
else
    echo "✓ .env file exists"
fi
echo

# 6. 验证配置
echo "🔍 Validating configuration..."
cd "$PROJECT_ROOT/repo-qa"
python scripts/check_config.py

echo
echo "=========================================="
echo "✅ Setup complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "  1. Edit $PROJECT_ROOT/.env to set your API key"
echo "  2. Run: python scripts/check_config.py"
echo "  3. Run: python scripts/run_single.py"
echo
