#![no_std]
use soroban_sdk::{
    contract, contracterror, contractimpl, contracttype, symbol_short, token, Address, BytesN, Env,
};

const TTL_THRESHOLD: u32 = 17_280;
const TTL_EXTEND: u32 = 518_400;
const MAX_PAYMENT_WINDOW: u64 = 86_400;

#[contracttype]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum State {
    AwaitingFunding,
    Funded,
    PaymentClaimed,
    Disputed,
    Released,
    Refunded,
}

#[contracttype]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Terms {
    pub seller: Address,
    pub buyer: Address,
    pub resolver: Address,
    pub token: Address,
    pub amount: i128,
    pub ngn_kobo: i128,
    pub deadline: u64,
    pub reference: BytesN<32>,
}

#[contracttype]
#[derive(Clone)]
enum Key {
    Terms,
    State,
}

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum Error {
    InvalidTerms = 1,
    InvalidState = 2,
    DeadlinePassed = 3,
    TooEarly = 4,
    Unauthorized = 5,
}

#[contract]
pub struct Escrow;

fn bump(env: &Env) {
    env.storage()
        .instance()
        .extend_ttl(TTL_THRESHOLD, TTL_EXTEND);
}
fn terms(env: &Env) -> Terms {
    env.storage().instance().get(&Key::Terms).unwrap()
}
fn state(env: &Env) -> State {
    env.storage().instance().get(&Key::State).unwrap()
}
fn set_state(env: &Env, next: State) {
    env.storage().instance().set(&Key::State, &next);
    bump(env);
    env.events().publish((symbol_short!("state"),), next);
}
fn payout(env: &Env, t: &Terms, buyer_wins: bool) {
    // Contract invocation rollback makes state and token transfer atomic.
    set_state(
        env,
        if buyer_wins {
            State::Released
        } else {
            State::Refunded
        },
    );
    let recipient = if buyer_wins { &t.buyer } else { &t.seller };
    token::Client::new(env, &t.token).transfer(
        &env.current_contract_address(),
        recipient,
        &t.amount,
    );
}

#[contractimpl]
impl Escrow {
    pub fn __constructor(env: Env, t: Terms) -> Result<(), Error> {
        let now = env.ledger().timestamp();
        if t.amount <= 0
            || t.ngn_kobo <= 0
            || t.deadline <= now
            || t.deadline - now > MAX_PAYMENT_WINDOW
            || t.seller == t.buyer
            || t.seller == t.resolver
            || t.buyer == t.resolver
            || t.seller == env.current_contract_address()
            || t.buyer == env.current_contract_address()
            || t.resolver == env.current_contract_address()
            || t.token == env.current_contract_address()
        {
            return Err(Error::InvalidTerms);
        }
        env.storage().instance().set(&Key::Terms, &t);
        set_state(&env, State::AwaitingFunding);
        Ok(())
    }

    pub fn fund(env: Env) -> Result<(), Error> {
        let t = terms(&env);
        t.seller.require_auth();
        if state(&env) != State::AwaitingFunding {
            return Err(Error::InvalidState);
        }
        if env.ledger().timestamp() >= t.deadline {
            return Err(Error::DeadlinePassed);
        }
        set_state(&env, State::Funded);
        token::Client::new(&env, &t.token).transfer(
            &t.seller,
            &env.current_contract_address(),
            &t.amount,
        );
        Ok(())
    }

    pub fn claim_payment(env: Env) -> Result<(), Error> {
        let t = terms(&env);
        t.buyer.require_auth();
        if state(&env) != State::Funded {
            return Err(Error::InvalidState);
        }
        if env.ledger().timestamp() >= t.deadline {
            return Err(Error::DeadlinePassed);
        }
        set_state(&env, State::PaymentClaimed);
        Ok(())
    }

    pub fn confirm_receipt(env: Env) -> Result<(), Error> {
        let t = terms(&env);
        t.seller.require_auth();
        if state(&env) != State::PaymentClaimed {
            return Err(Error::InvalidState);
        }
        payout(&env, &t, true);
        Ok(())
    }

    pub fn expire(env: Env) -> Result<(), Error> {
        let t = terms(&env);
        if state(&env) != State::Funded {
            return Err(Error::InvalidState);
        }
        if env.ledger().timestamp() < t.deadline {
            return Err(Error::TooEarly);
        }
        payout(&env, &t, false);
        Ok(())
    }

    pub fn open_dispute(env: Env, actor: Address) -> Result<(), Error> {
        let t = terms(&env);
        if actor != t.buyer && actor != t.seller {
            return Err(Error::Unauthorized);
        }
        actor.require_auth();
        if state(&env) != State::Funded && state(&env) != State::PaymentClaimed {
            return Err(Error::InvalidState);
        }
        set_state(&env, State::Disputed);
        Ok(())
    }

    pub fn resolve(env: Env, buyer_wins: bool) -> Result<(), Error> {
        let t = terms(&env);
        t.resolver.require_auth();
        if state(&env) != State::Disputed {
            return Err(Error::InvalidState);
        }
        payout(&env, &t, buyer_wins);
        Ok(())
    }

    pub fn get_state(env: Env) -> State {
        state(&env)
    }
    pub fn get_terms(env: Env) -> Terms {
        terms(&env)
    }
    pub fn bump_ttl(env: Env) {
        bump(&env);
    }
}

#[cfg(test)]
mod test;
