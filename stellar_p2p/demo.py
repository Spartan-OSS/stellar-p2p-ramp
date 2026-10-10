from .domain import Action, Trade, transition


def main():
    trade = Trade("demo-1", "seller", "buyer", "resolver", 1_000_000_000, 15_000_000, 1000)
    print("SIMULATION ONLY: 100 USDC for NGN 150,000 at an illustrative rate")
    print(trade.state.value)
    trade = transition(trade, Action.CLAIM_PAYMENT, "buyer", 900)
    print(trade.state.value)
    trade = transition(trade, Action.CONFIRM_RECEIPT, "seller", 1100)
    print(trade.state.value)


if __name__ == "__main__":
    main()
