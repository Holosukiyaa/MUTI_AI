#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终端回合制地下城RPG — 3层线性地下城，击败第3层魔王即可通关！"""
import random
import sys
import time
from dataclasses import dataclass

# ── ANSI 颜色常量 ──────────────────────────────────────────
ESC = chr(27)
C_RED = ESC + "[91m"
C_GREEN = ESC + "[92m"
C_YELLOW = ESC + "[93m"
C_BLUE = ESC + "[94m"
C_MAGENTA = ESC + "[95m"
C_CYAN = ESC + "[96m"
C_WHITE = ESC + "[97m"
C_BOLD = ESC + "[1m"
C_RESET = ESC + "[0m"

# ── 数据类 ──────────────────────────────────────────────────

@dataclass
class Monster:
    name: str
    hp: int
    attack: int
    defense: int
    exp: int
    gold: int


@dataclass
class Player:
    name: str
    hp: int = 100
    max_hp: int = 100
    attack: int = 15
    defense: int = 5
    gold: int = 0
    level: int = 1
    exp: int = 0

# ── 怪物池 ──────────────────────────────────────────────────

MOB_POOL = {
    1: [
        Monster("骷髅兵", hp=30, attack=8, defense=2, exp=15, gold=10),
        Monster("蝙蝠", hp=20, attack=6, defense=0, exp=10, gold=5),
    ],
    2: [
        Monster("石像鬼", hp=60, attack=14, defense=5, exp=30, gold=25),
        Monster("毒蜘蛛", hp=40, attack=12, defense=3, exp=20, gold=15),
    ],
    3: [
        Monster("黑暗骑士", hp=100, attack=20, defense=10, exp=50, gold=50),
        Monster("地狱犬", hp=80, attack=18, defense=6, exp=40, gold=35),
    ],
}

BOSS_POOL = {
    1: Monster("骷髅王", hp=80, attack=15, defense=5, exp=50, gold=50),
    2: Monster("石巨人", hp=150, attack=22, defense=12, exp=100, gold=100),
    3: Monster("魔王", hp=250, attack=35, defense=20, exp=300, gold=500),
}

# ── 宝藏道具效果 ────────────────────────────────────────────

def _apply_iron_sword(p: Player) -> None:
    p.attack += 5

def _apply_chainmail(p: Player) -> None:
    p.defense += 3

def _apply_first_aid(p: Player) -> None:
    p.hp = min(p.hp + 30, p.max_hp)

def _apply_potion(p: Player) -> None:
    p.max_hp += 20
    p.hp = p.max_hp

TREASURE_POOL = [
    ("铁剑", "攻击力永久 +5", _apply_iron_sword),
    ("锁甲", "防御力永久 +3", _apply_chainmail),
    ("急救包", "恢复 HP 30 点", _apply_first_aid),
    ("强化药剂", "最大HP永久 +20，HP回满", _apply_potion),
]

# ── 辅助函数 ────────────────────────────────────────────────

def cprint(text: str, color: str = "", bold: bool = False) -> None:
    """带 ANSI 颜色的打印。"""
    prefix = C_BOLD if bold else ""
    if color:
        print(prefix + color + text + C_RESET)
    else:
        print(text)


def game_over(monster_name: str) -> None:
    """显示 Game Over 并退出。"""
    cprint(f"你被 {monster_name} 击败了... GAME OVER", C_RED, bold=True)
    input("按回车键退出...")
    sys.exit(0)


def show_victory(player: Player, start_time: float) -> None:
    """显示通关结算画面并退出。"""
    elapsed = time.time() - start_time
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    print()
    cprint("========================================", C_YELLOW, bold=True)
    cprint("           恭喜通关！", C_YELLOW, bold=True)
    cprint("========================================", C_YELLOW, bold=True)
    show_status(player)
    cprint(f"用时: {mins} 分 {secs} 秒", C_CYAN, bold=True)
    cprint(f"总金币: {player.gold}", C_YELLOW, bold=True)
    cprint(f"最终等级: Lv.{player.level}", C_GREEN, bold=True)
    print()
    input("按回车键退出...")

# ── 地图生成 ────────────────────────────────────────────────

def create_map() -> list:
    """生成 3 层 × 3 间的地牢地图。"""
    dungeon = []
    for floor in range(1, 4):
        rooms = []
        for slot in range(2):
            rtype = random.choices(
                ["normal", "monster", "treasure"],
                weights=[30, 50, 20],
                k=1,
            )[0]
            if floor == 1 and slot == 0:
                rtype = "normal"
            rooms.append({"type": rtype, "cleared": False})
        rooms.append({"type": "boss", "cleared": False})
        dungeon.append(rooms)
    return dungeon


def spawn_monster(room: dict, floor_num: int) -> Monster | None:
    """根据房间类型和层数生成怪物实例。"""
    if room["type"] == "monster":
        t = random.choice(MOB_POOL[floor_num])
        return Monster(t.name, t.hp, t.attack, t.defense, t.exp, t.gold)
    elif room["type"] == "boss":
        t = BOSS_POOL[floor_num]
        return Monster(t.name, t.hp, t.attack, t.defense, t.exp, t.gold)
    return None


def room_desc(room_type: str, floor_num: int) -> str:
    """返回房间描述文字。"""
    normal_descs = [
        "这是一个安静的空房间，墙壁上长满了青苔。",
        "房间里空无一物，只有地上的灰尘和破碎的石砖。",
        "微弱的火光从墙上的火把中摇曳，房间里什么也没有。",
        "一个空旷的房间，空气中弥漫着古老的气息。",
    ]
    boss_names = {1: "骷髅王", 2: "石巨人", 3: "魔王"}
    if room_type == "normal":
        return random.choice(normal_descs)
    elif room_type == "monster":
        return "你感觉到了一股危险的气息 -- 有怪物潜伏在这里！"
    elif room_type == "treasure":
        return "房间中央摆放着一个闪闪发光的宝箱！"
    elif room_type == "boss":
        return f"一股强大的压迫感扑面而来 -- Boss [{boss_names[floor_num]}] 在此等候！"
    return ""

# ── 状态显示 & 升级 ─────────────────────────────────────────

def show_status(player: Player) -> None:
    """显示玩家当前状态面板。"""
    if player.hp > player.max_hp * 0.5:
        hp_color = C_GREEN
    elif player.hp > player.max_hp * 0.25:
        hp_color = C_YELLOW
    else:
        hp_color = C_RED
    print()
    cprint("+------------------------------+", C_CYAN)
    cprint(f"  勇者 {C_BOLD}{player.name}{C_RESET}{C_CYAN}", C_CYAN)
    cprint(f"  Lv.{player.level}  EXP: {player.exp}/{player.level * 50}", C_CYAN)
    cprint(f"  HP: {hp_color}{player.hp}{C_CYAN}/{player.max_hp}", C_CYAN)
    cprint(f"  攻击: {player.attack}  防御: {player.defense}", C_CYAN)
    cprint(f"  金币: {C_YELLOW}{player.gold}{C_CYAN}", C_CYAN)
    cprint("+------------------------------+", C_CYAN)
    print()


def check_level_up(player: Player) -> bool:
    """检查并处理升级。返回是否发生了升级。"""
    leveled = False
    while player.exp >= player.level * 50:
        player.level += 1
        player.attack += 3
        player.defense += 1
        player.max_hp += 20
        player.hp = player.max_hp
        leveled = True
        cprint(
            f"[升级] Lv.{player.level}！攻击+3 防御+1 最大HP+20 HP回满",
            C_GREEN,
            bold=True,
        )
    return leveled


def treasure_room(player: Player) -> None:
    """处理宝藏房间事件。"""
    name, desc, effect = random.choice(TREASURE_POOL)
    cprint(f"  发现宝箱！获得了 [{name}]: {desc}", C_YELLOW, bold=True)
    effect(player)
    cprint(f"  当前 HP: {player.hp}/{player.max_hp}", C_GREEN)

# ── 战斗系统 ────────────────────────────────────────────────

def battle(player: Player, monster: Monster) -> bool:
    """回合制战斗。返回 True=胜利, False=逃跑成功。"""
    cprint(
        f"战斗！遭遇了 {C_RED}{C_BOLD}{monster.name}{C_RESET}！",
        C_RED,
        bold=True,
    )
    print(f"   {monster.name} HP:{monster.hp} 攻击:{monster.attack} 防御:{monster.defense}")

    while monster.hp > 0 and player.hp > 0:
        print()
        cprint(
            f"你的 HP: {C_GREEN}{player.hp}{C_RESET}/{player.max_hp}"
            f"  |  {monster.name} HP: {C_RED}{monster.hp}{C_RESET}",
            C_WHITE,
        )
        print("  1.攻击  |  2.逃跑")
        choice = input("  请选择 (1/2): ").strip()

        if choice == "1":
            # 玩家攻击
            dmg = max(1, player.attack - monster.defense)
            monster.hp -= dmg
            cprint(f"  -> 你对 {monster.name} 造成 {C_RED}{dmg}{C_RESET} 点伤害！", C_WHITE)

            if monster.hp <= 0:
                cprint(f"击败了 {monster.name}！", C_GREEN, bold=True)
                player.exp += monster.exp
                player.gold += monster.gold
                cprint(
                    f"  获得 {C_GREEN}{monster.exp} EXP{C_RESET}，"
                    f"{C_YELLOW}{monster.gold} 金币{C_RESET}",
                    C_WHITE,
                )
                check_level_up(player)
                return True

            # 怪物反击
            dmg2 = max(1, monster.attack - player.defense)
            player.hp -= dmg2
            cprint(f"  <- {monster.name} 对你造成 {C_RED}{dmg2}{C_RESET} 点伤害！", C_WHITE)

            if player.hp <= 0:
                game_over(monster.name)

        elif choice == "2":
            cprint("  你试图逃跑...", C_YELLOW)
            if random.random() < 0.5:
                cprint("  逃跑成功！退回到了上一个房间。", C_GREEN)
                return False
            else:
                cprint("  逃跑失败！", C_RED)
                dmg2 = max(1, monster.attack - player.defense)
                player.hp -= dmg2
                cprint(f"  <- {monster.name} 对你造成 {C_RED}{dmg2}{C_RESET} 点伤害！", C_WHITE)
                if player.hp <= 0:
                    game_over(monster.name)
        else:
            cprint("  无效选择，请重新输入。", C_YELLOW)

    return True

# ── 移动逻辑 ────────────────────────────────────────────────

def move_forward(cf: int, cr: int, dungeon: list) -> tuple[int, int]:
    """尝试前进，返回新坐标。"""
    if cr < 2:
        return cf, cr + 1
    droom = dungeon[cf][cr]
    if droom["type"] == "boss" and not droom["cleared"]:
        cprint("你必须先击败本层Boss才能进入下一层！", C_YELLOW)
        return cf, cr
    if cf < 2:
        return cf + 1, 0
    return cf, cr


def move_backward(cf: int, cr: int) -> tuple[int, int]:
    """尝试后退，返回新坐标。"""
    if cr > 0:
        return cf, cr - 1
    elif cf > 0:
        return cf - 1, 2
    else:
        cprint("你已经在入口了，无法后退！", C_YELLOW)
        return cf, cr

# ── 主循环 ──────────────────────────────────────────────────

def main() -> None:
    """游戏入口。"""
    print()
    cprint("========================================", C_YELLOW, bold=True)
    cprint("          地下城 RPG", C_YELLOW, bold=True)
    cprint("========================================", C_YELLOW, bold=True)
    print()
    cprint("击败第3层的魔王即可通关！", C_CYAN)
    cprint("战斗中: 1=攻击, 2=逃跑 (逃跑50%成功率)", C_CYAN)
    print()

    name = input("请输入你的名字: ").strip()
    if not name:
        name = "冒险者"
    player = Player(name=name)

    dungeon = create_map()
    cf, cr = 0, 0               # 当前楼层, 当前房间
    start_time = time.time()

    while True:
        room = dungeon[cf][cr]
        floor_num = cf + 1
        room_num = cr + 1

        cprint(f"===== 第{floor_num}层 第{room_num}间 =====", C_BLUE, bold=True)
        cprint(room_desc(room["type"], floor_num), C_WHITE)

        if not room["cleared"]:
            if room["type"] in ("monster", "boss"):
                monster = spawn_monster(room, floor_num)
                if monster is None:
                    room["cleared"] = True
                else:
                    result = battle(player, monster)
                    if result:
                        room["cleared"] = True
                        if room["type"] == "boss":
                            cprint(f"Boss {monster.name} 已被击败！", C_GREEN, bold=True)
                            # 击败第3层魔王 → 直接通关
                            if cf == 2:
                                show_victory(player, start_time)
                                return
                    else:
                        # 逃跑成功 → 后退
                        cf, cr = move_backward(cf, cr)
                        continue
            elif room["type"] == "treasure":
                treasure_room(player)
                room["cleared"] = True
            else:
                room["cleared"] = True

        show_status(player)

        print("命令: [a]前进  [d]后退  [q]退出")
        cmd = input("> ").strip().lower()

        if cmd in ("a", "forward", "前进"):
            nf, nr = move_forward(cf, cr, dungeon)
            if nf == cf and nr == cr:
                # 前进被阻止 — 可能是第3层Boss已被击败
                if cf == 2 and dungeon[cf][cr]["type"] == "boss" and dungeon[cf][cr]["cleared"]:
                    show_victory(player, start_time)
                    return
            else:
                cf, cr = nf, nr
        elif cmd in ("d", "back", "后退"):
            cf, cr = move_backward(cf, cr)
        elif cmd in ("q", "quit", "退出"):
            cprint("游戏已退出。", C_YELLOW)
            return
        else:
            cprint("无效命令。可用: a=前进, d=后退, q=退出", C_YELLOW)


if __name__ == "__main__":
    main()
