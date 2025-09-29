# -*- coding: utf-8 -*-
"""
双人麻将 AI 对局模拟器

该脚本使用 rules_core.py 作为游戏引擎，advisor.py 作为 AI 决策者，
模拟两个 AI 玩家之间的对局，并统计胜率与得分。

如何运行:
python simulation.py --num_games 100 --verbose

参数:
--num_games: 模拟的总局数 (默认: 100)
--seed: 随机数种子，用于复现对局 (默认: 42)
--verbose: 是否打印每一局的详细过程 (默认: 关闭)
"""
import argparse
import random
import time
import os
import traceback
import concurrent.futures
from dataclasses import replace
from typing import Optional, Tuple, Dict, Any

from tqdm import tqdm

# 从您的文件中导入所有必要的组件
from mahjong_duo.rules_core import (
    GameState,
    init_game,
    draw,
    discard,
    claim_peng,
    claim_kong_exposed,
    kong_concealed,
    kong_added,
    compute_score_summary,
    tile_to_str,
)

import importlib

def load_advisor_modules(mod_names):
    """根据模块名列表动态导入 advisor 模块"""
    return [importlib.import_module("mahjong_duo.advisors." + name) for name in mod_names]

advisors = None  # 在 main() 中初始化

def print_state(state: GameState):
    """打印当前游戏状态，便于观察"""
    print("-" * 40)
    print(f"Step: {state.step_no}, Turn: Player {state.turn}, Wall left: {len(state.wall)}")
    
    for i, p in enumerate(state.players):
        hand_str = " ".join(tile_to_str(t) for t in p.hand)
        melds_str = " ".join(f"{m.kind.upper()}({', '.join(tile_to_str(t) for t in m.tiles)})" for m in p.melds)
        discards_str = " ".join(tile_to_str(t) for t in p.discards)
        
        print(f"  Player {i}:")
        print(f"    Hand ({len(p.hand)}): {hand_str}")
        if melds_str:
            print(f"    Melds: {melds_str}")
        if discards_str:
            print(f"    Discards: {discards_str}")
            
    if state.last_discard:
        seat, tile = state.last_discard
        print(f"Last discard: Player {seat} threw {tile_to_str(tile)}")
    print("-" * 40)


def run_single_game(seed: int, verbose: bool = False, advisor_modules=None) -> Tuple[Optional[int], int]:
    """
    运行一局完整的游戏。
    """
    first_turn = seed % 2
    state = init_game(seed, first_turn=first_turn)

    if verbose:
        print(f"\n--- Starting Game with Seed {seed}, Player {first_turn} starts ---")

    winner = None
    reason = ""

    if advisor_modules is None:
        advisor_modules = ["advisor", "advisor_random"]
    advisors = load_advisor_modules(advisor_modules)

    while not state.ended and state.wall:
        if verbose:
            print_state(state)

        current_player = state.turn
        current_advisor = advisors[current_player]
        
        # -----------------------------------------------------
        # 阶段 1: 响应对手的弃牌 (如果上一轮有弃牌)
        # -----------------------------------------------------
        if state.last_discard and state.last_discard[0] != current_player:
            advice = current_advisor.advise_on_opponent_discard(state, current_player)
            print(advice)
            action = advice["action"]
            
            if verbose:
                print(f"Player {current_player} reacts to discard. Advisor suggests: {advice['reason']}")

            if action == "hu":
                winner = current_player
                reason = "ron"
                state = replace(state, ended=True)
                break
            
            elif action == "peng":
                tile = advice["tile"]
                state = claim_peng(state, current_player, 1 - current_player, tile)
                # 碰牌后，轮到自己出牌 (手牌14张)
                discard_advice = current_advisor.advise_on_discard(state, current_player)
                state = discard(state, current_player, discard_advice["tile"])
                continue # 完成了碰和打，直接进入下一轮循环

            elif action == "kong":
                tile = advice["tile"]
                state = claim_kong_exposed(state, current_player, 1-current_player, tile)
                # 明杠后，需要从牌山摸一张牌
                state, _ = draw(state, current_player)
                if not state.wall: break # 杠后摸牌时牌山空了
                # 摸牌后，再次决策（通常是打牌）
                draw_advice = current_advisor.advise_on_draw(state, current_player)
                if draw_advice['action'] == 'discard':
                     state = discard(state, current_player, draw_advice['tile'])
                # (其他杠/胡的情况在 advise_on_draw 内部处理，这里简化流程)
                continue

            # action == "pass" -> 不做任何操作，进入摸牌阶段
        
        # -----------------------------------------------------
        # 阶段 2: 轮到自己，正常摸牌
        # -----------------------------------------------------
        state, drawn_tile = draw(state, current_player)

        if drawn_tile is None:
            # 牌山摸完，流局
            break

        if verbose:
            print(f"Player {current_player} draws {tile_to_str(drawn_tile)}")
        # -----------------------------------------------------
        # 阶段 3: 摸牌后决策 (胡/杠/打) - 使用内层循环处理连续动作
        # -----------------------------------------------------
        while True:
            # 如果因为补杠摸牌导致牌山空了，则结束回合
            if drawn_tile is None:
                break
                
            advice = current_advisor.advise_on_draw(state, current_player)
            action = advice["action"]

            if verbose:
                print(f"Player {current_player} after drawing. Advisor suggests: {advice['reason']}")

            if action == "hu":
                winner = current_player
                reason = "zimo"  # 自摸
                state = replace(state, ended=True)
                break  # 跳出内层决策循环

            elif action == "kong":
                tile = advice["tile"]
                style = advice["style"]
                if style == "concealed":
                    state = kong_concealed(state, current_player, tile)
                elif style == "added":
                    state = kong_added(state, current_player, tile)

                # 杠牌后，需要补摸一张，然后再次进入决策循环，但回合不变
                state, drawn_tile = draw(state, current_player)
                if verbose and drawn_tile is not None:
                    print(f"Player {current_player} draws replacement tile after kong: {tile_to_str(drawn_tile)}")
                
                # 继续内层循环，用新摸的牌再次决策
                continue

            elif action == "discard":
                tile_to_discard = advice["tile"]
                state = discard(state, current_player, tile_to_discard)
                break # 打牌后，结束本回合的决策，跳出内层循环

            else:
                raise RuntimeError(f"Unknown action from advisor: {action}")
        
        # 如果是因为胡牌或牌山摸完跳出的，也要结束外层游戏循环
        if state.ended or drawn_tile is None:
            break

    # 游戏结束，计算分数
    if winner is not None:
        if verbose:
            print_state(state)
            print(f"\nGame Over! Player {winner} wins by {reason}.")
        summary = compute_score_summary(state, winner, reason)
        if verbose:
            print("Score Summary:", summary)
        winner_score_change = summary["players"][str(winner)]["net_change"]
        return winner, winner_score_change
    else:
        if verbose:
            print("\nGame Over! Draw (wall exhausted).")
        return None, 0

def main():
    parser = argparse.ArgumentParser(
        description="Parallel AI Mahjong Simulation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--num_games", type=int, default=100, help="Number of games to simulate.")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed for reproducibility.")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes to use. Defaults to all available CPU cores.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed game logs. Only works with --workers 1.")
    parser.add_argument("--advisors", nargs=2, default=["advisor", "advisor_random"], help="Advisor module names for player 0 and 1 (default: advisor advisor_random)")
    args = parser.parse_args()

    advisor_modules = args.advisors

    cpu_count = os.cpu_count() or 2
    num_workers = args.workers if args.workers is not None else cpu_count // 2
    if num_workers > 1 and args.verbose:
        print("Warning: --verbose is not recommended in parallel mode. Disabling verbose output.")
        args.verbose = False

    print(f"Starting simulation of {args.num_games} games with base seed {args.seed} using {num_workers} worker(s)...")

    stats: Dict[str, Any] = {
        "wins": {0: 0, 1: 0},
        "total_score": {0: 0, 1: 0},
        "draws": 0,
    }

    start_time = time.time()

    # --- 并行执行逻辑 ---
    rng = random.Random(args.seed)
    game_seeds = [rng.randint(0, 2**31 - 1) for _ in range(args.num_games)]
    results = []

    run_single_game(args.seed, args.verbose, advisor_modules)  # 预热，避免首次调用开销影响计时
    raise ValueError

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        # 提交所有任务
        future_to_seed = {
            executor.submit(run_single_game, seed, args.verbose, advisor_modules): seed
            for seed in game_seeds
        }

        # 使用 tqdm 显示进度条，并在 postfix 中实时展示积分差与胜负统计
        futures_iter = concurrent.futures.as_completed(future_to_seed)
        with tqdm(total=args.num_games, desc="Simulating Games") as pbar:
            for future in futures_iter:
                try:
                    result = future.result()
                    results.append(result)

                    # 实时更新统计数据（用于进度条展示）
                    winner, score_change = result
                    if winner is not None:
                        loser = 1 - winner
                        stats["wins"][winner] += 1
                        stats["total_score"][winner] += score_change
                        stats["total_score"][loser] -= score_change
                    else:
                        stats["draws"] += 1

                except Exception as exc:
                    seed = future_to_seed.get(future)
                    print(f'Game with seed {seed} generated an exception: {exc}')
                    raise exc
                    traceback.print_exc()
                finally:
                    # 更新进度条并显示当前积分差与胜负
                    diff = stats["total_score"][0] - stats["total_score"][1]
                    pbar.update(1)
                    pbar.set_postfix({
                        "diff": f"{diff:+.0f}",
                        "wins": f"{stats['wins'][0]}-{stats['wins'][1]}",
                        "draws": stats["draws"],
                    })

    # 统计已在并行收集中实时更新，因此这里不再二次统计

    end_time = time.time()
    duration = end_time - start_time

    # --- 打印报告 ---
    print("\n" + "="*20 + " Simulation Report " + "="*20)
    print(f"Seed used: {args.seed}")
    print(f"Total games simulated: {args.num_games}")
    print(f"Total time taken: {duration:.2f} seconds")
    if duration > 0:
        print(f"Games per second: {args.num_games / duration:.2f}")
    print("-" * 59)

    p0_wins = stats["wins"][0]
    p1_wins = stats["wins"][1]
    total_wins = p0_wins + p1_wins

    p0_win_rate = (p0_wins / total_wins * 100) if total_wins > 0 else 0
    p1_win_rate = (p1_wins / total_wins * 100) if total_wins > 0 else 0
    draw_rate = (stats["draws"] / args.num_games * 100)

    p0_avg_score = (stats["total_score"][0] / args.num_games) if args.num_games > 0 else 0
    p1_avg_score = (stats["total_score"][1] / args.num_games) if args.num_games > 0 else 0

    print(f"Player 0 Wins: {p0_wins} ({p0_win_rate:.1f}%)")
    print(f"Player 1 Wins: {p1_wins} ({p1_win_rate:.1f}%)")
    print(f"Draws: {stats['draws']} ({draw_rate:.1f}%)")
    print("-" * 59)
    print(f"Player 0 Net Score: {stats['total_score'][0]:.0f} (Avg per game: {p0_avg_score:+.2f})")
    print(f"Player 1 Net Score: {stats['total_score'][1]:.0f} (Avg per game: {p1_avg_score:+.2f})")
    print("="*59)


if __name__ == "__main__":
    main()