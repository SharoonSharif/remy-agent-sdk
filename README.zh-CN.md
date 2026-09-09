# Remy Agent SDK 接入示例

这里是 Remy Agent SDK 的公开接入入口，包含 Python 和 TypeScript 的独立示例。
SDK 实现与 Core 运行时通过独立发行包提供；示例只使用公开 API。

**当前为预览阶段**：公开此仓库不代表 SDK 包和 Core 二进制已开放下载。
如暂时无法从包仓库安装，请向维护者获取 wheel／tarball 和配对的 Core 二进制。
无需访问实现仓库即可运行示例。

- [Python 安装与运行](python/README.md)
- [TypeScript 安装与运行](typescript/README.md)

两种语言都提供 hello、流式输出、自定义工具三个对应场景。
示例默认不启用产品 preset 或内置工具；工具示例仅批准自己的加法函数。

示例直接使用生产 API：`https://api.corepass.com/edge/v1`。
运行真实模型只需配置 `DEMO_MODEL` 和 `DEMO_TOKEN`。
预览阶段还需通过 `REMY_CORE` 指定兼容的冻结 Core 可执行文件。
`.env.example` 只提供占位符，程序不会自动读取它，也不要提交真实凭据。

当前示例分别针对 Python SDK 0.0.1、TypeScript SDK 0.1.0。
这不是 Core 版本配对声明。CI 目前仅做语法检查；具体安装和验证范围见英文首页。

两种语言环境安装后，可在仓库根目录运行离线模型联调：

```bash
REMY_CORE=/absolute/path/to/core/executable python3 scripts/smoke.py
```

它会运行六个示例，使用真实 Core 和本地模拟模型网关；不需要真实 token，
不调用外部模型。预期输出六行 PASS。
