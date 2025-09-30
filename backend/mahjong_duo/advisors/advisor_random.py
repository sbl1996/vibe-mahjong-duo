# -*- coding: utf-8 -*-
"""
advisor_random.py: A baseline AI advisor that makes random legal moves.

- If it can win (hu), it always will.
- Otherwise, it chooses randomly from all other legal options (peng, kong, pass, discard).
"""
import random
from typing import Dict, Any

from mahjong_duo.rules_core import (
    GameState,
    tile_to_str,
    can_hu_four_plus_one,
    can_peng,
    can_kong_exposed,
    can_kong_concealed,
    can_kong_added
)

def _rng_for_state(state: GameState, seat: int) -> random.Random:
    """Creates a seeded random number generator for reproducible decisions."""
    s = (state.seed * 0x9E3779B1) ^ (state.step_no * 0x85EBCA77) ^ (seat * 0xC2B2AE3D)
    return random.Random(s & 0xFFFFFFFF)


def advise_on_discard(state: GameState, seat: int) -> Dict[str, Any]:
    """From a 14-tile hand, randomly selects a tile to discard."""
    me = state.players[seat]
    assert len(me.hand) % 3 == 2, "advise_on_discard must be called with a 14, 11, etc. tile hand"
    
    # Strategy: discard from the suit with the fewest tiles (ties broken by suit order)
    suit_counts = [0, 0, 0]
    for tile in me.hand:
        suit_counts[tile // 9] += 1

    target_suit = None
    min_count = None
    for suit_index, count in enumerate(suit_counts):
        if count == 0:
            continue
        if min_count is None or count < min_count:
            min_count = count
            target_suit = suit_index

    if target_suit is None:
        tile_to_discard = me.hand[0]
        reason_suffix = "Fallback to the first tile because no suit data was available."
    else:
        tile_to_discard = next(tile for tile in me.hand if tile // 9 == target_suit)
        suit_label = ["万", "条", "筒"][target_suit]
        reason_suffix = f"Chose the first tile from the suit with the fewest tiles ({suit_label})."
    
    return {
        "action": "discard",
        "tile": tile_to_discard,
        "reason": f"{reason_suffix} Discarding {tile_to_str(tile_to_discard)}.",
        "detail": {}
    }


def advise_on_opponent_discard(state: GameState, seat: int) -> Dict[str, Any]:
    """Reacts to an opponent's discard."""
    assert state.last_discard is not None, "No discard to react to."
    from_seat, tile = state.last_discard
    me = state.players[seat]
    rng = _rng_for_state(state, seat)

    # Priority 1: Always win if possible.
    merged_hand = tuple(sorted(me.hand + (tile,)))
    if can_hu_four_plus_one(merged_hand, me.melds):
        return {
            "action": "hu",
            "tile": tile,
            "reason": "Win is always the best option.",
            "detail": {}
        }
    
    # Collect all other legal actions
    possible_actions = ["pass"]
    if can_peng(me.hand, tile):
        possible_actions.append("peng")
    if can_kong_exposed(me.hand, tile):
        possible_actions.append("kong")

    # Randomly choose from the available actions
    # chosen_action = rng.choice(possible_actions)
    chosen_action = possible_actions[0]

    if chosen_action == "peng":
        return {
            "action": "peng",
            "tile": tile,
            "reason": f"Randomly chose to Peng {tile_to_str(tile)}.",
            "detail": {"options": possible_actions}
        }
    elif chosen_action == "kong":
        return {
            "action": "kong",
            "style": "exposed",
            "tile": tile,
            "reason": f"Randomly chose to Kong {tile_to_str(tile)}.",
            "detail": {"options": possible_actions}
        }
    else: # pass
        return {
            "action": "pass",
            "tile": tile,
            "reason": "Randomly chose to Pass.",
            "detail": {"options": possible_actions}
        }


def advise_on_draw(state: GameState, seat: int) -> Dict[str, Any]:
    """After drawing a tile, decides whether to declare a win, kong, or discard."""
    me = state.players[seat]
    assert len(me.hand) % 3 == 2, "advise_on_draw must be called after drawing a tile."
    rng = _rng_for_state(state, seat)

    # Priority 1: Always declare a self-drawn win (zimo).
    if can_hu_four_plus_one(me.hand, me.melds):
        return {
            "action": "hu",
            "tile": None, # No specific tile for self-drawn win
            "reason": "Self-drawn win is always the best option.",
            "detail": {}
        }
    
    # Collect all other legal special actions
    possible_actions = ["discard"]
    
    kc = can_kong_concealed(me.hand)
    if kc is not None:
        possible_actions.append(("kong_concealed", kc))
        
    ka = can_kong_added(me.melds, me.hand)
    if ka is not None:
        possible_actions.append(("kong_added", ka))
        
    # Randomly choose an action
    # chosen_action = rng.choice(possible_actions)
    chosen_action = possible_actions[0]
    
    if chosen_action == "discard":
        # If the choice is to discard, delegate to the discard advisor
        return advise_on_discard(state, seat)
    
    else: # It must be a kong action
        action_type, tile = chosen_action
        style = "concealed" if action_type == "kong_concealed" else "added"
        return {
            "action": "kong",
            "style": style,
            "tile": tile,
            "reason": f"Randomly chose to perform a {style} Kong on {tile_to_str(tile)}.",
            "detail": {"options": possible_actions}
        }