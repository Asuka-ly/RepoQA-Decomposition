#!/bin/bash

#==========================================
# RepoQA-Decomposition 终端初始化脚本
#==========================================

# ========== 在这里填写您的配置 ==========
API_KEY="sk-xxxxxxxxxxxxx"
API_BASE="https://your-url.com/v1"
# ======================================

echo "🚀 开始初始化终端..."
echo ""

# 1. 激活 conda 环境
echo "📦 激活 conda 环境..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate swe-agent
echo "   ✓ 环境已激活: swe-agent"
echo ""

# 2. 进入项目目录
echo "📂 进入项目目录..."
cd /root/RepoQA-Decomposition
echo "   ✓ 当前目录: $(pwd)"
echo ""

# 3. 安装关键依赖
echo "📦 安装关键依赖..."
pip install python-dotenv --break-system-packages -q
echo "   ✓ python-dotenv 已安装"
echo ""

# 4. 验证环境
echo "🔍 验证环境..."
python -c "import minisweagent; print('   ✓ mini-swe-agent OK')"
python -c "from tree_sitter import Language, Parser; print('   ✓ tree-sitter OK')"
echo ""

# 5. 创建配置文件
echo "📝 创建配置文件..."
mkdir -p ~/.config/mini-swe-agent
cat > ~/.config/mini-swe-agent/.env << ENVEOF
OPENAI_API_KEY=$API_KEY
OPENAI_API_BASE=$API_BASE
ENVEOF
echo "   ✓ 配置文件已创建: ~/.config/mini-swe-agent/.env"
echo ""

# 6. 显示最终状态
echo "=========================================="
echo "✅ 初始化完成！"
echo "=========================================="
echo ""
echo "配置信息："
echo "  API_BASE: $API_BASE"
echo "  API_KEY: ${API_KEY:0:20}..."
echo ""
echo "项目目录: $(pwd)"
echo ""
echo "可用命令："
echo "  python test_strategic.py          # 测试代码图（不消耗 API）"
echo "  python run_strategic_stage1.py    # 完整测试（消耗 API）"
echo ""

# 7. 保持在激活状态
exec bash
