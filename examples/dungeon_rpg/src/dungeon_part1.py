#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import sys
import time
from dataclasses import dataclass
from typing import Optional

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

print("Part 1 OK")
