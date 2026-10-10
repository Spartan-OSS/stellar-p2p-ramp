import unittest
from dataclasses import replace
from stellar_p2p.domain import Action, InvalidTransition, State, Trade, transition


class TradeTests(unittest.TestCase):
    def setUp(self):
        self.trade = Trade("t1", "seller", "buyer", "resolver", 100, 15000, 1000)

    def test_payment_then_release(self):
        paid = transition(self.trade, Action.CLAIM_PAYMENT, "buyer", 999)
        released = transition(paid, Action.CONFIRM_RECEIPT, "seller", 1001)
        self.assertEqual(released.state, State.RELEASED)
        self.assertEqual(self.trade.state, State.FUNDED)

    def test_only_buyer_claims_payment(self):
        for actor in ["seller", "resolver", "stranger"]:
            with self.assertRaises(InvalidTransition):
                transition(self.trade, Action.CLAIM_PAYMENT, actor, 999)

    def test_boundary_expiry(self):
        with self.assertRaises(InvalidTransition):
            transition(self.trade, Action.EXPIRE, "anyone", 999)
        self.assertEqual(transition(self.trade, Action.EXPIRE, "anyone", 1000).state, State.REFUNDED)
        with self.assertRaises(InvalidTransition):
            transition(self.trade, Action.CLAIM_PAYMENT, "buyer", 1000)

    def test_payment_claim_blocks_timeout_refund(self):
        paid = transition(self.trade, Action.CLAIM_PAYMENT, "buyer", 900)
        with self.assertRaises(InvalidTransition):
            transition(paid, Action.EXPIRE, "seller", 2000)

    def test_dispute_blocks_release_and_expiry(self):
        disputed = transition(self.trade, Action.DISPUTE, "buyer", 1100)
        for action in [Action.EXPIRE, Action.CONFIRM_RECEIPT]:
            with self.assertRaises(InvalidTransition):
                transition(disputed, action, "seller", 1200)

    def test_only_resolver_decides_dispute(self):
        disputed = transition(self.trade, Action.DISPUTE, "seller", 900)
        for actor in ["buyer", "seller", "stranger"]:
            with self.assertRaises(InvalidTransition):
                transition(disputed, Action.RESOLVE_BUYER, actor, 1000)
        for action, state in [(Action.RESOLVE_BUYER, State.RELEASED), (Action.RESOLVE_SELLER, State.REFUNDED)]:
            self.assertEqual(transition(disputed, action, "resolver", 1000).state, state)

    def test_terminal_states_reject_every_action(self):
        for state in [State.RELEASED, State.REFUNDED]:
            for action in Action:
                for actor in ["buyer", "seller", "resolver"]:
                    with self.assertRaises(InvalidTransition):
                        transition(replace(self.trade, state=state), action, actor, 2000)

    def test_reject_invalid_trade(self):
        for kwargs in [{"usdc_units": 0}, {"ngn_kobo": 1.1}, {"resolver": "buyer"}, {"payment_deadline": True}]:
            with self.assertRaises(ValueError):
                replace(self.trade, **kwargs)

    def test_resolver_cannot_release_undisputed_trade(self):
        with self.assertRaises(InvalidTransition):
            transition(self.trade, Action.RESOLVE_BUYER, "resolver", 900)


if __name__ == "__main__":
    unittest.main()
