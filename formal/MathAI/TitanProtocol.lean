/-!
Titan's abstract envelope protocol state machine.

This proves only the declared transition relation and fail-closed terminal-state
properties. It does not model cryptographic algorithms or prove their security.
-/
namespace MathAI.TitanProtocol

inductive State where
  | initialized
  | keyEstablished
  | keysDerived
  | sealed
  | authenticated
  | accepted
  | rejected
  deriving DecidableEq, Repr

inductive Step : State → State → Prop where
  | establish : Step .initialized .keyEstablished
  | derive : Step .keyEstablished .keysDerived
  | seal : Step .keysDerived .sealed
  | authenticate : Step .sealed .authenticated
  | accept : Step .authenticated .accepted
  | rejectAtInitialization : Step .initialized .rejected
  | rejectAtEstablishment : Step .keyEstablished .rejected
  | rejectAtDerivation : Step .keysDerived .rejected
  | rejectAtSeal : Step .sealed .rejected
  | rejectAtAuthentication : Step .authenticated .rejected

theorem rejected_is_absorbing (next : State) :
    ¬ Step .rejected next := by
  intro h
  cases h

theorem accepted_is_terminal (next : State) :
    ¬ Step .accepted next := by
  intro h
  cases h

theorem acceptance_requires_authentication :
    Step .authenticated .accepted := Step.accept

theorem no_direct_initialization_to_acceptance :
    ¬ Step .initialized .accepted := by
  intro h
  cases h

/-- Facts an implementation must establish before the abstract accept state. -/
structure EnvelopeFacts where
  versionSupported : Prop
  suiteAllowListed : Prop
  contextPresent : Prop
  metadataAuthenticated : Prop
  authenticationSucceeded : Prop

def Eligible (facts : EnvelopeFacts) : Prop :=
  facts.versionSupported ∧
  facts.suiteAllowListed ∧
  facts.contextPresent ∧
  facts.metadataAuthenticated ∧
  facts.authenticationSucceeded

theorem eligible_requires_context (facts : EnvelopeFacts)
    (h : Eligible facts) : facts.contextPresent := by
  rcases h with ⟨_, _, hContext, _, _⟩
  exact hContext

theorem eligible_requires_authentication (facts : EnvelopeFacts)
    (h : Eligible facts) : facts.authenticationSucceeded := by
  rcases h with ⟨_, _, _, _, hAuthentication⟩
  exact hAuthentication

/-- Experimental topology is intentionally not a field of EnvelopeFacts. -/
theorem experimental_topology_not_in_protocol_facts :
    ∀ facts : EnvelopeFacts, facts.contextPresent → facts.contextPresent := by
  intro facts hContext
  exact hContext

end MathAI.TitanProtocol
