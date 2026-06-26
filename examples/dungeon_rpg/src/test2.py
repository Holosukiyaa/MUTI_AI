#!/usr/bin/env python3
import random
import sys
import time
from dataclasses import dataclass

ESC = chr(27)
C_RED = ESC + "[91m"
C_RESET = ESC + "[0m"

@dataclass
class Monster:
    name: str
    hp: int
    attack: int
    defense: int
    exp: int
    gold: int

print("测试成功")
