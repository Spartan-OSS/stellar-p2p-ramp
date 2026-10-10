extern crate std;
use super::*;
use soroban_sdk::testutils::{Address as _, Ledger};

struct Fixture {
    env: Env,
    id: Address,
    t: Terms,
}
impl Fixture {
    fn new() -> Self {
        let env = Env::default();
        env.mock_all_auths();
        env.ledger().with_mut(|l| l.timestamp = 100);
        let admin = Address::generate(&env);
        let token = env
            .register_stellar_asset_contract_v2(admin.clone())
            .address();
        let t = Terms {
            seller: Address::generate(&env),
            buyer: Address::generate(&env),
            resolver: Address::generate(&env),
            token: token.clone(),
            amount: 1000,
            ngn_kobo: 15000,
            deadline: 200,
            reference: BytesN::from_array(&env, &[1; 32]),
        };
        token::StellarAssetClient::new(&env, &token).mint(&t.seller, &3000);
        let id = env.register(Escrow, (t.clone(),));
        Self { env, id, t }
    }
    fn client(&self) -> EscrowClient<'_> {
        EscrowClient::new(&self.env, &self.id)
    }
    fn balance(&self, a: &Address) -> i128 {
        token::Client::new(&self.env, &self.t.token).balance(a)
    }
}

#[test]
fn release_conserves_tokens_and_cannot_repeat() {
    let f = Fixture::new();
    let c = f.client();
    c.fund();
    c.claim_payment();
    c.confirm_receipt();
    assert_eq!(c.get_state(), State::Released);
    assert_eq!(f.balance(&f.t.seller), 2000);
    assert_eq!(f.balance(&f.t.buyer), 1000);
    assert_eq!(f.balance(&f.id), 0);
    assert!(c.try_confirm_receipt().is_err());
    assert!(c.try_fund().is_err());
}

#[test]
fn disputed_refund_and_release_have_fixed_recipients() {
    for wins in [false, true] {
        let f = Fixture::new();
        let c = f.client();
        c.fund();
        c.claim_payment();
        c.open_dispute(&f.t.buyer);
        assert!(c.try_confirm_receipt().is_err());
        assert!(c.try_expire().is_err());
        c.resolve(&wins);
        assert_eq!(f.balance(&f.t.resolver), 0);
        assert_eq!(f.balance(&f.t.buyer), if wins { 1000 } else { 0 });
        assert_eq!(f.balance(&f.t.seller), if wins { 2000 } else { 3000 });
        assert_eq!(f.balance(&f.id), 0);
        assert!(c.try_resolve(&wins).is_err());
    }
}

#[test]
fn deadline_boundary_and_payment_claim_protection() {
    let f = Fixture::new();
    let c = f.client();
    c.fund();
    assert!(c.try_expire().is_err());
    f.env.ledger().with_mut(|l| l.timestamp = 200);
    assert!(c.try_claim_payment().is_err());
    c.expire();
    assert_eq!(c.get_state(), State::Refunded);
    let g = Fixture::new();
    let d = g.client();
    d.fund();
    d.claim_payment();
    g.env.ledger().with_mut(|l| l.timestamp = 500);
    assert!(d.try_expire().is_err());
    d.confirm_receipt();
}

#[test]
fn reject_nonparticipant_dispute_and_undisputed_resolution() {
    let f = Fixture::new();
    let c = f.client();
    c.fund();
    assert!(c.try_open_dispute(&f.t.resolver).is_err());
    assert!(c.try_open_dispute(&Address::generate(&f.env)).is_err());
    assert!(c.try_resolve(&true).is_err());
    assert!(c.try_confirm_receipt().is_err());
}

#[test]
fn funding_failure_rolls_back_state() {
    let f = Fixture::new();
    let c = f.client();
    token::Client::new(&f.env, &f.t.token).transfer(&f.t.seller, &f.t.buyer, &3000);
    assert!(c.try_fund().is_err());
    assert_eq!(c.get_state(), State::AwaitingFunding);
}

#[test]
fn no_authorization_cannot_fund() {
    let f = Fixture::new();
    f.env.mock_auths(&[]);
    assert!(f.client().try_fund().is_err());
    assert_eq!(f.client().get_state(), State::AwaitingFunding);
}

#[test]
fn no_authorization_cannot_claim_release_or_resolve() {
    let f = Fixture::new();
    let c = f.client();
    c.fund();
    f.env.mock_auths(&[]);
    assert!(c.try_claim_payment().is_err());
    f.env.mock_all_auths();
    c.claim_payment();
    f.env.mock_auths(&[]);
    assert!(c.try_confirm_receipt().is_err());
    f.env.mock_all_auths();
    c.open_dispute(&f.t.buyer);
    f.env.mock_auths(&[]);
    assert!(c.try_resolve(&true).is_err());
}

#[test]
fn constructor_rejects_invalid_amount_deadline_and_roles() {
    for invalid in 0..4 {
        let f = Fixture::new();
        let mut t = f.t.clone();
        match invalid {
            0 => t.amount = 0,
            1 => t.deadline = 100,
            2 => t.deadline = 100 + 86_401,
            _ => t.resolver = t.buyer.clone(),
        }
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            f.env.register(Escrow, (t,))
        }));
        assert!(result.is_err());
    }
}

#[test]
fn expired_unfunded_contract_cannot_take_tokens() {
    let f = Fixture::new();
    f.env.ledger().with_mut(|l| l.timestamp = 200);
    assert!(f.client().try_fund().is_err());
    assert_eq!(f.balance(&f.t.seller), 3000);
}

#[test]
fn no_authorization_cannot_open_participant_dispute() {
    let f = Fixture::new();
    let c = f.client();
    c.fund();
    f.env.mock_auths(&[]);
    assert!(c.try_open_dispute(&f.t.buyer).is_err());
    assert_eq!(c.get_state(), State::Funded);
}
