import os
import json
from pathlib import Path
import unittest
from app.gameengine import GameEngine, UNKNOWN_CARD_ID, ids_from_cards, PlayerState, UNLIMITED_SIZE
from app.gameengine import EventType, GameOverReason
from app.gameengine import GameAction, GamePhase
from app.card_database import CardDatabase
from helpers import RandomOverride, initialize_game_to_third_turn, validate_event, validate_actions, do_bloom, reset_mainstep, add_card_to_hand, do_cheer_step_on_card
from helpers import end_turn, validate_last_event_is_error, validate_last_event_not_error, do_collab_get_events, set_next_die_rolls
from helpers import put_card_in_play, spawn_cheer_on_card, reset_performancestep, generate_deck_with, begin_performance

class Test_hbp01_Support(unittest.TestCase):

    engine : GameEngine
    player1 : str
    player2 : str

    def setUp(self):
        pass

    def test_hbp01_116_not_kanata(self):
        p1deck = generate_deck_with([], {"hBP01-010": 2, "hBP01-116": 3 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        test_card = add_card_to_hand(self, player1, "hBP01-116")
        actions = reset_mainstep(self)
        self.assertTrue(GameAction.MainStepPlaySupport in [action["action_type"] for action in actions])

        # Play it onto the center.
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, choose holomem
        self.assertEqual(len(events), 4)
        validate_event(self, events[0], EventType.EventType_PlaySupportCard, self.player1, {
            "player_id": self.player1,
            "card_id": test_card["game_card_id"],
            "limited": False,
        })
        validate_event(self, events[2], EventType.EventType_Decision_ChooseHolomemForEffect, self.player1, {
            "effect_player_id": self.player1,
        })

        # Pick the center.
        center_id = player1.center[0]["game_card_id"]
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [center_id]
        })
        events = engine.grab_events()
        # Events - move card attachment, main step
        self.assertEqual(len(events), 4)
        validate_event(self, events[0], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "floating",
            "to_zone": "holomem",
            "card_id": test_card['game_card_id'],
        })
        validate_event(self, events[2], EventType.EventType_Decision_MainStep, self.player1, {
            "active_player": self.player1,
        })
        self.assertEqual(player1.center[0]["attached_support"][0]["game_card_id"], test_card["game_card_id"])

        # Now that it is attached, attack and we do +10 damage.
        performer = player1.center[0]
        target = player2.center[0]
        engine.handle_game_message(self.player1, GameAction.MainStepBeginPerformance, {})
        actions = reset_performancestep(self)

        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "performer_id": performer["game_card_id"],
            "art_id": "nunnun",
            "target_id": target["game_card_id"],
        })
        events = engine.grab_events()
        # Events - boost art, perform, damage, end turn, start turn, 2 resets, draw, cheer
        self.assertEqual(len(events), 18)
        validate_event(self, events[0], EventType.EventType_BoostStat, self.player1, {
            "card_id": player1.center[0]["game_card_id"],
            "stat": "power",
            "amount": 10,
        })
        validate_event(self, events[2], EventType.EventType_PerformArt, self.player1, {
            "performer_id": player1.center[0]["game_card_id"],
            "art_id": "nunnun",
            "target_id": player2.center[0]["game_card_id"],
            "power": 40,
        })
        validate_event(self, events[4], EventType.EventType_DamageDealt, self.player1, {
            "target_id": player2.center[0]["game_card_id"],
            "damage": 40,
            "died": False,
            "game_over": False,
            "target_player": self.player2,
            "special": False,
            "life_lost": 0,
            "life_loss_prevented": False,
        })

        # Player 2 turn
        do_cheer_step_on_card(self, player2.center[0])
        actions = reset_mainstep(self)

        # Attack back, since it isn't kanata, no on damage effect.
        engine.handle_game_message(self.player2, GameAction.MainStepBeginPerformance, {})
        actions = reset_performancestep(self)
        engine.handle_game_message(self.player2, GameAction.PerformanceStepUseArt, {
            "performer_id": player2.center[0]["game_card_id"],
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        # Events - perform, damage, end turn, start turn, 2 resets, draw, cheer.
        self.assertEqual(len(events), 16)
        validate_event(self, events[0], EventType.EventType_PerformArt, self.player1, {
            "performer_id": player2.center[0]["game_card_id"],
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
            "power": 30,
        })
        validate_event(self, events[2], EventType.EventType_DamageDealt, self.player1, {
            "target_id": player1.center[0]["game_card_id"],
            "damage": 30,
            "died": False,
            "game_over": False,
            "target_player": self.player1,
            "special": False,
            "life_lost": 0,
            "life_loss_prevented": False,
        })

        # Player 1 turn.
        do_cheer_step_on_card(self, player1.center[0])
        actions = reset_mainstep(self)


    def test_hbp01_116_upao_hits_back(self):
        p1deck = generate_deck_with([], {"hBP01-010": 2, "hBP01-116": 3 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        # Swap out center with 010.
        center_card = add_card_to_hand(self, player1, "hBP01-010")
        center_id = center_card["game_card_id"]
        player1.center = [center_card]
        player1.hand.remove(center_card)
        spawn_cheer_on_card(self, player1, center_id, "white", "w1")

        test_card = add_card_to_hand(self, player1, "hBP01-116")
        actions = reset_mainstep(self)
        self.assertTrue(GameAction.MainStepPlaySupport in [action["action_type"] for action in actions])

        # Play it onto the center.
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, choose holomem
        self.assertEqual(len(events), 4)
        validate_event(self, events[0], EventType.EventType_PlaySupportCard, self.player1, {
            "player_id": self.player1,
            "card_id": test_card["game_card_id"],
            "limited": False,
        })
        validate_event(self, events[2], EventType.EventType_Decision_ChooseHolomemForEffect, self.player1, {
            "effect_player_id": self.player1,
        })

        # Pick the center.
        center_id = player1.center[0]["game_card_id"]
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [center_id]
        })
        events = engine.grab_events()
        # Events - move card attachment, main step
        self.assertEqual(len(events), 4)
        validate_event(self, events[0], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "floating",
            "to_zone": "holomem",
            "card_id": test_card['game_card_id'],
        })
        validate_event(self, events[2], EventType.EventType_Decision_MainStep, self.player1, {
            "active_player": self.player1,
        })
        self.assertEqual(player1.center[0]["attached_support"][0]["game_card_id"], test_card["game_card_id"])

        # Now that it is attached, attack and we do +10 damage.
        performer = player1.center[0]
        target = player2.center[0]
        engine.handle_game_message(self.player1, GameAction.MainStepBeginPerformance, {})
        actions = reset_performancestep(self)

        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "performer_id": performer["game_card_id"],
            "art_id": "imoffnow",
            "target_id": target["game_card_id"],
        })
        events = engine.grab_events()
        # Events - boost art, perform, damage, end turn, start turn, 2 resets, draw, cheer
        self.assertEqual(len(events), 18)
        validate_event(self, events[0], EventType.EventType_BoostStat, self.player1, {
            "card_id": player1.center[0]["game_card_id"],
            "stat": "power",
            "amount": 10,
        })
        validate_event(self, events[2], EventType.EventType_PerformArt, self.player1, {
            "performer_id": player1.center[0]["game_card_id"],
            "art_id": "imoffnow",
            "target_id": player2.center[0]["game_card_id"],
            "power": 30,
        })
        validate_event(self, events[4], EventType.EventType_DamageDealt, self.player1, {
            "target_id": player2.center[0]["game_card_id"],
            "damage": 30,
            "died": False,
            "game_over": False,
            "target_player": self.player2,
            "special": False,
            "life_lost": 0,
            "life_loss_prevented": False,
        })

        # Player 2 turn
        do_cheer_step_on_card(self, player2.center[0])
        actions = reset_mainstep(self)

        # Put a p2 card in collab spot, 2nd nun nunner.
        p2center = player2.center[0]
        p2center_id = p2center["game_card_id"]
        p2collab = player2.backstage[0]
        p2collab_id = p2collab["game_card_id"]
        player2.collab = [p2collab]
        player2.backstage.remove(p2collab)
        spawn_cheer_on_card(self, player2, p2collab_id, "white", "p2w1")

        # Attack back, it is kanata so it WILL do damage.
        engine.handle_game_message(self.player2, GameAction.MainStepBeginPerformance, {})
        actions = reset_performancestep(self)
        print("---- SUBMIT PROBLEMATIC ART")
        engine.handle_game_message(self.player2, GameAction.PerformanceStepUseArt, {
            "performer_id": player2.center[0]["game_card_id"],
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        # Events - perform, on_damage revenge damage, damage, performance step
        self.assertEqual(len(events), 8)
        validate_event(self, events[0], EventType.EventType_PerformArt, self.player1, {
            "performer_id": p2center_id,
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
            "power": 30,
        })
        validate_event(self, events[2], EventType.EventType_DamageDealt, self.player1, {
            "target_id": p2center_id,
            "damage": 20,
            "died": False,
            "game_over": False,
            "target_player": self.player2,
            "special": True,
            "life_lost": 0,
            "life_loss_prevented": False,
        })
        validate_event(self, events[4], EventType.EventType_DamageDealt, self.player1, {
            "target_id": player1.center[0]["game_card_id"],
            "damage": 30,
            "died": False,
            "game_over": False,
            "target_player": self.player1,
            "special": False,
            "life_lost": 0,
            "life_loss_prevented": False,
        })
        validate_event(self, events[6], EventType.EventType_Decision_PerformanceStep, self.player1, {
            "active_player": self.player2,
        })

        # Now attack with collab parnter.
        # No upao revenge this time.
        # Since the test would be annoying if kanata died, heal her.
        player1.center[0]["damage"] = 0
        engine.handle_game_message(self.player2, GameAction.PerformanceStepUseArt, {
            "performer_id": p2collab_id,
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        # Events - perform, damage, end turn, start turn, 2 resets, draw, cheer
        self.assertEqual(len(events), 16)
        validate_event(self, events[0], EventType.EventType_PerformArt, self.player1, {
            "performer_id": p2collab_id,
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
            "power": 30,
        })
        validate_event(self, events[2], EventType.EventType_DamageDealt, self.player1, {
            "target_id": player1.center[0]["game_card_id"],
            "damage": 30,
            "died": False,
            "game_over": False,
            "target_player": self.player1,
            "special": False,
            "life_lost": 0,
            "life_loss_prevented": False,
        })

        # Player 1 turn.
        do_cheer_step_on_card(self, player1.center[0])
        actions = reset_mainstep(self)
        self.assertEqual(p2center["damage"], 50)

        # To wrap up the test, we'll have p2 center die as it attacks.
        # Before that, give p1 a collab partner so the performance step doesn't end right away.
        player1.collab = [player1.backstage[0]]
        player1.backstage = []
        end_turn(self)
        p1center_id = player1.center[0]["game_card_id"]
        p1center = player1.center[0]
        self.assertEqual(p1center["damage"], 30) # From one nunnun
        do_cheer_step_on_card(self, player2.center[0])
        # Give p2 a collab again.
        player2.collab = [player2.backstage[0]]
        player2.backstage = []
        engine.handle_game_message(self.player2, GameAction.MainStepBeginPerformance, {})
        events = engine.grab_events()
        actions = reset_performancestep(self)
        engine.handle_game_message(self.player2, GameAction.PerformanceStepUseArt, {
            "performer_id": p2center_id,
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        # Events - perform, on damage = attacker dies first?, send cheer?
        self.assertEqual(len(events), 6)
        validate_event(self, events[0], EventType.EventType_PerformArt, self.player1, {
            "performer_id": p2center_id,
            "art_id": "nunnun",
            "target_id": player1.center[0]["game_card_id"],
            "power": 30,
        })
        # Revenge damage
        validate_event(self, events[2], EventType.EventType_DamageDealt, self.player1, {
            "target_id": p2center_id,
            "damage": 20,
            "died": True,
            "game_over": False,
            "target_player": self.player2,
            "special": True,
            "life_lost": 1,
            "life_loss_prevented": False,
        })
        validate_event(self, events[4], EventType.EventType_Decision_SendCheer, self.player1, {
            "effect_player_id": self.player2,
            "amount_min": 1,
            "amount_max": 1,
            "from_zone": "life",
            "to_zone": "holomem",
        })
        from_options = events[4]["from_options"]
        to_options = events[4]["to_options"]
        cheer_placement = {
            from_options[0]: player2.collab[0]["game_card_id"]
        }

        # P2 distributes cheer.
        self.engine.handle_game_message(self.player2, GameAction.EffectResolution_MoveCheerBetweenHolomems, {"placements": cheer_placement })
        events = self.engine.grab_events()
        # Events - move cheer, continue the attack and now damage dealt to p1 center, and send cheer.
        self.assertEqual(len(events), 6)
        validate_event(self, events[0], EventType.EventType_MoveAttachedCard, self.player1, {
            "owning_player_id": self.player2,
            "from_holomem_id": "life",
            "to_holomem_id": player2.collab[0]["game_card_id"],
            "attached_id": from_options[0],
        })
        validate_event(self, events[2], EventType.EventType_DamageDealt, self.player1, {
            "target_id": p1center_id,
            "damage": 30,
            "died": True,
            "game_over": False,
            "target_player": self.player1,
            "special": False,
            "life_lost": 1,
            "life_loss_prevented": False,
        })
        validate_event(self, events[4], EventType.EventType_Decision_SendCheer, self.player1, {
            "effect_player_id": self.player1,
            "amount_min": 1,
            "amount_max": 1,
            "from_zone": "life",
            "to_zone": "holomem",
        })

        # P1 distributes
        from_options = events[4]["from_options"]
        to_options = events[4]["to_options"]
        cheer_placement = {
            from_options[0]: player1.collab[0]["game_card_id"]
        }
        self.engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {"placements": cheer_placement })
        events = self.engine.grab_events()
        # events - move cheer, performance step
        self.assertEqual(len(events), 4)
        validate_event(self, events[0], EventType.EventType_MoveAttachedCard, self.player1, {
            "owning_player_id": self.player1,
            "from_holomem_id": "life",
            "to_holomem_id": player1.collab[0]["game_card_id"],
            "attached_id": from_options[0],
        })
        validate_event(self, events[2], EventType.EventType_Decision_PerformanceStep, self.player1, {
            "active_player": self.player2,
        })
        actions = reset_performancestep(self)
        # Still in performance step, because both collabs are present.
        self.assertEqual(len(player1.center), 0)
        self.assertEqual(len(player2.center), 0)

    def test_hbp01_106_switch_skipresting(self):
        p1deck = generate_deck_with([], {"hBP01-106": 2 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        """Test"""
        player1.backstage[1]["resting"] = True
        test_card = add_card_to_hand(self, player1, "hBP01-106", True)
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, choose holomem
        self.assertEqual(len(events), 4)
        validate_event(self, events[2], EventType.EventType_Decision_SwapHolomemToCenter, self.player1, {
            "effect_player_id": self.player1,
        })
        cards_can_choose = events[2]["cards_can_choose"]
        expected = [player1.backstage[0], player1.backstage[2], player1.backstage[3], player1.backstage[4]]
        self.assertListEqual(cards_can_choose, [card["game_card_id"] for card in expected])
        # Do the swap
        chosen_id = player1.backstage[0]["game_card_id"]
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [player1.backstage[0]["game_card_id"]],
        })
        events = self.engine.grab_events()
        actions = reset_mainstep(self)
        self.assertEqual(player1.center[0]["game_card_id"], chosen_id)

    def test_hbp01_107_choosecards_from_archive_to_cheer_deck_no_archived(self):
        p1deck = generate_deck_with([], {"hBP01-107": 2 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        """Test"""
        test_card = add_card_to_hand(self, player1, "hBP01-107", True)
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, choose cards from archive
        self.assertEqual(len(events), 4)
        validate_event(self, events[2], EventType.EventType_Decision_ChooseCards, self.player1, {
            "effect_player_id": self.player1,
            "from_zone": "archive",
            "to_zone": "cheer_deck",
            "amount_min": 0,
            "amount_max": 3,
            "reveal_chosen": True,
            "remaining_cards_action": "nothing",
        })
        cards_can_choose = events[2]["cards_can_choose"]
        self.assertEqual(len(cards_can_choose), 0)
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [],
        })
        events = self.engine.grab_events()
        self.assertEqual(len(events), 4)
        # Discard
        validate_event(self, events[0], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "floating",
            "to_zone": "archive",
            "card_id": test_card["game_card_id"],
        })
        actions = reset_mainstep(self)


    def test_hbp01_107_choosecards_from_archive_to_cheer_deck_movecheer(self):
        p1deck = generate_deck_with([], {"hBP01-107": 2 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        """Test"""
        # Dump some cheer.
        player1.archive = player1.cheer_deck[:5]
        player1.cheer_deck = player1.cheer_deck[5:]
        test_card = add_card_to_hand(self, player1, "hBP01-107", True)
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, choose cards from archive
        self.assertEqual(len(events), 4)
        validate_event(self, events[2], EventType.EventType_Decision_ChooseCards, self.player1, {
            "effect_player_id": self.player1,
            "from_zone": "archive",
            "to_zone": "cheer_deck",
            "amount_min": 1,
            "amount_max": 3,
            "reveal_chosen": True,
            "remaining_cards_action": "nothing",
        })
        cards_can_choose = events[2]["cards_can_choose"]
        self.assertEqual(len(cards_can_choose), 5)
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": cards_can_choose[:3],
        })
        events = self.engine.grab_events()
        self.assertEqual(len(events), 10)
        # Move card x 3
        validate_event(self, events[0], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "archive",
            "to_zone": "cheer_deck",
            "card_id": cards_can_choose[0],
        })
        validate_event(self, events[2], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "archive",
            "to_zone": "cheer_deck",
            "card_id": cards_can_choose[1],
        })
        validate_event(self, events[4], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "archive",
            "to_zone": "cheer_deck",
            "card_id": cards_can_choose[2],
        })
        # Discard
        validate_event(self, events[6], EventType.EventType_MoveCard, self.player1, {
            "moving_player_id": self.player1,
            "from_zone": "floating",
            "to_zone": "archive",
            "card_id": test_card["game_card_id"],
        })
        actions = reset_mainstep(self)


    def test_hbp01_110_wrongoshi(self):
        p1deck = generate_deck_with("", {"hBP01-110": 2 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        """Test"""
        set_next_die_rolls(self, [1,1])

        # Remove all cheer from opponent.
        player2.center[0]["attached_cheer"] = []

        test_card = add_card_to_hand(self, player1, "hBP01-110", True)
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, roll die, discard, main step
        self.assertEqual(len(events), 8)
        validate_event(self, events[2], EventType.EventType_RollDie, self.player1, {
            "effect_player_id": self.player1,
            "die_result": 1,
            "rigged": False,
        })
        actions = reset_mainstep(self)

    def test_hbp01_110_passchoose(self):
        p1deck = generate_deck_with("hBP01-002", {"hBP01-110": 2 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        """Test"""
        set_next_die_rolls(self, [1,1])

        w1 = spawn_cheer_on_card(self, player2, player2.center[0]["game_card_id"], "white", "w1")
        self.assertEqual(len(player2.center[0]["attached_cheer"]), 2)

        test_card = add_card_to_hand(self, player1, "hBP01-110", True)
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, decision
        self.assertEqual(len(events), 4)
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MakeChoice, {
            "choice_index": 1,
        })
        # Roll die, send cheer
        events = self.engine.grab_events()
        self.assertEqual(len(events), 4)
        validate_event(self, events[0], EventType.EventType_RollDie, self.player1, {
            "effect_player_id": self.player1,
            "die_result": 1,
            "rigged": False,
        })
        validate_event(self, events[2], EventType.EventType_Decision_SendCheer, self.player1, {
            "effect_player_id": self.player1,
            "amount_min": 1,
            "amount_max": 1,
            "from_zone": "opponent_holomem",
            "to_zone": "archive",
        })
        from_options = events[2]["from_options"]
        self.assertEqual(len(from_options), 2)
        placements = {
            w1["game_card_id"]: "archive"
        }
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
            "placements": placements
        })
        events = self.engine.grab_events()
        # Events - move cheer, discard, main step
        self.assertEqual(len(events), 6)
        self.assertEqual(player2.archive[0]["game_card_id"], w1["game_card_id"])
        actions = reset_mainstep(self)


    def test_hbp01_110_useoshi_cantusetwice(self):
        p1deck = generate_deck_with("hBP01-002", {"hBP01-110": 2 }, [])
        initialize_game_to_third_turn(self, p1deck)
        player1 : PlayerState = self.engine.get_player(self.players[0]["player_id"])
        player2 : PlayerState = self.engine.get_player(self.players[1]["player_id"])
        engine = self.engine
        self.assertEqual(engine.active_player_id, self.player1)
        # Has 004 and 2 005 in hand.
        # Center is 003
        # Backstage has 3 003 and 2 004.

        """Test"""
        set_next_die_rolls(self, [1,1])
        player1.generate_holopower(2)

        w1 = spawn_cheer_on_card(self, player2, player2.center[0]["game_card_id"], "white", "w1")
        w2 = spawn_cheer_on_card(self, player2, player2.backstage[0]["game_card_id"], "white", "w2")
        w3 = spawn_cheer_on_card(self, player2, player2.backstage[1]["game_card_id"], "white", "w3")
        self.assertEqual(len(player2.center[0]["attached_cheer"]), 2)

        test_card = add_card_to_hand(self, player1, "hBP01-110", True)
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, choice
        self.assertEqual(len(events), 4)
        validate_event(self, events[2], EventType.EventType_Decision_Choice, self.player1, {
            "effect_player_id": self.player1,
        })
        # Use the ability.
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MakeChoice, {
            "choice_index": 0,
        })
        events = self.engine.grab_events()
        # Events - choose 2 cheer.
        self.assertEqual(len(events), 2)
        validate_event(self, events[0], EventType.EventType_Decision_SendCheer, self.player1, {
            "effect_player_id": self.player1,
            "amount_min": 2,
            "amount_max": 2,
            "from_zone": "opponent_holomem",
            "to_zone": "archive",
        })
        # Because this is the center holomem only ability, its only 2 cheer.
        from_options = events[0]["from_options"]
        self.assertEqual(len(from_options), 2)
        placements = {
            from_options[0]: "archive",
            from_options[1]: "archive"
        }
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
            "placements": placements
        })
        # Move 2 cheer, discard, main step.
        events = self.engine.grab_events()
        self.assertEqual(len(events), 8)
        self.assertEqual(len(player2.archive), 2)
        self.assertEqual(player2.archive[0]["game_card_id"], from_options[1])
        self.assertEqual(player2.archive[1]["game_card_id"], from_options[0])
        actions = reset_mainstep(self)

        # Next up, remove the limit flag and try again.
        player1.used_limited_this_turn = False
        test_card = add_card_to_hand(self, player1, "hBP01-110", True)

        # Play the card.
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = self.engine.grab_events()
        # Events - play support, roll die because already used oshi power, choose cheer
        self.assertEqual(len(events), 6)
        validate_event(self, events[2], EventType.EventType_RollDie, self.player1, {
            "effect_player_id": self.player1,
            "die_result": 1,
            "rigged": False,
        })
        validate_event(self, events[4], EventType.EventType_Decision_SendCheer, self.player1, {
            "effect_player_id": self.player1,
            "amount_min": 1,
            "amount_max": 1,
            "from_zone": "opponent_holomem",
            "to_zone": "archive",
        })
        from_options = events[4]["from_options"]
        self.assertEqual(len(from_options), 2)
        # This should be the cheer on the 2 backstage members.
        self.assertEqual(from_options[0], player2.backstage[0]["attached_cheer"][0]["game_card_id"])
        self.assertEqual(from_options[1], player2.backstage[1]["attached_cheer"][0]["game_card_id"])

if __name__ == '__main__':
    unittest.main()
