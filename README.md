# 🔮 Tarot-it

**在聊天里，给自己抽一张塔罗牌。**

**Draw a tarot card for yourself, right in your chat.**

[简体中文](#简体中文) · [English](#english)

![78 张牌面 / 78 illustrated cards](https://img.shields.io/badge/%F0%9F%83%8F_The_Deck-78_cards-7451A1?style=flat-square)
![8 套牌阵 / 8 spreads](https://img.shields.io/badge/%E2%9C%A8_The_Table-8_spreads-B36A38?style=flat-square)
![默想即可 / Keep your question to yourself](https://img.shields.io/badge/%F0%9F%8C%99_Your_Question-keep_it_to_yourself-293D68?style=flat-square)

<p>
  <img src="tarot-it/assets/deck/upright/major-00.jpg" width="96" alt="愚者 / The Fool">
  <img src="tarot-it/assets/deck/upright/major-17.jpg" width="96" alt="星星 / The Star">
  <img src="tarot-it/assets/deck/upright/major-19.jpg" width="96" alt="太阳 / The Sun">
</p>

## 简体中文

### 1. 请助手帮你装

把这句话复制给你正在用的 Codex、Claude Code、OpenClaw 或 Hermes Agent。

```text
请从 https://github.com/EricArcha/Tarot-it 帮我安装完整的 Tarot-it 技能（包括牌图），并确认你能找到它。
```

### 2. 抽一张试试

等助手说装好了，像平时聊天一样发一句。

```text
抽一张。
```

助手会从整副韦特塔罗里抽一张，直接给你看牌图、牌名和正逆位。想听解读，再说「解读」。

想亲自切牌、选号，就说「陪我慢慢抽一轮」。你也可以带着一件具体的事来，比如「我想占卜一下，最近怎么融入新团队」。助手会带你一步步选好牌，等你说「翻开」。

[手动安装与各助手说明](tarot-it/references/hosts.md#安装与牌图交付)

## English

### 1. Ask your assistant to install it

Paste this into Codex, Claude Code, OpenClaw, or Hermes Agent.

```text
Please install the complete Tarot-it skill from https://github.com/EricArcha/Tarot-it, including the card images, and make sure you can find it.
```

### 2. Try your first draw

Once your assistant says it's ready, send an ordinary chat message.

```text
Draw one tarot card.
```

Your assistant draws from the full Rider–Waite–Smith deck and shows the card, its name, and whether it's upright or reversed. To hear a reading, ask what the card means. Readings are primarily in Simplified Chinese.

To cut the deck and pick a card yourself, say “Let’s take our time with this draw.” You can also bring a specific question, such as “I'd like a tarot reading about finding my feet on a new team.” Your assistant guides you through the steps and waits for you to say “Turn it over.”

[Manual setup and notes for each assistant](tarot-it/references/hosts.md#安装与牌图交付)

<details>
<summary>终端一行安装 · One-line terminal install</summary>

如果电脑上有 Node.js，可在你要使用的项目目录运行这一行，把 Tarot-it 装进四个助手各自的项目技能目录。

If you have Node.js, run this in your project folder to install Tarot-it for all four assistants in that project.

```sh
npx skills add https://github.com/EricArcha/Tarot-it --skill tarot-it -a codex -a claude-code -a openclaw -a hermes-agent --copy -y
```

</details>

## 牌面与署名 · Artwork and credits

Pamela Colman Smith 绘制了这副牌的插画。The card artwork is by Pamela Colman Smith. [牌图与牌义来源 · Artwork and reading sources](tarot-it/references/credits.md)

代码和原创牌义采用 MIT 许可。牌图保留各自的公版标记。Code and original card notes are MIT-licensed. The card artwork retains its public-domain markings. [MIT License](LICENSE)
