# 地下城RPG 游戏设计蓝图（管家专有，Worker不可见）

## 游戏概述
文字地下城RPG，单文件Python实现，在终端运行。

## 地图结构
3层地下城，每层3个房间，房间类型：
- 普通房间：无事件
- 怪物房间：触发战斗
- 宝藏房间：获得金币或装备
- Boss房间：每层最后一间，击败后进入下一层

房间连接：线性，玩家只能前进或后退（不可跳层）。

## 玩家属性
- name: 玩家名
- hp: 生命值（初始100）
- max_hp: 最大生命值（初始100）
- attack: 攻击力（初始15）
- defense: 防御力（初始5）
- gold: 金币（初始0）
- level: 等级（初始1）
- exp: 经验值（初始0）

升级条件：exp >= level * 50，升级后attack+3, defense+1, max_hp+20, hp恢复满。

## 怪物列表（按层）
第1层：
- 骷髅兵: hp=30, attack=8, defense=2, exp=15, gold=10
- 蝙蝠: hp=20, attack=6, defense=0, exp=10, gold=5

第2层：
- 石像鬼: hp=60, attack=14, defense=5, exp=30, gold=25
- 毒蜘蛛: hp=40, attack=12, defense=3, exp=20, gold=15

第3层：
- 黑暗骑士: hp=100, attack=20, defense=10, exp=50, gold=50
- 地狱犬: hp=80, attack=18, defense=6, exp=40, gold=35

Boss（每层固定）：
- 第1层Boss 骷髅王: hp=80, attack=15, defense=5, exp=50, gold=50
- 第2层Boss 石巨人: hp=150, attack=22, defense=12, exp=100, gold=100
- 第3层Boss 魔王: hp=250, attack=35, defense=20, exp=300, gold=500

## 战斗系统
回合制：
1. 玩家选择：攻击 / 逃跑（50%成功率）
2. 玩家伤害 = max(1, player.attack - monster.defense)
3. 怪物伤害 = max(1, monster.attack - player.defense)
4. 击败怪物：获得exp和gold，检查升级
5. 玩家hp<=0：游戏结束（Game Over）

## 装备系统（宝藏房间随机）
- 铁剑: attack+5
- 锁甲: defense+3
- 急救包: hp恢复30
- 强化药剂: max_hp+20, hp恢复满

## 胜利条件
击败第3层Boss魔王，显示通关结算（总金币、等级、用时）。

## 代码结构要求
单文件 `dungeon.py`，用dataclass定义Player和Monster，
用函数划分模块（create_map, battle, show_status等），
终端彩色输出（用 \033 转义码），
所有文字使用中文。
