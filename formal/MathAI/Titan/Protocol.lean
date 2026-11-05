import Mathlib

/-!
Titan protocol-state model, not a proof of ML-KEM/ML-DSA security.
The model captures transcript binding, independent key identifiers,
hybrid acceptance preconditions, and a fail-closed downgrade transition.
-/

namespace MathAI.Titan

inductive Phase where
  | fresh
  | transcriptBound
  | kemEstablished
  | signatureBound
  | hybridAccepted
  deriving DecidableEq, Repr

inductive Event where
  | bindTranscript
  | establishKem (keyId : Nat)
  | bindSignature (keyId : Nat)
  | acceptHybrid
  | downgrade
  deriving DecidableEq, Repr

structure State where
  phase : Phase
  transcriptBound : Bool
  kemKeyId : Option Nat
  signatureKeyId : Option Nat
  downgradeLocked : Bool
  deriving DecidableEq, Repr

def initial : State :=
  ⟨.fresh, false, none, none, false⟩

def step (s : State) : Event → Option State
  | .bindTranscript =>
      if s.phase == .fresh then
        some ⟨.transcriptBound, true, none, none, true⟩
      else none
  | .establishKem keyId =>
      if s.transcriptBound && s.phase == .transcriptBound then
        some ⟨.kemEstablished, true, some keyId, none, true⟩
      else none
  | .bindSignature keyId =>
      if s.transcriptBound && s.phase == .kemEstablished &&
          s.kemKeyId != some keyId then
        some ⟨.signatureBound, true, s.kemKeyId, some keyId, true⟩
      else none
  | .acceptHybrid =>
      if s.transcriptBound && s.kemKeyId.isSome &&
          s.signatureKeyId.isSome && s.downgradeLocked &&
          s.phase == .signatureBound then
        some ⟨.hybridAccepted, true, s.kemKeyId, s.signatureKeyId, true⟩
      else none
  | .downgrade => none

def keySeparated (s : State) : Prop :=
  s.kemKeyId.isSome ∧ s.signatureKeyId.isSome →
    s.kemKeyId ≠ s.signatureKeyId

def hybridReady (s : State) : Prop :=
  s.phase == .hybridAccepted →
    s.transcriptBound = true ∧ s.downgradeLocked = true ∧ keySeparated s

theorem downgrade_never_accepted (s : State) :
    step s .downgrade = none := by
  rfl

theorem kem_requires_transcript (s : State) (keyId : Nat) (next : State)
    (h : step s (.establishKem keyId) = some next) :
    s.transcriptBound = true := by
  simp [step] at h
  rcases h with ⟨⟨hbound, _⟩, rfl⟩
  exact hbound

theorem signature_key_is_separate (s : State) (keyId : Nat) (next : State)
    (h : step s (.bindSignature keyId) = some next) :
    s.kemKeyId ≠ some keyId := by
  simp [step] at h
  rcases h with ⟨⟨⟨_, _⟩, hseparate⟩, rfl⟩
  exact hseparate

theorem accepted_hybrid_is_transcript_bound (s : State) (next : State)
    (h : step s .acceptHybrid = some next) :
    next.transcriptBound = true ∧ next.downgradeLocked = true := by
  simp [step] at h
  rcases h with ⟨_, rfl⟩
  exact ⟨rfl, rfl⟩

theorem hybrid_acceptance_requires_both_keys (s : State) (next : State)
    (h : step s .acceptHybrid = some next) :
    next.kemKeyId.isSome ∧ next.signatureKeyId.isSome := by
  simp [step] at h
  rcases h with ⟨⟨⟨⟨⟨_, hkem⟩, hsignature⟩, _⟩, _⟩, rfl⟩
  exact ⟨hkem, hsignature⟩

end MathAI.Titan
