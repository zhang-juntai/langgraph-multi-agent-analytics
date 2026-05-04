# UI 设计规范 - 液态玻璃风格

## 设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 视觉风格 | 液态玻璃 (Liquid Glass) | 2026年最前沿趋势 |
| 布局结构 | 双栏 + 浮动抽屉 | 左侧可折叠，右侧浮动 |
| Agent可视化 | 状态卡片组 | 横向排列，活跃发光 |
| 主色调 | 紫蓝渐变 (AI Tech) | 科技感强 |
| 侧边栏交互 | 点击展开/收缩 | (v2更新) 不再使用悬停 |
| 对话标题 | 自动生成 + 可重命名 | (v2更新) 从首条消息提取 |
| 产物存储 | 多产物列表 | (v2更新) 支持多个代码块/图表 |

## 视觉规范

### 颜色系统

```css
/* 主渐变背景 */
--gradient-primary: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(168,85,247,0.15));

/* 玻璃效果 */
--glass-bg: rgba(255, 255, 255, 0.5);
--glass-blur: backdrop-filter: blur(12px);
--glass-border: 1px solid rgba(255, 255, 255, 0.4);

/* Agent状态色 */
--agent-active: linear-gradient(135deg, #8b5cf6, #6366f1);
--agent-idle: #6b7280;
--agent-glow: box-shadow: 0 0 8px #a78bfa;

/* 文字色 */
--text-primary: #e0e7ff;
--text-secondary: #9ca3af;
--text-muted: #6b7280;
```

### 玻璃卡片样式

```css
.glass-card {
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 12px;
}
```

## 布局规范

### 整体结构

```
┌─────────────────────────────────────────────────────────┐
│ ┌──┐  Agent状态卡片组                                    │
│ │图│  [Coordinator●] [Profiler○] [Code Gen○]            │
│ │标│                                                     │
│ │区│  聊天消息区                           ┌──────────┐  │
│ │  │                                      │ 浮动抽屉 │  │
│ │可│  用户: 分析数据...                    │ 代码/图表 │  │
│ │折│                                      │   报告   │  │
│ │叠│  AI: 我已完成分析...                  └──────────┘  │
│ └──┘                                                     │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 输入框                                    [发送]    │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 左侧边栏 (可折叠) - v2 更新

- **折叠状态**: 64px宽，显示图标按钮
- **展开状态**: 256px宽，显示会话列表
- **交互**: 点击展开/收缩按钮切换 (不再使用悬停)
- **新建对话**: 点击 `+` 按钮创建新会话
- **对话标题**:
  - 自动生成: 从第一条用户消息提取前20字符
  - 重命名: 双击会话项或点击编辑图标
- **搜索**: 展开状态下可搜索会话

### 浮动抽屉 (右侧) - v2 更新

- **默认位置**: 右上角
- **尺寸**: 400px宽 x 520px高 (展开状态)
- **功能**:
  - **代码 Tab**: 多个代码块历史，支持滚动预览，单独/批量下载
  - **图表 Tab**: 多个图表画廊，点击下载，悬停预览
  - **报告 Tab**: Markdown渲染，支持多份报告历史
- **交互**: 可拖拽位置，可展开/收起
- **产物持久化**: 所有代码/图表保存在会话中，页面刷新后保留

## Agent状态卡片

### 样式

```css
.agent-card {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(8px);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.agent-card.active {
  background: rgba(139, 92, 246, 0.3);
  border-color: rgba(139, 92, 246, 0.4);
}

.agent-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.agent-indicator.active {
  background: #a78bfa;
  box-shadow: 0 0 8px #a78bfa;
  animation: pulse 2s infinite;
}
```

### Agent颜色映射

| Agent | 颜色 | 图标 |
|-------|------|------|
| coordinator | 紫色 #8b5cf6 | 🎯 |
| data_parser | 蓝色 #3b82f6 | 📄 |
| data_profiler | 青色 #06b6d4 | 🔍 |
| code_generator | 琥珀色 #f59e0b | 💻 |
| debugger | 橙色 #f97316 | 🔧 |
| visualizer | 粉色 #ec4899 | 📊 |
| report_writer | 靛蓝 #6366f1 | 📝 |

## 动画规范

### 过渡

```css
--transition-fast: 150ms ease;
--transition-normal: 250ms ease;
--transition-slow: 400ms ease;
```

### 脉冲动画

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
```

## 文件修改清单

### v1 初始实现
1. `frontend/src/app/globals.css` - 添加玻璃效果CSS变量和动画
2. `frontend/src/app/page.tsx` - 更新主布局结构
3. `frontend/src/components/sidebar/Sidebar.tsx` - 改为可折叠设计 (已删除)
4. `frontend/src/components/panel/RightPanel.tsx` - 改为浮动抽屉 (已删除)
5. `frontend/src/components/chat/ChatInterface.tsx` - 添加Agent状态卡片组
6. `frontend/src/components/chat/ExecutionPanel.tsx` - 移除或整合到状态卡片 (已删除)

### v2 交互改进 (2026-04-05)
1. `frontend/src/components/sidebar/CollapsibleSidebar.tsx` - 点击展开/收缩 + 会话重命名
2. `frontend/src/components/panel/FloatingDrawer.tsx` - 多代码块/图表列表 + 滚动修复
3. `frontend/src/lib/store.ts` - 添加 `CodeArtifact`, `FigureArtifact` 类型 + 多产物存储
4. `frontend/src/lib/api.ts` - 添加 `updateSessionName` API
5. `frontend/src/hooks/useChat.ts` - 自动生成对话标题

## Store 数据结构 (v2)

```typescript
interface Session {
  id: string
  name: string
  messages: Message[]
  datasets: DatasetMeta[]
  codeArtifacts: CodeArtifact[]   // 新: 多个代码产物
  figures: FigureArtifact[]       // 新: 多个图表
  reports: string[]               // 新: 多个报告
  createdAt: string
  updatedAt: string
}

interface CodeArtifact {
  id: string
  name: string
  code: string
  timestamp: number
}

interface FigureArtifact {
  id: string
  path: string
  name: string
  timestamp: number
}
```
