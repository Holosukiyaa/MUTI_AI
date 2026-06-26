#!/usr/bin/env python3
import random, time
from dataclasses import dataclass

ESC = chr(27)
R = ESC + "[91m"; G = ESC + "[92m"; Y = ESC + "[93m"
C = ESC + "[96m"; M = ESC + "[95m"; B = ESC + "[1m"; X = ESC + "[0m"

@dataclass
class Player:
    name: str; hp: int; max_hp: int; attack: int; defense: int
    gold: int; level: int; exp: int

@dataclass
class Monster:
    name: str; hp: int; max_hp: int; attack: int; defense: int
    exp_reward: int; gold_reward: int

def mons(f):
    if f==0: return [Monster("骷髅兵",30,30,8,2,15,10),Monster("蝙蝠",20,20,6,0,10,5)]
    if f==1: return [Monster("石像鬼",60,60,14,5,30,25),Monster("毒蜘蛛",40,40,12,3,20,15)]
    return [Monster("黑暗骑士",100,100,20,10,50,50),Monster("地狱犬",80,80,18,6,40,35)]

def boss(f):
    if f==0: return Monster("骷髅王",80,80,15,5,50,50)
    if f==1: return Monster("石巨人",150,150,22,12,100,100)
    return Monster("魔王",250,250,35,20,300,500)

def mkmap():
    rt=["normal","monster","treasure"]; m=[]
    for fl in range(3):
        fr=[]
        for _ in range(2):
            t=random.choice(rt); r={"t":t,"done":False,"m":None}
            if t=="monster": r["m"]=random.choice(mons(fl))
            fr.append(r)
        fr.append({"t":"boss","done":False,"m":boss(fl)}); m.append(fr)
    return m

def ftime(s):
    s=int(s); h,r=divmod(s,3600); m,sc=divmod(r,60)
    if h>0: return f"{h}小时{m}分{sc}秒"
    if m>0: return f"{m}分{sc}秒"
    return f"{sc}秒"

def banner():
    print(f"\n{C}{B}  +========================================+")
    print("  |                                        |")
    print("  |          地  下  城  R P G              |")
    print("  |                                        |")
    print(f"  +========================================+{X}\n")
    print(f"{Y}深入三层地下城，击败魔王，赢得胜利！{X}\n")

def stat(p):
    hc=R if p.hp<p.max_hp*0.3 else G
    print(f"\n{Y}{'='*40}{X}\n{B}[ {p.name} 的状态 ]{X}\n{Y}{'='*40}{X}")
    print(f"  HP:{hc}{p.hp}{X}/{G}{p.max_hp}{X}  攻:{C}{p.attack}{X}  防:{C}{p.defense}{X}")
    print(f"  Lv:{Y}{p.level}{X}  EXP:{Y}{p.exp}{X}/{Y}{p.level*50}{X}  金币:{Y}{p.gold}{X}")
    print(f"{Y}{'='*40}{X}\n")

def lvup(p):
    g=0
    while p.exp>=p.level*50:
        p.exp-=p.level*50; p.level+=1; p.attack+=3; p.defense+=1
        p.max_hp+=20; p.hp=p.max_hp; g+=1
        print(f"\n  {G}{B}*** 升级! Lv.{p.level} ***{X}")
        print(f"  {G}攻+3 防+1 最大HP+20 HP回满!{X}")
    return g

def fight(p, mon, isb=False):
    m=Monster(mon.name,mon.hp,mon.max_hp,mon.attack,mon.defense,mon.exp_reward,mon.gold_reward)
    print(f"\n{R}{'='*40}{X}\n{R}遭遇: {C}{B}{m.name}{X}  HP:{m.max_hp} 攻:{m.attack} 防:{m.defense}\n{R}{'='*40}{X}\n")
    while True:
        print(f"{Y}--- 回合 ---{X}  你HP:{G}{p.hp}/{p.max_hp}{X} | {m.name}HP:{R}{m.hp}/{m.max_hp}{X}")
        if isb:
            print(f"  {C}[1]攻击{X}  {R}(Boss战无法逃跑!){X}")
            c=input("  选择(1): ").strip()
            if c!="1": print(f"  {Y}只能攻击!{X}"); continue
            act="atk"
        else:
            print(f"  {C}[1]攻击{X}  {Y}[2]逃跑(50%){X}")
            c=input("  选择(1-2): ").strip()
            if c=="1": act="atk"
            elif c=="2": act="flee"
            else: print(f"  {Y}无效{X}"); continue
        if act=="atk":
            pd=max(1,p.attack-m.defense); m.hp-=pd
            print(f"\n  {G}你对{m.name}造成{R}{pd}{X}{G}伤害!{X}")
            if m.hp<=0:
                print(f"\n{G}{B}*** 击败{m.name}! ***{X}")
                p.gold+=m.gold_reward; p.exp+=m.exp_reward
                print(f"  {G}+EXP:{m.exp_reward}{X}  {Y}+金币:{m.gold_reward}{X}")
                lvup(p); return True
            md=max(1,m.attack-p.defense); p.hp-=md
            print(f"  {R}{m.name}对你造成{R}{md}{X}{R}伤害!{X}")
            if p.hp<=0:
                print(f"\n{R}{B}*** 被{m.name}击败... ***{X}")
                print(f"\n{R}{B}========== GAME OVER =========={X}\n")
                return False
        elif act=="flee":
            if random.random()<0.5:
                print(f"\n  {G}逃跑成功!退回之前房间。{X}"); return None
            print(f"\n  {R}逃跑失败!{X}"); md=max(1,m.attack-p.defense); p.hp-=md
            print(f"  {R}{m.name}造成{R}{md}{X}{R}伤害!{X}")
            if p.hp<=0:
                print(f"\n{R}{B}*** 被{m.name}击败... ***{X}")
                print(f"\n{R}{B}========== GAME OVER =========={X}\n")
                return False
        print()

def treasure(p):
    t=random.choice([("铁剑","atk",5),("锁甲","def",3),("急救包","heal",30),("强化药剂","mhp",20)])
    nm,ef,v=t; print(f"\n  {G}{B}发现: {nm}!{X}")
    if ef=="atk": p.attack+=v; print(f"  {C}攻击+{v}!(攻:{p.attack}){X}")
    elif ef=="def": p.defense+=v; print(f"  {C}防御+{v}!(防:{p.defense}){X}")
    elif ef=="heal": h=min(v,p.max_hp-p.hp); p.hp+=h; print(f"  {G}恢复{h}HP!(HP:{p.hp}/{p.max_hp}){X}")
    elif ef=="mhp": p.max_hp+=v; p.hp=p.max_hp; print(f"  {G}最大HP升至{p.max_hp},已回满!{X}")

FN=["第一层--幽暗墓穴","第二层--石铸深渊","第三层--魔王城"]
ND=["昏暗的石室，潮湿墙壁爬满青苔。","狭窄通道火把熄灭，石板发出沉闷回响。",
    "石柱支撑天花板，地面裂纹下可见岩浆。","硫磺弥漫，石壁刻着古老符文泛暗红。",
    "魔王城前厅，黑色大理石光洁如镜。","高耸穹顶绘扭曲壁画，压迫感窒息。"]
MOND=["黑暗中有窸窣声响，什么东西在等候！","邪恶气息扑面，阴影中亮起猩红眼睛！",
      "沉重的呼吸声，强大敌人已察觉到你！"]
TD=["陈旧木箱缝隙透出微弱金光。","石棺半开，堆满闪亮宝物。",
    "华丽黄金宝箱静静躺在房间中央。"]
BD=["骷髅王手持骨剑从王座上站起...","石巨人从墙壁中剥离，发出咆哮！",
    "魔王端坐黑铁王座，血红双眼注视。最终之战！"]

def desc(room, fl, ri):
    print(f"\n{C}{'-'*40}{X}\n{B}{FN[fl]} --- 房间{ri+1}{X}\n{C}{'-'*40}{X}")
    if room["done"]:
        print(f"\n  {Y}(已完成){X}"); return
    if room["t"]=="normal":
        i=min(ri,1)+fl*2; print(f"\n  {Y}{ND[i]}{X}\n  {Y}很安全，没有异常。{X}")
    elif room["t"]=="monster": print(f"\n  {R}{MOND[fl]}{X}")
    elif room["t"]=="treasure": print(f"\n  {G}{TD[fl]}{X}")
    elif room["t"]=="boss": print(f"\n  {M}{BD[fl]}{X}")

def event(p, room, fl):
    if room["done"]: return True
    if room["t"]=="normal": room["done"]=True; return True
    if room["t"]=="monster":
        r=fight(p,room["m"],False)
        if r is True: room["done"]=True; return True
        if r is False: return False if p.hp<=0 else None
        return True
    if room["t"]=="boss":
        r=fight(p,room["m"],True)
        if r is True: room["done"]=True; return True
        if r is False: return False
        return True
    if room["t"]=="treasure": treasure(p); room["done"]=True; return True
    return True

def main():
    banner()
    name=input(f"{Y}冒险者名字: {X}").strip()
    if not name: name="无名勇者"
    p=Player(name,100,100,15,5,0,1,0)
    dmap=mkmap(); cf=0; cr=0; start=time.time()
    print(f"\n{G}欢迎，{name}！冒险开始...{X}\n")
    while True:
        room=dmap[cf][cr]; desc(room,cf,cr)
        res=event(p,room,cf)
        if res is False: break
        if res is None:
            if cr>0: cr-=1
            elif cf>0: cf-=1; cr=2
            continue
        stat(p)
        if cf==2 and cr==2 and room["done"]:
            ela=time.time()-start
            print(f"\n{G}{B}{'='*50}{X}")
            print(f"{G}{B}           恭 喜 通 关 !{X}")
            print(f"{G}{B}{'='*50}{X}")
            print(f"\n  {Y}{B}{name}{X}{Y} 击败了魔王！{X}")
            print(f"\n  {Y}[通关结算]{X}")
            print(f"  {B}名字:{X} {name}")
            print(f"  {B}等级:{X} {Y}{p.level}{X}")
            print(f"  {B}金币:{X} {Y}{p.gold}{X}")
            print(f"  {B}用时:{X} {C}{ftime(ela)}{X}")
            print(f"\n{G}{B}感谢游玩！{X}\n")
            break
        has_prev=cr>0 or cf>0
        has_next=not(cf==2 and cr==2 and room["done"])
        if cf<2 and cr==2 and room["done"]:
            opts="  [A]前进 [D]后退 [Q]退出"
            print(f"{C}选项: [A]进入下一层 [D]后退 [Q]退出{X}")
            c=input("  行动: ").strip().lower()
            if c in("a",""): cf+=1; cr=0; print(f"\n{G}进入{FN[cf]}...{X}")
            elif c=="d": cr-=1
            elif c=="q":
                print(f"\n{Y}你退出了冒险。{X}\n"); break
            else: continue
        elif has_prev and has_next:
            print(f"{C}选项: [A]前进 [D]后退 [Q]退出{X}")
            c=input("  行动: ").strip().lower()
            if c=="a" or c=="":
                if cr<2: cr+=1
                elif cf==2: pass
            elif c=="d":
                if cr>0: cr-=1
                elif cf>0: cf-=1; cr=2
            elif c=="q": print(f"\n{Y}你退出了冒险。{X}\n"); break
            else: continue
        elif has_next:
            print(f"{C}选项: [A]前进 [Q]退出{X}")
            c=input("  行动: ").strip().lower()
            if c=="a" or c=="":
                if cr<2: cr+=1
                elif cf<2: cf+=1; cr=0
            elif c=="q": print(f"\n{Y}你退出了冒险。{X}\n"); break
            else: continue
        else:
            print(f"{C}选项: [D]后退 [Q]退出{X}")
            c=input("  行动: ").strip().lower()
            if c=="d":
                if cr>0: cr-=1
                elif cf>0: cf-=1; cr=2
            elif c=="q": print(f"\n{Y}你退出了冒险。{X}\n"); break
            else: continue

if __name__=="__main__":
    main()
