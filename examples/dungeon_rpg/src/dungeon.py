#!/usr/bin/env python3
"""
地下城RPG —— 纯文字终端冒险游戏
勇者独闯三层地下城，击败魔王成为传奇！
"""

import random
import time
from dataclasses import dataclass


# ============================================================
# ANSI 颜色转义码
# ============================================================
def color(text: str, code: int) -> str:
    """使用 ANSI 转义码给文字着色"""
    return f"\033[{code}m{text}\033[0m"


RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36
WHITE = 37


# ============================================================
# 数据结构
# ============================================================
@dataclass
class Monster:
    """怪物数据类"""
    name: str
    hp: int
    attack: int
    defense: int
    exp: int
    gold: int


@dataclass
class Player:
    """玩家数据类"""
    name: str
    hp: int = 100
    max_hp: int = 100
    attack: int = 15
    defense: int = 5
    gold: int = 0
    level: int = 1
    exp: int = 0


# ============================================================
# 地图生成
# ============================================================
def create_map() -> list:
    """生成3层×3房间的地下城地图"""
    # 每层可选小怪
    floor_monsters = [
        [
            Monster("骷髅兵", 30, 8, 2, 15, 10),
            Monster("蝙蝠", 20, 6, 0, 10, 5),
        ],
        [
            Monster("石像鬼", 60, 14, 5, 30, 25),
            Monster("毒蜘蛛", 40, 12, 3, 20, 15),
        ],
        [
            Monster("黑暗骑士", 100, 20, 10, 50, 50),
            Monster("地狱犬", 80, 18, 6, 40, 35),
        ],
    ]

    # Boss
    bosses = [
        Monster("骷髅王", 80, 15, 5, 50, 50),
        Monster("石巨人", 150, 22, 12, 100, 100),
        Monster("魔王", 250, 35, 20, 300, 500),
    ]

    dungeon = []
    for floor_idx in range(3):
        # 正确：先取完整Monster对象，再用其属性构建新对象
        m = random.choice(floor_monsters[floor_idx])
        rooms = [
            {
                "type": "monster",
                "cleared": False,
                "monster": Monster(m.name, m.hp, m.attack, m.defense, m.exp, m.gold),
            },
            {
                "type": "treasure",
                "cleared": False,
                "monster": None,
            },
            {
                "type": "boss",
                "cleared": False,
                "monster": Monster(
                    bosses[floor_idx].name,
                    bosses[floor_idx].hp,
                    bosses[floor_idx].attack,
                    bosses[floor_idx].defense,
                    bosses[floor_idx].exp,
                    bosses[floor_idx].gold,
                ),
            },
        ]
        dungeon.append(rooms)

    return dungeon


# ============================================================
# 显示函数
# ============================================================
def show_status(player: Player) -> None:
    """打印玩家当前属性面板"""
    print()
    print(color("─" * 40, CYAN))
    print(color(f"  【{player.name}】  Lv.{player.level}", CYAN))
    print(color(f"  生命: {player.hp}/{player.max_hp}", GREEN))
    print(color(f"  攻击: {player.attack}  防御: {player.defense}", WHITE))
    print(color(f"  经验: {player.exp}  金币: {player.gold}", YELLOW))
    print(color("─" * 40, CYAN))
    print()


def show_monster(monster: Monster, is_boss: bool = False) -> None:
    """显示怪物信息"""
    if is_boss:
        print(color(f"  ⚔ Boss登场！{monster.name} ⚔", RED))
    else:
        print(color(f"  ⚔ 遭遇了 {monster.name}！", MAGENTA))
    print(f"  生命: {monster.hp}  攻击: {monster.attack}  防御: {monster.defense}")
    print()


def floor_name(floor_idx: int) -> str:
    """返回层名"""
    names = ["第一层 · 暗影墓地", "第二层 · 熔岩洞穴", "第三层 · 魔王城"]
    return names[floor_idx]


def room_description(room: dict, floor_idx: int, room_idx: int) -> str:
    """返回房间描述"""
    type_names = {"monster": "怪物房间", "treasure": "宝藏房间", "boss": "Boss房间"}
    return f"第{room_idx + 1}间 - {type_names.get(room['type'], '未知房间')}"


# ============================================================
# 升级系统
# ============================================================
def check_level_up(player: Player) -> int:
    """
    检查并执行升级，返回升级次数。
    连续升级直到经验不足。
    """
    times = 0
    while player.exp >= player.level * 50:
        player.level += 1
        player.attack += 3
        player.defense += 1
        player.max_hp += 20
        player.hp = player.max_hp
        times += 1
        print(color(f"  ★ 升级！你升到了 Lv.{player.level}！", GREEN))
        print(color(f"    攻击+3  防御+1  最大生命+20  生命回满！", GREEN))
    return times


# ============================================================
# 宝藏系统
# ============================================================
TREASURE_ITEMS = [
    {"name": "铁剑", "desc": "攻击力 +5", "effect": "attack", "value": 5},
    {"name": "锁甲", "desc": "防御力 +3", "effect": "defense", "value": 3},
    {"name": "急救包", "desc": "恢复30点生命", "effect": "heal", "value": 30},
    {"name": "强化药剂", "desc": "最大生命 +20 并补满", "effect": "maxhp_boost", "value": 20},
]


def treasure_room(player: Player, room: dict) -> None:
    """处理宝藏房间：随机选一件物品立即生效"""
    if room["cleared"]:
        print(color("  这里什么都没有了...", CYAN))
        return

    item = random.choice(TREASURE_ITEMS)
    print(color(f"  你发现了宝藏：{item['name']}！（{item['desc']}）", YELLOW))
    effect = item["effect"]
    value = item["value"]

    if effect == "attack":
        player.attack += value
        print(color(f"    攻击力提升 {value} 点！", GREEN))
    elif effect == "defense":
        player.defense += value
        print(color(f"    防御力提升 {value} 点！", GREEN))
    elif effect == "heal":
        healed = min(value, player.max_hp - player.hp)
        player.hp += healed
        print(color(f"    恢复了 {healed} 点生命！", GREEN))
    elif effect == "maxhp_boost":
        player.max_hp += value
        player.hp = player.max_hp
        print(color(f"    最大生命提升 {value} 点，生命回满！", GREEN))

    room["cleared"] = True


# ============================================================
# 战斗系统
# ============================================================
def calc_damage(attack_val: int, defense_val: int) -> int:
    """计算伤害：max(1, 攻击 - 防御)"""
    return max(1, attack_val - defense_val)


def battle(player: Player, monster: Monster, is_boss: bool = False) -> bool:
    """
    处理战斗逻辑。
    返回 True 表示玩家胜利（怪物死亡），False 表示玩家逃跑成功。
    玩家死亡会导致程序退出（Game Over）。
    """
    show_monster(monster, is_boss)

    while True:
        # --- 玩家行动 ---
        if is_boss:
            print("  Boss面前无路可逃！只能战斗！")
            print()
            action = "1"
        else:
            print("  1. 攻击  2. 逃跑")
            action = input("  请选择 > ").strip()

        if action == "1":
            # 玩家攻击
            dmg = calc_damage(player.attack, monster.defense)
            monster.hp -= dmg
            print(color(f"  你对 {monster.name} 造成了 {dmg} 点伤害！", WHITE))

            if monster.hp <= 0:
                # 怪物死亡
                monster.hp = 0
                print(color(f"  你击败了 {monster.name}！", GREEN))
                player.exp += monster.exp
                player.gold += monster.gold
                print(color(f"  获得经验 +{monster.exp}，金币 +{monster.gold}", YELLOW))
                check_level_up(player)
                return True

        elif action == "2" and not is_boss:
            # 逃跑
            if random.random() < 0.5:
                print(color("  你成功逃跑了！", CYAN))
                return False
            else:
                print(color("  逃跑失败！", RED))
                # 逃跑失败，怪物直接攻击（跳过玩家攻击阶段）
        else:
            print(color("  无效选择，请重新输入。", RED))
            continue  # 重新显示行动菜单

        # --- 怪物攻击 ---
        dmg = calc_damage(monster.attack, player.defense)
        player.hp -= dmg
        print(color(f"  {monster.name} 对你造成了 {dmg} 点伤害！", RED))
        print(color(f"  你的生命: {player.hp}/{player.max_hp}", GREEN))

        # 检查玩家死亡
        if player.hp <= 0:
            player.hp = 0
            print()
            print(color("  ★==============★", RED))
            print(color("  ||  你死了...   ||", RED))
            print(color("  ★==============★", RED))
            print(color("  GAME OVER", RED))
            print()
            show_final_stats(player, won=False)
            exit(0)

        print()


def show_final_stats(player: Player, won: bool, elapsed: float = 0) -> None:
    """显示结算信息"""
    print(color("═" * 40, CYAN))
    if won:
        print(color("  ★★★ 恭喜通关！★★★", YELLOW))
        print(color(f"  勇者 {player.name} 击败魔王，成为传奇！", GREEN))
    print(color(f"  最终等级: {player.level}", WHITE))
    print(color(f"  总金币: {player.gold}", YELLOW))
    if won:
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        print(color(f"  用时: {mins}分{secs}秒", CYAN))
    print(color("═" * 40, CYAN))
    print()


# ============================================================
# 主游戏逻辑
# ============================================================
def main() -> None:
    """游戏主入口"""
    print()
    print(color("╔══════════════════════════════════╗", YELLOW))
    print(color("║       地 下 城 R P G            ║", YELLOW))
    print(color("║    深入三层地城，击败魔王！     ║", YELLOW))
    print(color("╚══════════════════════════════════╝", YELLOW))
    print()

    # 输入玩家名
    name = input(color("  请输入你的名字：", CYAN)).strip()
    if not name:
        name = "无名勇者"
    player = Player(name=name)
    print(color(f"\n  勇者 {player.name}，踏上征途吧！\n", GREEN))
    time.sleep(0.8)

    # 初始化地图
    dungeon = create_map()
    floor_idx = 0   # 当前层索引
    room_idx = 0    # 当前房间索引

    start_time = time.time()

    # 显示初始状态
    show_status(player)
    print(color(f"  ★★ {floor_name(floor_idx)} ★★", BLUE))
    print(f"  你站在第 {room_idx + 1} 间房间前。")
    print()

    # ---- 游戏主循环 ----
    while True:
        floor = dungeon[floor_idx]
        room = floor[room_idx]

        # 进入当前房间，触发事件
        room_type = room["type"]
        desc = room_description(room, floor_idx, room_idx)
        print(color(f"  >>> {desc} <<<", BLUE))

        if room_type == "monster" and not room["cleared"]:
            print(color("  有怪物！准备战斗！", RED))
            print()
            won = battle(player, room["monster"], is_boss=False)
            if won:
                room["cleared"] = True
            else:
                # 逃跑成功，房间保持未清理
                pass

        elif room_type == "boss" and not room["cleared"]:
            print(color("  黑暗的气息扑面而来...", RED))
            print()
            won = battle(player, room["monster"], is_boss=True)
            if won:
                room["cleared"] = True
                if floor_idx == 2:
                    # 击败魔王，通关！
                    elapsed = time.time() - start_time
                    print()
                    print(color("  ★★★★★★★★★★★★★★★★★★★★★★★★", YELLOW))
                    print(color(f"  魔王倒下了！{player.name} 拯救了世界！", GREEN))
                    print(color("  ★★★★★★★★★★★★★★★★★★★★★★★★", YELLOW))
                    print()
                    show_status(player)
                    show_final_stats(player, won=True, elapsed=elapsed)
                    return
                else:
                    # 进入下一层
                    print(color(f"  你击败了{room['monster'].name}！", GREEN))
                    print(color("  通往下一层的大门打开了...", BLUE))
                    print()
                    floor_idx += 1
                    room_idx = 0
                    show_status(player)
                    print(color(f"  ★★ {floor_name(floor_idx)} ★★", BLUE))
                    print(f"  你站在第 {room_idx + 1} 间房间前。")
                    print()
                    continue  # 跳过移动选择，直接处理新房间

        elif room_type == "treasure" and not room["cleared"]:
            treasure_room(player, room)

        else:
            # 空房间
            print(color("  这里什么都没有了...", CYAN))

        print()

        # ---- 移动选择 ----
        show_status(player)
        print(color(f"  ★★ {floor_name(floor_idx)} · 第{room_idx + 1}间 ★★", BLUE))

        # 判断可移动方向
        can_forward = room_idx < 2
        can_backward = room_idx > 0

        if can_forward and can_backward:
            print("  w/前进 → 前进   s/后退 → 后退")
        elif can_forward:
            print("  w/前进 → 前进")
        elif can_backward:
            print("  s/后退 → 后退")

        while True:
            cmd = input("  请选择移动方向 > ").strip().lower()
            if cmd in ("w", "前进") and can_forward:
                room_idx += 1
                break
            elif cmd in ("s", "后退") and can_backward:
                room_idx -= 1
                break
            else:
                print(color("  无法向该方向移动，请重新选择。", RED))

        print()


if __name__ == "__main__":
    main()
