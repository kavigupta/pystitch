
Require Import Frap.

Section programs.

Variable var : Set.

Variable expr : Set.

Variable effect : Set.

Variable value : Set.

Variable truthy : value -> bool.

Definition environment := list (var * value).

(* Fix this so it catches red undant variables *)
Definition equal_env := fun (x : environment) y => x = y.

Variable exec_e : environment -> expr -> value -> list effect -> Prop.

Inductive prog :=
  | prog_e : expr -> prog
  | prog_a : var -> expr -> prog
  (* add multi-assignment *)
  | prog_s : prog -> prog -> prog
  | prog_i : expr -> prog -> prog -> prog
  (* | prog_w : expr -> prog -> prog -> prog *)
  | prog_b : prog
  | prog_c : prog
  | prog_r : expr -> prog
  (* add while/for/try/def *)
.

Inductive continuation :=
  | normal : continuation
  | break : continuation
  | continue : continuation
  | returns : value -> continuation
.

Inductive exec_p : environment -> prog -> environment -> list effect -> continuation -> Prop :=
  | exec_p_e
    : forall env_1 env_2 effs e x,
      exec_e env_1 e x effs -> equal_env env_1 env_2 -> exec_p env_1 (prog_e e) env_2 effs normal
  | exec_p_a
    : forall env_1 env_2 effs v e x,
      exec_e env_1 e x effs -> env_2 = cons (v, x) env_1 -> exec_p env_1 (prog_a v e) env_2 effs normal
  | exec_p_s_n
    : forall env_1 env_2 effs p_1 p_2 c env_inter eff_1 eff_2,
      exec_p env_1 p_1 env_inter eff_1 normal
       -> exec_p env_inter p_2 env_2 eff_2 c
       -> app eff_1 eff_2 = effs
       -> exec_p env_1 (prog_s p_1 p_2) env_2 effs c
  | exec_p_s_bcr
    : forall env_1 env_2 effs p_1 p_2 c,
      exec_p env_1 p_1 env_2 effs c 
       -> c <> normal
       -> exec_p env_1 (prog_s p_1 p_2) env_2 effs c
  | exec_p_i
    : forall env_1 env_2 effs cond p_1 p_2 c x eff_1 eff_2,
      exec_e env_1 cond x eff_1
        -> exec_p env_1 (if truthy x then p_1 else p_2) env_2 eff_2 c
        -> app eff_1 eff_2 = effs
        -> exec_p env_1 (prog_i cond p_1 p_2) env_2 effs c
  | exec_p_b : forall env, exec_p env prog_b env nil break
  | exec_p_c : forall env, exec_p env prog_c env nil continue
  | exec_p_r : forall env effs x e, 
      exec_e env e x effs
        -> exec_p env (prog_r e) env effs (returns x)
.

Hypothesis exec_e_deterministic : forall {env e x_a effs_a x_b effs_b},
  exec_e env e x_a effs_a -> exec_e env e x_b effs_b -> x_a = x_b /\ effs_a = effs_b.

Theorem exec_p_deterministic : forall {p env_1 env_2a effs_a c_a},
  exec_p env_1 p env_2a effs_a c_a -> forall env_2b effs_b c_b, exec_p env_1 p env_2b effs_b c_b -> equal_env env_2a env_2b /\ effs_a = effs_b /\ c_a = c_b.
  induct 1.
  all: invert 1.
  all: repeat match goal with
    | [H1: exec_e _ _ _ _, H2: exec_e _ _ _ _ |- _] => destruct (exec_e_deterministic H2 H1); clear H1 H2
    end.
  all: unfold equal_env in *.
  all: subst.
  all: try (destruct (truthy x)).
  all: repeat match goal with
     | [
      IH : forall _ _ _, exec_p _ ?p _ _ _ -> _,
      HA : exec_p _ ?p _ _ _
     |- _] => 
        destruct (IH _ _ _ HA) as [? [? ?]]; clear IH; subst
   end.
  all: try solve [subst; repeat split; auto; try contradiction].
Qed.

End programs.
