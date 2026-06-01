# 脚本规则

这里的脚本文件是给 `RocoKingdom-Clicker-Release` 使用的动作序列配置。脚本不通过菜单创建，而是直接编辑当前目录下的 JSON 文件。

## 放在哪里

脚本统一放在同一个目录：

- `data/action_scripts/script_1.json`
- `data/action_scripts/script_2.json`
- 你自己新增的其他 `.json` 文件

程序会读取这个目录下的所有 `.json` 文件，并在脚本菜单中列出。

## 文件结构

每个脚本文件至少包含两个字段：

- `name`：脚本名称
- `actions`：动作数组

示例：

```json
{
  "name": "script_1",
  "actions": []
}
```

## 支持的动作类型

### 1. click

移动到指定坐标后点击一次。

字段：

- `type`: `click`
- `x`: 屏幕 X 坐标
- `y`: 屏幕 Y 坐标
- `hold_ms`: 按住时长，单位毫秒，可选，默认 `100`

示例：

```json
{"type": "click", "x": 900, "y": 500, "hold_ms": 80}
```

### 2. move

移动到指定坐标，不点击。

字段：

- `type`: `move`
- `x`: 屏幕 X 坐标
- `y`: 屏幕 Y 坐标
- `duration_ms`: 移动耗时，单位毫秒，可选，默认 `100`

示例：

```json
{"type": "move", "x": 900, "y": 500, "duration_ms": 120}
```

### 3. key

按下并释放一个虚拟键码。

字段：

- `type`: `key`
- `vk_code`: 虚拟键码
- `hold_ms`: 按住时长，单位毫秒，可选，默认 `50`

示例：

```json
{"type": "key", "vk_code": 32, "hold_ms": 50}
```

### 3.1 combo

组合按键动作，适合 WASD 转圈、斜向移动、短促组合输入。

字段：

- `type`: `combo`
- `vk_codes`: 虚拟键码数组，例如 `[87, 68]`
- `hold_ms`: 组合按住时长，单位毫秒，可选，默认 `50`
- `hold_jitter_ms`: 组合按住时长的随机扰动，可选，默认 `0`

示例：

```json
{"type": "combo", "vk_codes": [87, 68], "hold_ms": 220, "hold_jitter_ms": 35}
```

### 4. wait

等待指定时间。

字段：

- `type`: `wait`
- `duration_ms`: 等待时长，单位毫秒
- `duration_jitter_ms`: 等待时长的随机扰动，可选，默认 `0`

示例：

```json
{"type": "wait", "duration_ms": 300}
```

### 5. loop

循环执行一组动作。

字段：

- `type`: `loop`
- `count`: 循环次数
- `forever`: 是否一直循环，可选
- `actions`: loop 内部的动作数组
- `pause_ms`: 每轮 loop 结束后的额外停顿，可选，默认 `0`
- `pause_jitter_ms`: 每轮 loop 停顿的随机扰动，可选，默认 `0`

规则：

- `count > 0` 表示循环指定次数
- `count = 0` 或 `forever = true` 表示一直循环，直到你按 `F4`
- `loop` 里面可以继续嵌套 `click`、`move`、`key`、`wait`、`loop`

示例：

```json
{
  "type": "loop",
  "count": 0,
  "actions": [
    {"type": "move", "x": 900, "y": 500, "duration_ms": 120},
    {"type": "click", "x": 900, "y": 500, "hold_ms": 80},
    {"type": "wait", "duration_ms": 300}
  ]
}
```

### 6. timed

`timed` 用于创建一个“执行窗口 + 休眠” 的周期性包装器。它会在每个执行窗口内循环运行被包装的 `actions`，直到执行窗口到期；然后进入休眠窗口，之后根据 `repeat` 或 `forever` 决定是否再次进入执行窗口。

字段：

- `type`: `timed`
- `execute_ms`: 执行窗口时长（毫秒）
- `sleep_ms`: 执行窗口之间的休眠时长（毫秒）
- `repeat`: 重复次数（可选，默认 `1`）
- `forever`: 是否一直重复（可选，默认 `false`）
- `actions`: 在执行窗口内重复运行的动作数组

行为要点：

- 在 `execute_ms` 窗口内，会反复执行内部 `actions`（每次完整执行一轮）。
- 当脚本被 `F2` 暂停时，执行窗口的计时会同时暂停（即恢复后继续剩余时间）。
- 如果内部动作某次执行超出窗口，会自然结束该次执行，然后检测是否到期。

示例：

```json
{
  "type": "timed",
  "execute_ms": 300000,
  "sleep_ms": 300000,
  "repeat": 0,
  "forever": true,
  "actions": [
    { "type": "click", "x": 900, "y": 500, "hold_ms": 80 },
    { "type": "wait", "duration_ms": 100 }
  ]
}
```

## 脚本会话热键

选择脚本后会进入脚本会话模式：

- `F1`：继续执行，继续前会再次等待 3 秒
- `F2`：暂停脚本

退出脚本请使用界面上的停止按钮或通过脚本内部条件结束（例如 `timed`）。

## 类人化选项

为了更像真人操作，脚本支持这些随机扰动字段：

- `x_jitter_px` / `y_jitter_px`：坐标抖动，适合 `click` 和 `move`
- `hold_jitter_ms`：按住时长抖动，适合 `click`、`key`、`combo`
- `duration_jitter_ms`：持续时间抖动，适合 `move` 和 `wait`
- `pause_jitter_ms`：循环间隔抖动，适合 `loop`

这些字段都可以单独使用，也可以一起叠加。

## 推荐写法

如果你想把连点器本身写成一个常驻脚本，可以直接把整套连点流程放进 `loop`，并设置：

- `count = 0`
- 或 `forever = true`

这样脚本会一直循环，直到用户停止脚本（通过 GUI 停止）或脚本自身条件结束（例如 `timed`）。

如果是 WASD 转圈移动，推荐使用 `combo` 组合按键，再配合 `hold_jitter_ms` 和 `pause_jitter_ms`。

## 命名约定

建议使用这种命名方式：

- `script_1.json`
- `script_2.json`
- `farm_loop.json`
- `battle_cycle.json`

程序只要能读到 `.json` 文件，就会把它列入脚本列表。

## 注意事项

- 坐标使用的是屏幕像素坐标
- `click` 和 `move` 最终都会被转换成 Interception 绝对坐标
- JSON 语法必须正确，少一个逗号都会导致加载失败
- 建议每次修改后先保存，再回到程序里重新打开脚本列表
