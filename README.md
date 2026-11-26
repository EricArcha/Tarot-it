# Tarot-it

Tarot-it 是一份本地塔罗 Skill。你可以默想一个问题，选一套牌阵和抽法，看到真实韦特牌面，然后再决定要不要听解读。

## 安装与试用

从候选 ZIP 解压完整 `tarot-it` 目录，或直接复制本仓库里的同名目录。按 [宿主安装说明](tarot-it/references/hosts.md) 放到对应 Agent 的位置。需要 Python 3.10+。Pillow 可选，用于多牌阵的 PNG 全景。Python 基础运行、附带的牌图、牌义和离线牌桌都可在断网环境使用。

装好后可以说「用 Tarot-it 直接抽一张，只翻牌」，或「想做一次三张塔罗，我自己选号」。在 Codex 可用 `$tarot-it`，Claude Code 可用 `/tarot-it`。普通终端中，用浏览器打开回复给出的离线牌桌。桌面或 Gateway 聊天可显示什么，见实际宿主的 [验收记录](docs/验收记录.md)。

卸载时，移除本次复制的 Skill 目录。需要同时清理本机暂存时，先确认所用工作区的 `.tarot-it` 仅存放 Tarot-it 状态，再按需删除。你另外保存的牌桌由你自行管理。

## 开发与验收

```sh
python3 -m unittest discover -s tests -v
python3 tools/package_skill.py
```

实现范围见 [开发计划](docs/开发计划.md) 和 [实施规格](docs/SPEC.md)。牌图来源与权利信息见 [署名](tarot-it/references/credits.md)。当前 ZIP 供本地验收。对外发布前需按验收记录补齐证据和项目许可。
