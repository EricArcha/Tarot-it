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
帮我从整副塔罗牌里直接抽一张，翻开看看吧。我想给今天找个小提醒。
```

翻开后，你会看到韦特塔罗的原版插画、牌名和正逆位。想听牌义，再问一句「这张牌怎么解读？」也可以把问题留在心里，下次试试亲自切牌、选号，或抽三张看「现状、盲点、下一步」。

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
Could you draw one tarot card from the full deck and turn it over right away? I'd like a little prompt for today.
```

You'll see the original Rider–Waite–Smith illustration, the card's name, and whether it's upright or reversed. If you're curious, ask what the card means. Readings are primarily in Simplified Chinese. You can also keep your question to yourself, cut the deck, choose your own cards, or try a three-card spread next time.

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
