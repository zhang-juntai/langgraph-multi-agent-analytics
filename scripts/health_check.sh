#!/bin/bash
# ============================================
# 多 Agent 数据分析平台 - 健康检查脚本
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
API_URL="${API_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

# 检查函数
check_service() {
    local name="$1"
    local url="$2"
    local timeout="${3:-5}"

    echo -n "Checking $name... "

    if curl -sf --max-time "$timeout" "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

check_docker() {
    local service="$1"
    echo -n "Checking Docker container $service... "

    if docker ps --format '{{.Names}}' | grep -q "$service"; then
        local status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "unknown")
        if [ "$status" = "healthy" ] || [ "$status" = "unknown" ]; then
            echo -e "${GREEN}✓ Running (${status})${NC}"
            return 0
        else
            echo -e "${YELLOW}! Status: ${status}${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Not running${NC}"
        return 1
    fi
}

# 主检查函数
main() {
    echo "========================================"
    echo "   Multi-Agent Platform Health Check"
    echo "========================================"
    echo ""

    # 检查 Docker 服务
    echo "=== Docker Services ==="
    check_docker "multiagent-postgres" || true
    check_docker "multiagent-backend" || true
    check_docker "multiagent-frontend" || true
    check_docker "multiagent-nginx" || true
    echo ""

    # 检查 HTTP 服务
    echo "=== HTTP Endpoints ==="
    check_service "Backend Health" "$API_URL/health" || true
    check_service "Backend API" "$API_URL/docs" 10 || true
    check_service "Frontend" "$FRONTEND_URL" 10 || true
    echo ""

    # 详细健康检查
    echo "=== Detailed Backend Status ==="
    if curl -sf --max-time 5 "$API_URL/health/detailed" 2>/dev/null; then
        echo ""
    else
        echo -e "${YELLOW}Detailed health check unavailable${NC}"
    fi

    echo ""
    echo "========================================"
    echo "   Health check completed"
    echo "========================================"
}

# 运行
main "$@"
