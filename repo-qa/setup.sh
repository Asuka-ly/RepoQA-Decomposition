#!/bin/bash
# 简单环境配置脚本

set -e

echo "🚀 Setting up repo-qa environment..."

# 1. 激活 conda 环境
echo "📦 Activating conda environment..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate swe-agent

# 2. 进入项目目录
cd /root/repo-qa

# 3. 创建 .env 模板（如果不存在）
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cat > .env << 'EOF'
# ==============================================
# API Configuration
# ==============================================
# Fill in your values below, then run: bash setup.sh

OPENAI_API_KEY="sk-jMwotJusiO6yFwPRcclkoy5t3MefqzgssdUhpdnPUs7ABfVH"
OPENAI_API_BASE="https://api.qingyuntop.top/v1"
DEFAULT_MODEL=gpt-5.1-mini

# ==============================================
# Examples for different providers:
# ==============================================

# OpenAI:
# OPENAI_API_KEY=sk-xxxxx
# OPENAI_API_BASE=https://api.openai.com/v1
# DEFAULT_MODEL=gpt-4o-mini

# DeepSeek:
# OPENAI_API_KEY=sk-xxxxx
# OPENAI_API_BASE=https://api.deepseek.com/v1
# DEFAULT_MODEL=deepseek-chat

# Custom:
# OPENAI_API_KEY=your-key
# OPENAI_API_BASE=https://your-url.com/v1
# DEFAULT_MODEL=your-model
EOF
    echo ""
    echo "⚠️  .env file created!"
    echo "   Please edit .env and add your API credentials, then run 'bash setup.sh' again"
    exit 0
fi

# 4. 检查配置
source .env
if [ "$OPENAI_API_KEY" = "your-api-key-here" ]; then
    echo "❌ Error: Please edit .env and fill in your OPENAI_API_KEY"
    exit 1
fi

echo "✓ API configured: ${OPENAI_API_BASE}"

# 5. 安装依赖
echo "📦 Installing dependencies..."
pip install -r requirements.txt --break-system-packages -q

# 6. 验证
echo "🔍 Verifying environment..."
python -c "import minisweagent; print('✓ mini-swe-agent')"
python -c "from tree_sitter import Language; print('✓ tree-sitter')"
python -c "import networkx; print('✓ networkx')"
python -c "import yaml; print('✓ pyyaml')"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Quick start:"
echo "  python scripts/run_single.py"
